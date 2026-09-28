"""
Host API Router.

Endpoints for host discovery, inventory listing, metadata management,
and status updates.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_viewer, get_current_admin
from backend.app.models.user import User
from backend.app.schemas.host import HostCreate, HostRead, HostUpdate
from backend.app.services.host_service import (
    create_host,
    get_host,
    get_hosts,
    update_host,
    deactivate_host,
    get_host_by_name,
)

router = APIRouter(prefix="/hosts", tags=["Hosts"])


@router.get("", response_model=List[HostRead])
def list_hosts(
    active_only: bool = False,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Retrieves all registered hosts in the inventory with optional status filters.
    """
    return get_hosts(db, active_only=active_only, environment=environment)


@router.post("", response_model=HostRead, status_code=status.HTTP_201_CREATED)
def register_host(
    host_in: HostCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Manually provisions or registers a host in the monitoring inventory. Requires ADMIN role.
    """
    existing = get_host_by_name(db, host_in.hostname)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Host with hostname '{host_in.hostname}' is already registered.",
        )
    return create_host(
        db=db,
        hostname=host_in.hostname,
        ip_address=host_in.ip_address,
        environment=host_in.environment,
        instance_type=host_in.instance_type,
        provider=host_in.provider,
        region=host_in.region,
        tags=host_in.tags,
    )


@router.get("/{host_id}", response_model=HostRead)
def get_host_details(
    host_id: int,
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Fetches detailed metadata for a specific host by its ID.
    """
    host = get_host(db, host_id)
    if not host:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Host with ID {host_id} not found.",
        )
    return host


@router.patch("/{host_id}", response_model=HostRead)
def update_host_metadata(
    host_id: int,
    host_in: HostUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Updates configuration or metadata attributes on a host. Requires ADMIN role.
    """
    host = update_host(db, host_id, host_in)
    if not host:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Host with ID {host_id} not found.",
        )
    return host


@router.delete("/{host_id}", response_model=HostRead)
def deactivate_monitored_host(
    host_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Deactivates a host from active telemetry expectation. Requires ADMIN role.
    """
    host = deactivate_host(db, host_id)
    if not host:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Host with ID {host_id} not found.",
        )
    return host
