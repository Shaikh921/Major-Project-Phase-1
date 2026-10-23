"""
Integration Tests for Lab PC Monitoring API (GET /api/v1/lab/summary).

Validates:
- Authentication & RBAC enforcement (Viewer, Admin, Deactivated, Anonymous).
- Multi-tenant host isolation (Lab vs Production vs Staging).
- Telemetry provenance filtering (REAL_AGENT vs SIMULATED).
- Online/offline status thresholds and never-seen host handling.
- Room grouping, alphabetized sorting, and room average CPU computation.
- CPU severity boundary classifications (normal, warning, high, offline).
- Deduplication of duplicate metric timestamps.
- Exclusion of deactivated hosts.
- Live ingestion of REAL_AGENT telemetry and subsequent reflection in lab summary.
- Query parameter validation bounds (ge=10, le=3600).
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.api.deps import get_db, get_current_viewer
from backend.app.models.user import User, UserRole
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.schemas.lab import LabSummaryResponse

client = TestClient(app)


@pytest.fixture
def test_db_session():
    """Provides a transactional session on the isolated in-memory test database."""
    from tests.conftest import TestingSessionLocal
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_viewer_user():
    return User(
        id=901,
        email="lab-viewer@test.local",
        password_hash="dummy",
        role=UserRole.VIEWER,
        is_active=True,
        is_verified=True,
    )


@pytest.fixture
def mock_deactivated_user():
    return User(
        id=902,
        email="lab-deactivated@test.local",
        password_hash="dummy",
        role=UserRole.VIEWER,
        is_active=False,
        is_verified=True,
    )


def test_lab_summary_unauthenticated():
    """TEST-LAB-01: Anonymous request without Bearer token returns 401 Unauthorized."""
    app.dependency_overrides.pop(get_current_viewer, None)
    res = client.get("/api/v1/lab/summary")
    assert res.status_code == 401
    assert "WWW-Authenticate" in res.headers or "detail" in res.json()


def test_lab_summary_viewer_authorized(test_db_session):
    """TEST-LAB-02: Authenticated Viewer receives 200 OK matching LabSummaryResponse."""
    from backend.app.core.security import create_access_token
    viewer = User(
        email="lab-active-viewer@test.local",
        password_hash="dummy",
        role=UserRole.VIEWER,
        is_active=True,
        is_verified=True,
    )
    test_db_session.add(viewer)
    test_db_session.commit()
    test_db_session.refresh(viewer)

    token = create_access_token(user_id=viewer.id, email=viewer.email, role=viewer.role)
    app.dependency_overrides.pop(get_current_viewer, None)
    res = client.get(
        "/api/v1/lab/summary?environment=lab",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "generated_at" in data
    assert "environment" in data
    assert data["environment"] == "lab"
    assert "totals" in data
    assert "rooms" in data
    assert "busiest_pcs" in data
    # Validate against Pydantic schema
    validated = LabSummaryResponse.model_validate(data)
    assert validated.environment == "lab"


def test_lab_summary_deactivated_user(test_db_session):
    """TEST-LAB-03: Deactivated user (is_active=False) receives 403 Forbidden."""
    from backend.app.core.security import create_access_token
    deactivated = User(
        email="lab-deactivated-user@test.local",
        password_hash="dummy",
        role=UserRole.VIEWER,
        is_active=False,
        is_verified=True,
    )
    test_db_session.add(deactivated)
    test_db_session.commit()
    test_db_session.refresh(deactivated)

    token = create_access_token(user_id=deactivated.id, email=deactivated.email, role=deactivated.role)
    app.dependency_overrides.pop(get_current_viewer, None)
    res = client.get(
        "/api/v1/lab/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "deactivated" in res.json()["detail"].lower()




def test_lab_environment_isolation(test_db_session, mock_viewer_user):
    """TEST-LAB-04: Non-lab hosts (production, staging) are strictly excluded from lab summary."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        # Create production host and lab host
        prod_host = Host(
            hostname="prod-srv-99",
            environment="production",
            provider="aws",
            region="us-east-1",
            source_type="REAL_AGENT",
            is_active=True,
        )
        lab_host = Host(
            hostname="lab1-pc-isolate",
            environment="lab",
            provider="college-lab",
            region="lab-1",
            source_type="REAL_AGENT",
            is_active=True,
        )
        test_db_session.add_all([prod_host, lab_host])
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab")
        assert res.status_code == 200
        data = res.json()
        hostnames = [pc["hostname"] for room in data["rooms"] for pc in room["pcs"]]
        assert "lab1-pc-isolate" in hostnames
        assert "prod-srv-99" not in hostnames
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_provenance_filter(test_db_session, mock_viewer_user):
    """TEST-LAB-05: real_agents_only filters out SIMULATED hosts unless explicitly disabled."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        real_host = Host(
            hostname="lab-real-hw",
            environment="lab-prov-test",
            region="lab-1",
            source_type="REAL_AGENT",
            is_active=True,
        )
        sim_host = Host(
            hostname="lab-sim-vm",
            environment="lab-prov-test",
            region="lab-1",
            source_type="SIMULATED",
            is_active=True,
        )
        test_db_session.add_all([real_host, sim_host])
        test_db_session.commit()

        # Query with real_agents_only=True (default)
        res_real = client.get("/api/v1/lab/summary?environment=lab-prov-test&real_agents_only=true")
        assert res_real.status_code == 200
        real_pcs = [pc["hostname"] for room in res_real.json()["rooms"] for pc in room["pcs"]]
        assert "lab-real-hw" in real_pcs
        assert "lab-sim-vm" not in real_pcs

        # Query with real_agents_only=False
        res_all = client.get("/api/v1/lab/summary?environment=lab-prov-test&real_agents_only=false")
        assert res_all.status_code == 200
        all_pcs = [pc["hostname"] for room in res_all.json()["rooms"] for pc in room["pcs"]]
        assert "lab-real-hw" in all_pcs
        assert "lab-sim-vm" in all_pcs
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_online_status_calculation(test_db_session, mock_viewer_user):
    """TEST-LAB-06: Evaluates online status calculation for active heartbeat within threshold."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        now = datetime.now(timezone.utc)
        online_host = Host(
            hostname="lab-pc-active-only",
            environment="lab-online-test",
            region="lab-1",
            source_type="REAL_AGENT",
            is_active=True,
        )
        test_db_session.add(online_host)
        test_db_session.commit()

        # online_host reported 25 seconds ago (< 90s)
        m_online = Metric(
            host_id=online_host.id,
            timestamp=now - timedelta(seconds=25),
            cpu_percent=42.0,
            memory_percent=50.0,
            disk_percent=30.0,
        )
        test_db_session.add(m_online)
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab-online-test&offline_after_seconds=90")
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["total_pcs"] == 1
        assert data["totals"]["online"] == 1
        assert data["totals"]["offline"] == 0

        pc = data["rooms"][0]["pcs"][0]
        assert pc["hostname"] == "lab-pc-active-only"
        assert pc["online"] is True
        assert pc["cpu_level"] == "normal"
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_offline_status_calculation(test_db_session, mock_viewer_user):
    """TEST-LAB-07: Evaluates offline status calculation when heartbeat exceeds threshold."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        now = datetime.now(timezone.utc)
        offline_host = Host(
            hostname="lab-pc-dead-only",
            environment="lab-offline-test",
            region="lab-1",
            source_type="REAL_AGENT",
            is_active=True,
        )
        test_db_session.add(offline_host)
        test_db_session.commit()

        # offline_host reported 180 seconds ago (> 90s threshold)
        m_offline = Metric(
            host_id=offline_host.id,
            timestamp=now - timedelta(seconds=180),
            cpu_percent=10.0,
            memory_percent=40.0,
            disk_percent=30.0,
        )
        test_db_session.add(m_offline)
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab-offline-test&offline_after_seconds=90")
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["total_pcs"] == 1
        assert data["totals"]["online"] == 0
        assert data["totals"]["offline"] == 1

        pc = data["rooms"][0]["pcs"][0]
        assert pc["hostname"] == "lab-pc-dead-only"
        assert pc["online"] is False
        assert pc["cpu_level"] == "offline"
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)



def test_lab_never_seen_host(test_db_session, mock_viewer_user):
    """TEST-LAB-08: Lab host with zero recorded metrics renders safely with offline status."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        ghost_host = Host(
            hostname="lab-ghost-node",
            environment="lab-ghost-test",
            region="lab-ghost-room",
            source_type="REAL_AGENT",
            is_active=True,
        )
        test_db_session.add(ghost_host)
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab-ghost-test")
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["total_pcs"] == 1
        assert data["totals"]["online"] == 0
        assert data["totals"]["offline"] == 1
        assert data["totals"]["avg_cpu"] is None

        pc = data["rooms"][0]["pcs"][0]
        assert pc["hostname"] == "lab-ghost-node"
        assert pc["online"] is False
        assert pc["last_seen"] is None
        assert pc["cpu_percent"] is None
        assert pc["cpu_level"] == "offline"
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_cpu_severity_boundaries(test_db_session, mock_viewer_user):
    """TEST-LAB-09: Validates precise threshold classification boundaries (<80, 80-94.9, >=95)."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        now = datetime.now(timezone.utc)
        cases = [
            ("pc-normal-79", 79.9, "normal"),
            ("pc-warning-80", 80.0, "warning"),
            ("pc-warning-94", 94.9, "warning"),
            ("pc-high-95", 95.0, "high"),
            ("pc-high-99", 99.1, "high"),
        ]


        for name, cpu, expected_level in cases:
            h = Host(
                hostname=name,
                environment="lab-cpu-boundary",
                region="lab-bench",
                source_type="REAL_AGENT",
                is_active=True,
            )
            test_db_session.add(h)
            test_db_session.flush()
            m = Metric(
                host_id=h.id,
                timestamp=now - timedelta(seconds=10),
                cpu_percent=cpu,
                memory_percent=40.0,
                disk_percent=20.0,
            )
            test_db_session.add(m)
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab-cpu-boundary")
        assert res.status_code == 200
        pcs = {pc["hostname"]: pc for room in res.json()["rooms"] for pc in room["pcs"]}

        for name, _, expected_level in cases:
            assert pcs[name]["cpu_level"] == expected_level, f"Failed boundary classification for {name}"
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_room_grouping_and_sorting(test_db_session, mock_viewer_user):
    """TEST-LAB-10: Groups PCs by room (region) and returns rooms sorted alphabetically."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        now = datetime.now(timezone.utc)
        h1 = Host(hostname="pc-z", environment="lab-room-test", region="room-b", source_type="REAL_AGENT", is_active=True)
        h2 = Host(hostname="pc-a", environment="lab-room-test", region="room-b", source_type="REAL_AGENT", is_active=True)
        h3 = Host(hostname="pc-1", environment="lab-room-test", region="room-a", source_type="REAL_AGENT", is_active=True)
        test_db_session.add_all([h1, h2, h3])
        test_db_session.flush()

        test_db_session.add_all([
            Metric(host_id=h1.id, timestamp=now, cpu_percent=30.0, memory_percent=40.0, disk_percent=50.0),
            Metric(host_id=h2.id, timestamp=now, cpu_percent=50.0, memory_percent=40.0, disk_percent=50.0),
            Metric(host_id=h3.id, timestamp=now, cpu_percent=70.0, memory_percent=40.0, disk_percent=50.0),
        ])
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab-room-test")
        assert res.status_code == 200
        rooms = res.json()["rooms"]

        # Rooms sorted alphabetically: room-a, then room-b
        assert len(rooms) == 2
        assert rooms[0]["room"] == "room-a"
        assert rooms[1]["room"] == "room-b"

        # Within room-b, PCs sorted alphabetically by hostname: pc-a, then pc-z
        room_b_hostnames = [pc["hostname"] for pc in rooms[1]["pcs"]]
        assert room_b_hostnames == ["pc-a", "pc-z"]
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_room_avg_cpu_calculation(test_db_session, mock_viewer_user):
    """TEST-LAB-11: Room avg_cpu correctly computes the arithmetic mean of online machines only."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        now = datetime.now(timezone.utc)
        h_on1 = Host(hostname="pc-on-1", environment="lab-avg-test", region="lab-math", source_type="REAL_AGENT", is_active=True)
        h_on2 = Host(hostname="pc-on-2", environment="lab-avg-test", region="lab-math", source_type="REAL_AGENT", is_active=True)
        h_off = Host(hostname="pc-off", environment="lab-avg-test", region="lab-math", source_type="REAL_AGENT", is_active=True)
        test_db_session.add_all([h_on1, h_on2, h_off])
        test_db_session.flush()

        # Online PCs: 40.0% and 60.0% -> expected avg = 50.0%
        # Offline PC: 99.0% -> should be completely ignored in avg_cpu
        test_db_session.add_all([
            Metric(host_id=h_on1.id, timestamp=now - timedelta(seconds=10), cpu_percent=40.0, memory_percent=30.0, disk_percent=20.0),
            Metric(host_id=h_on2.id, timestamp=now - timedelta(seconds=10), cpu_percent=60.0, memory_percent=30.0, disk_percent=20.0),
            Metric(host_id=h_off.id, timestamp=now - timedelta(seconds=200), cpu_percent=99.0, memory_percent=30.0, disk_percent=20.0),
        ])
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab-avg-test&offline_after_seconds=90")
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["avg_cpu"] == 50.0
        assert data["rooms"][0]["avg_cpu"] == 50.0
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_busiest_pcs_ranking(test_db_session, mock_viewer_user):
    """TEST-LAB-12: busiest_pcs returns top 5 online machines sorted descending by CPU."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        now = datetime.now(timezone.utc)
        # Create 7 hosts with different loads
        cpu_values = [15.0, 85.0, 45.0, 95.0, 65.0, 75.0, 55.0]
        for idx, cpu in enumerate(cpu_values):
            h = Host(hostname=f"busiest-pc-{idx}", environment="lab-busy-test", region="lab-triage", source_type="REAL_AGENT", is_active=True)
            test_db_session.add(h)
            test_db_session.flush()
            test_db_session.add(Metric(host_id=h.id, timestamp=now - timedelta(seconds=5), cpu_percent=cpu, memory_percent=50.0, disk_percent=50.0))
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab-busy-test")
        assert res.status_code == 200
        busiest = res.json()["busiest_pcs"]
        assert len(busiest) == 5
        busiest_cpus = [p["cpu_percent"] for p in busiest]
        assert busiest_cpus == [95.0, 85.0, 75.0, 65.0, 55.0]
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_duplicate_timestamps_guard(test_db_session, mock_viewer_user):
    """TEST-LAB-13: Deduplicates multiple metric records with identical timestamps for a single host."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        dup_ts = datetime.now(timezone.utc)
        h = Host(hostname="pc-duplicate-ts", environment="lab-dup-test", region="lab-1", source_type="REAL_AGENT", is_active=True)
        test_db_session.add(h)
        test_db_session.flush()

        # Insert 2 metrics with identical max timestamp
        m1 = Metric(host_id=h.id, timestamp=dup_ts, cpu_percent=50.0, memory_percent=50.0, disk_percent=50.0)
        m2 = Metric(host_id=h.id, timestamp=dup_ts, cpu_percent=50.0, memory_percent=50.0, disk_percent=50.0)
        test_db_session.add_all([m1, m2])
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab-dup-test")
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["total_pcs"] == 1
        assert len(data["rooms"][0]["pcs"]) == 1
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_inactive_host_exclusion(test_db_session, mock_viewer_user):
    """TEST-LAB-14: Inactive hosts (is_active=False) are completely excluded from lab summary."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        now = datetime.now(timezone.utc)
        h_inactive = Host(hostname="pc-decommissioned", environment="lab-inact-test", region="lab-1", source_type="REAL_AGENT", is_active=False)
        test_db_session.add(h_inactive)
        test_db_session.flush()
        test_db_session.add(Metric(host_id=h_inactive.id, timestamp=now, cpu_percent=90.0, memory_percent=90.0, disk_percent=90.0))
        test_db_session.commit()

        res = client.get("/api/v1/lab/summary?environment=lab-inact-test")
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["total_pcs"] == 0
        assert len(data["rooms"]) == 0
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_agent_telemetry_ingestion(test_db_session, mock_viewer_user):
    """TEST-LAB-15: Submitting REAL_AGENT telemetry via POST /api/v1/metrics updates lab summary."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        # Submit metric with valid agent ingestion secret
        payload = {
            "hostname": "physical-lab-node-01",
            "ip_address": "192.168.1.101",
            "cpu_percent": 68.5,
            "memory_percent": 42.0,
            "disk_percent": 35.0,
            "network_sent_mb": 1.2,
            "network_received_mb": 4.5,
            "environment": "lab-e2e-live",
            "provider": "college-lab",
            "region": "lab-3",
            "source_type": "REAL_AGENT",
        }
        ingest_res = client.post(
            "/api/v1/metrics",
            json=payload,
            headers={"X-Agent-Key": "test-agent-key-fixture-secret-2026"},
        )
        assert ingest_res.status_code == 201

        # Verify summary reflects the ingested workstation
        summary_res = client.get("/api/v1/lab/summary?environment=lab-e2e-live")
        assert summary_res.status_code == 200
        data = summary_res.json()
        assert data["totals"]["total_pcs"] == 1
        assert data["totals"]["online"] == 1
        pc = data["rooms"][0]["pcs"][0]
        assert pc["hostname"] == "physical-lab-node-01"
        assert pc["room"] == "lab-3"
        assert pc["cpu_percent"] == 68.5
        assert pc["cpu_level"] == "normal"
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_provenance_violation_rejection():
    """TEST-LAB-16: Provenance guard rejects unvetted or mismatched source_type with 403."""
    bad_payload = {
        "hostname": "fake-pc-01",
        "cpu_percent": 50.0,
        "memory_percent": 50.0,
        "disk_percent": 50.0,
        "environment": "lab",
        "region": "lab-1",
        "source_type": "UNKNOWN",
    }
    res = client.post(
        "/api/v1/metrics",
        json=bad_payload,
        headers={"X-Agent-Key": "test-agent-key-fixture-secret-2026"},
    )
    assert res.status_code == 403
    assert "provenance" in res.json()["detail"].lower()


def test_lab_parameter_validation_bounds(mock_viewer_user):
    """TEST-LAB-17: offline_after_seconds enforces ge=10, le=3600 (returns 422 if invalid)."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        # Lower bound violation (5 < 10)
        res_low = client.get("/api/v1/lab/summary?offline_after_seconds=5")
        assert res_low.status_code == 422

        # Upper bound violation (5000 > 3600)
        res_high = client.get("/api/v1/lab/summary?offline_after_seconds=5000")
        assert res_high.status_code == 422

        # Valid boundaries (10 and 3600)
        res_10 = client.get("/api/v1/lab/summary?offline_after_seconds=10")
        assert res_10.status_code == 200
        res_3600 = client.get("/api/v1/lab/summary?offline_after_seconds=3600")
        assert res_3600.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)


def test_lab_query_performance_and_scaling(test_db_session, mock_viewer_user):
    """TEST-LAB-18: Validates scaling across multiple hosts and multi-room topologies."""
    app.dependency_overrides[get_current_viewer] = lambda: mock_viewer_user
    try:
        now = datetime.now(timezone.utc)
        # Create 20 synthetic lab PCs across 4 rooms
        for room_idx in range(1, 5):
            for pc_idx in range(1, 6):
                h = Host(
                    hostname=f"room{room_idx}-pc{pc_idx:02d}",
                    environment="lab-scale-test",
                    region=f"lab-room-{room_idx}",
                    source_type="REAL_AGENT",
                    is_active=True,
                )
                test_db_session.add(h)
                test_db_session.flush()
                test_db_session.add(
                    Metric(
                        host_id=h.id,
                        timestamp=now - timedelta(seconds=pc_idx * 5),
                        cpu_percent=float(room_idx * 15 + pc_idx * 4),
                        memory_percent=55.0,
                        disk_percent=30.0,
                    )
                )
        test_db_session.commit()

        start_time = datetime.now(timezone.utc)
        res = client.get("/api/v1/lab/summary?environment=lab-scale-test")
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0

        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["total_pcs"] == 20
        assert data["totals"]["online"] == 20
        assert len(data["rooms"]) == 4
        # Assert fast query latency under in-memory SQLite (< 100ms)
        assert duration_ms < 100.0, f"Query took too long: {duration_ms:.2f}ms"
    finally:
        app.dependency_overrides.pop(get_current_viewer, None)
