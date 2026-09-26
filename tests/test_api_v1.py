"""
Integration Tests for REST API v1 Endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.init_db import seed_default_rules
from backend.app.api.deps import get_db
from backend.app.main import app


@pytest.fixture(scope="module", autouse=True)
def setup_v1_test_database():
    """Sets up an isolated in-memory SQLite database for API v1 tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        seed_default_rules(db)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_root_and_health(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "running"

    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_hosts_endpoints(client):
    # 1. Create host
    res = client.post(
        "/api/v1/hosts",
        json={
            "hostname": "api-test-host",
            "ip_address": "10.0.0.1",
            "environment": "staging",
            "provider": "aws",
            "region": "us-east-1",
        },
    )
    assert res.status_code == 201
    host_id = res.json()["id"]

    # 2. List hosts
    res = client.get("/api/v1/hosts")
    assert res.status_code == 200
    assert any(h["id"] == host_id for h in res.json())

    # 3. Get single host
    res = client.get(f"/api/v1/hosts/{host_id}")
    assert res.status_code == 200
    assert res.json()["hostname"] == "api-test-host"


def test_metrics_and_summary_flow(client):
    # 1. Submit metric
    res = client.post(
        "/api/v1/metrics",
        json={
            "hostname": "live-stream-host",
            "ip_address": "192.168.1.55",
            "cpu_percent": 88.5,  # Breaches warning threshold (>=80%)
            "memory_percent": 65.0,
            "disk_percent": 50.0,
            "network_sent_mb": 0.5,
            "network_received_mb": 1.2,
        },
    )
    assert res.status_code == 201
    assert res.json()["generated_alerts"] >= 1

    # 2. Query summary
    res = client.get("/api/v1/summary")
    assert res.status_code == 200
    summary = res.json()
    assert summary["total_hosts"] >= 1
    assert summary["total_active_alerts"] >= 1

    # 3. List active alerts
    res = client.get("/api/v1/alerts?status=active")
    assert res.status_code == 200
    alerts = res.json()
    assert len(alerts) >= 1
    target_alert_id = alerts[0]["id"]

    # 4. Acknowledge alert
    res = client.post(f"/api/v1/alerts/{target_alert_id}/ack")
    assert res.status_code == 200
    assert res.json()["status"] == "acknowledged"

    # 5. Submit feedback on alert
    res = client.post(
        f"/api/v1/alerts/{target_alert_id}/feedback",
        json={"verdict": "true_positive", "operator_notes": "Tested from API test suite."},
    )
    assert res.status_code == 201
    assert res.json()["verdict"] == "true_positive"
