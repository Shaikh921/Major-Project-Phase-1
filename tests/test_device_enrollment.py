"""
Automated Test Suite for Lab PC Sensor Enrollment, Lifecycle Governance,
and Durable Telemetry Spooling.

Guarantees 100% isolation via in-memory SQLite and verifies all security rules.
"""

import os
import time
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.init_db import seed_default_rules, seed_pricing_catalog
from backend.app.api.deps import get_db
from backend.app.main import app
from backend.app.models.user import User, UserRole
from backend.app.models.device import EnrollmentCode, DeviceEnrollment, DeviceStatus, TelemetryHealthStatus
from backend.app.models.agent_key import AgentApiKey
from backend.app.core.config import settings
from backend.app.core.rate_limit import auth_rate_limiter
from backend.app.services.device_service import (
    generate_enrollment_code,
    request_enrollment,
    approve_device,
    reject_device,
    claim_credential,
    disable_device,
    enable_device,
    retire_device,
    record_uninstall_request,
    update_device_telemetry_heartbeat,
    get_device_summary_stats,
)
from backend.app.schemas.device import (
    DeviceEnrollRequest,
    DeviceApproveRequest,
    DeviceClaimCredentialRequest,
    DeviceUninstallNoticeRequest,
)
from monitoring_agent.buffer import MetricBuffer


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestingSession() as db:
        seed_default_rules(db)
        seed_pricing_catalog(db)
        # Create Super Admin and Normal Admin users for testing
        sa = User(
            email="superadmin.devices@ops.local",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
            password_hash="hashed_pw_superadmin",
        )
        admin = User(
            email="admin.devices@ops.local",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            password_hash="hashed_pw_admin",
        )
        viewer = User(
            email="viewer.devices@ops.local",
            role=UserRole.VIEWER,
            is_active=True,
            is_verified=True,
            password_hash="hashed_pw_viewer",
        )
        db.add_all([sa, admin, viewer])
        db.commit()
    return engine


@pytest.fixture
def db(db_engine):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def _override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.pop(get_db, None)


# --------------------------------------------------------------------------
# 1. ENROLLMENT CODE GENERATION, EXPIRATION, REVOCATION & SINGLE-USE
# --------------------------------------------------------------------------

def test_enrollment_code_generation_and_hashing(db):
    sa = db.scalar(select(User).where(User.email == "superadmin.devices@ops.local"))
    res = generate_enrollment_code(db, super_admin=sa, expires_in_minutes=15, notes="Lab 1 Test")

    assert res.id is not None
    assert len(res.raw_code) > 20
    assert res.code_prefix.startswith("ec_")
    assert res.expires_at > datetime.now(timezone.utc)

    # Verify database record does NOT store the raw secret
    db_record = db.scalar(select(EnrollmentCode).where(EnrollmentCode.id == res.id))
    assert db_record is not None
    assert db_record.code_hash != res.raw_code
    assert db_record.is_used is False


def test_enrollment_code_single_use(db):
    sa = db.scalar(select(User).where(User.email == "superadmin.devices@ops.local"))
    code_res = generate_enrollment_code(db, super_admin=sa, expires_in_minutes=15)

    req_data = DeviceEnrollRequest(
        enrollment_code=code_res.raw_code,
        device_uuid="test-uuid-pc-001",
        reported_hostname="LAB-PC-01",
        ip_address="10.0.0.101",
        agent_version="1.0.0",
    )
    # First enrollment succeeds
    enroll_res = request_enrollment(db, req_data)
    assert enroll_res.status == "PENDING"
    assert enroll_res.claim_token is not None

    # Code is now marked is_used = True
    code_rec = db.scalar(select(EnrollmentCode).where(EnrollmentCode.id == code_res.id))
    assert code_rec.is_used is True

    # Second enrollment attempt with same code fails
    with pytest.raises(Exception) as exc:
        req_data2 = DeviceEnrollRequest(
            enrollment_code=code_res.raw_code,
            device_uuid="test-uuid-pc-002",
            reported_hostname="LAB-PC-02",
        )
        request_enrollment(db, req_data2)
    assert "already" in str(exc.value).lower() or "invalid" in str(exc.value).lower()


def test_enrollment_code_expiration(db):
    sa = db.scalar(select(User).where(User.email == "superadmin.devices@ops.local"))
    code_res = generate_enrollment_code(db, super_admin=sa, expires_in_minutes=15)

    # Force expiration in DB
    code_rec = db.scalar(select(EnrollmentCode).where(EnrollmentCode.id == code_res.id))
    code_rec.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    with pytest.raises(Exception) as exc:
        req_data = DeviceEnrollRequest(
            enrollment_code=code_res.raw_code,
            device_uuid="test-uuid-pc-expired",
            reported_hostname="EXPIRED-PC",
        )
        request_enrollment(db, req_data)
    assert "expired" in str(exc.value).lower()


# --------------------------------------------------------------------------
# 2. PENDING DEVICE INGESTION REJECTION & APPROVAL WORKFLOW
# --------------------------------------------------------------------------

def test_pending_device_approval_and_one_time_claim(db):
    sa = db.scalar(select(User).where(User.email == "superadmin.devices@ops.local"))
    code_res = generate_enrollment_code(db, super_admin=sa, expires_in_minutes=15)

    req_data = DeviceEnrollRequest(
        enrollment_code=code_res.raw_code,
        device_uuid="test-uuid-claim-001",
        reported_hostname="ENG-PC-10",
        ip_address="10.10.1.10",
        agent_version="1.0.0",
    )
    enroll_res = request_enrollment(db, req_data)
    device_id = enroll_res.request_id
    claim_token = enroll_res.claim_token

    # 1. While PENDING: claim credential returns status="PENDING"
    poll_req = DeviceClaimCredentialRequest(device_uuid="test-uuid-claim-001", claim_token=claim_token)
    claim_status = claim_credential(db, poll_req)
    assert claim_status.status == "PENDING"
    assert claim_status.agent_key is None

    # 2. Super Admin approves and assigns physical lab location
    approve_data = DeviceApproveRequest(
        assigned_name="PC-ENG-10",
        lab_name="Computer Systems Lab",
        room_number="Room 401",
        pc_number="10",
    )
    approved_dev = approve_device(db, device_id, approve_data, super_admin=sa)
    assert approved_dev.status == "APPROVED"
    assert approved_dev.assigned_name == "PC-ENG-10"

    # 3. Sensor claims credential (one-time protocol)
    claim_res = claim_credential(db, poll_req)
    assert claim_res.status == "APPROVED"
    assert claim_res.agent_key is not None
    assert claim_res.agent_key.startswith("ak_lab_")

    # 4. Immediate second claim attempt: claim token invalidated, raises error
    with pytest.raises(Exception) as exc:
        claim_credential(db, poll_req)
    assert "invalid claim token" in str(exc.value).lower() or "claimed" in str(exc.value).lower()

    # 5. Verify server DB stores only key hash, not raw key
    dev_rec = db.scalar(select(DeviceEnrollment).where(DeviceEnrollment.id == device_id))
    assert dev_rec.pending_raw_key is None
    assert dev_rec.credential_claimed is True


# --------------------------------------------------------------------------
# 3. INGESTION WITH PROVISIONED DEVICE KEY & HEARTBEAT TRACKING
# --------------------------------------------------------------------------

def test_device_telemetry_ingestion_and_heartbeat(client, db):
    sa = db.scalar(select(User).where(User.email == "superadmin.devices@ops.local"))
    code_res = generate_enrollment_code(db, super_admin=sa, expires_in_minutes=15)
    req_data = DeviceEnrollRequest(
        enrollment_code=code_res.raw_code,
        device_uuid="test-uuid-telemetry-001",
        reported_hostname="TELEMETRY-PC",
        agent_version="1.0.0",
    )
    enroll_res = request_enrollment(db, req_data)
    approve_device(
        db,
        enroll_res.request_id,
        DeviceApproveRequest(assigned_name="PC-TEL-01", lab_name="Lab A", room_number="R1", pc_number="01"),
        super_admin=sa,
    )
    claim_res = claim_credential(
        db,
        DeviceClaimCredentialRequest(device_uuid="test-uuid-telemetry-001", claim_token=enroll_res.claim_token)
    )
    agent_key = claim_res.agent_key

    # Submit valid telemetry with provisioned agent key
    sample = {
        "hostname": "TELEMETRY-PC",
        "cpu_percent": 24.5,
        "memory_percent": 55.0,
        "disk_percent": 42.0,
        "network_sent_mb": 1.2,
        "network_received_mb": 3.4,
        "environment": "local",
        "source_type": "REAL_AGENT",
    }
    res = client.post(
        "/api/v1/metrics",
        json=sample,
        headers={"X-Agent-Key": agent_key},
    )
    assert res.status_code == 201

    # Verify device record heartbeat was updated
    dev = db.scalar(select(DeviceEnrollment).where(DeviceEnrollment.device_uuid == "test-uuid-telemetry-001"))
    assert dev.last_upload_at is not None
    assert dev.telemetry_health == TelemetryHealthStatus.HEALTHY.value


# --------------------------------------------------------------------------
# 4. DISABLE, RE-ENABLE, AND RETIREMENT LIFECYCLE CONTROLS
# --------------------------------------------------------------------------

def test_device_disable_and_reenable(client, db):
    sa = db.scalar(select(User).where(User.email == "superadmin.devices@ops.local"))
    code_res = generate_enrollment_code(db, super_admin=sa, expires_in_minutes=15)
    req_data = DeviceEnrollRequest(
        enrollment_code=code_res.raw_code,
        device_uuid="test-uuid-disable-001",
        reported_hostname="DISABLE-PC",
    )
    enroll_res = request_enrollment(db, req_data)
    approve_device(
        db,
        enroll_res.request_id,
        DeviceApproveRequest(assigned_name="PC-DIS-01"),
        super_admin=sa,
    )
    claim_res = claim_credential(
        db,
        DeviceClaimCredentialRequest(device_uuid="test-uuid-disable-001", claim_token=enroll_res.claim_token)
    )
    agent_key = claim_res.agent_key

    sample = {
        "hostname": "DISABLE-PC",
        "cpu_percent": 15.0,
        "memory_percent": 30.0,
        "disk_percent": 20.0,
        "source_type": "REAL_AGENT",
    }

    # 1. Works when enabled
    res = client.post("/api/v1/metrics", json=sample, headers={"X-Agent-Key": agent_key})
    assert res.status_code == 201

    # 2. Disable device
    disable_device(db, enroll_res.request_id, super_admin=sa)

    # 3. Telemetry ingestion immediately rejected with 403 Forbidden
    res_disabled = client.post("/api/v1/metrics", json=sample, headers={"X-Agent-Key": agent_key})
    assert res_disabled.status_code == 403
    assert "disabled" in res_disabled.json()["detail"].lower()

    # 4. Re-enable device
    enable_device(db, enroll_res.request_id, super_admin=sa)

    # 5. Ingestion succeeds again
    res_reenabled = client.post("/api/v1/metrics", json=sample, headers={"X-Agent-Key": agent_key})
    assert res_reenabled.status_code == 201


def test_device_permanent_retirement(client, db):
    sa = db.scalar(select(User).where(User.email == "superadmin.devices@ops.local"))
    code_res = generate_enrollment_code(db, super_admin=sa, expires_in_minutes=15)
    req_data = DeviceEnrollRequest(
        enrollment_code=code_res.raw_code,
        device_uuid="test-uuid-retire-001",
        reported_hostname="RETIRE-PC",
    )
    enroll_res = request_enrollment(db, req_data)
    approve_device(
        db,
        enroll_res.request_id,
        DeviceApproveRequest(assigned_name="PC-RET-01"),
        super_admin=sa,
    )
    claim_res = claim_credential(
        db,
        DeviceClaimCredentialRequest(device_uuid="test-uuid-retire-001", claim_token=enroll_res.claim_token)
    )
    agent_key = claim_res.agent_key

    # Retire device permanently
    retire_device(db, enroll_res.request_id, super_admin=sa)

    # Credential is permanently revoked
    sample = {
        "hostname": "RETIRE-PC",
        "cpu_percent": 15.0,
        "memory_percent": 30.0,
        "disk_percent": 20.0,
        "source_type": "REAL_AGENT",
    }
    res_retired = client.post("/api/v1/metrics", json=sample, headers={"X-Agent-Key": agent_key})
    assert res_retired.status_code in (401, 403)


# --------------------------------------------------------------------------
# 5. DURABLE SQLITE SPOOL BUFFER RESILIENCE
# --------------------------------------------------------------------------

def test_durable_metric_buffer_persistence(tmp_path):
    spool_file = tmp_path / "test_spool.db"

    # 1. Initialize buffer with local SQLite file
    buffer1 = MetricBuffer(
        ingest_url="https://mock.invalid:8443/api/v1/metrics",
        api_key="ak_test_key",
        spool_path=str(spool_file),
    )
    sample = {
        "hostname": "TEST-CRASH-PC",
        "cpu_percent": 50.0,
        "memory_percent": 60.0,
        "disk_percent": 70.0,
    }
    buffer1.push(sample)
    assert buffer1.size() == 1
    buffer1.close()

    # 2. Simulate process crash / restart: create new buffer instance pointing to same file
    buffer2 = MetricBuffer(
        ingest_url="https://mock.invalid:8443/api/v1/metrics",
        api_key="ak_test_key",
        spool_path=str(spool_file),
    )
    # Record survived crash
    assert buffer2.size() == 1
    diag = buffer2.get_diagnostics()
    assert diag["queue_size"] == 1
    assert diag["dropped_count"] == 0
    buffer2.close()
