"""
Metric Ingestion and Time-Series Query Service.

Provides telemetry sample persistence, auto-discovery of newly provisioned hosts (M1-FR2),
alert evaluation triggering, and aggregated fleet summary snapshots (Section 7: /api/summary).
"""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, desc, func, and_, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.models.metric import Metric, IngestedBatch
from backend.app.models.alert import Alert
from backend.app.schemas.metric import MetricCreate, MetricBatchCreate, MetricRead, MetricTimeSeriesResponse
from backend.app.schemas.summary import HostStatusSummary, FleetSummaryResponse
from backend.app.schemas.alert import AlertRead
from backend.app.services.host_service import get_or_create_host, get_hosts, get_host
from backend.app.services.alert_service import evaluate_metric_sample
from backend.app.services.ai_service import evaluate_and_record_ai_anomaly, evaluate_correlated_anomaly


def compute_metric_payload_hash(items: List[MetricCreate]) -> str:
    """
    Computes a deterministic SHA-256 digest of metric payload contents.
    Used for idempotency conflict detection across batch retries.
    """
    canonical_items = []
    for item in items:
        ts_str = item.timestamp.isoformat() if item.timestamp else ""
        canonical_items.append({
            "hostname": item.hostname,
            "timestamp": ts_str,
            "cpu_percent": round(item.cpu_percent, 4),
            "memory_percent": round(item.memory_percent, 4),
            "disk_percent": round(item.disk_percent, 4),
            "network_sent_mb": round(item.network_sent_mb, 4),
            "network_received_mb": round(item.network_received_mb, 4),
        })
    raw_json = json.dumps(canonical_items, sort_keys=True)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


def _persist_metric_record(
    db: Session,
    metric_in: MetricCreate,
    commit: bool = True,
) -> Tuple[Metric, List[Alert]]:
    """
    Lower-level metric persistence helper that separates sample insertion and alert
    evaluation from transaction ownership (AUD-01).

    When commit=False:
        Flushes host discovery, metric sample, and alert evaluations into the active
        transaction without committing, allowing caller (e.g. batch ingestion) to own
        the transaction boundary.
    When commit=True:
        Commits transaction and refreshes objects (preserving standalone ingest_metric contract).
    """
    host = get_or_create_host(
        db=db,
        hostname=metric_in.hostname,
        ip_address=metric_in.ip_address,
        environment=metric_in.environment,
        provider=metric_in.provider,
        region=metric_in.region,
        source_type=metric_in.source_type or "UNKNOWN",
        owner_email=metric_in.owner_email,
        commit=commit,
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

    if commit:
        batch_id = metric_in.batch_id
        if batch_id:
            payload_hash = compute_metric_payload_hash([metric_in])
            try:
                batch_record = IngestedBatch(
                    batch_id=batch_id,
                    host_id=host.id,
                    payload_hash=payload_hash,
                    processed_samples=1,
                    generated_alerts=0,
                )
                db.add(batch_record)
            except Exception:
                pass

        db.commit()
        db.refresh(metric)
    else:
        db.flush()

    # Trigger threshold alert evaluation
    alerts = evaluate_metric_sample(db, host, metric, commit=commit)

    # Trigger AI multivariate anomaly detector (M2-FR2)
    ai_alert = evaluate_and_record_ai_anomaly(db, host, metric, commit=commit)
    if ai_alert:
        alerts.append(ai_alert)

    # Trigger 3-Model Correlated Incident Evaluation (Threshold + Isolation Forest + LSTM)
    corr_alert = evaluate_correlated_anomaly(db, host, metric, commit=commit)
    if corr_alert:
        alerts.append(corr_alert)

    return metric, alerts


def ingest_metric(db: Session, metric_in: MetricCreate) -> Tuple[Metric, List[Alert]]:
    """
    Ingests a single metric sample, auto-discovers/registers the host if unknown,
    and runs static threshold, AI multivariate anomaly, and 3-model correlated consensus evaluation.
    Supports optional batch_id for idempotent retry safety.
    Commits the transaction atomically.
    """
    batch_id = metric_in.batch_id
    if batch_id:
        payload_hash = compute_metric_payload_hash([metric_in])
        existing_batch = db.scalar(select(IngestedBatch).where(IngestedBatch.batch_id == batch_id))
        if existing_batch:
            if existing_batch.payload_hash == payload_hash:
                # Idempotent retry: return latest recorded metric for host without duplicate insertion
                if existing_batch.host_id:
                    existing_metric = db.scalar(
                        select(Metric).where(Metric.host_id == existing_batch.host_id).order_by(desc(Metric.id)).limit(1)
                    )
                    if existing_metric:
                        return existing_metric, []
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Batch ID '{batch_id}' has already been processed with different telemetry payload.",
                )

    return _persist_metric_record(db, metric_in, commit=True)


def ingest_metrics_batch(db: Session, batch_in: MetricBatchCreate) -> Dict[str, Any]:
    """
    Batch ingests multiple telemetry data points atomically and idempotently (AUD-01, REL-02).

    Transactional Contract:
    - All metric samples, host auto-discovery records, alert evaluations, and the IngestedBatch
      idempotency record are committed in a single, atomic database transaction.
    - If any failure occurs during batch processing, the entire transaction is rolled back,
      leaving zero committed metric rows or side effects.
    - If batch_id is present and previously committed with identical payload:
        Returns established duplicate success response without re-inserting duplicate metrics.
    - If batch_id is present and previously committed with DIFFERENT payload:
        Rejects with HTTP 409 Conflict.
    - Concurrent duplicate submissions are synchronized via unique constraint on batch_id;
      the second request rolls back cleanly and verifies the existing record before returning success.
    """
    batch_id = batch_in.batch_id
    payload_hash = None

    if batch_id:
        payload_hash = compute_metric_payload_hash(batch_in.metrics)
        existing = db.scalar(select(IngestedBatch).where(IngestedBatch.batch_id == batch_id))
        if existing:
            if existing.payload_hash == payload_hash:
                # Safe idempotent retry: return cached success without duplicate inserts
                return {
                    "status": "success",
                    "batch_id": batch_id,
                    "processed_samples": existing.processed_samples,
                    "generated_alerts": existing.generated_alerts,
                    "affected_hosts": [existing.host_id] if existing.host_id else [],
                    "is_duplicate": True,
                }
            else:
                # Batch ID reused with conflicting payload
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Batch ID '{batch_id}' has already been processed with different telemetry payload.",
                )

    total_samples = 0
    total_alerts = 0
    affected_hosts = set()
    first_host_id = None

    try:
        for item in batch_in.metrics:
            metric, alerts = _persist_metric_record(db, item, commit=False)
            total_samples += 1
            total_alerts += len(alerts)
            affected_hosts.add(metric.host_id)
            if first_host_id is None:
                first_host_id = metric.host_id

        if batch_id and payload_hash:
            batch_record = IngestedBatch(
                batch_id=batch_id,
                host_id=first_host_id,
                payload_hash=payload_hash,
                processed_samples=total_samples,
                generated_alerts=total_alerts,
            )
            db.add(batch_record)

        # Single atomic transaction commit for all metrics and idempotency record
        db.commit()

        return {
            "status": "success",
            "batch_id": batch_id,
            "processed_samples": total_samples,
            "generated_alerts": total_alerts,
            "affected_hosts": list(affected_hosts),
            "is_duplicate": False,
        }
    except IntegrityError:
        db.rollback()
        # Handle concurrent submission race
        if batch_id and payload_hash:
            existing = db.scalar(select(IngestedBatch).where(IngestedBatch.batch_id == batch_id))
            if existing and existing.payload_hash == payload_hash:
                return {
                    "status": "success",
                    "batch_id": batch_id,
                    "processed_samples": existing.processed_samples,
                    "generated_alerts": existing.generated_alerts,
                    "affected_hosts": [existing.host_id] if existing.host_id else [],
                    "is_duplicate": True,
                }
            elif existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Batch ID '{batch_id}' has already been processed with different telemetry payload.",
                )
        raise
    except Exception:
        db.rollback()
        raise


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
                source_type=getattr(host, "source_type", "UNKNOWN") or "UNKNOWN",
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


def cleanup_expired_idempotency_records(
    db: Session,
    retention_hours: float = 72.0,
    batch_limit: int = 1000,
) -> int:
    """
    Safely and transactionally prunes expired IngestedBatch idempotency records (AUD-03).

    Retention Policy Contract:
    - Default retention: 72 hours (3 days).
    - Guarantees records remain preserved for 3x the client spool maximum retention (24 hours),
      ensuring no legitimately replayable batch ID can be purged before client spool expiration.
    - Bounded execution via batch_limit to prevent extended SQLite table locks.
    - Strictly purges only IngestedBatch rows; never mutates or deletes Metric, Host, Alert,
      User, or AuditLog records.
    - Returns the count of deleted idempotency records.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)

    # Select IDs of expired batches bounded by batch_limit
    expired_ids = list(
        db.scalars(
            select(IngestedBatch.id)
            .where(IngestedBatch.created_at < cutoff)
            .limit(batch_limit)
        ).all()
    )

    if not expired_ids:
        return 0

    stmt = delete(IngestedBatch).where(IngestedBatch.id.in_(expired_ids))
    result = db.execute(stmt)
    db.commit()
    return int(result.rowcount)

