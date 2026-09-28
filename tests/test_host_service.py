"""
Unit Tests for Host Service.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.base import Base
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import AlertRule, Alert, AlertFeedback
from backend.app.services.host_service import (
    create_host,
    get_or_create_host,
    deactivate_host,
    get_host,
    get_hosts,
    update_host,
)
from backend.app.schemas.host import HostUpdate


def create_test_database():
    """Sets up an isolated in-memory SQLite test database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestSessionLocal()


def test_create_and_get_host():
    """Tests basic host creation and retrieval."""
    db = create_test_database()

    host = create_host(
        db=db,
        hostname="test-server",
        ip_address="192.168.1.10",
        environment="test",
        provider="aws",
        region="us-east-1",
        tags={"tier": "api"},
    )

    assert host.id is not None
    assert host.hostname == "test-server"
    assert host.ip_address == "192.168.1.10"
    assert host.environment == "test"
    assert host.provider == "aws"
    assert host.region == "us-east-1"
    assert host.tags == {"tier": "api"}
    assert host.is_active is True

    fetched_host = get_host(db, host.id)
    assert fetched_host is not None
    assert fetched_host.hostname == "test-server"

    db.close()


def test_get_or_create_host_auto_discovery():
    """Tests auto-discovery and auto-registration of unknown hosts (M1-FR2)."""
    db = create_test_database()

    # 1. Provision new host automatically
    host1 = get_or_create_host(
        db=db,
        hostname="auto-discovered-host",
        ip_address="10.0.0.5",
        environment="staging",
        provider="gcp",
        region="us-central1",
    )
    assert host1.id is not None
    assert host1.hostname == "auto-discovered-host"
    assert host1.provider == "gcp"

    # 2. Retrieve existing host and update IP
    host2 = get_or_create_host(
        db=db,
        hostname="auto-discovered-host",
        ip_address="10.0.0.9",
    )
    assert host2.id == host1.id
    assert host2.ip_address == "10.0.0.9"

    db.close()


def test_get_hosts():
    """Tests list querying and active status filtering."""
    db = create_test_database()

    create_host(db=db, hostname="server-1", environment="production")
    create_host(db=db, hostname="server-2", environment="staging")

    hosts = get_hosts(db)
    assert len(hosts) == 2

    staging_hosts = get_hosts(db, environment="staging")
    assert len(staging_hosts) == 1
    assert staging_hosts[0].hostname == "server-2"

    db.close()


def test_update_and_deactivate_host():
    """Tests updating metadata and deactivating a host."""
    db = create_test_database()

    host = create_host(db=db, hostname="server-to-update")
    assert host.is_active is True

    # Update metadata
    updated = update_host(db, host.id, HostUpdate(ip_address="192.168.1.99", environment="production"))
    assert updated is not None
    assert updated.ip_address == "192.168.1.99"
    assert updated.environment == "production"

    # Deactivate
    deactivated = deactivate_host(db=db, host_id=host.id)
    assert deactivated is not None
    assert deactivated.is_active is False

    db.close()


def test_host_source_type_classification():
    """Tests that host creation and auto-discovery correctly store and update source_type."""
    db = create_test_database()

    # 1. Real Agent Host
    real_host = create_host(
        db=db,
        hostname="real-workstation",
        source_type="REAL_AGENT",
        provider="bare-metal",
        region="local",
    )
    assert real_host.source_type == "REAL_AGENT"

    # 2. Simulated Host Auto-Discovery
    sim_host = get_or_create_host(
        db=db,
        hostname="sim-node-01",
        source_type="SIMULATED",
        provider="simulation",
        region="synthetic",
    )
    assert sim_host.source_type == "SIMULATED"
    assert sim_host.provider == "simulation"

    # 3. Retrieval verifies persistence
    fetched_sim = get_host(db, sim_host.id)
    assert fetched_sim is not None
    assert fetched_sim.source_type == "SIMULATED"

    db.close()