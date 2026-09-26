"""
Unit Tests for Security & Intrusion Detection Engine (Module 4).
"""

from security_engine.detector import SecurityDetector
from backend.app.schemas.security import SecurityEventCreate, SecurityStatusUpdate
from backend.app.services.security_service import (
    record_security_event,
    get_security_events,
    get_security_summary,
    update_security_event_status,
)
from tests.test_alert_engine import create_test_db


def test_security_detector_egress_spike():
    detector = SecurityDetector()
    res = detector.analyze_network_sample(
        "prod-api-01",
        network_sent_mb=250.0,
        network_received_mb=10.0,
        source_ip="192.168.10.50",
        destination_port=8443,
    )
    assert res is not None
    assert res["event_type"] == "suspicious_egress"
    assert res["severity"] == "critical"
    assert res["source_ip"] == "192.168.10.50"
    assert res["destination_port"] == 8443

    # Default fallback when IP not provided
    res_default = detector.analyze_network_sample("prod-api-01", network_sent_mb=200.0, network_received_mb=10.0)
    assert res_default is not None
    assert res_default["source_ip"] == "unknown"
    assert res_default["destination_port"] == 443

    normal_res = detector.analyze_network_sample("prod-api-01", network_sent_mb=15.0, network_received_mb=10.0)
    assert normal_res is None


def test_security_detector_auth_brute_force():
    detector = SecurityDetector()
    event = detector.analyze_auth_event(
        hostname="bastion-01",
        failed_attempts=6,
        source_ip="203.0.113.42",
        username="root",
    )
    assert event is not None
    assert event["event_type"] == "ssh_brute_force"
    assert event["severity"] == "high"
    assert event["source_ip"] == "203.0.113.42"
    assert event["destination_port"] == 22

    normal_auth = detector.analyze_auth_event(hostname="bastion-01", failed_attempts=2)
    assert normal_auth is None


def test_security_service_persistence_and_summary():
    db = create_test_db()
    
    event = record_security_event(
        db,
        SecurityEventCreate(
            hostname="test-host",
            event_type="ssh_brute_force",
            severity="high",
            source_ip="198.51.100.1",
            description="5 failed SSH attempts",
        ),
    )
    assert event.id is not None
    assert event.status == "open"

    summary = get_security_summary(db)
    assert summary.total_events >= 1
    assert summary.high_events >= 1

    # Update status to mitigated
    updated = update_security_event_status(db, event.id, SecurityStatusUpdate(status="mitigated"))
    assert updated is not None
    assert updated.status == "mitigated"
    assert updated.resolved_at is not None

    db.close()
