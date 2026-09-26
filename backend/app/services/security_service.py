"""
Security Service.

Provides security event logging, threat detection queries, and status updates (M4).
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.models.security import SecurityEvent, AuditLog
from backend.app.schemas.security import (
    SecurityEventCreate,
    SecurityEventRead,
    SecuritySummaryResponse,
    SecurityStatusUpdate,
)
from backend.app.services.host_service import get_host_by_name


def record_security_event(
    db: Session,
    event_in: SecurityEventCreate,
) -> SecurityEvent:
    """Persists a new security event into the database."""
    host_id = None
    if event_in.hostname:
        host = get_host_by_name(db, event_in.hostname)
        if host:
            host_id = host.id

    event = SecurityEvent(
        host_id=host_id,
        event_type=event_in.event_type,
        severity=event_in.severity,
        source_ip=event_in.source_ip,
        destination_port=event_in.destination_port,
        description=event_in.description,
        raw_evidence=event_in.raw_evidence,
        status="open",
        timestamp=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_security_events(
    db: Session,
    host_id: Optional[int] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[SecurityEvent]:
    """Queries security events matching filter criteria."""
    statement = select(SecurityEvent).order_by(desc(SecurityEvent.timestamp))
    if host_id:
        statement = statement.where(SecurityEvent.host_id == host_id)
    if severity:
        statement = statement.where(SecurityEvent.severity == severity)
    if status:
        statement = statement.where(SecurityEvent.status == status)
    statement = statement.limit(limit)
    return list(db.scalars(statement).all())


def get_security_summary(db: Session) -> SecuritySummaryResponse:
    """Aggregates security counts by severity and returns recent events."""
    events = list(db.scalars(select(SecurityEvent).order_by(desc(SecurityEvent.timestamp)).limit(50)).all())
    
    total = len(events)
    crit = sum(1 for e in events if e.severity == "critical")
    high = sum(1 for e in events if e.severity == "high")
    med = sum(1 for e in events if e.severity == "medium")
    low = sum(1 for e in events if e.severity == "low")
    open_incidents = sum(1 for e in events if e.status in ["open", "investigating"])

    recent = [
        SecurityEventRead(
            id=e.id,
            host_id=e.host_id,
            hostname=e.host.hostname if e.host else None,
            event_type=e.event_type,
            severity=e.severity,
            source_ip=e.source_ip,
            destination_port=e.destination_port,
            description=e.description,
            status=e.status,
            raw_evidence=e.raw_evidence,
            timestamp=e.timestamp,
            resolved_at=e.resolved_at,
        )
        for e in events[:20]
    ]

    return SecuritySummaryResponse(
        total_events=total,
        critical_events=crit,
        high_events=high,
        medium_events=med,
        low_events=low,
        open_incidents=open_incidents,
        recent_events=recent,
    )


def update_security_event_status(
    db: Session,
    event_id: int,
    status_update: SecurityStatusUpdate,
) -> Optional[SecurityEvent]:
    """Updates the status of a security incident."""
    event = db.get(SecurityEvent, event_id)
    if not event:
        return None
    event.status = status_update.status
    if status_update.status in ["mitigated", "false_positive"]:
        event.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return event
