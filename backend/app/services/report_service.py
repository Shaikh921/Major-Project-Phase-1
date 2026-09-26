"""
Reporting and Analytics Aggregation Service.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.models.alert import Alert
from backend.app.models.security import SecurityEvent, AuditLog
from backend.app.schemas.report import ReportGenerateRequest, ReportResponse
from backend.app.services.cost_service import generate_fleet_cost_analysis


def generate_executive_report(
    db: Session,
    req: ReportGenerateRequest,
) -> ReportResponse:
    """Aggregates multi-domain data into an operational report."""
    now = datetime.now(timezone.utc)
    start_ts = now - timedelta(hours=req.time_range_hours)

    # 1. Hosts
    hosts = list(db.scalars(select(Host)).all())
    active_hosts = sum(1 for h in hosts if h.is_active)

    # 2. Alerts in window
    alert_stmt = select(Alert).where(Alert.created_at >= start_ts)
    alerts = list(db.scalars(alert_stmt).all())
    crit_alerts = sum(1 for a in alerts if a.severity == "critical")
    warn_alerts = sum(1 for a in alerts if a.severity == "warning")

    # 3. Security events in window
    sec_stmt = select(SecurityEvent).where(SecurityEvent.timestamp >= start_ts)
    sec_events = list(db.scalars(sec_stmt).all())

    # 4. Cost analysis
    cost_summary = generate_fleet_cost_analysis(db)

    # 5. Build section breakdown
    sections: List[Dict[str, Any]] = [
        {
            "section_title": "Fleet Overview & Health",
            "status": "Healthy" if crit_alerts == 0 else "Degraded",
            "details": f"Total registered hosts: {len(hosts)}, Active: {active_hosts}. Incident load: {crit_alerts} critical, {warn_alerts} warning.",
        },
        {
            "section_title": "Security & Threat Observations",
            "status": "Secure" if len(sec_events) == 0 else f"{len(sec_events)} events detected",
            "details": f"Monitored auth and flow streams recorded {len(sec_events)} security incidents during this time window.",
        },
        {
            "section_title": "Cost Efficiency & Optimization",
            "status": f"${cost_summary.estimated_potential_savings_usd:.2f}/mo potential savings",
            "details": f"Current estimated monthly spend: ${cost_summary.estimated_monthly_spend_usd:.2f}. Identified {cost_summary.idle_resources_count} idle and {cost_summary.underutilized_resources_count} underutilized instances.",
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
            "total_alerts": len(alerts),
            "critical_alerts": crit_alerts,
            "warning_alerts": warn_alerts,
        },
        active_incidents_count=crit_alerts + warn_alerts,
        anomalies_detected_count=len([a for a in alerts if a.kind == "anomaly"]),
        security_events_count=len(sec_events),
        estimated_monthly_spend_usd=cost_summary.estimated_monthly_spend_usd,
        potential_savings_usd=cost_summary.estimated_potential_savings_usd,
        sections=sections,
    )
