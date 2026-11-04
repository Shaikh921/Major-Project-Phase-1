"""
Reporting and Analytics Aggregation Service.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, desc, func, and_
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import Alert
from backend.app.models.security import SecurityEvent, AuditLog
from backend.app.schemas.report import ReportGenerateRequest, ReportResponse, HostInventorySummary
from backend.app.services.cost_service import generate_fleet_cost_analysis


def _aware(ts: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime timestamps returned from SQLite are timezone-aware (UTC)."""
    if ts is None:
        return None
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def generate_executive_report(
    db: Session,
    req: ReportGenerateRequest,
) -> ReportResponse:
    """Aggregates multi-domain data into an operational report."""
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
    hosts = list(db.scalars(hosts_stmt.order_by(Host.hostname)).all())
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

    inventory_list: List[HostInventorySummary] = []
    for h in hosts:
        m = host_metrics.get(h.id)
        last_seen = _aware(m.timestamp) if m and m.timestamp else None

        if last_seen:
            if latest_telemetry_ts is None or last_seen > latest_telemetry_ts:
                latest_telemetry_ts = last_seen

        if last_seen is None:
            status = "NO_DATA"
            unseen_count += 1
        elif last_seen >= cutoff:
            status = "ONLINE"
            online_count += 1
        else:
            status = "OFFLINE"
            offline_count += 1

        cpu_val = round(m.cpu_percent, 1) if (m and m.cpu_percent is not None) else None
        mem_val = round(m.memory_percent, 1) if (m and m.memory_percent is not None) else None
        disk_val = round(m.disk_percent, 1) if (m and m.disk_percent is not None) else None

        inventory_list.append(
            HostInventorySummary(
                host_id=h.id,
                hostname=h.hostname,
                environment=h.environment,
                room=h.region or "unknown",
                ip_address=h.ip_address,
                status=status,
                last_seen=last_seen,
                cpu_percent=cpu_val,
                memory_percent=mem_val,
                disk_percent=disk_val,
            )
        )

    # 3. Alerts in window
    alert_filter = [Alert.created_at >= start_ts]
    if host_filter:
        if host_ids:
            alert_filter.append(Alert.host_id.in_(host_ids))
        else:
            alert_filter.append(Alert.id == -1)
    alert_stmt = select(Alert).where(and_(*alert_filter))
    alerts = list(db.scalars(alert_stmt).all())
    crit_alerts = sum(1 for a in alerts if a.severity == "critical")
    warn_alerts = sum(1 for a in alerts if a.severity == "warning")

    # 4. Security events in window
    sec_filter = [SecurityEvent.timestamp >= start_ts]
    if host_filter:
        if host_ids:
            sec_filter.append(SecurityEvent.host_id.in_(host_ids))
        else:
            sec_filter.append(SecurityEvent.id == -1)
    sec_stmt = select(SecurityEvent).where(and_(*sec_filter))
    sec_events = list(db.scalars(sec_stmt).all())

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

    # 7. Security status (mandatory: no false "Secure" claims)
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

    # 9. Build section breakdown
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
    )
