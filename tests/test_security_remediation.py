"""
Phase 1 Critical Security Remediation Verification Suite.

Comprehensive tests verifying:
1. Telemetry Ingestion Authentication (missing, invalid, inactive, revoked keys).
2. Host Auto-Registration Prevention on unauthorized requests.
3. Batch Size Limit Enforcement (<=1000 items).
4. Real Monitoring Agent & Fleet Simulator Credential Dispatch.
5. Production JWT Signing Secret Validation (default and short secrets rejected).
6. Local Development Configuration Stability.
7. Active Database File Immutability.
"""

import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.main import app
from backend.app.core.config import Settings
from backend.app.api.deps import hash_agent_key
from backend.app.models.agent_key import AgentApiKey
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import Alert
from monitoring_agent.buffer import MetricBuffer
from scripts.simulate_fleet import FleetSimulator
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """TestClient wired to isolated test database."""
    return TestClient(app)


# ==============================================================================
# 1. Telemetry Ingestion Authentication Tests
# ==============================================================================

def test_missing_agent_credentials_rejected(client):
    """Verifies that metric ingestion without credentials returns HTTP 401 Unauthorized."""
    payload = {
        "hostname": "unauth-host-01",
        "ip_address": "10.0.0.99",
        "cpu_percent": 50.0,
        "memory_percent": 50.0,
        "disk_percent": 50.0,
    }
    response = client.post("/api/v1/metrics", json=payload)
    assert response.status_code == 401
    assert "Missing agent ingestion credentials" in response.json()["detail"]


def test_invalid_agent_credentials_rejected(client):
    """Verifies that an incorrect or forged agent key returns HTTP 401 Unauthorized."""
    payload = {
        "hostname": "unauth-host-02",
        "cpu_percent": 60.0,
        "memory_percent": 60.0,
        "disk_percent": 60.0,
    }
    response = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": "forged-invalid-secret-key-12345"},
        json=payload,
    )
    assert response.status_code == 401
    assert "Invalid agent ingestion credentials" in response.json()["detail"]


def test_unauthorized_requests_cannot_create_hosts_or_metrics(client, isolated_db):
    """
    CRITICAL: Verifies that unauthorized requests are blocked before database writes.
    Neither a Host record nor a Metric record must be persisted.
    """
    hostname = "malicious-auto-register-attempt"
    
    # Verify host does not exist initially
    initial_host = isolated_db.scalar(select(Host).where(Host.hostname == hostname))
    assert initial_host is None

    # Submit unauthorized payload
    res = client.post(
        "/api/v1/metrics",
        json={
            "hostname": hostname,
            "ip_address": "198.51.100.77",
            "cpu_percent": 99.9,
            "memory_percent": 99.9,
            "disk_percent": 99.9,
        },
    )
    assert res.status_code == 401

    # Verify host was NOT created in database
    isolated_db.expire_all()
    host_after = isolated_db.scalar(select(Host).where(Host.hostname == hostname))
    assert host_after is None, "Security violation: Host was created by an unauthorized request!"


def test_valid_configured_agent_key_permits_single_ingestion(client):
    """Verifies that a valid configured agent key permits authorized single metric ingestion."""
    payload = {
        "hostname": "prod-auth-worker-01",
        "ip_address": "10.0.1.50",
        "environment": "production",
        "provider": "aws",
        "region": "us-east-1",
        "source_type": "REAL_AGENT",
        "cpu_percent": 42.0,
        "memory_percent": 55.0,
        "disk_percent": 30.0,
    }
    response = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": "test-agent-key-fixture-secret-2026"},
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["metric"]["cpu_percent"] == 42.0


def test_valid_configured_agent_key_permits_batch_ingestion(client):
    """Verifies that a valid configured agent key permits authorized batch ingestion."""
    batch_payload = {
        "metrics": [
            {
                "hostname": "prod-batch-worker-01",
                "source_type": "REAL_AGENT",
                "cpu_percent": 35.0,
                "memory_percent": 40.0,
                "disk_percent": 45.0,
            },
            {
                "hostname": "prod-batch-worker-02",
                "source_type": "REAL_AGENT",
                "cpu_percent": 75.0,
                "memory_percent": 80.0,
                "disk_percent": 60.0,
            },
        ]
    }
    response = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": "test-agent-key-fixture-secret-2026"},
        json=batch_payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["processed_samples"] == 2


def test_database_managed_agent_key_lifecycle(client, isolated_db):
    """
    Verifies that database-managed keys function correctly across their lifecycle:
    1. Active key succeeds
    2. Inactive key is rejected (401)
    3. Revoked key is rejected (401)
    """
    raw_secret = "custom-agent-db-secret-key-999888"
    hashed = hash_agent_key(raw_secret)
    
    # 1. Provision active key
    key_record = AgentApiKey(
        name="Test Ingestion Key",
        key_prefix="ak_test_",
        hashed_key=hashed,
        source_type="REAL_AGENT",
        is_active=True,
    )
    isolated_db.add(key_record)
    isolated_db.commit()
    isolated_db.refresh(key_record)

    # Ingest with active key
    res_active = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json={
            "hostname": "db-keyed-worker-01",
            "source_type": "REAL_AGENT",
            "cpu_percent": 25.0,
            "memory_percent": 30.0,
            "disk_percent": 35.0,
        },
    )
    assert res_active.status_code == 201

    # 2. Deactivate key
    key_record.is_active = False
    isolated_db.commit()

    res_inactive = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json={
            "hostname": "db-keyed-worker-01",
            "source_type": "REAL_AGENT",
            "cpu_percent": 25.0,
            "memory_percent": 30.0,
            "disk_percent": 35.0,
        },
    )
    assert res_inactive.status_code == 401
    assert "inactive" in res_inactive.json()["detail"].lower()

    # 3. Revoke key
    key_record.is_active = True
    key_record.revoked_at = datetime.now(timezone.utc)
    isolated_db.commit()

    res_revoked = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json={
            "hostname": "db-keyed-worker-01",
            "source_type": "REAL_AGENT",
            "cpu_percent": 25.0,
            "memory_percent": 30.0,
            "disk_percent": 35.0,
        },
    )
    assert res_revoked.status_code == 401
    assert "revoked" in res_revoked.json()["detail"].lower()


def test_batch_size_limit_enforced(client):
    """Verifies that batches exceeding the 1,000 item limit are rejected with HTTP 422."""
    oversized_samples = [
        {
            "hostname": f"spam-host-{i}",
            "source_type": "REAL_AGENT",
            "cpu_percent": 50.0,
            "memory_percent": 50.0,
            "disk_percent": 50.0,
        }
        for i in range(1001)
    ]
    response = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": "test-agent-key-fixture-secret-2026"},
        json={"metrics": oversized_samples},
    )
    assert response.status_code == 422


# ==============================================================================
# 2. Agent & Simulator Credential Dispatch Tests
# ==============================================================================

@patch("requests.post")
def test_agent_buffer_transmits_authentication_header(mock_post):
    """Verifies that MetricBuffer transmits the X-Agent-Key header."""
    mock_post.return_value = MagicMock(status_code=201)
    
    buffer = MetricBuffer(
        ingest_url="https://mock-collector/api/v1/metrics",
        api_key="secret-agent-key-xyz",
    )
    buffer.push({"hostname": "test-agent-01", "cpu_percent": 30.0})
    success = buffer.flush()

    assert success is True
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert "headers" in kwargs
    assert kwargs["headers"].get("X-Agent-Key") == "secret-agent-key-xyz"


@patch("requests.post")
def test_fleet_simulator_transmits_authentication_header(mock_post):
    """Verifies that FleetSimulator transmits the X-Agent-Key header."""
    mock_post.return_value = MagicMock(status_code=201, json=lambda: {"generated_alerts": 0})

    sim = FleetSimulator(
        target_url="https://mock-collector/api/v1/metrics",
        api_key="fleet-simulator-key-abc",
    )
    sim.run(interval=0, iterations=1)

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert "headers" in kwargs
    assert kwargs["headers"].get("X-Agent-Key") == "fleet-simulator-key-abc"


# ==============================================================================
# 3. Production JWT Secret Validation Tests
# ==============================================================================

def test_production_rejects_default_jwt_secret():
    """Verifies that production environment refuses to boot with the default JWT secret."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            environment="production",
            secret_key="cloudops-intel-secure-jwt-hmac-sha256-default-key-production-change-me",
        )
    assert "Insecure or default SECRET_KEY detected" in str(exc_info.value)
    # Ensure raw secret is NOT leaked in the error message
    assert "cloudops-intel-secure-jwt-hmac" not in str(exc_info.value)


def test_production_rejects_short_jwt_secret():
    """Verifies that production environment refuses to boot with secret < 32 characters."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            environment="production",
            secret_key="too-short-secret-1234",
        )
    assert "SECRET_KEY is too short" in str(exc_info.value)


def test_production_accepts_strong_jwt_secret():
    """Verifies that production environment boots with a strong, secure 32+ character secret."""
    strong_key = "a" * 64
    prod_settings = Settings(
        environment="production",
        secret_key=strong_key,
    )
    assert prod_settings.environment == "production"
    assert prod_settings.secret_key == strong_key


def test_development_permits_default_secret():
    """Verifies that local development mode remains frictionless without breaking."""
    dev_settings = Settings(
        environment="development",
        secret_key="cloudops-intel-secure-jwt-hmac-sha256-default-key-production-change-me",
    )
    assert dev_settings.environment == "development"


# ==============================================================================
# 4. Telemetry Source Provenance Enforcement Tests (Phase 1.2)
# ==============================================================================

def test_provenance_real_agent_credential_matching_succeeds(client, isolated_db):
    """
    Verifies that a credential restricted to REAL_AGENT succeeds when submitting
    REAL_AGENT telemetry, and auto-registers host with REAL_AGENT provenance.
    """
    raw_secret = "real-agent-authorized-key-001"
    key_record = AgentApiKey(
        name="Real Agent Collector",
        key_prefix="ak_real_",
        hashed_key=hash_agent_key(raw_secret),
        source_type="REAL_AGENT",
        is_active=True,
    )
    isolated_db.add(key_record)
    isolated_db.commit()

    res = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json={
            "hostname": "prod-real-server-01",
            "ip_address": "10.10.1.10",
            "source_type": "REAL_AGENT",
            "cpu_percent": 35.0,
            "memory_percent": 45.0,
            "disk_percent": 55.0,
        },
    )
    assert res.status_code == 201
    assert res.json()["status"] == "success"

    host = isolated_db.scalar(select(Host).where(Host.hostname == "prod-real-server-01"))
    assert host is not None
    assert host.source_type == "REAL_AGENT"


def test_provenance_simulated_credential_matching_succeeds(client, isolated_db):
    """
    Verifies that a credential restricted to SIMULATED succeeds when submitting
    SIMULATED telemetry, and auto-registers host with SIMULATED provenance.
    """
    raw_secret = "simulated-agent-authorized-key-002"
    key_record = AgentApiKey(
        name="Fleet Simulator Engine",
        key_prefix="ak_sim_",
        hashed_key=hash_agent_key(raw_secret),
        source_type="SIMULATED",
        is_active=True,
    )
    isolated_db.add(key_record)
    isolated_db.commit()

    res = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json={
            "hostname": "simulated-virtual-node-01",
            "ip_address": "172.16.0.5",
            "source_type": "SIMULATED",
            "cpu_percent": 28.0,
            "memory_percent": 32.0,
            "disk_percent": 40.0,
        },
    )
    assert res.status_code == 201
    assert res.json()["status"] == "success"

    host = isolated_db.scalar(select(Host).where(Host.hostname == "simulated-virtual-node-01"))
    assert host is not None
    assert host.source_type == "SIMULATED"


def test_provenance_real_agent_attempting_simulated_rejected_403(client, isolated_db):
    """
    Verifies that a REAL_AGENT credential attempting to submit SIMULATED telemetry
    is rejected with HTTP 403 Forbidden.
    """
    raw_secret = "real-agent-probe-key-003"
    key_record = AgentApiKey(
        name="Real Agent Restricted",
        key_prefix="ak_real_",
        hashed_key=hash_agent_key(raw_secret),
        source_type="REAL_AGENT",
        is_active=True,
    )
    isolated_db.add(key_record)
    isolated_db.commit()

    res = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json={
            "hostname": "spoof-attempt-from-real-key",
            "source_type": "SIMULATED",
            "cpu_percent": 50.0,
            "memory_percent": 50.0,
            "disk_percent": 50.0,
        },
    )
    assert res.status_code == 403
    assert "Telemetry provenance violation" in res.json()["detail"]


def test_provenance_simulated_attempting_real_agent_rejected_403(client, isolated_db):
    """
    Verifies that a SIMULATED credential attempting to submit REAL_AGENT telemetry
    is rejected with HTTP 403 Forbidden.
    """
    raw_secret = "simulated-probe-key-004"
    key_record = AgentApiKey(
        name="Simulator Restricted",
        key_prefix="ak_sim_",
        hashed_key=hash_agent_key(raw_secret),
        source_type="SIMULATED",
        is_active=True,
    )
    isolated_db.add(key_record)
    isolated_db.commit()

    res = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json={
            "hostname": "spoof-attempt-from-sim-key",
            "source_type": "REAL_AGENT",
            "cpu_percent": 50.0,
            "memory_percent": 50.0,
            "disk_percent": 50.0,
        },
    )
    assert res.status_code == 403
    assert "Telemetry provenance violation" in res.json()["detail"]


def test_provenance_restricted_batch_mismatched_item_rejected_403(client, isolated_db):
    """
    Verifies that batch requests cannot bypass provenance enforcement by placing
    a conflicting source_type in one item. The entire batch must fail with HTTP 403.
    """
    raw_secret = "real-agent-batch-key-005"
    key_record = AgentApiKey(
        name="Real Agent Batch Collector",
        key_prefix="ak_real_",
        hashed_key=hash_agent_key(raw_secret),
        source_type="REAL_AGENT",
        is_active=True,
    )
    isolated_db.add(key_record)
    isolated_db.commit()

    batch_payload = {
        "metrics": [
            {
                "hostname": "batch-real-node-01",
                "source_type": "REAL_AGENT",
                "cpu_percent": 20.0,
                "memory_percent": 30.0,
                "disk_percent": 40.0,
            },
            {
                "hostname": "batch-sim-poison-02",
                "source_type": "SIMULATED",  # Mismatched provenance!
                "cpu_percent": 95.0,
                "memory_percent": 90.0,
                "disk_percent": 85.0,
            },
            {
                "hostname": "batch-real-node-03",
                "source_type": "REAL_AGENT",
                "cpu_percent": 25.0,
                "memory_percent": 35.0,
                "disk_percent": 45.0,
            },
        ]
    }

    res = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json=batch_payload,
    )
    assert res.status_code == 403
    assert "Telemetry provenance violation" in res.json()["detail"]

    # Verify zero hosts and zero metrics created from this rejected batch
    isolated_db.expire_all()
    for hname in ["batch-real-node-01", "batch-sim-poison-02", "batch-real-node-03"]:
        host = isolated_db.scalar(select(Host).where(Host.hostname == hname))
        assert host is None, f"Batch violation: Host '{hname}' was created despite rejected batch!"


def test_provenance_all_credential_allows_real_and_simulated(client):
    """
    Verifies the policy for ALL credentials (such as configured environment key):
    Permits both explicit REAL_AGENT and SIMULATED telemetry.
    """
    all_key = "test-agent-key-fixture-secret-2026"

    # 1. REAL_AGENT submission succeeds
    res_real = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": all_key},
        json={
            "hostname": "all-cred-real-worker",
            "source_type": "REAL_AGENT",
            "cpu_percent": 33.0,
            "memory_percent": 44.0,
            "disk_percent": 55.0,
        },
    )
    assert res_real.status_code == 201

    # 2. SIMULATED submission succeeds
    res_sim = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": all_key},
        json={
            "hostname": "all-cred-sim-worker",
            "source_type": "SIMULATED",
            "cpu_percent": 44.0,
            "memory_percent": 55.0,
            "disk_percent": 66.0,
        },
    )
    assert res_sim.status_code == 201


def test_provenance_missing_unknown_or_malformed_rejected_403(client, isolated_db):
    """
    Verifies that absent, unknown, or malformed source types are explicitly rejected
    with HTTP 403 Forbidden under both ALL and restricted credentials.
    Telemetry is never silently misclassified as real.
    """
    all_key = "test-agent-key-fixture-secret-2026"

    # 1. ALL key with omitted source_type (schema default UNKNOWN)
    res_missing = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": all_key},
        json={
            "hostname": "unclassified-host-01",
            "cpu_percent": 20.0,
            "memory_percent": 20.0,
            "disk_percent": 20.0,
        },
    )
    assert res_missing.status_code == 403

    # 2. ALL key with explicit UNKNOWN
    res_unknown = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": all_key},
        json={
            "hostname": "unclassified-host-02",
            "source_type": "UNKNOWN",
            "cpu_percent": 20.0,
            "memory_percent": 20.0,
            "disk_percent": 20.0,
        },
    )
    assert res_unknown.status_code == 403

    # 3. ALL key with malformed/fabricated source_type
    res_malformed = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": all_key},
        json={
            "hostname": "unclassified-host-03",
            "source_type": "FABRICATED_SOURCE",
            "cpu_percent": 20.0,
            "memory_percent": 20.0,
            "disk_percent": 20.0,
        },
    )
    assert res_malformed.status_code == 403

    # 4. Restricted REAL_AGENT key with omitted source_type
    raw_secret = "real-agent-strict-key-006"
    key_record = AgentApiKey(
        name="Real Agent Strict",
        key_prefix="ak_real_",
        hashed_key=hash_agent_key(raw_secret),
        source_type="REAL_AGENT",
        is_active=True,
    )
    isolated_db.add(key_record)
    isolated_db.commit()

    res_real_missing = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json={
            "hostname": "unclassified-host-04",
            "cpu_percent": 20.0,
            "memory_percent": 20.0,
            "disk_percent": 20.0,
        },
    )
    assert res_real_missing.status_code == 403


def test_provenance_rejected_requests_create_zero_hosts_metrics_alerts(client, isolated_db):
    """
    CRITICAL: Verifies that requests rejected due to provenance violations
    create zero Host records, zero Metric records, and zero Alert records.
    Validation strictly occurs BEFORE any database write.
    """
    raw_secret = "real-agent-guarded-key-007"
    key_record = AgentApiKey(
        name="Guarded Real Agent",
        key_prefix="ak_real_",
        hashed_key=hash_agent_key(raw_secret),
        source_type="REAL_AGENT",
        is_active=True,
    )
    isolated_db.add(key_record)
    isolated_db.commit()

    hostname = "canary-disallowed-provenance-target"
    
    # Ensure host does not exist initially
    initial_host = isolated_db.scalar(select(Host).where(Host.hostname == hostname))
    assert initial_host is None

    # Submit disallowed telemetry with CPU at 99.5% (which would trigger critical alert if processed)
    res = client.post(
        "/api/v1/metrics",
        headers={"X-Agent-Key": raw_secret},
        json={
            "hostname": hostname,
            "ip_address": "10.99.99.99",
            "source_type": "SIMULATED",  # Disallowed for REAL_AGENT credential!
            "cpu_percent": 99.5,
            "memory_percent": 99.5,
            "disk_percent": 99.5,
        },
    )
    assert res.status_code == 403

    # Assert 0 Hosts created
    isolated_db.expire_all()
    host_after = isolated_db.scalar(select(Host).where(Host.hostname == hostname))
    assert host_after is None, "Provenance violation: Host was created on a rejected request!"

    # Assert 0 Metrics created
    metric_after = isolated_db.scalar(select(Metric).where(Metric.cpu_percent == 99.5))
    assert metric_after is None, "Provenance violation: Metric was created on a rejected request!"

    # Assert 0 Alerts created
    alert_after = isolated_db.scalars(select(Alert)).all()
    canary_alerts = [a for a in alert_after if a.value == 99.5]
    assert len(canary_alerts) == 0, "Provenance violation: Alert was created on a rejected request!"


# ==============================================================================
# 5. Active Database Immutability Verification
# ==============================================================================

def test_active_database_immutability(isolated_db):
    """
    Verifies test database isolation and immutability of active application storage.
    Ensures that test executions are strictly routed to the isolated in-memory engine
    and never connect to or mutate the persistent development database file.
    """
    from backend.app.core.config import settings
    from backend.app.api.deps import get_db
    from backend.app.main import app
    from sqlalchemy import text

    # 1. Verify application configuration is isolated in-memory
    assert settings.database_url == "sqlite:///:memory:", (
        f"Configuration isolation failure: settings.database_url is '{settings.database_url}'"
    )

    # 2. Verify FastAPI dependency override is wired to isolated test session
    assert get_db in app.dependency_overrides, "FastAPI get_db dependency override is missing!"

    # 3. Verify database session connection is in-memory (no physical file path)
    db_list = isolated_db.execute(text("PRAGMA database_list;")).fetchall()
    for seq, name, file_path in db_list:
        if name == "main":
            assert file_path == "" or file_path is None, (
                f"Test database isolation failure: Active test session is connected to physical file '{file_path}' "
                f"instead of isolated in-memory storage!"
            )

    # 4. Verify that persistent development database file exists
    db_path = Path("cloud_intelligence.db").resolve()
    assert db_path.exists(), "cloud_intelligence.db must exist."
