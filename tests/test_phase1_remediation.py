"""
Phase 1 Security & Reliability Remediation Test Suite.

Verifies all four Phase 1 findings:
- SEC-01: Credential and documentation cleanup (no hard-coded production secrets).
- REL-01: Durable telemetry queue capacity calculation, 24h retention, overflow policies, and observable diagnostics.
- REL-02: Idempotent telemetry ingestion, deduplication, retry safety, and 409 conflict detection.
- SEC-02: Rate limiting on public sensor enrollment and credential claim endpoints.

Strictly runs against isolated in-memory test databases (StaticPool) and temporary spool files.
"""

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.init_db import seed_default_rules, seed_pricing_catalog
from backend.app.api.deps import get_db
from backend.app.main import app
from backend.app.models.user import User, UserRole
from backend.app.models.host import Host
from backend.app.models.metric import Metric, IngestedBatch
from backend.app.models.agent_key import AgentApiKey
import threading
import concurrent.futures
from backend.app.database.connection import configure_sqlite_pragmas
from backend.app.core.rate_limit import auth_rate_limiter, get_client_ip, SlidingWindowRateLimiter
from backend.app.core.security import hash_password
from backend.app.schemas.metric import MetricCreate, MetricBatchCreate
from backend.app.services.metric_service import (
    ingest_metric,
    ingest_metrics_batch,
    compute_metric_payload_hash,
    cleanup_expired_idempotency_records,
)
from backend.app.services.device_service import (
    generate_enrollment_code,
    request_enrollment,
    approve_device,
    claim_credential,
)
from backend.app.schemas.device import (
    DeviceEnrollRequest,
    DeviceClaimCredentialRequest,
    DeviceApproveRequest,
)
from monitoring_agent.buffer import MetricBuffer, calculate_queue_capacity


@pytest.fixture(scope="module")
def remediation_client():
    """Provides isolated FastAPI test client with in-memory database."""
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
        # Seed Super Admin
        sa = User(
            email="remediation.superadmin@example.invalid",
            password_hash=hash_password("SuperSecureFixturePass2026!"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
        )
        db.add(sa)
        db.commit()

    def override_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==============================================================================
# SEC-01: Credential and Documentation Tests
# ==============================================================================

def test_sec01_no_production_credentials_in_documentation():
    """SEC-01: Verifies that documentation files use nonfunctional placeholders."""
    doc_paths = [
        "README_SENSOR.md",
        "docs/lab-monitoring/IMPLEMENTATION_REPORT.md",
        "docs/lab-monitoring/ENROLLMENT_AND_DEVICE_LIFECYCLE.md",
    ]
    forbidden_strings = [
        "SuperAdminSecret2026!",
        "superadmin@ops.local",
    ]
    for rel_path in doc_paths:
        abs_path = os.path.join(os.path.dirname(__file__), "..", rel_path)
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            for forbidden in forbidden_strings:
                assert forbidden not in content, (
                    f"SEC-01 Violation: Found forbidden credential string '{forbidden}' in {rel_path}"
                )


# ==============================================================================
# REL-01: Durable Telemetry Queue Retention & Capacity Tests
# ==============================================================================

def test_rel01_queue_capacity_calculation():
    """REL-01: Verifies mathematical capacity calculation across polling intervals."""
    # 5s polling: 720 samples/hr * 24h = 17,280 samples + 25% safety = 21,600 samples
    cap_5s = calculate_queue_capacity(poll_interval=5.0, max_age_hours=24.0, safety_margin=0.25)
    assert cap_5s == 21600

    # 15s polling: 240 samples/hr * 24h = 5,760 samples + 25% safety = 7,200 samples
    cap_15s = calculate_queue_capacity(poll_interval=15.0, max_age_hours=24.0, safety_margin=0.25)
    assert cap_15s == 7200

    # 1s polling: 3,600 samples/hr * 24h = 86,400 samples + 25% safety = 108,000 samples
    # But 50MB disk quota (at 512 bytes/sample) caps at ~102,400 samples
    cap_1s = calculate_queue_capacity(poll_interval=1.0, max_age_hours=24.0, max_disk_mb=50.0)
    assert cap_1s == 102400  # Strictly bounded by disk quota


def test_rel01_overflow_preserve_queued_policy(tmp_path):
    """REL-01: Verifies that preserve_queued overflow policy keeps existing records."""
    spool = tmp_path / "overflow_test.db"
    buf = MetricBuffer(
        ingest_url="https://mock.invalid:8443/api/v1/metrics",
        max_size=3,
        overflow_policy="preserve_queued",
        spool_path=str(spool),
    )

    # Push 3 initial items
    assert buf.push({"idx": 1, "data": "initial-1"}) is True
    assert buf.push({"idx": 2, "data": "initial-2"}) is True
    assert buf.push({"idx": 3, "data": "initial-3"}) is True
    assert buf.size() == 3

    # Push 4th item -> should be dropped under preserve_queued to protect historical backlog
    pushed = buf.push({"idx": 4, "data": "excess"})
    assert pushed is False
    assert buf.size() == 3

    diag = buf.get_diagnostics()
    assert diag["dropped_count"] == 1
    assert diag["last_overflow_reason"] == "max_size_reached"
    assert diag["last_overflow_at"] is not None

    buf.close()


def test_rel01_age_based_expiration(tmp_path):
    """REL-01: Verifies observable record expiration when age exceeds max_age_hours."""
    spool = tmp_path / "exp_test.db"
    # Set retention to 1 hour
    buf = MetricBuffer(
        ingest_url="https://mock.invalid:8443/api/v1/metrics",
        max_age_hours=1.0,
        spool_path=str(spool),
    )

    now = time.time()
    # Insert an artificially aged record (2 hours old) directly into SQLite
    with buf._lock:
        buf._conn.execute(
            "INSERT INTO spool_queue (created_at, payload_json) VALUES (?, ?);",
            (now - 7200, json.dumps({"stale": True})),
        )
        buf._conn.commit()

    assert buf.size() == 1

    # Pushing a new sample triggers expiration pass
    buf.push({"fresh": True})

    diag = buf.get_diagnostics()
    assert diag["expired_count"] == 1
    assert buf.size() == 1  # Only the fresh sample remains
    buf.close()


# ==============================================================================
# REL-02: Idempotent Ingestion & Safe Retries Tests
# ==============================================================================

def test_rel02_batch_idempotency_exact_retry(remediation_client):
    """REL-02: Verifies that retrying an exact batch does not create duplicate metric records."""
    headers = {"X-Agent-Key": "test-agent-key-fixture-secret-2026"}
    batch_id = f"batch_test_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "batch_id": batch_id,
        "metrics": [
            {
                "hostname": "IDEMPOTENT-HOST-01",
                "cpu_percent": 45.0,
                "memory_percent": 55.0,
                "disk_percent": 65.0,
                "timestamp": now_iso,
                "source_type": "REAL_AGENT",
            },
            {
                "hostname": "IDEMPOTENT-HOST-01",
                "cpu_percent": 48.0,
                "memory_percent": 56.0,
                "disk_percent": 65.0,
                "timestamp": now_iso,
                "source_type": "REAL_AGENT",
            },
        ],
    }

    # 1. First submission -> 201 Created
    res1 = remediation_client.post("/api/v1/metrics", json=payload, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["processed_samples"] == 2
    assert data1.get("is_duplicate") is False

    # 2. Resubmit exact same batch (lost ACK simulation) -> 201 Created with is_duplicate: True
    res2 = remediation_client.post("/api/v1/metrics", json=payload, headers=headers)
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["batch_id"] == batch_id
    assert data2.get("is_duplicate") is True
    assert data2["processed_samples"] == 2


def test_rel02_batch_payload_conflict_rejection(remediation_client):
    """REL-02: Verifies that reusing the same batch_id with different payload content returns HTTP 409 Conflict."""
    headers = {"X-Agent-Key": "test-agent-key-fixture-secret-2026"}
    batch_id = f"batch_conflict_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    payload_initial = {
        "batch_id": batch_id,
        "metrics": [
            {
                "hostname": "CONFLICT-HOST-01",
                "cpu_percent": 20.0,
                "memory_percent": 30.0,
                "disk_percent": 40.0,
                "timestamp": now_iso,
                "source_type": "REAL_AGENT",
            }
        ],
    }

    # 1. First submission succeeds
    res1 = remediation_client.post("/api/v1/metrics", json=payload_initial, headers=headers)
    assert res1.status_code == 201

    # 2. Resubmit same batch_id with altered metric payload
    payload_altered = {
        "batch_id": batch_id,
        "metrics": [
            {
                "hostname": "CONFLICT-HOST-01",
                "cpu_percent": 99.0,  # Altered CPU value!
                "memory_percent": 30.0,
                "disk_percent": 40.0,
                "timestamp": now_iso,
                "source_type": "REAL_AGENT",
            }
        ],
    }
    res2 = remediation_client.post("/api/v1/metrics", json=payload_altered, headers=headers)
    assert res2.status_code == 409
    assert "different telemetry payload" in res2.json()["detail"]


def test_rel02_agent_buffer_retains_batch_id_on_failure(tmp_path):
    """REL-02: Verifies that agent MetricBuffer preserves stable batch_id across retry attempts."""
    spool = tmp_path / "retry_batch.db"
    buf = MetricBuffer(
        ingest_url="https://mock.invalid:8443/api/v1/metrics",
        spool_path=str(spool),
    )
    buf.push({"cpu_percent": 42.0, "hostname": "RETRY-PC"})

    with patch("requests.post") as mock_post:
        # First attempt: network error
        mock_post.side_effect = Exception("Network timeout")
        assert buf.flush() is False

        # Verify batch_id was assigned and persisted in SQLite spool
        with buf._lock:
            row = buf._conn.execute("SELECT batch_id FROM spool_queue LIMIT 1;").fetchone()
            first_batch_id = row["batch_id"]
            assert first_batch_id is not None
            assert first_batch_id.startswith("batch_")

        # Second attempt: network succeeds
        mock_post.side_effect = None
        mock_post.return_value = MagicMock(status_code=201)

        assert buf.flush() is True
        # Assert the request sent that exact same batch_id
        sent_payload = mock_post.call_args[1]["json"]
        assert sent_payload["batch_id"] == first_batch_id
        assert buf.size() == 0

    buf.close()


# ==============================================================================
# SEC-02: Rate Limiting on Public Sensor Endpoints Tests
# ==============================================================================

def test_sec02_device_enrollment_rate_limit(remediation_client):
    """SEC-02: Verifies that POST /api/v1/devices/enroll enforces rate limits per client IP."""
    # Reset limiter history for testclient
    auth_rate_limiter.reset_for_key("device_enroll:testclient")

    enroll_payload = {
        "enrollment_code": "ec_nonexistent_rate_limit_test",
        "reported_hostname": "TEST-RATE-LIMIT-PC",
        "mac_address": "00:11:22:33:44:55",
        "device_uuid": str(uuid.uuid4()),
        "os_version": "Windows 11 Pro",
    }

    # First 10 requests are evaluated (they return 400 because code is invalid, but allowed past rate limiter)
    for _ in range(10):
        res = remediation_client.post("/api/v1/devices/enroll", json=enroll_payload)
        assert res.status_code != 429

    # 11th request triggers rate limiter -> 429 Too Many Requests
    res_limited = remediation_client.post("/api/v1/devices/enroll", json=enroll_payload)
    assert res_limited.status_code == 429
    assert "Retry-After" in res_limited.headers
    assert "Too many requests" in res_limited.json()["detail"]


def test_sec02_device_claim_rate_limit(remediation_client):
    """SEC-02: Verifies that POST /api/v1/devices/claim-credential enforces rate limits."""
    auth_rate_limiter.reset_for_key("device_claim:testclient")

    claim_payload = {
        "device_uuid": str(uuid.uuid4()),
        "claim_token": "ct_nonexistent_test_token",
    }

    # First 30 requests permitted past limiter
    for _ in range(30):
        res = remediation_client.post("/api/v1/devices/claim-credential", json=claim_payload)
        assert res.status_code != 429

    # 31st request triggers 429
    res_limited = remediation_client.post("/api/v1/devices/claim-credential", json=claim_payload)
    assert res_limited.status_code == 429
    assert "Retry-After" in res_limited.headers
    assert "Too many requests" in res_limited.json()["detail"]


# ==============================================================================
# AUD-01: Atomic Batch Ingestion Tests
# ==============================================================================

def test_aud01_atomic_batch_rollback_on_mid_batch_failure():
    """AUD-01: Verifies that a mid-batch failure rolls back ALL changes, leaving 0 metrics committed."""
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    batch_id = f"batch_atomic_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    host_name = "ATOMIC-FAIL-PC"

    batch_payload = MetricBatchCreate(
        batch_id=batch_id,
        metrics=[
            MetricCreate(hostname=host_name, cpu_percent=10.0, memory_percent=20.0, disk_percent=30.0, timestamp=now_iso, source_type="REAL_AGENT"),
            MetricCreate(hostname=host_name, cpu_percent=15.0, memory_percent=25.0, disk_percent=35.0, timestamp=now_iso, source_type="REAL_AGENT"),
            MetricCreate(hostname=host_name, cpu_percent=20.0, memory_percent=30.0, disk_percent=40.0, timestamp=now_iso, source_type="REAL_AGENT"),
        ],
    )

    call_count = 0
    from backend.app.services.metric_service import _persist_metric_record
    original_persist = _persist_metric_record

    def faulty_persist(db, metric_in, commit=True):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise RuntimeError("Simulated crash on sample 3")
        return original_persist(db, metric_in, commit=commit)

    with TestingSession() as db:
        with patch("backend.app.services.metric_service._persist_metric_record", side_effect=faulty_persist):
            with pytest.raises(RuntimeError, match="Simulated crash on sample 3"):
                ingest_metrics_batch(db, batch_payload)

        # 1. Assert transaction was completely rolled back: 0 metrics exist in database!
        metrics = list(db.scalars(select(Metric)).all())
        assert len(metrics) == 0, f"Expected 0 metrics after rollback, but found {len(metrics)}"

        # 2. Assert no idempotency record was created
        batch_rec = db.scalar(select(IngestedBatch).where(IngestedBatch.batch_id == batch_id))
        assert batch_rec is None

        # 3. Assert failed batch is now safely retryable and succeeds completely
        res_retry = ingest_metrics_batch(db, batch_payload)
        assert res_retry["status"] == "success"
        assert res_retry["processed_samples"] == 3
        assert res_retry["is_duplicate"] is False

        # Verify exactly 3 metric rows are committed
        metrics_after = list(db.scalars(select(Metric)).all())
        assert len(metrics_after) == 3

        # Exact retry returns cached duplicate success without inserting more metrics
        res_dup = ingest_metrics_batch(db, batch_payload)
        assert res_dup["is_duplicate"] is True
        assert len(list(db.scalars(select(Metric)).all())) == 3


def test_aud01_concurrent_duplicate_batch_ingestion(tmp_path):
    """AUD-01: Verifies that concurrent duplicate submissions produce one logical batch and no duplicate metrics."""
    db_file = tmp_path / "concurrent_batch_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    configure_sqlite_pragmas(engine, timeout_ms=5000)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    batch_id = f"batch_concurrent_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    unique_host = f"CONCURRENT-PC-{uuid.uuid4().hex[:6]}"

    payload = MetricBatchCreate(
        batch_id=batch_id,
        metrics=[
            MetricCreate(
                hostname=unique_host,
                cpu_percent=30.0,
                memory_percent=40.0,
                disk_percent=50.0,
                timestamp=now_iso,
                source_type="REAL_AGENT",
            ),
            MetricCreate(
                hostname=unique_host,
                cpu_percent=32.0,
                memory_percent=42.0,
                disk_percent=50.0,
                timestamp=now_iso,
                source_type="REAL_AGENT",
            ),
        ],
    )

    results = []
    errors = []

    def submit_task():
        try:
            with TestingSession() as session:
                res = ingest_metrics_batch(session, payload)
                return res
        except Exception as e:
            errors.append(str(e))
            raise

    # Submit simultaneously from 5 concurrent worker threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(submit_task) for _ in range(5)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    assert len(errors) == 0, f"Unexpected errors during concurrent submissions: {errors}"
    assert len(results) == 5

    # All threads receive success
    for body in results:
        assert body["status"] == "success"
        assert body["batch_id"] == batch_id
        assert body["processed_samples"] == 2

    # Exactly one thread executed the initial write; the other 4 returned duplicate success
    duplicates = [b["is_duplicate"] for b in results]
    assert duplicates.count(False) == 1
    assert duplicates.count(True) == 4

    # Verify database state: EXACTLY 2 metric rows exist (no duplicates!)
    with TestingSession() as verify_session:
        metrics = list(verify_session.scalars(select(Metric).join(Host).where(Host.hostname == unique_host)).all())
        assert len(metrics) == 2, f"Expected exactly 2 metric rows, but found {len(metrics)}"

        batches = list(verify_session.scalars(select(IngestedBatch).where(IngestedBatch.batch_id == batch_id)).all())
        assert len(batches) == 1, f"Expected exactly 1 IngestedBatch row, but found {len(batches)}"


def test_aud01_standalone_single_metric_ingestion_preserved():
    """AUD-01: Verifies that standalone single-metric ingestion retains its correct atomic behavior."""
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    metric_in = MetricCreate(
        hostname="STANDALONE-PC",
        cpu_percent=55.0,
        memory_percent=65.0,
        disk_percent=75.0,
        source_type="REAL_AGENT",
    )

    with TestingSession() as db:
        seed_default_rules(db)
        metric, alerts = ingest_metric(db, metric_in)
        assert metric.id is not None
        assert metric.cpu_percent == 55.0
        # Host is registered
        host = db.scalar(select(Host).where(Host.hostname == "STANDALONE-PC"))
        assert host is not None
        assert host.id == metric.host_id


# ==============================================================================
# AUD-02: Trusted Reverse Proxy Client Identity Tests
# ==============================================================================

def test_aud02_trusted_proxy_forwarded_client_identity(remediation_client):
    """AUD-02: Verifies that trusted proxy requests use verified forwarded IP and give independent buckets."""
    client_a_ip = "198.51.100.41"
    client_b_ip = "198.51.100.42"

    auth_rate_limiter.reset_for_key(f"device_enroll:{client_a_ip}")
    auth_rate_limiter.reset_for_key(f"device_enroll:{client_b_ip}")

    enroll_payload = {
        "enrollment_code": "ec_test_proxy_ip",
        "reported_hostname": "PROXY-TEST-PC",
        "mac_address": "00:11:22:33:44:55",
        "device_uuid": str(uuid.uuid4()),
        "os_version": "Windows 11 Pro",
    }

    # Client A: 10 requests allowed
    for _ in range(10):
        res = remediation_client.post(
            "/api/v1/devices/enroll",
            json=enroll_payload,
            headers={"X-Real-IP": client_a_ip},
        )
        assert res.status_code != 429

    # 11th request from Client A is rate limited (429)
    res_a_limited = remediation_client.post(
        "/api/v1/devices/enroll",
        json=enroll_payload,
        headers={"X-Real-IP": client_a_ip},
    )
    assert res_a_limited.status_code == 429
    assert "Retry-After" in res_a_limited.headers

    # Client B on a distinct IP is NOT blocked and has an independent bucket!
    res_b = remediation_client.post(
        "/api/v1/devices/enroll",
        json=enroll_payload,
        headers={"X-Real-IP": client_b_ip},
    )
    assert res_b.status_code != 429


def test_aud02_untrusted_peer_spoofing_rejected():
    """AUD-02: Verifies that an untrusted direct peer cannot spoof client identity."""
    class MockClient:
        host = "203.0.113.88"  # Untrusted external IP

    class MockRequest:
        client = MockClient()
        headers = {"x-real-ip": "10.0.0.1", "x-forwarded-for": "10.0.0.1"}

    # Untrusted peer's spoofed X-Real-IP is strictly ignored
    resolved_ip = get_client_ip(MockRequest(), trusted_proxies={"127.0.0.1", "testclient"})
    assert resolved_ip == "203.0.113.88"


def test_aud02_malformed_and_missing_headers_safe():
    """AUD-02: Verifies that malformed or missing headers from trusted proxy fail safely."""
    class MockTrustedClient:
        host = "127.0.0.1"

    # Malformed IP header
    class MockMalformedRequest:
        client = MockTrustedClient()
        headers = {"x-real-ip": "not_an_ip_address_or_injection"}

    resolved_malformed = get_client_ip(MockMalformedRequest(), trusted_proxies={"127.0.0.1"})
    assert resolved_malformed == "127.0.0.1"

    # Missing header
    class MockEmptyRequest:
        client = MockTrustedClient()
        headers = {}

    resolved_empty = get_client_ip(MockEmptyRequest(), trusted_proxies={"127.0.0.1"})
    assert resolved_empty == "127.0.0.1"


# ==============================================================================
# AUD-04: Rate Limiter Thread Synchronization Tests
# ==============================================================================

def test_aud04_rate_limiter_multithreaded_concurrency():
    """AUD-04: Verifies thread-safe atomic check-and-record state transitions under concurrent bursts."""
    limiter = SlidingWindowRateLimiter()
    test_key = f"concurrent_test_key_{uuid.uuid4().hex}"
    max_requests = 10
    window_seconds = 60

    allowed_count = 0
    rejected_count = 0

    def attempt_request():
        nonlocal allowed_count, rejected_count
        allowed, retry_after = limiter.check_rate_limit(test_key, max_requests, window_seconds)
        if allowed:
            allowed_count += 1
        else:
            rejected_count += 1

    # Launch 20 concurrent threads attempting requests at the exact same instant
    threads = [threading.Thread(target=attempt_request) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Under strict thread safety, exactly max_requests (10) are allowed and exactly 10 are rejected
    assert allowed_count == 10
    assert rejected_count == 10
    assert len(limiter._history[test_key]) == 10


# ==============================================================================
# AUD-03: Idempotency Record Retention & Safe Cleanup Tests
# ==============================================================================

def test_aud03_idempotency_retention_and_cleanup_boundaries():
    """AUD-03: Verifies that cleanup strictly purges records >72h and preserves records <72h without touching other tables."""
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    now = datetime.now(timezone.utc)
    expired_time = now - timedelta(hours=96)  # Older than 72h
    retained_time = now - timedelta(hours=24)  # Younger than 72h (within client replay window)

    with TestingSession() as db:
        # Seed a host and a metric
        host = Host(hostname="RETENTION-PC", is_active=True)
        db.add(host)
        db.commit()

        metric = Metric(host_id=host.id, timestamp=now, cpu_percent=50.0, memory_percent=50.0, disk_percent=50.0)
        db.add(metric)

        # Seed expired batch record (>72h)
        batch_old = IngestedBatch(
            batch_id="batch_old_to_purge",
            host_id=host.id,
            payload_hash="oldhash123",
            processed_samples=5,
            generated_alerts=0,
            created_at=expired_time,
        )
        # Seed active batch record (<72h)
        batch_new = IngestedBatch(
            batch_id="batch_new_to_retain",
            host_id=host.id,
            payload_hash="newhash456",
            processed_samples=5,
            generated_alerts=0,
            created_at=retained_time,
        )
        db.add(batch_old)
        db.add(batch_new)
        db.commit()

        # Execute retention cleanup with 72h policy
        deleted_count = cleanup_expired_idempotency_records(db, retention_hours=72.0, batch_limit=100)
        assert deleted_count == 1

        # Verify old batch is purged
        old_rec = db.scalar(select(IngestedBatch).where(IngestedBatch.batch_id == "batch_old_to_purge"))
        assert old_rec is None

        # Verify new batch within replay window is retained
        new_rec = db.scalar(select(IngestedBatch).where(IngestedBatch.batch_id == "batch_new_to_retain"))
        assert new_rec is not None

        # Verify Metric and Host records are 100% untouched
        metrics = list(db.scalars(select(Metric)).all())
        assert len(metrics) == 1
        hosts = list(db.scalars(select(Host)).all())
        assert len(hosts) == 1

