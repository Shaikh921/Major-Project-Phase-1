"""
Integration Tests for AI and Forecasting API Endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.init_db import seed_default_rules
from backend.app.models.user import User
from backend.app.api.deps import get_db, get_current_viewer, get_current_operator, get_current_admin
from backend.app.main import app
from backend.app.services.metric_service import ingest_metric
from backend.app.schemas.metric import MetricCreate


@pytest.fixture(scope="module", autouse=True)
def setup_ai_test_database():
    """Sets up an isolated in-memory SQLite database for AI endpoint tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        seed_default_rules(db)
        # Seed 10 metric samples for host 'forecast-test-host'
        for i in range(10):
            ingest_metric(
                db,
                MetricCreate(
                    hostname="forecast-test-host",
                    cpu_percent=25.0 + i,
                    memory_percent=40.0 + (i * 0.5),
                    disk_percent=75.0 + (i * 1.5),  # climbing disk
                    network_sent_mb=1.0,
                    network_received_mb=2.0,
                ),
            )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    mock_admin = User(id=1, email="test-admin@ops.local", password_hash="dummy", role="ADMIN", is_active=True, is_verified=True)
    from backend.app.api.deps import get_current_viewer, get_current_operator, get_current_admin
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_viewer] = lambda: mock_admin
    app.dependency_overrides[get_current_operator] = lambda: mock_admin
    app.dependency_overrides[get_current_admin] = lambda: mock_admin
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_viewer, None)
    app.dependency_overrides.pop(get_current_operator, None)
    app.dependency_overrides.pop(get_current_admin, None)
    Base.metadata.drop_all(bind=engine)
    from backend.app.services.ai_service import reset_global_detector
    reset_global_detector()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_ai_score_endpoint(client):
    """Tests POST /api/v1/ai/score for multivariate evaluation."""
    payload = {
        "hostname": "test-box",
        "cpu_percent": 96.0,
        "memory_percent": 90.0,
        "disk_percent": 50.0,
        "network_sent_mb": 120.0,
        "network_received_mb": 5.0,
    }
    res = client.post("/api/v1/ai/score", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "is_anomaly" in data
    assert "anomaly_score" in data
    assert "feature_contributions" in data
    assert len(data["feature_contributions"]) == 5
    assert len(data["explanation"]) > 0


def test_ai_train_and_models_endpoints(client):
    """Tests POST /api/v1/ai/train and GET /api/v1/ai/models."""
    res = client.post("/api/v1/ai/train", json={"contamination": 0.05, "version": "v1"})
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "success"
    assert data["samples_trained"] >= 10

    # List models
    models_res = client.get("/api/v1/ai/models")
    assert models_res.status_code == 200
    models_list = models_res.json()
    assert len(models_list) >= 1
    assert any(m["model_name"] == "fleet_anomaly_detector" for m in models_list)


def test_forecast_endpoint(client):
    """Tests GET /api/v1/forecast for time-series projection and time-to-threshold countdown."""
    res = client.get("/api/v1/forecast?host_id=1&metric=disk_percent&horizon_hours=24&critical_threshold=95.0")
    assert res.status_code == 200
    data = res.json()
    assert data["host_id"] == 1
    assert data["metric"] == "disk_percent"
    assert len(data["forecast_points"]) == 24
    assert data["time_to_threshold"] is not None
    assert "hours_remaining" in data["time_to_threshold"]
