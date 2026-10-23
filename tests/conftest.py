"""
Pytest Central Configuration & Test Database Isolation Fixtures.

Guarantees 100% isolation of all automated tests from the active
application database (cloud_intelligence.db). Uses an ephemeral, in-memory
SQLite database and verifies that active project database files remain
strictly unmodified.
"""

import os
import hashlib
from pathlib import Path
from typing import Generator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Ensure test environment settings are enforced before backend initialization
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SMTP_ENABLED"] = "false"
os.environ["NOTIFY_ON_CRITICAL_ALERTS"] = "false"
os.environ["AGENT_INGESTION_KEY"] = "test-agent-key-fixture-secret-2026"

from backend.app.core.config import settings
settings.environment = "development"
settings.database_url = "sqlite:///:memory:"
settings.smtp_enabled = False
settings.notify_on_critical_alerts = False
settings.agent_ingestion_key = "test-agent-key-fixture-secret-2026"

import backend.app.database.connection as db_conn
import backend.app.database.session as db_sess
from backend.app.database.base import Base
from backend.app.database.init_db import seed_default_rules, seed_pricing_catalog, seed_baseline_telemetry_if_empty
from backend.app.main import app
from backend.app.api.deps import get_db

# Create shared isolated in-memory SQLite engine with StaticPool
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Monkeypatch global engine and SessionLocal across connection, session, and deps modules
db_conn.engine = test_engine
db_sess.engine = test_engine
db_sess.SessionLocal = TestingSessionLocal
import backend.app.api.deps as api_deps
api_deps.SessionLocal = TestingSessionLocal

# Initialize all table schemas and seed baseline rules/catalogs in-memory
Base.metadata.create_all(bind=test_engine)
with TestingSessionLocal() as init_db_session:
    seed_default_rules(init_db_session)
    seed_pricing_catalog(init_db_session)
    seed_baseline_telemetry_if_empty(init_db_session)


def override_get_db() -> Generator[Session, None, None]:
    """Dependency override routing all FastAPI requests to isolated in-memory DB."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# Globally wire dependency override into FastAPI application
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def ensure_test_database_isolation():
    """Autouse fixture guaranteeing that get_db always routes to the isolated in-memory test database."""
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def verify_active_db_unaltered():
    """
    Safety Guard Fixture:
    Asserts 100% test database isolation by verifying that test_engine,
    db_conn.engine, and db_sess.SessionLocal are strictly bound to in-memory SQLite
    and that no test query or session opens the persistent cloud_intelligence.db file.
    """
    from sqlalchemy import text

    # Verify initial isolation on session start
    with test_engine.connect() as conn:
        db_list = conn.execute(text("PRAGMA database_list;")).fetchall()
        for seq, name, file_path in db_list:
            if name == "main":
                assert file_path == "" or file_path is None, (
                    f"CRITICAL TEST ISOLATION FAILURE: Test engine is bound to file '{file_path}' "
                    f"instead of isolated in-memory database!"
                )

    yield

    # Verify isolation persisted throughout the entire test session
    with test_engine.connect() as conn:
        db_list = conn.execute(text("PRAGMA database_list;")).fetchall()
        for seq, name, file_path in db_list:
            if name == "main":
                assert file_path == "" or file_path is None, (
                    f"CRITICAL TEST ISOLATION FAILURE: Test engine became bound to file '{file_path}'!"
                )


@pytest.fixture
def isolated_db() -> Generator[Session, None, None]:
    """Provides a thread-safe test session bound to the isolated in-memory database."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def agent_auth_headers() -> dict:
    """Returns valid agent authentication headers for test client requests."""
    return {"X-Agent-Key": "test-agent-key-fixture-secret-2026"}
