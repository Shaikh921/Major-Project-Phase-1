"""
Telemetry & Incident Signal Chunker for Real-Time Operational Database Ingestion.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from RAG_System.chunking.text_chunker import DocumentChunk


def chunk_telemetry_signals(
    alerts: List[Any],
    security_events: List[Any],
    hosts: List[Any],
    cost_recommendations: Optional[List[Any]] = None,
) -> List[DocumentChunk]:
    """
    Transforms relational telemetry records (Alerts, Security Events, Cost Recs, Hosts)
    into semantically rich DocumentChunk instances for hybrid vector indexing.
    """
    chunks: List[DocumentChunk] = []
    host_map = {h.id: h for h in hosts}

    # 1. Chunk Host Hardware Configurations
    for host in hosts:
        h_id = getattr(host, "id", None)
        hostname = getattr(host, "hostname", f"Host-{h_id}")
        ip = getattr(host, "ip_address", getattr(host, "ip", "Unknown IP"))
        env = getattr(host, "environment", "all")
        os_name = getattr(host, "os", "Linux")
        is_active = getattr(host, "is_active", True)
        status = "active" if is_active else "inactive"

        text = (
            f"### Registered Node: {hostname} ({ip})\n"
            f"- Environment: {env}\n"
            f"- Operating System: {os_name}\n"
            f"- Lifecycle Status: {status}\n"
            f"- Node ID: {h_id}\n"
        )
        if hasattr(host, "room") and host.room:
            text += f"- Physical Location: Room/Lab {host.room}\n"

        chunks.append(
            DocumentChunk(
                chunk_id=f"host_{h_id}",
                doc_id=f"host_{h_id}",
                title=f"Node Inventory: {hostname}",
                section="Host Profile",
                text=text,
                metadata={
                    "host_id": h_id,
                    "hostname": hostname,
                    "ip": ip,
                    "environment": env,
                    "type": "host_inventory",
                },
            )
        )

    # 2. Chunk Performance & Threshold Alerts
    for alert in alerts:
        a_id = getattr(alert, "id", "unknown")
        h_id = getattr(alert, "host_id", None)
        host = host_map.get(h_id)
        hostname = host.hostname if host else f"Host-{h_id}"
        metric = getattr(alert, "metric", "resource")
        val = getattr(alert, "value", 0.0)
        thresh = getattr(alert, "threshold", 0.0)
        sev = getattr(alert, "severity", "warning").lower()
        msg = getattr(alert, "message", "Threshold exceeded")
        created_at = getattr(alert, "created_at", datetime.now(timezone.utc))
        status = getattr(alert, "status", "active")
        env = host.environment if host else "unknown"

        text = (
            f"### Operational Alert [ALERT-{a_id}]: {sev.upper()} on {hostname}\n"
            f"- Target Resource: {hostname} (Host ID: {h_id}, Env: {env})\n"
            f"- Metric Monitored: {metric}\n"
            f"- Observed Value: {val:.2f}% (Threshold: {thresh:.2f}%)\n"
            f"- Alert Status: {status.upper()}\n"
            f"- Timestamp: {created_at}\n"
            f"- Incident Description: {msg}\n"
        )

        chunks.append(
            DocumentChunk(
                chunk_id=f"alert_{a_id}",
                doc_id=f"alert_{a_id}",
                title=f"Alert #{a_id}: {metric} on {hostname}",
                section=f"{sev.title()} Alert",
                text=text,
                metadata={
                    "alert_id": a_id,
                    "host_id": h_id,
                    "hostname": hostname,
                    "severity": sev,
                    "metric": metric,
                    "environment": env,
                    "type": "telemetry_alert",
                    "timestamp": str(created_at),
                },
            )
        )

    # 3. Chunk Security Threat Events
    for sec in security_events:
        s_id = getattr(sec, "id", "unknown")
        h_id = getattr(sec, "host_id", None)
        host = host_map.get(h_id)
        hostname = host.hostname if host else "Network Perimeter"
        event_type = getattr(sec, "event_type", "Security Event")
        sev = getattr(sec, "severity", "medium").lower()
        desc = getattr(sec, "description", "")
        ts = getattr(sec, "timestamp", datetime.now(timezone.utc))
        ip = getattr(sec, "ip_address", "Unknown")

        text = (
            f"### Security Intrusion Detection [SEC-{s_id}]: {event_type}\n"
            f"- Target Node: {hostname} (Host ID: {h_id})\n"
            f"- Source IP Address: {ip}\n"
            f"- Threat Severity: {sev.upper()}\n"
            f"- Recorded Timestamp: {ts}\n"
            f"- Security Finding: {desc}\n"
        )

        chunks.append(
            DocumentChunk(
                chunk_id=f"sec_{s_id}",
                doc_id=f"sec_{s_id}",
                title=f"Security Event #{s_id}: {event_type}",
                section="Threat Analysis",
                text=text,
                metadata={
                    "sec_id": s_id,
                    "host_id": h_id,
                    "hostname": hostname,
                    "severity": sev,
                    "event_type": event_type,
                    "type": "security_event",
                    "timestamp": str(ts),
                },
            )
        )

    # 4. Chunk Cost Optimization Recommendations
    if cost_recommendations:
        for cost in cost_recommendations:
            c_id = getattr(cost, "id", "unknown")
            h_id = getattr(cost, "host_id", None)
            host = host_map.get(h_id)
            hostname = host.hostname if host else f"Host-{h_id}"
            rec_type = getattr(cost, "recommendation_type", "Right-sizing")
            savings = getattr(cost, "estimated_monthly_savings_usd", 0.0)
            reason = getattr(cost, "reason", "Resource underutilization detected")

            text = (
                f"### Cost Optimization Opportunity [COST-{c_id}]: {rec_type} on {hostname}\n"
                f"- Candidate Host: {hostname} (Host ID: {h_id})\n"
                f"- Recommendation Type: {rec_type}\n"
                f"- Estimated Monthly Savings: ${savings:.2f} USD\n"
                f"- Rationalization: {reason}\n"
            )

            chunks.append(
                DocumentChunk(
                    chunk_id=f"cost_{c_id}",
                    doc_id=f"cost_{c_id}",
                    title=f"Cost Recommendation #{c_id} ({hostname})",
                    section="Financial Optimization",
                    text=text,
                    metadata={
                        "cost_id": c_id,
                        "host_id": h_id,
                        "hostname": hostname,
                        "type": "cost_recommendation",
                    },
                )
            )

    return chunks
