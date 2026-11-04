"""
Automated Test Suite for Enhanced Reporting Module.

Verifies:
1. Overall Infrastructure Monitoring Report (Aggregations, Environment Filtering, Liveness Model, PDF generation).
2. Individual Sensor / PC Performance Report (Host isolation, Statistics, Alerts, Security events, PDF generation).
3. RBAC & Data Isolation (Super Admin vs Viewer vs Forbidden Host Access).
4. Edge cases (0 hosts, 0 telemetry, offline cutoff thresholds).
"""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from backend.app.database.base import Base
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import Alert
from backend.app.models.security import SecurityEvent
from backend.app.models.user import User, UserRole
from backend.app.models.device import DeviceEnrollment
from backend.app.schemas.report import ReportGenerateRequest, HostReportRequest
from backend.app.services.report_service import (
    generate_executive_report,
    generate_overall_report_pdf,
    generate_host_report_data,
    generate_host_report_pdf,
    verify_user_host_access,
)


@pytest.fixture(scope="function")
def isolated_test_db():
    """Provides a completely isolated, clean in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ==============================================================================
# OVERALL REPORT TESTS
# ==============================================================================

def test_overall_report_host_liveness_and_inventory(isolated_test_db: Session):
    """Test 1: Verifies host count, online/offline/unseen calculations against threshold."""
    now = datetime.now(timezone.utc)

    # Host 1: Online (recent heartbeat 20s ago)
    h1 = Host(hostname="node-online-01", ip_address="10.1.1.10", environment="lab", is_active=True)
    isolated_test_db.add(h1)
    isolated_test_db.flush()

    m1 = Metric(
        host_id=h1.id,
        timestamp=now - timedelta(seconds=20),
        cpu_percent=35.0,
        memory_percent=50.0,
        disk_percent=40.0,
    )
    isolated_test_db.add(m1)

    # Host 2: Offline (heartbeat 200s ago, beyond 90s cutoff)
    h2 = Host(hostname="node-offline-02", ip_address="10.1.1.11", environment="lab", is_active=True)
    isolated_test_db.add(h2)
    isolated_test_db.flush()

    m2 = Metric(
        host_id=h2.id,
        timestamp=now - timedelta(seconds=200),
        cpu_percent=80.0,
        memory_percent=75.0,
        disk_percent=65.0,
    )
    isolated_test_db.add(m2)

    # Host 3: Unseen / No Telemetry
    h3 = Host(hostname="node-unseen-03", ip_address="10.1.1.12", environment="lab", is_active=True)
    isolated_test_db.add(h3)
    isolated_test_db.commit()

    req = ReportGenerateRequest(environment="lab", time_range_hours=24, offline_threshold_seconds=90)
    rep = generate_executive_report(isolated_test_db, req)

    assert rep.summary_metrics["total_hosts"] == 3
    assert rep.online_hosts_count == 1
    assert rep.offline_hosts_count == 1
    assert rep.unseen_hosts_count == 1
    assert len(rep.host_inventories) == 3

    inv_map = {item.hostname: item for item in rep.host_inventories}
    assert inv_map["node-online-01"].status == "ONLINE"
    assert inv_map["node-offline-02"].status == "OFFLINE"
    assert inv_map["node-unseen-03"].status == "NO_DATA"


def test_overall_report_environment_filtering(isolated_test_db: Session):
    """Test 2: Verifies environment filtering excludes other environments."""
    h_prod = Host(hostname="prod-srv-01", ip_address="10.0.1.1", environment="production", is_active=True)
    h_lab = Host(hostname="lab-pc-01", ip_address="10.2.1.1", environment="lab", is_active=True)
    isolated_test_db.add_all([h_prod, h_lab])
    isolated_test_db.commit()

    # Scope to 'lab'
    req_lab = ReportGenerateRequest(environment="lab", time_range_hours=24)
    rep_lab = generate_executive_report(isolated_test_db, req_lab)
    assert rep_lab.summary_metrics["total_hosts"] == 1
    assert rep_lab.host_inventories[0].hostname == "lab-pc-01"

    # Scope to 'production'
    req_prod = ReportGenerateRequest(environment="production", time_range_hours=24)
    rep_prod = generate_executive_report(isolated_test_db, req_prod)
    assert rep_prod.summary_metrics["total_hosts"] == 1
    assert rep_prod.host_inventories[0].hostname == "prod-srv-01"


def test_overall_report_empty_fleet(isolated_test_db: Session):
    """Test 3: Handles 0 enrolled hosts gracefully without division-by-zero errors."""
    req = ReportGenerateRequest(environment="non-existent", time_range_hours=24)
    rep = generate_executive_report(isolated_test_db, req)
    assert rep.summary_metrics["total_hosts"] == 0
    assert rep.online_hosts_count == 0
    assert rep.offline_hosts_count == 0
    assert rep.avg_cpu_percent is None
    assert len(rep.host_inventories) == 0


def test_overall_report_pdf_generation(isolated_test_db: Session):
    """Test 4: Generates multi-page PDF with valid PDF binary header (%PDF)."""
    now = datetime.now(timezone.utc)
    h = Host(hostname="pdf-test-host", ip_address="10.5.5.5", environment="production", is_active=True)
    isolated_test_db.add(h)
    isolated_test_db.flush()

    for i in range(10):
        m = Metric(
            host_id=h.id,
            timestamp=now - timedelta(minutes=(10 - i)),
            cpu_percent=20.0 + i,
            memory_percent=40.0 + i,
            disk_percent=30.0,
        )
        isolated_test_db.add(m)
    isolated_test_db.commit()

    req = ReportGenerateRequest(time_range_hours=24)
    pdf_bytes = generate_overall_report_pdf(isolated_test_db, req)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


# ==============================================================================
# INDIVIDUAL SENSOR / PC REPORT TESTS
# ==============================================================================

def test_individual_host_report_isolation(isolated_test_db: Session):
    """Test 5: Guarantees ONLY the selected PC's metrics, alerts, and security events appear."""
    now = datetime.now(timezone.utc)

    # Host A (Target)
    hA = Host(hostname="target-node-A", ip_address="10.10.1.1", environment="lab", is_active=True)
    # Host B (Other)
    hB = Host(hostname="other-node-B", ip_address="10.10.1.2", environment="lab", is_active=True)
    isolated_test_db.add_all([hA, hB])
    isolated_test_db.flush()

    # Metrics for A
    mA = Metric(host_id=hA.id, timestamp=now - timedelta(minutes=5), cpu_percent=45.0, memory_percent=60.0, disk_percent=55.0)
    # Metrics for B
    mB = Metric(host_id=hB.id, timestamp=now - timedelta(minutes=5), cpu_percent=99.0, memory_percent=99.0, disk_percent=99.0)
    isolated_test_db.add_all([mA, mB])

    # Alert for A
    altA = Alert(host_id=hA.id, metric="cpu_percent", severity="warning", message="Target warning", value=45.0, status="active")
    # Alert for B
    altB = Alert(host_id=hB.id, metric="memory_percent", severity="critical", message="Other critical", value=99.0, status="active")
    isolated_test_db.add_all([altA, altB])

    # Security event for A
    secA = SecurityEvent(host_id=hA.id, event_type="auth_failure", severity="medium", description="Auth failure on A", status="open")
    # Security event for B
    secB = SecurityEvent(host_id=hB.id, event_type="port_scan", severity="critical", description="Port scan on B", status="open")
    isolated_test_db.add_all([secA, secB])
    isolated_test_db.commit()

    req = HostReportRequest(time_range_hours=24)
    repA = generate_host_report_data(isolated_test_db, hA.id, req)

    # Verify Host A identity
    assert repA.host_identity.host_id == hA.id
    assert repA.host_identity.hostname == "target-node-A"

    # Verify ONLY Host A metrics are included (avg CPU should be 45.0, not 99.0)
    assert repA.cpu_stats.avg == 45.0
    assert repA.cpu_stats.max == 45.0

    # Verify ONLY Host A alerts are included
    assert repA.total_alerts == 1
    assert repA.alerts[0].message == "Target warning"
    assert repA.alerts[0].metric == "cpu_percent"

    # Verify ONLY Host A security events are included
    assert repA.security_events_count == 1
    assert repA.security_events[0].description == "Auth failure on A"


def test_individual_host_report_non_existent_host(isolated_test_db: Session):
    """Test 6: Requesting a non-existent host ID raises 404."""
    req = HostReportRequest(time_range_hours=24)
    with pytest.raises(HTTPException) as exc:
        generate_host_report_data(isolated_test_db, host_id=99999, req=req)
    assert exc.value.status_code == 404


def test_individual_host_report_rbac_unauthorized_user(isolated_test_db: Session):
    """Test 7: Operator/Viewer attempting to access restricted host is rejected with 403."""
    h = Host(
        hostname="restricted-host",
        ip_address="10.20.1.1",
        environment="production",
        owner_email="admin@corp.internal",
        tags={"allowed_users": ["admin@corp.internal"]},
        is_active=True,
    )
    isolated_test_db.add(h)
    isolated_test_db.commit()

    unauthorized_viewer = User(
        id=77,
        email="guest@lab.internal",
        password_hash="dummy",
        role=UserRole.VIEWER,
        is_active=True,
    )

    req = HostReportRequest(time_range_hours=24)
    with pytest.raises(HTTPException) as exc:
        generate_host_report_data(isolated_test_db, host_id=h.id, req=req, user=unauthorized_viewer)
    assert exc.value.status_code == 403


def test_individual_host_report_rbac_super_admin_bypass(isolated_test_db: Session):
    """Test 8: SUPER_ADMIN has full access to any host regardless of ownership."""
    h = Host(
        hostname="priv-host",
        ip_address="10.30.1.1",
        environment="production",
        owner_email="someone-else@ops.internal",
        tags={"allowed_users": ["someone-else@ops.internal"]},
        is_active=True,
    )
    isolated_test_db.add(h)
    isolated_test_db.commit()

    super_admin = User(
        id=1,
        email="root@cloudops.internal",
        password_hash="dummy",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )

    req = HostReportRequest(time_range_hours=24)
    rep = generate_host_report_data(isolated_test_db, host_id=h.id, req=req, user=super_admin)
    assert rep.host_identity.hostname == "priv-host"


def test_individual_host_report_pdf_generation(isolated_test_db: Session):
    """Test 9: Generates dedicated host PDF with valid PDF binary header (%PDF)."""
    now = datetime.now(timezone.utc)
    h = Host(hostname="lab-pc-pdf-test", ip_address="10.40.1.5", environment="lab", is_active=True)
    isolated_test_db.add(h)
    isolated_test_db.flush()

    for i in range(15):
        m = Metric(
            host_id=h.id,
            timestamp=now - timedelta(minutes=(15 - i)),
            cpu_percent=15.0 + i,
            memory_percent=35.0,
            disk_percent=50.0,
            network_sent_mb=1.2,
            network_received_mb=3.4,
        )
        isolated_test_db.add(m)
    isolated_test_db.commit()

    req = HostReportRequest(time_range_hours=24)
    pdf_bytes = generate_host_report_pdf(isolated_test_db, h.id, req)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")

