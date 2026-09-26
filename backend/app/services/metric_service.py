"""
Metric Ingestion and Time-Series Query Service.

Provides telemetry sample persistence, auto-discovery of newly provisioned hosts (M1-FR2),
alert evaluation triggering, and aggregated fleet summary snapshots (Section 7: /api/summary).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, desc, func, and_
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import Alert
from backend.app.schemas.metric import MetricCreate, MetricBatchCreate, MetricRead, MetricTimeSeriesResponse
from backend.app.schemas.summary import HostStatusSummary, FleetSummaryResponse
from backend.app.schemas.alert import AlertRead
from backend.app.services.host_service import get_or_create_host, get_hosts, get_host
from backend.app.services.alert_service import evaluate_metric_sample
from backend.app.services.ai_service import evaluate_and_record_ai_anomaly


def ingest_metric(db: Session, metric_in: MetricCreate) -> Tuple[Metric, List[Alert]]:
    """
    Ingests a single metric sample, auto-discovers/registers the host if unknown,
    and runs both static threshold and AI multivariate anomaly evaluation engines.
    """
    # Auto-discover or update host (M1-FR2)
    host = get_or_create_host(
        db=db,
        hostname=metric_in.hostname,
        ip_address=metric_in.ip_address,
        environment=metric_in.environment,
        provider=metric_in.provider,
        region=metric_in.region,
    )

    sample_ts = metric_in.timestamp or datetime.now(timezone.utc)

    # Persist the metric sample
    metric = Metric(
        host_id=host.id,
        timestamp=sample_ts,
        cpu_percent=metric_in.cpu_percent,
        memory_percent=metric_in.memory_percent,
        disk_percent=metric_in.disk_percent,
        network_sent_mb=metric_in.network_sent_mb,
        network_received_mb=metric_in.network_received_mb,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)

    # Trigger threshold alert evaluation
    alerts = evaluate_metric_sample(db, host, metric)

    # Trigger AI multivariate anomaly detector (M2-FR2)
    ai_alert = evaluate_and_record_ai_anomaly(db, host, metric)
    if ai_alert:
        alerts.append(ai_alert)

    return metric, alerts


def ingest_metrics_batch(db: Session, batch_in: MetricBatchCreate) -> Dict[str, Any]:
    """
    Batch ingests multiple telemetry data points efficiently.
    """
    total_samples = 0
    total_alerts = 0
    affected_hosts = set()

    for item in batch_in.metrics:
        metric, alerts = ingest_metric(db, item)
        total_samples += 1
        total_alerts += len(alerts)
        affected_hosts.add(metric.host_id)

    return {
        "status": "success",
        "processed_samples": total_samples,
        "generated_alerts": total_alerts,
        "affected_hosts": list(affected_hosts),
    }


def get_host_metrics(
    db: Session,
    host_id: int,
    limit: int = 100,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> MetricTimeSeriesResponse:
    """
    Queries historical time-series telemetry for a specific host.
    """
    host = get_host(db, host_id)
    if host is None:
        raise ValueError(f"Host with ID {host_id} not found.")

    statement = select(Metric).where(Metric.host_id == host_id)

    if start_time:
        statement = statement.where(Metric.timestamp >= start_time)
    if end_time:
        statement = statement.where(Metric.timestamp <= end_time)

    statement = statement.order_by(desc(Metric.timestamp)).limit(limit)
    metrics = list(db.scalars(statement).all())
    
    # Return chronologically ascending for charts
    metrics.reverse()

    data_read = [MetricRead.model_validate(m) for m in metrics]

    return MetricTimeSeriesResponse(
        host_id=host.id,
        hostname=host.hostname,
        total_samples=len(data_read),
        data=data_read,
        time_series=data_read,
    )


def get_latest_host_metric(db: Session, host_id: int) -> Optional[Metric]:
    """
    Fetches the most recent metric sample for a host.
    """
    statement = (
        select(Metric)
        .where(Metric.host_id == host_id)
        .order_by(desc(Metric.timestamp))
        .limit(1)
    )
    return db.scalar(statement)


def get_fleet_summary(db: Session) -> FleetSummaryResponse:
    """
    Aggregates the entire fleet status across all registered hosts,
    identifying latest telemetry and worst active alert per host.
    """
    hosts = get_hosts(db)
    host_summaries: List[HostStatusSummary] = []

    total_active_alerts = 0
    healthy_count = 0
    warning_count = 0
    critical_count = 0
    offline_count = 0

    now = datetime.now(timezone.utc)
    # Stale heartbeat threshold (no metrics in past 5 minutes = offline)
    heartbeat_cutoff = now - timedelta(minutes=5)

    for host in hosts:
        latest_metric = get_latest_host_metric(db, host.id)

        # Get open alerts for this host
        open_alerts_stmt = (
            select(Alert)
            .where(
                and_(
                    Alert.host_id == host.id,
                    Alert.status.in_(["active", "acknowledged"]),
                )
            )
            .order_by(desc(Alert.created_at))
        )
        open_alerts = list(db.scalars(open_alerts_stmt).all())
        total_active_alerts += len(open_alerts)

        # Determine worst alert
        worst_alert: Optional[Alert] = None
        has_critical = any(a.severity == "critical" for a in open_alerts)
        has_warning = any(a.severity == "warning" for a in open_alerts)

        if has_critical:
            worst_alert = next(a for a in open_alerts if a.severity == "critical")
        elif has_warning:
            worst_alert = next(a for a in open_alerts if a.severity == "warning")
        elif open_alerts:
            worst_alert = open_alerts[0]

        # Determine host operational health status
        if not host.is_active or (latest_metric is None) or (
            latest_metric.timestamp.replace(tzinfo=timezone.utc) < heartbeat_cutoff
        ):
            status = "offline" if not host.is_active else "warning"
            if not host.is_active:
                offline_count += 1
            elif has_critical:
                status = "critical"
                critical_count += 1
            elif has_warning:
                status = "warning"
                warning_count += 1
            else:
                healthy_count += 1
        elif has_critical:
            status = "critical"
            critical_count += 1
        elif has_warning:
            status = "warning"
            warning_count += 1
        else:
            status = "healthy"
            healthy_count += 1

        metric_read = MetricRead.model_validate(latest_metric) if latest_metric else None
        worst_alert_read = (
            AlertRead(
                id=worst_alert.id,
                host_id=worst_alert.host_id,
                hostname=host.hostname,
                rule_id=worst_alert.rule_id,
                metric=worst_alert.metric,
                kind=worst_alert.kind,
                severity=worst_alert.severity,
                message=worst_alert.message,
                value=worst_alert.value,
                threshold=worst_alert.threshold,
                status=worst_alert.status,
                created_at=worst_alert.created_at,
                acknowledged_at=worst_alert.acknowledged_at,
                resolved_at=worst_alert.resolved_at,
            )
            if worst_alert
            else None
        )

        host_summaries.append(
            HostStatusSummary(
                host_id=host.id,
                hostname=host.hostname,
                ip_address=host.ip_address,
                environment=host.environment,
                provider=host.provider,
                region=host.region,
                is_active=host.is_active,
                status=status,
                last_seen=latest_metric.timestamp if latest_metric else host.updated_at,
                latest_metric=metric_read,
                latest_metrics=metric_read,
                worst_active_alert=worst_alert_read,
                active_alert_count=len(open_alerts),
            )
        )

    return FleetSummaryResponse(
        total_hosts=len(hosts),
        healthy_hosts=healthy_count,
        warning_hosts=warning_count,
        critical_hosts=critical_count,
        offline_hosts=offline_count,
        hosts_with_warnings=warning_count,
        hosts_with_critical_alerts=critical_count,
        total_active_alerts=total_active_alerts,
        hosts=host_summaries,
    )
