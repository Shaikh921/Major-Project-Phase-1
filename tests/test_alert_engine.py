"""
Unit Tests for Alert Engine, Deduplication, and Rule Evaluation.
"""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.database.base import Base
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import AlertRule, Alert, AlertFeedback
from backend.app.database.init_db import seed_default_rules
from backend.app.schemas.metric import MetricCreate
from backend.app.schemas.alert import AlertFeedbackCreate, AlertRuleCreate
from backend.app.services.metric_service import ingest_metric
from backend.app.services.alert_service import (
    get_alerts,
    acknowledge_alert,
    resolve_alert,
    record_alert_feedback,
    create_alert_rule,
)


from backend.app.services.ai_service import reset_global_detector


def create_test_db():
    reset_global_detector()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    seed_default_rules(db)
    return db


def test_alert_threshold_breach_and_deduplication():
    """
    Tests that:
    1. A breached metric sample raises an active alert.
    2. A second breached sample on the same host & metric updates the existing alert rather than creating a duplicate.
    """
    db = create_test_db()

    # 1. First sample with high CPU (88% >= 80% Warning)
    _, alerts1 = ingest_metric(
        db,
        MetricCreate(
            hostname="web-prod-01",
            cpu_percent=88.0,
            memory_percent=40.0,
            disk_percent=30.0,
        ),
    )
    assert len(alerts1) == 1
    alert_id = alerts1[0].id
    assert alerts1[0].status == "active"
    assert alerts1[0].severity == "warning"

    # Verify 1 active alert in DB
    all_alerts = get_alerts(db, status="active")
    assert len(all_alerts) == 1

    # 2. Second sample still high CPU (92%)
    _, alerts2 = ingest_metric(
        db,
        MetricCreate(
            hostname="web-prod-01",
            cpu_percent=92.0,
            memory_percent=40.0,
            disk_percent=30.0,
        ),
    )
    # Deduplication check: Same alert record updated, count remains 1
    all_alerts_after = get_alerts(db, status="active")
    assert len(all_alerts_after) == 1
    assert all_alerts_after[0].id == alert_id
    assert all_alerts_after[0].value == 92.0

    db.close()


def test_alert_auto_resolution():
    """
    Tests that when a metric returns to normal, any active alert is automatically resolved.
    """
    db = create_test_db()

    # 1. Breach threshold
    ingest_metric(
        db,
        MetricCreate(
            hostname="db-server",
            cpu_percent=96.0,  # Critical CPU
            memory_percent=40.0,
            disk_percent=30.0,
        ),
    )
    active_alerts = get_alerts(db, status="active")
    assert len(active_alerts) >= 1

    # 2. Ingest normal sample (CPU falls to 30%)
    ingest_metric(
        db,
        MetricCreate(
            hostname="db-server",
            cpu_percent=30.0,
            memory_percent=40.0,
            disk_percent=30.0,
        ),
    )

    # Active alerts should now be 0, and the previous alert resolved
    active_alerts_after = get_alerts(db, status="active")
    assert len(active_alerts_after) == 0

    resolved_alerts = get_alerts(db, status="resolved")
    assert len(resolved_alerts) >= 1
    assert resolved_alerts[0].resolved_at is not None

    db.close()


def test_alert_acknowledgment_and_feedback():
    """
    Tests operator acknowledgment and true/false-positive feedback logging (M5-FR6).
    """
    db = create_test_db()

    _, alerts = ingest_metric(
        db,
        MetricCreate(
            hostname="app-node",
            cpu_percent=86.0,
            memory_percent=40.0,
            disk_percent=30.0,
        ),
    )
    alert = alerts[0]
    assert alert.status == "active"

    # Acknowledge alert
    acked = acknowledge_alert(db, alert.id)
    assert acked is not None
    assert acked.status == "acknowledged"
    assert acked.acknowledged_at is not None

    # Record operator feedback
    feedback = record_alert_feedback(
        db=db,
        alert_id=alert.id,
        feedback_in=AlertFeedbackCreate(
            verdict="true_positive",
            operator_notes="Confirmed CPU spike during database backup job.",
        ),
    )
    assert feedback is not None
    assert feedback.verdict == "true_positive"
    assert feedback.alert_id == alert.id

    db.close()
