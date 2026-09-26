"""
Security Center API Router.

Endpoints for intrusion detection event streams, security summaries, and status updates (M4).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.security import (
    SecurityEventCreate,
    SecurityEventRead,
    SecuritySummaryResponse,
    SecurityStatusUpdate,
)
from backend.app.services.security_service import (
    record_security_event,
    get_security_events,
    get_security_summary,
    update_security_event_status,
)

router = APIRouter(prefix="/security", tags=["Security & Intrusion Detection"])


@router.get("/summary", response_model=SecuritySummaryResponse)
def get_security_health_summary(
    db: Session = Depends(get_db),
):
    """Returns aggregated security event counts by severity and recent threats."""
    return get_security_summary(db)


@router.get("/events", response_model=List[SecurityEventRead])
def list_security_events(
    host_id: Optional[int] = Query(None, description="Filter by Host ID"),
    severity: Optional[str] = Query(None, description="Filter by severity (critical, high, medium, low)"),
    status: Optional[str] = Query(None, description="Filter by status (open, investigating, mitigated)"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Lists security events matching filter criteria."""
    events = get_security_events(
        db=db,
        host_id=host_id,
        severity=severity,
        status=status,
        limit=limit,
    )
    return [
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
        for e in events
    ]


@router.post("/events", response_model=SecurityEventRead, status_code=status.HTTP_201_CREATED)
def create_security_event(
    event_in: SecurityEventCreate,
    db: Session = Depends(get_db),
):
    """Records a new security event from monitoring collectors or flow logs."""
    event = record_security_event(db, event_in)
    return SecurityEventRead(
        id=event.id,
        host_id=event.host_id,
        hostname=event.host.hostname if event.host else None,
        event_type=event.event_type,
        severity=event.severity,
        source_ip=event.source_ip,
        destination_port=event.destination_port,
        description=event.description,
        status=event.status,
        raw_evidence=event.raw_evidence,
        timestamp=event.timestamp,
        resolved_at=event.resolved_at,
    )


@router.patch("/events/{event_id}", response_model=SecurityEventRead)
def update_event_status(
    event_id: int,
    status_in: SecurityStatusUpdate,
    db: Session = Depends(get_db),
):
    """Updates the operational status of a security event (e.g. mitigated, false_positive)."""
    event = update_security_event_status(db, event_id, status_in)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security event with ID {event_id} not found.",
        )
    return SecurityEventRead(
        id=event.id,
        host_id=event.host_id,
        hostname=event.host.hostname if event.host else None,
        event_type=event.event_type,
        severity=event.severity,
        source_ip=event.source_ip,
        destination_port=event.destination_port,
        description=event.description,
        status=event.status,
        raw_evidence=event.raw_evidence,
        timestamp=event.timestamp,
        resolved_at=event.resolved_at,
    )
