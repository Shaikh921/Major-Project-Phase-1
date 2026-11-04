"""
Reporting and Analytics Aggregation Service.
Supports:
1. Overall Infrastructure Monitoring Report (Consolidated fleet analytics & PDF)
2. Individual Sensor / PC Performance Report (Single workstation telemetry & PDF)
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, desc, func, and_
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import Alert
from backend.app.models.security import SecurityEvent, AuditLog
from backend.app.models.device import DeviceEnrollment
from backend.app.models.user import User, UserRole
from backend.app.schemas.report import (
    ReportGenerateRequest,
    ReportResponse,
    HostInventorySummary,
    HostReportRequest,
    HostReportResponse,
    HostIdentityInfo,
    ResourceMetricStats,
    HostReportAlertItem,
    HostReportSecurityItem,
)
from backend.app.services.cost_service import generate_fleet_cost_analysis
from backend.app.services.pdf_generator import build_overall_system_pdf, build_individual_host_pdf


def _aware(ts: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime timestamps returned from SQLite are timezone-aware (UTC)."""
    if ts is None:
        return None
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def verify_user_host_access(user: Optional[User], host: Host) -> bool:
    """
    Enforces hybrid RBAC isolation policy:
    - SUPER_ADMIN: Full access across entire fleet.
    - ADMIN: Full access across environments.
    - OPERATOR / VIEWER: Scoped to their assigned hosts or environments.
    """
    if user is None:
        return True  # Internal / fixture bypass

    role = getattr(user, "role", UserRole.VIEWER)
    if role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        return True

    # Check host owner
    if host.owner_email and host.owner_email.strip().lower() == user.email.strip().lower():
        return True

    # Check tags for explicit user or role grants
    tags = host.tags or {}
    allowed_users = tags.get("allowed_users", [])
    if isinstance(allowed_users, list) and user.email.strip().lower() in [u.lower() for u in allowed_users]:
        return True

    # If no explicit restriction on host, operator and viewer can view
    if not host.owner_email and not allowed_users:
        return True

    return False


# ==============================================================================
# OVERALL INFRASTRUCTURE REPORT
# ==============================================================================

def generate_executive_report(
    db: Session,
    req: ReportGenerateRequest,
    user: Optional[User] = None,
) -> ReportResponse:
    """Aggregates multi-domain data across all authorized infrastructure."""
    now = datetime.now(timezone.utc)
    start_ts = now - timedelta(hours=req.time_range_hours)
    cutoff = now - timedelta(seconds=req.offline_threshold_seconds)

    # 1. Hosts query (optionally filtered by environment)
    host_filter = []
    if req.environment and req.environment.strip() and req.environment.lower() != "all environments":
        host_filter.append(Host.environment == req.environment.strip())

    hosts_stmt = select(Host)
    if host_filter:
        hosts_stmt = hosts_stmt.where(and_(*host_filter))
    all_hosts = list(db.scalars(hosts_stmt.order_by(Host.hostname)).all())

    # Filter hosts by RBAC authorization
    hosts = [h for h in all_hosts if verify_user_host_access(user, h)]
    active_hosts = sum(1 for h in hosts if h.is_active)
    host_ids = [h.id for h in hosts]

    # Latest metric per host query (scoped to host_ids)
    host_metrics: Dict[int, Metric] = {}
    if host_ids:
        latest_ts_sub = (
            select(Metric.host_id, func.max(Metric.timestamp).label("max_ts"))
            .where(Metric.host_id.in_(host_ids))
            .group_by(Metric.host_id)
            .subquery()
        )
        metric_stmt = (
            select(Metric)
            .join(
                latest_ts_sub,
                and_(
                    Metric.host_id == latest_ts_sub.c.host_id,
                    Metric.timestamp == latest_ts_sub.c.max_ts,
                ),
            )
        )
        for m in db.scalars(metric_stmt).all():
            host_metrics[m.host_id] = m

    # 2. Build host inventory summary and calculate online / offline / unseen
    online_count = 0
    offline_count = 0
    unseen_count = 0
    latest_telemetry_ts: Optional[datetime] = None

    cpu_values: List[float] = []
    mem_values: List[float] = []
    disk_values: List[float] = []

    inventory_list: List[HostInventorySummary] = []
    for h in hosts:
        m = host_metrics.get(h.id)
        last_seen = _aware(m.timestamp) if m and m.timestamp else None

        if last_seen:
            if latest_telemetry_ts is None or last_seen > latest_telemetry_ts:
                latest_telemetry_ts = last_seen

        if last_seen is None:
            status_val = "NO_DATA"
            unseen_count += 1
        elif last_seen >= cutoff:
            status_val = "ONLINE"
            online_count += 1
        else:
            status_val = "OFFLINE"
            offline_count += 1

        cpu_val = round(m.cpu_percent, 1) if (m and m.cpu_percent is not None) else None
        mem_val = round(m.memory_percent, 1) if (m and m.memory_percent is not None) else None
        disk_val = round(m.disk_percent, 1) if (m and m.disk_percent is not None) else None

        if cpu_val is not None:
            cpu_values.append(cpu_val)
        if mem_val is not None:
            mem_values.append(mem_val)
        if disk_val is not None:
            disk_values.append(disk_val)

        inventory_list.append(
            HostInventorySummary(
                host_id=h.id,
                hostname=h.hostname,
                environment=h.environment,
                room=h.region or "unknown",
                ip_address=h.ip_address,
                status=status_val,
                last_seen=last_seen,
                cpu_percent=cpu_val,
                memory_percent=mem_val,
                disk_percent=disk_val,
            )
        )

    # Averages
    avg_cpu = round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else None
    avg_mem = round(sum(mem_values) / len(mem_values), 1) if mem_values else None
    avg_disk = round(sum(disk_values) / len(disk_values), 1) if disk_values else None

    # 3. Alerts in window (scoped to authorized hosts)
    alert_filter = [Alert.created_at >= start_ts]
    if host_ids:
        alert_filter.append(Alert.host_id.in_(host_ids))
    else:
        alert_filter.append(Alert.id == -1)
    
    alert_stmt = select(Alert).where(and_(*alert_filter)).order_by(desc(Alert.created_at))
    alerts = list(db.scalars(alert_stmt).all())
    crit_alerts = sum(1 for a in alerts if a.severity.lower() == "critical")
    warn_alerts = sum(1 for a in alerts if a.severity.lower() == "warning")

    # Group alerts by category
    alerts_by_cat: Dict[str, int] = {}
    for a in alerts:
        cat = a.kind or "threshold"
        alerts_by_cat[cat] = alerts_by_cat.get(cat, 0) + 1

    host_name_map = {h.id: h.hostname for h in hosts}
    recent_alerts_data = [
        {
            "id": a.id,
            "hostname": host_name_map.get(a.host_id, f"Host {a.host_id}"),
            "kind": a.kind,
            "metric": a.metric,
            "severity": a.severity,
            "message": a.message,
            "value": a.value,
            "threshold": a.threshold,
            "status": a.status,
            "created_at": _aware(a.created_at).isoformat() if a.created_at else None,
        }
        for a in alerts[:25]
    ]

    # 4. Security events in window
    sec_filter = [SecurityEvent.timestamp >= start_ts]
    if host_ids:
        sec_filter.append(SecurityEvent.host_id.in_(host_ids))
    else:
        sec_filter.append(SecurityEvent.id == -1)

    sec_stmt = select(SecurityEvent).where(and_(*sec_filter)).order_by(desc(SecurityEvent.timestamp))
    sec_events = list(db.scalars(sec_stmt).all())
    recent_sec_data = [
        {
            "id": se.id,
            "hostname": host_name_map.get(se.host_id, f"Host {se.host_id}") if se.host_id else "Global Scope",
            "event_type": se.event_type,
            "severity": se.severity,
            "source_ip": se.source_ip,
            "description": se.description,
            "status": se.status,
            "timestamp": _aware(se.timestamp).isoformat() if se.timestamp else None,
        }
        for se in sec_events[:20]
    ]

    # 5. Cost analysis
    cost_summary = generate_fleet_cost_analysis(db)

    # 6. Fleet overview status
    if len(hosts) == 0:
        fleet_status = "No Monitored Hosts"
        fleet_details = "No hosts are currently enrolled in this scope. Ensure sensor nodes are deployed and active."
    elif online_count == 0:
        fleet_status = "Fleet Offline"
        fleet_details = f"All {len(hosts)} registered hosts are currently offline or have ceased emitting heartbeats beyond the {req.offline_threshold_seconds}s threshold. Active incidents in window: {crit_alerts} critical, {warn_alerts} warning."
    elif crit_alerts > 0:
        fleet_status = "Degraded"
        fleet_details = f"Monitored hosts: {len(hosts)} ({online_count} online, {offline_count} offline, {unseen_count} with no telemetry). Heartbeat threshold: {req.offline_threshold_seconds}s. Critical incident load: {crit_alerts} critical, {warn_alerts} warning."
    else:
        fleet_status = "Healthy"
        fleet_details = f"Monitored hosts: {len(hosts)} ({online_count} online, {offline_count} offline, {unseen_count} with no telemetry). Heartbeat threshold: {req.offline_threshold_seconds}s. Zero critical alerts in the active {req.time_range_hours}h window."

    # 7. Security status (Mandatory: no unconditional "Secure" claim)
    security_disclaimer = (
        "Absence of recorded security events indicates no active threat signatures or anomalous authentication "
        "events were flagged during the window; it does not constitute a formal warranty of complete threat absence."
    )
    if len(hosts) == 0 and len(sec_events) == 0:
        sec_status = "Monitoring Inactive (No Hosts Enrolled)"
        sec_details = "No hosts enrolled to generate telemetry or auth event streams. Security monitoring is inactive for this scope."
    elif len(sec_events) == 0:
        sec_status = "No Security Events Flagged"
        sec_details = f"Zero anomalous authentication attempts or flow breaches detected across monitored endpoints in the {req.time_range_hours}h window. Note: {security_disclaimer}"
    else:
        sec_status = f"{len(sec_events)} Security Event(s) Flagged"
        sec_details = f"Monitored auth and flow streams recorded {len(sec_events)} security incident(s) during this time window. Review incident details for threat containment."

    # 8. Cost status
    cost_status = f"${cost_summary.estimated_potential_savings_usd:.2f}/mo potential savings"
    cost_details = (
        f"Current estimated monthly spend: ${cost_summary.estimated_monthly_spend_usd:.2f}. "
        f"Identified {cost_summary.idle_resources_count} idle and {cost_summary.underutilized_resources_count} "
        f"underutilized instances across catalog pricing rules."
    )

    # 9. Evidence-based recommendations
    recommendations: List[str] = []
    if offline_count > 0:
        recommendations.append(f"Investigate {offline_count} workstation(s) that have stopped emitting heartbeats beyond the {req.offline_threshold_seconds}s threshold.")
    if crit_alerts > 0:
        recommendations.append(f"Triage {crit_alerts} critical alert(s) across affected hosts to prevent resource starvation or process crashes.")
    if unseen_count > 0:
        recommendations.append(f"Deploy sensor agent to {unseen_count} enrolled host(s) currently exhibiting zero recorded telemetry.")
    if avg_cpu and avg_cpu > 75.0:
        recommendations.append(f"High fleet-wide average CPU utilization ({avg_cpu}%). Evaluate workload distribution across compute nodes.")
    if avg_mem and avg_mem > 80.0:
        recommendations.append(f"High fleet-wide memory consumption ({avg_mem}%). Profile active background services for memory leaks.")
    if cost_summary.estimated_potential_savings_usd > 0.0:
        recommendations.append(f"Review rightsizing opportunities: potential monthly savings of ${cost_summary.estimated_potential_savings_usd:.2f} identified.")
    if not recommendations:
        recommendations.append("All monitored systems are operating within configured performance boundaries. Maintain active polling schedule.")

    sections: List[Dict[str, Any]] = [
        {
            "section_title": "Fleet Overview & Health",
            "status": fleet_status,
            "details": fleet_details,
        },
        {
            "section_title": "Security & Threat Observations",
            "status": sec_status,
            "details": sec_details,
        },
        {
            "section_title": "Cost Efficiency & Optimization",
            "status": cost_status,
            "details": cost_details,
        },
    ]

    return ReportResponse(
        report_id=f"RPT-{uuid.uuid4().hex[:8].upper()}",
        title=f"Cloud Infrastructure & Security Intelligence Report ({req.time_range_hours}h Horizon)",
        generated_at=now,
        time_window_start=start_ts,
        time_window_end=now,
        environment=req.environment or "All Environments",
        summary_metrics={
            "total_hosts": len(hosts),
            "active_hosts": active_hosts,
            "online_hosts": online_count,
            "offline_hosts": offline_count,
            "unseen_hosts": unseen_count,
            "total_alerts": len(alerts),
            "critical_alerts": crit_alerts,
            "warning_alerts": warn_alerts,
            "offline_threshold_seconds": req.offline_threshold_seconds,
            "data_freshness_timestamp": latest_telemetry_ts.isoformat() if latest_telemetry_ts else None,
        },
        active_incidents_count=crit_alerts + warn_alerts,
        anomalies_detected_count=len([a for a in alerts if a.kind == "anomaly"]),
        security_events_count=len(sec_events),
        estimated_monthly_spend_usd=cost_summary.estimated_monthly_spend_usd,
        potential_savings_usd=cost_summary.estimated_potential_savings_usd,
        sections=sections,
        data_freshness_timestamp=latest_telemetry_ts,
        online_hosts_count=online_count,
        offline_hosts_count=offline_count,
        unseen_hosts_count=unseen_count,
        host_inventories=inventory_list,
        security_audit_disclaimer=security_disclaimer,
        avg_cpu_percent=avg_cpu,
        avg_memory_percent=avg_mem,
        avg_disk_percent=avg_disk,
        critical_alerts_count=crit_alerts,
        warning_alerts_count=warn_alerts,
        alerts_by_category=alerts_by_cat,
        recent_alerts=recent_alerts_data,
        recent_security_events=recent_sec_data,
        recommendations=recommendations,
    )


def generate_overall_report_pdf(
    db: Session,
    req: ReportGenerateRequest,
    user: Optional[User] = None,
) -> bytes:
    """Generates the printable PDF for the Overall Infrastructure Report."""
    report = generate_executive_report(db, req, user)
    start_ts = report.time_window_start

    # Query timeline samples across authorized hosts for the chart
    inv_ids = [h.host_id for h in report.host_inventories]
    timeline_samples: List[Dict[str, Any]] = []

    if inv_ids:
        # Group metrics into time buckets or fetch recent 100 samples
        metric_stmt = (
            select(
                Metric.timestamp,
                func.avg(Metric.cpu_percent).label("avg_cpu"),
                func.avg(Metric.memory_percent).label("avg_ram"),
                func.avg(Metric.disk_percent).label("avg_disk"),
            )
            .where(and_(Metric.host_id.in_(inv_ids), Metric.timestamp >= start_ts))
            .group_by(Metric.timestamp)
            .order_by(Metric.timestamp.asc())
            .limit(150)
        )
        results = db.execute(metric_stmt).all()
        for r in results:
            timeline_samples.append({
                "timestamp": _aware(r.timestamp),
                "avg_cpu": round(float(r.avg_cpu), 1),
                "avg_ram": round(float(r.avg_ram), 1),
                "avg_disk": round(float(r.avg_disk), 1),
            })

    requester_label = user.email if user else "Authorized SRE Operator"
    return build_overall_system_pdf(report.model_dump(), timeline_samples, requester_label)


# ==============================================================================
# INDIVIDUAL SENSOR / PC REPORT
# ==============================================================================

def generate_host_report_data(
    db: Session,
    host_id: int,
    req: HostReportRequest,
    user: Optional[User] = None,
) -> HostReportResponse:
    """
    Generates detailed report data strictly scoped to one selected host.
    Validates host identity and authorization before data extraction.
    """
    host = db.get(Host, host_id)
    if not host:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitored host with ID {host_id} not found in inventory.",
        )

    # Authorization enforcement
    if not verify_user_host_access(user, host):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: User is not authorized to access host '{host.hostname}'.",
        )

    now = datetime.now(timezone.utc)
    start_ts = now - timedelta(hours=req.time_range_hours)
    cutoff = now - timedelta(seconds=req.offline_threshold_seconds)

    # Query linked DeviceEnrollment metadata
    dev_enrollment = db.scalar(
        select(DeviceEnrollment)
        .where(DeviceEnrollment.host_id == host.id)
        .order_by(desc(DeviceEnrollment.id))
        .limit(1)
    )

    host_identity = HostIdentityInfo(
        host_id=host.id,
        hostname=host.hostname,
        assigned_name=dev_enrollment.assigned_name if dev_enrollment else None,
        device_uuid=dev_enrollment.device_uuid if dev_enrollment else None,
        ip_address=host.ip_address,
        mac_address=dev_enrollment.mac_address if dev_enrollment else None,
        os_version=dev_enrollment.os_version if dev_enrollment else None,
        agent_version=dev_enrollment.agent_version if dev_enrollment else None,
        environment=host.environment,
        room=dev_enrollment.room_number if dev_enrollment else host.region,
        lab_name=dev_enrollment.lab_name if dev_enrollment else None,
        source_type=host.source_type,
        is_active=host.is_active,
    )

    # Query metrics strictly for this host
    metrics = list(
        db.scalars(
            select(Metric)
            .where(and_(Metric.host_id == host.id, Metric.timestamp >= start_ts))
            .order_by(Metric.timestamp.asc())
        ).all()
    )

    # Determine latest metric (might be older than window if host is inactive)
    latest_metric = db.scalar(
        select(Metric)
        .where(Metric.host_id == host.id)
        .order_by(desc(Metric.timestamp))
        .limit(1)
    )

    last_heartbeat = _aware(latest_metric.timestamp) if latest_metric else None
    freshness_sec = int((now - last_heartbeat).total_seconds()) if last_heartbeat else None

    if last_heartbeat is None:
        conn_status = "NO_DATA"
    elif last_heartbeat >= cutoff:
        conn_status = "ONLINE"
    else:
        conn_status = "OFFLINE"

    # Calculate statistics for each subsystem
    def calc_stats(values_with_ts: List[tuple]) -> ResourceMetricStats:
        valid_items = [(v, ts) for v, ts in values_with_ts if v is not None]
        if not valid_items:
            return ResourceMetricStats(sample_count=0)
        
        vals = [v for v, _ in valid_items]
        avg_val = round(sum(vals) / len(vals), 1)
        max_val = round(max(vals), 1)
        min_val = round(min(vals), 1)

        # Find peak timestamp
        peak_ts = None
        for v, ts in valid_items:
            if v == max_val:
                peak_ts = ts
                break

        latest_val = valid_items[-1][0] if valid_items else None
        return ResourceMetricStats(
            avg=avg_val,
            max=max_val,
            min=min_val,
            peak_timestamp=peak_ts,
            latest=round(latest_val, 1) if latest_val is not None else None,
            sample_count=len(valid_items),
        )

    # Extract subsystem series
    cpu_series = [(m.cpu_percent, _aware(m.timestamp)) for m in metrics]
    mem_series = [(m.memory_percent, _aware(m.timestamp)) for m in metrics]
    disk_series = [(m.disk_percent, _aware(m.timestamp)) for m in metrics]
    sent_series = [(m.network_sent_mb, _aware(m.timestamp)) for m in metrics]
    recv_series = [(m.network_received_mb, _aware(m.timestamp)) for m in metrics]

    cpu_stats = calc_stats(cpu_series)
    mem_stats = calc_stats(mem_series)
    disk_stats = calc_stats(disk_series)
    sent_stats = calc_stats(sent_series)
    recv_stats = calc_stats(recv_series)

    # If no metrics in window but a latest metric exists, populate latest reading
    if latest_metric:
        if cpu_stats.latest is None and latest_metric.cpu_percent is not None:
            cpu_stats.latest = round(latest_metric.cpu_percent, 1)
        if mem_stats.latest is None and latest_metric.memory_percent is not None:
            mem_stats.latest = round(latest_metric.memory_percent, 1)
        if disk_stats.latest is None and latest_metric.disk_percent is not None:
            disk_stats.latest = round(latest_metric.disk_percent, 1)
        if sent_stats.latest is None and latest_metric.network_sent_mb is not None:
            sent_stats.latest = round(latest_metric.network_sent_mb, 1)
        if recv_stats.latest is None and latest_metric.network_received_mb is not None:
            recv_stats.latest = round(latest_metric.network_received_mb, 1)

    # Telemetry availability calculation
    # Standard sensor interval is 15 seconds -> 240 samples per hour
    expected_samples = max(1, req.time_range_hours * 240)
    avail_pct = round(min(100.0, (len(metrics) / expected_samples) * 100.0), 1) if metrics else 0.0
    if conn_status == "ONLINE" and avail_pct == 0.0 and len(metrics) > 0:
        avail_pct = 100.0

    # Alerts strictly for this host
    alerts = list(
        db.scalars(
            select(Alert)
            .where(and_(Alert.host_id == host.id, Alert.created_at >= start_ts))
            .order_by(desc(Alert.created_at))
        ).all()
    )
    active_alerts = sum(1 for a in alerts if a.status.lower() == "active")
    alert_items = [
        HostReportAlertItem(
            id=a.id,
            timestamp=_aware(a.created_at),
            severity=a.severity,
            kind=a.kind,
            metric=a.metric,
            message=a.message,
            value=round(a.value, 1),
            threshold=round(a.threshold, 1) if a.threshold is not None else None,
            status=a.status,
        )
        for a in alerts
    ]

    # Security events strictly for this host
    sec_events = list(
        db.scalars(
            select(SecurityEvent)
            .where(and_(SecurityEvent.host_id == host.id, SecurityEvent.timestamp >= start_ts))
            .order_by(desc(SecurityEvent.timestamp))
        ).all()
    )
    sec_items = [
        HostReportSecurityItem(
            id=se.id,
            timestamp=_aware(se.timestamp),
            event_type=se.event_type,
            severity=se.severity,
            description=se.description,
            status=se.status,
            raw_evidence=se.raw_evidence,
        )
        for se in sec_events
    ]

    # Evidence-based assessment
    assessment_notes = []
    if conn_status == "ONLINE":
        assessment_notes.append(f"Workstation is actively emitting heartbeats within the {req.offline_threshold_seconds}s threshold.")
    elif conn_status == "OFFLINE":
        gap_desc = f"{freshness_sec // 60} minutes" if freshness_sec else "an extended period"
        assessment_notes.append(f"Workstation has ceased emitting telemetry for {gap_desc}. Immediate connectivity verification required.")
    else:
        assessment_notes.append("No telemetry has been ingested for this workstation. The sensor agent may not be initialized.")

    if cpu_stats.avg and cpu_stats.avg > 75.0:
        assessment_notes.append(f"High average CPU load ({cpu_stats.avg}%). Peak reached {cpu_stats.max}%.")
    elif cpu_stats.avg:
        assessment_notes.append(f"CPU load is nominal (average {cpu_stats.avg}%, peak {cpu_stats.max}%).")

    if mem_stats.avg and mem_stats.avg > 80.0:
        assessment_notes.append(f"Memory consumption is constrained (average {mem_stats.avg}%). Potential RAM exhaustion risk.")

    if disk_stats.latest and disk_stats.latest > 85.0:
        assessment_notes.append(f"Storage capacity is critically low at {disk_stats.latest}%.")

    if active_alerts > 0:
        assessment_notes.append(f"There are currently {active_alerts} active alert(s) requiring operator attention.")

    technical_assessment = " ".join(assessment_notes)

    # Evidence-based recommendations
    recommendations = []
    if conn_status == "OFFLINE":
        recommendations.append("Inspect host power state, Ethernet/Wi-Fi connection, and verify the Windows Scheduled Task 'CloudOpsSensor'.")
    if cpu_stats.max and cpu_stats.max >= 95.0:
        recommendations.append(f"CPU spiked to {cpu_stats.max}% at {cpu_stats.peak_timestamp}. Review high-priority background tasks.")
    if disk_stats.latest and disk_stats.latest >= 85.0:
        recommendations.append("Execute disk cleanup utilities to free space on primary partitions.")
    if active_alerts > 0:
        recommendations.append(f"Acknowledge and resolve {active_alerts} open alert incident(s) in the SRE Command Center.")
    if not recommendations:
        recommendations.append("Workstation is operating reliably within normal operational tolerances. Continue regular monitoring.")

    security_disclaimer = (
        "Absence of recorded security events indicates no active threat signatures were flagged during the window; "
        "it does not constitute a formal warranty of complete threat absence."
    )

    return HostReportResponse(
        report_id=f"RPT-HOST-{uuid.uuid4().hex[:8].upper()}",
        title=f"Individual Sensor Performance Report — {host.hostname}",
        generated_at=now,
        time_window_start=start_ts,
        time_window_end=now,
        reporting_period_hours=req.time_range_hours,
        host_identity=host_identity,
        connectivity_status=conn_status,
        last_heartbeat=last_heartbeat,
        telemetry_freshness_seconds=freshness_sec,
        telemetry_availability_pct=avail_pct,
        total_samples=len(metrics),
        cpu_stats=cpu_stats,
        memory_stats=mem_stats,
        disk_stats=disk_stats,
        network_sent_stats=sent_stats,
        network_recv_stats=recv_stats,
        total_alerts=len(alerts),
        active_alerts_count=active_alerts,
        alerts=alert_items,
        security_events_count=len(sec_events),
        security_events=sec_items,
        technical_assessment=technical_assessment,
        recommendations=recommendations,
        security_disclaimer=security_disclaimer,
    )


def generate_host_report_pdf(
    db: Session,
    host_id: int,
    req: HostReportRequest,
    user: Optional[User] = None,
) -> bytes:
    """Generates the dedicated printable PDF for an individual sensor node."""
    host_report = generate_host_report_data(db, host_id, req, user)
    start_ts = host_report.time_window_start

    # Fetch metric series for plotting (limit to 200 points for crisp layout)
    metric_stmt = (
        select(Metric)
        .where(and_(Metric.host_id == host_id, Metric.timestamp >= start_ts))
        .order_by(Metric.timestamp.asc())
        .limit(200)
    )
    metrics = db.scalars(metric_stmt).all()
    metric_samples = [
        {
            "timestamp": _aware(m.timestamp),
            "cpu_percent": m.cpu_percent,
            "memory_percent": m.memory_percent,
            "disk_percent": m.disk_percent,
            "network_sent_mb": m.network_sent_mb,
            "network_received_mb": m.network_received_mb,
        }
        for m in metrics
    ]

    requester_label = user.email if user else "Authorized SRE Operator"
    return build_individual_host_pdf(host_report.model_dump(), metric_samples, requester_label)
