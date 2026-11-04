"""
Tests for Enhanced Operational & Executive Report Service.

Validates:
1. Populated fleet with online host health triage.
2. Offline fleet when heartbeats exceed configured threshold.
3. Hosts with no ingested telemetry (distinguished from zero utilization).
4. Empty fleet handling (0 enrolled nodes).
5. Accurate security posture reporting (absence of events != proof of security).
6. API endpoint contract and response schema compatibility.
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.security import SecurityEvent
from backend.app.models.user import User
from backend.app.api.deps import get_current_viewer
from backend.app.schemas.report import ReportGenerateRequest
from backend.app.services.report_service import generate_executive_report

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_viewer_auth_override():
    mock_viewer = User(
        id=99,
        email="auditor@ops.local",
        password_hash="dummy",
        role="VIEWER",
        is_active=True,
        is_verified=True,
    )
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer
    yield
    app.dependency_overrides.pop(get_current_viewer, None)


def test_report_generation_populated_online_fleet(isolated_db: Session):
    now = datetime.now(timezone.utc)
    env_name = "test-online-env"

    # Create host
    h = Host(
        hostname="online-node-01",
        ip_address="10.1.10.5",
        environment=env_name,
        region="Lab-A",
        is_active=True,
    )
    isolated_db.add(h)
    isolated_db.flush()

    # Add recent metric (20s ago, well within 90s cutoff)
    m = Metric(
        host_id=h.id,
        timestamp=now - timedelta(seconds=20),
        cpu_percent=42.5,
        memory_percent=61.0,
        disk_percent=33.2,
    )
    isolated_db.add(m)
    isolated_db.commit()

    req = ReportGenerateRequest(
        environment=env_name,
        time_range_hours=24,
        offline_threshold_seconds=90,
    )
    report = generate_executive_report(isolated_db, req)

    assert report.environment == env_name
    assert report.summary_metrics["total_hosts"] == 1
    assert report.online_hosts_count == 1
    assert report.offline_hosts_count == 0
    assert report.unseen_hosts_count == 0
    assert report.data_freshness_timestamp is not None
    assert len(report.host_inventories) == 1

    inv = report.host_inventories[0]
    assert inv.hostname == "online-node-01"
    assert inv.status == "ONLINE"
    assert inv.cpu_percent == 42.5
    assert inv.memory_percent == 61.0
    assert inv.disk_percent == 33.2


def test_report_generation_offline_fleet(isolated_db: Session):
    now = datetime.now(timezone.utc)
    env_name = "test-offline-env"

    h = Host(
        hostname="offline-node-02",
        ip_address="10.1.10.6",
        environment=env_name,
        region="Lab-B",
        is_active=True,
    )
    isolated_db.add(h)
    isolated_db.flush()

    # Telemetry is 250s old (exceeds 90s cutoff)
    m = Metric(
        host_id=h.id,
        timestamp=now - timedelta(seconds=250),
        cpu_percent=88.0,
        memory_percent=75.0,
        disk_percent=50.0,
    )
    isolated_db.add(m)
    isolated_db.commit()

    req = ReportGenerateRequest(
        environment=env_name,
        time_range_hours=24,
        offline_threshold_seconds=90,
    )
    report = generate_executive_report(isolated_db, req)

    assert report.online_hosts_count == 0
    assert report.offline_hosts_count == 1
    assert report.unseen_hosts_count == 0

    inv = report.host_inventories[0]
    assert inv.status == "OFFLINE"
    assert "Fleet Offline" in report.sections[0]["status"]


def test_report_generation_unseen_host_distinguished_from_zero(isolated_db: Session):
    env_name = "test-unseen-env"

    h = Host(
        hostname="unseen-node-03",
        ip_address="10.1.10.7",
        environment=env_name,
        region="Lab-C",
        is_active=True,
    )
    isolated_db.add(h)
    isolated_db.commit()

    req = ReportGenerateRequest(
        environment=env_name,
        time_range_hours=24,
        offline_threshold_seconds=90,
    )
    report = generate_executive_report(isolated_db, req)

    assert report.unseen_hosts_count == 1
    assert report.online_hosts_count == 0
    assert report.offline_hosts_count == 0

    inv = report.host_inventories[0]
    assert inv.status == "NO_DATA"
    assert inv.last_seen is None
    # Metrics must be None, distinguishing missing samples from 0.0% utilization
    assert inv.cpu_percent is None
    assert inv.memory_percent is None
    assert inv.disk_percent is None


def test_report_generation_empty_fleet(isolated_db: Session):
    env_name = "test-nonexistent-empty-env"

    req = ReportGenerateRequest(
        environment=env_name,
        time_range_hours=24,
        offline_threshold_seconds=90,
    )
    report = generate_executive_report(isolated_db, req)

    assert report.summary_metrics["total_hosts"] == 0
    assert report.online_hosts_count == 0
    assert len(report.host_inventories) == 0
    assert report.sections[0]["status"] == "No Monitored Hosts"
    assert "Monitoring Inactive" in report.sections[1]["status"]
    assert report.security_audit_disclaimer != ""


def test_security_status_zero_events_includes_qualification_and_disclaimer(isolated_db: Session):
    env_name = "test-sec-zero-env"

    h = Host(
        hostname="sec-node-04",
        ip_address="10.1.10.8",
        environment=env_name,
        is_active=True,
    )
    isolated_db.add(h)
    isolated_db.commit()

    req = ReportGenerateRequest(
        environment=env_name,
        time_range_hours=24,
        offline_threshold_seconds=90,
    )
    report = generate_executive_report(isolated_db, req)

    sec_section = report.sections[1]
    # Mandatory rule: zero security events must NOT be reported as unconditionally "Secure"
    assert sec_section["status"] == "No Security Events Flagged"
    assert "Absence of recorded security events" in sec_section["details"]
    assert "not constitute a formal warranty" in report.security_audit_disclaimer


def test_security_status_with_active_flagged_events(isolated_db: Session):
    now = datetime.now(timezone.utc)
    env_name = "test-sec-events-env"

    h = Host(
        hostname="sec-node-05",
        ip_address="10.1.10.9",
        environment=env_name,
        is_active=True,
    )
    isolated_db.add(h)
    isolated_db.flush()

    sec_event = SecurityEvent(
        host_id=h.id,
        event_type="auth_failure",
        severity="high",
        source_ip="192.168.1.50",
        destination_port=22,
        description="Repeated failed SSH logins",
        timestamp=now - timedelta(minutes=15),
    )
    isolated_db.add(sec_event)
    isolated_db.commit()

    req = ReportGenerateRequest(
        environment=env_name,
        time_range_hours=24,
        offline_threshold_seconds=90,
    )
    report = generate_executive_report(isolated_db, req)

    assert report.security_events_count >= 1
    sec_section = report.sections[1]
    assert "Flagged" in sec_section["status"] or "events detected" in sec_section["status"].lower()


from backend.app.api.v1.reports import generate_report

def test_reports_api_endpoint(isolated_db: Session):
    req = ReportGenerateRequest(
        time_range_hours=24,
        offline_threshold_seconds=90,
    )
    mock_viewer = User(
        id=99,
        email="auditor@ops.local",
        password_hash="dummy",
        role="VIEWER",
        is_active=True,
        is_verified=True,
    )
    res = generate_report(req=req, current_user=mock_viewer, db=isolated_db)
    data = res.model_dump()

    assert "report_id" in data
    assert "title" in data
    assert "time_window_start" in data
    assert "time_window_end" in data
    assert "online_hosts_count" in data
    assert "offline_hosts_count" in data
    assert "unseen_hosts_count" in data
    assert "host_inventories" in data
    assert "security_audit_disclaimer" in data
    assert "summary_metrics" in data
    assert "sections" in data
    assert len(data["sections"]) == 3

