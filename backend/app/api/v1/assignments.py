"""
Assignments API Router (Phase 9A.1 Hybrid RBAC).

Provides administrative endpoints to manage environment and host assignments.
Protected by Super Admin role permissions.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_super_admin, get_current_user
from backend.app.models.user import User, UserRole
from backend.app.schemas.assignment import (
    EnvironmentAssignmentCreate,
    HostAssignmentCreate,
    AssignmentResponse,
)
from backend.app.services.assignment_service import (
    grant_environment_assignment,
    revoke_environment_assignment,
    grant_host_assignment,
    revoke_host_assignment,
    list_assignments,
)

router = APIRouter(prefix="/assignments", tags=["Assignments RBAC"])


@router.get("", response_model=List[AssignmentResponse])
def get_all_assignments(
    active_only: bool = True,
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Lists all environment and host assignments. Requires SUPER_ADMIN role.
    """
    return list_assignments(db, active_only=active_only)


@router.post("/environments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_user_to_environment(
    req: EnvironmentAssignmentCreate,
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Grants a user operational access to an entire deployment environment. Requires SUPER_ADMIN role.
    """
    ea = grant_environment_assignment(
        db=db,
        user_id=req.user_id,
        environment=req.environment,
        granted_by_id=current_user.id,
    )
    return {
        "id": ea.id,
        "user_id": ea.user_id,
        "scope_type": "ENVIRONMENT",
        "scope_value": ea.environment,
        "host_id": None,
        "status": ea.status,
        "granted_by_id": ea.granted_by_id,
        "revoked_by_id": ea.revoked_by_id,
        "created_at": ea.created_at,
        "revoked_at": ea.revoked_at,
    }


@router.delete("/environments/{assignment_id}", response_model=AssignmentResponse)
def revoke_user_environment_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Revokes an environment assignment. Requires SUPER_ADMIN role.
    """
    ea = revoke_environment_assignment(
        db=db,
        assignment_id=assignment_id,
        revoked_by_id=current_user.id,
    )
    return {
        "id": ea.id,
        "user_id": ea.user_id,
        "scope_type": "ENVIRONMENT",
        "scope_value": ea.environment,
        "host_id": None,
        "status": ea.status,
        "granted_by_id": ea.granted_by_id,
        "revoked_by_id": ea.revoked_by_id,
        "created_at": ea.created_at,
        "revoked_at": ea.revoked_at,
    }


@router.post("/hosts", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_user_to_host(
    req: HostAssignmentCreate,
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Grants a user operational access to a specific host. Requires SUPER_ADMIN role.
    """
    ha = grant_host_assignment(
        db=db,
        user_id=req.user_id,
        host_id=req.host_id,
        granted_by_id=current_user.id,
    )
    from backend.app.models.host import Host
    host = db.get(Host, ha.host_id)
    hostname = host.hostname if host else f"Host #{ha.host_id}"

    return {
        "id": ha.id,
        "user_id": ha.user_id,
        "scope_type": "HOST",
        "scope_value": hostname,
        "host_id": ha.host_id,
        "status": ha.status,
        "granted_by_id": ha.granted_by_id,
        "revoked_by_id": ha.revoked_by_id,
        "created_at": ha.created_at,
        "revoked_at": ha.revoked_at,
    }


@router.delete("/hosts/{assignment_id}", response_model=AssignmentResponse)
def revoke_user_host_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Revokes a host assignment. Requires SUPER_ADMIN role.
    """
    ha = revoke_host_assignment(
        db=db,
        assignment_id=assignment_id,
        revoked_by_id=current_user.id,
    )
    from backend.app.models.host import Host
    host = db.get(Host, ha.host_id)
    hostname = host.hostname if host else f"Host #{ha.host_id}"

    return {
        "id": ha.id,
        "user_id": ha.user_id,
        "scope_type": "HOST",
        "scope_value": hostname,
        "host_id": ha.host_id,
        "status": ha.status,
        "granted_by_id": ha.granted_by_id,
        "revoked_by_id": ha.revoked_by_id,
        "created_at": ha.created_at,
        "revoked_at": ha.revoked_at,
    }

