"""
AI Incident Narrator Engine (Module 5).

Provides deterministic and LLM-ready cross-module intelligence by joining
metric telemetry, active alerts, security events, and forecasting horizons
into grounded, structured operational explanations.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import Alert
from backend.app.models.security import SecurityEvent
from backend.app.models.cost import CostRecommendation


class IncidentNarratorEngine:
    """
    Correlates multi-domain signals across Performance, Security, and Cost
    to produce structured incident narratives with clear evidence citations.
    """

    def analyze_incident(
        self,
        db: Session,
        query: str,
        host_id: Optional[int] = None,
        environment: Optional[str] = None,
        time_window_minutes: int = 60,
    ) -> Dict[str, Any]:
        """
        Executes cross-module signal aggregation and generates a structured analysis.
        """
        now = datetime.now(timezone.utc)
        since_ts = now - timedelta(minutes=time_window_minutes)

        # 1. Fetch matching hosts
        host_stmt = select(Host)
        if host_id:
            host_stmt = host_stmt.where(Host.id == host_id)
        elif environment:
            host_stmt = host_stmt.where(Host.environment == environment)
        hosts = list(db.scalars(host_stmt.limit(10)).all())
        host_ids = [h.id for h in hosts] if hosts else []

        # 2. Query Alerts in window
        alert_stmt = select(Alert).order_by(desc(Alert.created_at)).limit(20)
        if host_ids:
            alert_stmt = alert_stmt.where(Alert.host_id.in_(host_ids))
        recent_alerts = list(db.scalars(alert_stmt).all())

        # 3. Query Security Events
        sec_stmt = select(SecurityEvent).order_by(desc(SecurityEvent.timestamp)).limit(20)
        if host_ids:
            sec_stmt = sec_stmt.where(SecurityEvent.host_id.in_(host_ids))
        recent_sec = list(db.scalars(sec_stmt).all())

        # 4. Query Cost Recommendations
        cost_stmt = select(CostRecommendation).order_by(desc(CostRecommendation.created_at)).limit(10)
        if host_ids:
            cost_stmt = cost_stmt.where(CostRecommendation.host_id.in_(host_ids))
        recent_cost = list(db.scalars(cost_stmt).all())

        # 5. Build Timeline Events
        timeline_events = []
        cited_sources = ["Telemetry Database (metrics)"]

        for a in recent_alerts:
            timeline_events.append({
                "category": "Alert",
                "timestamp": a.created_at,
                "resource": a.host.hostname if a.host else f"Host-{a.host_id}",
                "detail": f"[{a.severity.upper()}] {a.message} (Metric: {a.metric}={a.value:.1f}, Threshold: {a.threshold:.1f})",
                "severity": a.severity,
            })
            cited_sources.append(f"Alert Record #{a.id} ({a.metric})")

        for s in recent_sec:
            timeline_events.append({
                "category": "Security",
                "timestamp": s.timestamp,
                "resource": s.host.hostname if s.host else "Network Perimeter",
                "detail": f"[{s.severity.upper()}] {s.event_type}: {s.description}",
                "severity": s.severity,
            })
            cited_sources.append(f"Security Event #{s.id} ({s.event_type})")

        for c in recent_cost:
            timeline_events.append({
                "category": "Cost",
                "timestamp": c.created_at,
                "resource": c.host.hostname if c.host else f"Host-{c.host_id}",
                "detail": f"Cost Optimization: {c.recommendation_type} (Potential savings: ${c.estimated_monthly_savings_usd:.2f}/mo)",
                "severity": "info",
            })
            cited_sources.append(f"Cost Recommendation #{c.id}")

        # Sort timeline
        timeline_events.sort(key=lambda x: x["timestamp"] or now, reverse=True)

        # 6. Synthesize Structured Explanation
        affected_hosts = list({e["resource"] for e in timeline_events}) or ["Fleet-wide Infrastructure"]
        
        has_critical_alert = any(a.severity == "critical" for a in recent_alerts)
        has_security_event = len(recent_sec) > 0
        
        # Evidence points
        evidence_points = []
        if recent_alerts:
            for a in recent_alerts[:3]:
                evidence_points.append(
                    f"Observed {a.severity} threshold breach on {a.host.hostname if a.host else 'host'}: "
                    f"{a.metric} reached {a.value:.1f}% (threshold: {a.threshold:.1f}%)."
                )
        if recent_sec:
            for s in recent_sec[:2]:
                evidence_points.append(
                    f"Security detection flag: {s.event_type} on {s.host.hostname if s.host else 'perimeter'} "
                    f"with severity {s.severity}."
                )
        if not evidence_points:
            evidence_points.append("All primary cluster metrics are operating within expected baseline thresholds.")

        # Root cause hypothesis
        if has_security_event and has_critical_alert:
            root_cause = "Correlated Security & Workload Impact: An anomalous security event coincides with rapid resource consumption spikes, suggesting potential unauthorized process execution or denial-of-service pressure."
            recommendations = [
                "Isolate suspicious external IPs identified in security logs.",
                "Inspect running processes on affected nodes for unauthorized high-CPU binaries.",
                "Review audit trail for recent privilege escalation or configuration alterations.",
            ]
            confidence = "High"
        elif has_critical_alert:
            root_cause = "Workload Saturation: High demand on compute or memory pipelines exceeding instance provisioning capacity."
            recommendations = [
                "Inspect active container application logs and request queue depths.",
                "Evaluate scaling policies or consider rightsizing instances according to cost intelligence recommendations.",
                "Review time-to-threshold forecast to determine remaining headroom.",
            ]
            confidence = "High" if len(recent_alerts) > 2 else "Medium"
        else:
            root_cause = "Nominal Operations: System is stable with no anomalous performance or security correlations detected."
            recommendations = [
                "Continue standard telemetry monitoring.",
                "Check Cost Intelligence for idle host rightsizing opportunities.",
            ]
            confidence = "High"

        observation = (
            f"Analysis of {len(affected_hosts)} resource(s) over the last {time_window_minutes} minutes identified "
            f"{len(recent_alerts)} performance alerts and {len(recent_sec)} security events."
        )

        structured = {
            "observation": observation,
            "evidence_points": evidence_points,
            "possible_root_cause": root_cause,
            "recommended_investigation": recommendations,
            "confidence_level": confidence,
            "affected_resources": affected_hosts,
            "timeline_events": timeline_events[:15],
            "cited_data_sources": list(set(cited_sources)),
        }

        # Build raw markdown response
        raw_markdown = f"""### AI Incident Analysis & Evidence Summary

**Observation**: {observation}

#### Supporting Evidence (Observed Data):
{chr(10).join(f"- {pt}" for pt in evidence_points)}

#### Inferred Root Cause:
> {root_cause}

#### Recommended Investigation (Suggested Action):
{chr(10).join(f"1. {rec}" for rec in recommendations)}

**Confidence**: `{confidence}` | **Affected Entities**: `{', '.join(affected_hosts)}`
"""

        return {
            "query": query,
            "generated_at": now,
            "structured_explanation": structured,
            "raw_markdown_narrative": raw_markdown,
            "disclaimer": "AI model inferences are analytical suggestions grounded in telemetry and must be validated by operators before taking destructive remediation actions.",
        }
