"""
Acceptance Test Suite for Database Seeding and PII Sanitization (Phase 8B).

Verifies:
1. Fresh database initialization uses neutral, non-deliverable example addresses.
2. No hardcoded personal email addresses are inserted during seeding.
3. Database initialization and migrations are idempotent and do not overwrite existing records.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.init_db import (
    seed_default_rules,
    seed_pricing_catalog,
    seed_baseline_telemetry_if_empty,
)
from backend.app.models.host import Host

PERSONAL_EMAILS = {
    "irafanshaikh505@gmail.com",
    "projectinengineering@gmail.com",
    "mrirfanshaikh0777@gmail.com",
}


@pytest.fixture
def clean_memory_db():
    """Provides a fresh isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_seed_baseline_telemetry_uses_neutral_emails(clean_memory_db):
    """
    CRITICAL: Verifies that newly seeded hosts never contain personal Gmail addresses
    and strictly use neutral .example.internal addresses.
    """
    seed_baseline_telemetry_if_empty(clean_memory_db)

    hosts = clean_memory_db.scalars(select(Host)).all()
    assert len(hosts) > 0, "Seed baseline telemetry must create sample hosts."

    for host in hosts:
        assert host.owner_email is not None, f"Host {host.hostname} should have an owner_email."
        # Must not contain any personal emails
        assert host.owner_email not in PERSONAL_EMAILS, (
            f"Security violation: Host {host.hostname} was seeded with personal email {host.owner_email}!"
        )
        # Must use neutral internal domain
        assert host.owner_email.endswith("@cloudops.example.internal"), (
            f"Host {host.hostname} owner_email '{host.owner_email}' does not use @cloudops.example.internal domain."
        )


def test_seeding_is_idempotent_and_does_not_duplicate_or_overwrite(clean_memory_db):
    """
    Verifies that calling seeding logic multiple times is idempotent:
    does not create duplicate hosts and does not overwrite modified owner emails.
    """
    # First seed
    seed_baseline_telemetry_if_empty(clean_memory_db)
    initial_hosts = clean_memory_db.scalars(select(Host)).all()
    initial_count = len(initial_hosts)

    # Modify an owner email to a custom address
    custom_email = "custom-lead@engineering.internal"
    initial_hosts[0].owner_email = custom_email
    clean_memory_db.commit()

    # Second seed invocation (should be no-op because hosts already exist)
    seed_baseline_telemetry_if_empty(clean_memory_db)

    hosts_after = clean_memory_db.scalars(select(Host)).all()
    assert len(hosts_after) == initial_count, "Repeated seeding must not duplicate host records."

    # Verify custom email was preserved and not overwritten
    reloaded_first_host = clean_memory_db.scalar(select(Host).where(Host.id == initial_hosts[0].id))
    assert reloaded_first_host.owner_email == custom_email, (
        "Idempotence violation: Existing host owner_email was overwritten by repeated seeding!"
    )
