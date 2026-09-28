"""
Unit Tests for Metric Ingestion and Time-Series Query Service.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.base import Base
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import AlertRule, Alert, AlertFeedback
from backend.app.database.init_db import seed_default_rules
from backend.app.schemas.metric import MetricCreate, MetricBatchCreate
from backend.app.services.metric_service import (
    ingest_metric,
    ingest_metrics_batch,
    get_host_metrics,
    get_fleet_summary,
)
from backend.app.services.ai_service import reset_global_detector


def create_test_db():
    """Sets up an in-memory SQLite database with default seeded rules."""
    reset_global_detector()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    seed_default_rules(db)
    return db


def test_ingest_single_metric_with_auto_registration():
    """Tests that ingesting a metric from an unknown host auto-creates the Host record."""
    db = create_test_db()

    payload = MetricCreate(
        hostname="new-worker-01",
        ip_address="10.0.3.5",
        environment="production",
        provider="aws",
        region="us-west-2",
        cpu_percent=45.5,
        memory_percent=60.0,
        disk_percent=55.0,
        network_sent_mb=1.2,
        network_received_mb=3.4,
    )

    metric, alerts = ingest_metric(db, payload)

    assert metric.id is not None
    assert metric.cpu_percent == 45.5
    assert metric.host.hostname == "new-worker-01"
    assert metric.host.provider == "aws"
    assert len(alerts) == 0  # Below 80% threshold

    db.close()


def test_ingest_metrics_batch():
    """Tests batch ingestion of multiple data points."""
    db = create_test_db()

    batch = MetricBatchCreate(
        metrics=[
            MetricCreate(
                hostname="batch-host-1",
                cpu_percent=30.0,
                memory_percent=40.0,
                disk_percent=50.0,
            ),
            MetricCreate(
                hostname="batch-host-2",
                cpu_percent=88.0,  # Breaches 80% Warning rule!
                memory_percent=40.0,
                disk_percent=50.0,
            ),
        ]
    )

    result = ingest_metrics_batch(db, batch)

    assert result["status"] == "success"
    assert result["processed_samples"] == 2
    assert result["generated_alerts"] == 1
    assert len(result["affected_hosts"]) == 2

    db.close()


def test_get_host_metrics_timeseries():
    """Tests time-series retrieval with ordering and limits."""
    db = create_test_db()

    now = datetime.now(timezone.utc)
    for i in range(5):
        ingest_metric(
            db,
            MetricCreate(
                hostname="chart-host",
                cpu_percent=20.0 + i,
                memory_percent=50.0,
                disk_percent=60.0,
                timestamp=now + timedelta(minutes=i),
            ),
        )

    # Get host ID
    from backend.app.services.host_service import get_host_by_name
    host = get_host_by_name(db, "chart-host")
    assert host is not None

    timeseries = get_host_metrics(db, host_id=host.id, limit=3)
    assert timeseries.total_samples == 3
    assert timeseries.hostname == "chart-host"
    # Should be sorted chronologically ascending
    assert timeseries.data[0].cpu_percent < timeseries.data[-1].cpu_percent

    db.close()


def test_get_fleet_summary():
    """Tests fleet-wide aggregation and status grouping."""
    db = create_test_db()

    # Host 1: Healthy
    ingest_metric(
        db,
        MetricCreate(
            hostname="healthy-host",
            cpu_percent=20.0,
            memory_percent=30.0,
            disk_percent=40.0,
        ),
    )

    # Host 2: Critical (CPU >= 95)
    ingest_metric(
        db,
        MetricCreate(
            hostname="critical-host",
            cpu_percent=96.0,
            memory_percent=50.0,
            disk_percent=40.0,
        ),
    )

    summary = get_fleet_summary(db)
    assert summary.total_hosts == 2
    assert summary.healthy_hosts == 1
    assert summary.critical_hosts == 1
    assert summary.total_active_alerts >= 1

    db.close()


def test_metric_ingestion_preserves_source_type():
    """Tests that ingesting telemetry with source_type propagates through to fleet summary."""
    db = create_test_db()

    # Ingest from Real Agent
    ingest_metric(
        db,
        MetricCreate(
            hostname="local-agent-node",
            source_type="REAL_AGENT",
            cpu_percent=15.0,
            memory_percent=45.0,
            disk_percent=50.0,
        ),
    )

    # Ingest from Simulated Fleet
    ingest_metric(
        db,
        MetricCreate(
            hostname="simulated-fleet-node",
            source_type="SIMULATED",
            provider="simulation",
            region="synthetic",
            cpu_percent=85.0,
            memory_percent=70.0,
            disk_percent=60.0,
        ),
    )

    summary = get_fleet_summary(db)
    assert summary.total_hosts == 2
    sources = {h.hostname: h.source_type for h in summary.hosts}
    assert sources["local-agent-node"] == "REAL_AGENT"
    assert sources["simulated-fleet-node"] == "SIMULATED"

    db.close()
