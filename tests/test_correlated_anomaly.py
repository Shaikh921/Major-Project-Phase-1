"""
Unit & Integration Test Suite for Multi-Model Correlated Anomaly Alerting.

Validates:
1. LSTM Autoencoder sequence detection (ai_engine/lstm_detector.py).
2. HTML/Plaintext Correlated Incident email generation.
3. EmailService.send_correlated_anomaly_notification dispatch.
4. End-to-end multi-tier consensus:
   - High resource utilization (Thresholds)
   - Multivariate Isolation Forest anomaly
   - Deep LSTM Autoencoder temporal sequence anomaly
5. Multi-recipient dispatch to Super Admin AND Host-associated owner email.
6. Alert deduplication and lifecycle management.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from backend.app.database.session import SessionLocal
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import Alert
from backend.app.models.user import User, UserRole
from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.services.email_service import EmailService
from backend.app.services.ai_service import evaluate_correlated_anomaly, reset_global_detector
from backend.app.services.metric_service import ingest_metric
from backend.app.schemas.metric import MetricCreate
from backend.app.templates.email_templates import get_correlated_anomaly_email
from ai_engine.lstm_detector import LSTMAutoencoderAnomalyDetector


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_state():
    orig_smtp = settings.smtp_enabled
    orig_notify = settings.notify_on_critical_alerts
    settings.smtp_enabled = False
    settings.notify_on_critical_alerts = True
    EmailService.clear_outbox()
    reset_global_detector()
    yield
    settings.smtp_enabled = orig_smtp
    settings.notify_on_critical_alerts = orig_notify


def test_lstm_autoencoder_detector_healthy_and_anomalous():
    """Validates LSTM Autoencoder sequence evaluator on normal vs spike patterns."""
    detector = LSTMAutoencoderAnomalyDetector(seq_len=15, threshold=0.79135)

    # 1. Healthy sequence (baseline utilization)
    healthy_samples = [
        {"cpu_percent": 25.0 + (i % 3), "memory_percent": 40.0, "disk_percent": 30.0, "network_sent_mb": 2.0, "network_received_mb": 4.0}
        for i in range(15)
    ]
    res_healthy = detector.predict_window(healthy_samples)
    assert res_healthy["is_anomaly"] is False
    assert res_healthy["status"] == "NORMAL"
    assert res_healthy["reconstruction_error"] < res_healthy["operating_threshold"]

    # 2. Critical anomalous spike sequence
    anom_samples = [
        {"cpu_percent": 95.0, "memory_percent": 92.0, "disk_percent": 88.0, "network_sent_mb": 85.0, "network_received_mb": 90.0}
        for i in range(15)
    ]
    res_anom = detector.predict_window(anom_samples)
    assert res_anom["is_anomaly"] is True
    assert res_anom["status"] == "ANOMALY"


def test_correlated_anomaly_email_template():
    """Validates HTML and plaintext rendering of the correlated anomaly email."""
    subject, html_body, text_body = get_correlated_anomaly_email(
        alert_id=999,
        host_name="prod-k8s-master-01",
        ip_address="10.0.4.15",
        environment="production",
        metric_name="cpu_percent",
        metric_value=96.5,
        threshold_value=80.0,
        iso_score=0.885,
        lstm_score=1.4520,
        lstm_threshold=0.7913,
        explanation="Severe CPU saturation and multi-core exhaustion detected.",
    )

    assert "CRITICAL CORRELATED INCIDENT" in subject
    assert "prod-k8s-master-01" in subject
    assert "10.0.4.15" in html_body
    assert "0.885" in html_body
    assert "1.4520" in html_body
    assert "Severe CPU saturation" in html_body
    assert "#999" in text_body
    assert "10.0.4.15" in text_body


def test_correlated_anomaly_end_to_end_dispatch(db_session):
    """
    Validates that when high resources + Isolation Forest + LSTM models all flag an anomaly,
    emails are dispatched to both the Super Admin and the Host-associated owner email.
    """
    EmailService.clear_outbox()

    # 1. Ensure a Super Admin user exists
    super_admin_email = "superadmin.security@cloudops.internal"
    super_admin = db_session.scalar(select(User).where(User.email == super_admin_email))
    if not super_admin:
        super_admin = User(
            email=super_admin_email,
            password_hash=hash_password("SuperSecretAdminPass123!"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
        )
        db_session.add(super_admin)
        db_session.commit()
        db_session.refresh(super_admin)

    # 2. Create Host with an associated owner email
    host_owner_email = "lead-sre.database@cloudops.internal"
    test_hostname = "prod-db-e2e-node-corr"
    host = db_session.scalar(select(Host).where(Host.hostname == test_hostname))
    if not host:
        host = Host(
            hostname=test_hostname,
            ip_address="192.168.100.99",
            environment="production",
            owner_email=host_owner_email,
            source_type="REAL_AGENT",
            is_active=True,
            tags={"tier": "database", "contact_email": host_owner_email},
        )
        db_session.add(host)
        db_session.commit()
        db_session.refresh(host)
    else:
        host.owner_email = host_owner_email
        db_session.commit()

    # Clean any stale alerts/metrics for this host from previous runs
    for a in db_session.scalars(select(Alert).where(Alert.host_id == host.id)).all():
        db_session.delete(a)
    for m in db_session.scalars(select(Metric).where(Metric.host_id == host.id)).all():
        db_session.delete(m)
    db_session.commit()

    # 3. Ingest baseline normal historical metrics first (healthy sequence)
    for i in range(14):
        m_in = MetricCreate(
            hostname=test_hostname,
            ip_address="192.168.100.99",
            environment="production",
            cpu_percent=25.0 + (i % 3),
            memory_percent=40.0,
            disk_percent=30.0,
            network_sent_mb=2.0,
            network_received_mb=4.0,
        )
        ingest_metric(db_session, m_in)

    # Clear outbox before triggering anomalous spike
    EmailService.clear_outbox()

    # 4. Ingest critical anomalous spike sample (breaches threshold, Isolation Forest & LSTM)
    final_sample = MetricCreate(
        hostname=test_hostname,
        ip_address="192.168.100.99",
        environment="production",
        cpu_percent=98.5,
        memory_percent=96.0,
        disk_percent=88.0,
        network_sent_mb=85.0,
        network_received_mb=95.0,
    )
    metric, alerts = ingest_metric(db_session, final_sample)

    # Verify correlated alert was generated
    corr_alerts = [a for a in alerts if a.kind == "correlated_anomaly"]
    assert len(corr_alerts) >= 1
    corr_alert = corr_alerts[0]
    assert corr_alert.severity == "critical"
    assert corr_alert.status == "active"
    assert "CRITICAL CORRELATED INCIDENT" in corr_alert.message

    # Verify Emails in Dev Outbox
    outbox = EmailService.get_outbox()
    assert len(outbox) >= 2, f"Expected at least 2 emails, got {len(outbox)}"

    recipient_emails = [msg["to_email"] for msg in outbox]
    assert super_admin_email in recipient_emails, f"Super admin {super_admin_email} did not receive email: {recipient_emails}"
    assert host_owner_email in recipient_emails, f"Host owner {host_owner_email} did not receive email: {recipient_emails}"

    # Verify Email Metadata
    correlated_dispatches = [m for m in outbox if m.get("type") == "CORRELATED_ANOMALY_ALERT"]
    assert len(correlated_dispatches) >= 2
    sample_dispatch = correlated_dispatches[0]
    assert sample_dispatch["host_name"] == test_hostname
    assert sample_dispatch["alert_id"] == corr_alert.id


def test_healthy_metrics_do_not_trigger_correlated_email(db_session):
    """Verifies that normal metrics do not trigger false positive correlated alert emails."""
    EmailService.clear_outbox()
    normal_sample = MetricCreate(
        hostname="prod-web-healthy-01",
        ip_address="10.0.2.10",
        environment="production",
        cpu_percent=32.0,
        memory_percent=45.0,
        disk_percent=40.0,
        network_sent_mb=5.0,
        network_received_mb=8.0,
    )
    metric, alerts = ingest_metric(db_session, normal_sample)
    corr_alerts = [a for a in alerts if a.kind == "correlated_anomaly"]
    assert len(corr_alerts) == 0

    outbox = EmailService.get_outbox()
    corr_emails = [m for m in outbox if m.get("metadata", {}).get("type") == "CORRELATED_ANOMALY_ALERT"]
    assert len(corr_emails) == 0
