"""
Host Service.

Handles host inventory lifecycle, metadata querying, updates,
and auto-registration when new telemetry arrives (M1-FR2).
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.schemas.host import HostCreate, HostUpdate


def create_host(
    db: Session,
    hostname: str,
    ip_address: Optional[str] = None,
    environment: str = "local",
    instance_type: Optional[str] = None,
    provider: Optional[str] = "bare-metal",
    region: Optional[str] = "local",
    source_type: str = "UNKNOWN",
    tags: Optional[Dict[str, Any]] = None,
) -> Host:
    """
    Registers a new monitored host.
    """
    host = Host(
        hostname=hostname,
        ip_address=ip_address,
        environment=environment,
        instance_type=instance_type,
        provider=provider,
        region=region,
        source_type=source_type,
        tags=tags or {},
        is_active=True,
    )
    db.add(host)
    db.commit()
    db.refresh(host)
    return host


def get_or_create_host(
    db: Session,
    hostname: str,
    ip_address: Optional[str] = None,
    environment: Optional[str] = "local",
    provider: Optional[str] = "bare-metal",
    region: Optional[str] = "local",
    source_type: Optional[str] = "UNKNOWN",
) -> Host:
    """
    Retrieves an existing host by hostname or automatically provisions a new record (M1-FR2).
    Updates IP address, source_type, and last seen metadata if changed.
    """
    statement = select(Host).where(Host.hostname == hostname)
    host = db.scalar(statement)

    if host is None:
        host = Host(
            hostname=hostname,
            ip_address=ip_address,
            environment=environment or "local",
            provider=provider or "bare-metal",
            region=region or "local",
            source_type=source_type or "UNKNOWN",
            is_active=True,
            tags={},
        )
        db.add(host)
        db.commit()
        db.refresh(host)
    else:
        # Update IP, source_type, and activity if it was offline or changed
        changed = False
        if ip_address and host.ip_address != ip_address:
            host.ip_address = ip_address
            changed = True
        if source_type and source_type != "UNKNOWN" and host.source_type != source_type:
            host.source_type = source_type
            changed = True
        if not host.is_active:
            host.is_active = True
            changed = True
        if changed:
            host.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(host)

    return host


def get_host(db: Session, host_id: int) -> Optional[Host]:
    """Retrieves a single host by its primary key ID."""
    statement = select(Host).where(Host.id == host_id)
    return db.scalar(statement)


def get_host_by_name(db: Session, hostname: str) -> Optional[Host]:
    """Retrieves a host by unique hostname string."""
    statement = select(Host).where(Host.hostname == hostname)
    return db.scalar(statement)


def get_hosts(
    db: Session,
    active_only: bool = False,
    environment: Optional[str] = None,
) -> List[Host]:
    """
    Retrieves all registered hosts with optional active and environment filters.
    """
    statement = select(Host).order_by(Host.id)
    if active_only:
        statement = statement.where(Host.is_active == True)
    if environment:
        statement = statement.where(Host.environment == environment)

    return list(db.scalars(statement).all())


def update_host(db: Session, host_id: int, host_in: HostUpdate) -> Optional[Host]:
    """
    Updates metadata attributes of an existing host.
    """
    host = get_host(db, host_id)
    if host is None:
        return None

    update_data = host_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(host, field, value)

    host.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(host)
    return host


def deactivate_host(db: Session, host_id: int) -> Optional[Host]:
    """
    Marks a host as inactive (e.g. decommissioned or gracefully stopped).
    """
    host = get_host(db, host_id)
    if host is None:
        return None

    host.is_active = False
    host.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(host)
    return host