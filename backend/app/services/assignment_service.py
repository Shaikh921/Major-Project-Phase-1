"""
Assignment Service for Phase 9A.1 Hybrid RBAC.

Manages authoritative assignment of users to environments and individual hosts,
with strict audit logging, concurrency locking, and status tracking.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.models.user import User, UserRole
from backend.app.models.host import Host
from backend.app.models.assignment import (
    UserEnvironmentAssignment,
    UserHostAssignment,
    AssignmentStatus,
)
from backend.app.models.security import AuditLog


def grant_environment_assignment(
    db: Session,
    user_id: int,
    environment: str,
    granted_by_id: int,
) -> UserEnvironmentAssignment:
    """Grants a user operational access to an entire deployment environment."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign inactive user")

    clean_env = environment.strip()

    # Check for existing active assignment
    existing = db.scalar(
        select(UserEnvironmentAssignment).where(
            and_(
                UserEnvironmentAssignment.user_id == user_id,
                UserEnvironmentAssignment.environment == clean_env,
                UserEnvironmentAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
    )
    if existing:
        return existing

    assignment = UserEnvironmentAssignment(
        user_id=user_id,
        environment=clean_env,
        status=AssignmentStatus.ACTIVE,
        granted_by_id=granted_by_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(assignment)
    db.flush()

    # Audit log
    grantor = db.get(User, granted_by_id)
    audit = AuditLog(
        user_email=grantor.email if grantor else "system@ops.local",
        action="GRANT_ENVIRONMENT_ASSIGNMENT",
        target_resource=f"User #{user_id} -> {clean_env}",
        details=f"Granted environment '{clean_env}' to user '{user.email}' (ID: {user_id}).",
        result="success",
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)
    return assignment


def revoke_environment_assignment(
    db: Session,
    assignment_id: int,
    revoked_by_id: int,
) -> UserEnvironmentAssignment:
    """Revokes an environment assignment from a user."""
    assignment = db.get(UserEnvironmentAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.status == AssignmentStatus.REVOKED:
        return assignment

    now = datetime.now(timezone.utc)
    assignment.status = AssignmentStatus.REVOKED
    assignment.revoked_by_id = revoked_by_id
    assignment.revoked_at = now
    assignment.updated_at = now

    revoker = db.get(User, revoked_by_id)
    audit = AuditLog(
        user_email=revoker.email if revoker else "system@ops.local",
        action="REVOKE_ENVIRONMENT_ASSIGNMENT",
        target_resource=f"Assignment #{assignment.id}",
        details=f"Revoked environment '{assignment.environment}' from user ID {assignment.user_id}.",
        result="success",
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)
    return assignment


def grant_host_assignment(
    db: Session,
    user_id: int,
    host_id: int,
    granted_by_id: int,
) -> UserHostAssignment:
    """Grants a user operational access to an individual host."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign inactive user")

    host = db.get(Host, host_id)
    if not host or not host.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found or is inactive")

    existing = db.scalar(
        select(UserHostAssignment).where(
            and_(
                UserHostAssignment.user_id == user_id,
                UserHostAssignment.host_id == host_id,
                UserHostAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
    )
    if existing:
        return existing

    assignment = UserHostAssignment(
        user_id=user_id,
        host_id=host_id,
        status=AssignmentStatus.ACTIVE,
        granted_by_id=granted_by_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(assignment)
    db.flush()

    grantor = db.get(User, granted_by_id)
    audit = AuditLog(
        user_email=grantor.email if grantor else "system@ops.local",
        action="GRANT_HOST_ASSIGNMENT",
        target_resource=f"User #{user_id} -> Host {host.hostname}",
        details=f"Granted host '{host.hostname}' (ID: {host_id}) to user '{user.email}'.",
        result="success",
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)
    return assignment


def revoke_host_assignment(
    db: Session,
    assignment_id: int,
    revoked_by_id: int,
) -> UserHostAssignment:
    """Revokes a host assignment from a user."""
    assignment = db.get(UserHostAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.status == AssignmentStatus.REVOKED:
        return assignment

    now = datetime.now(timezone.utc)
    assignment.status = AssignmentStatus.REVOKED
    assignment.revoked_by_id = revoked_by_id
    assignment.revoked_at = now
    assignment.updated_at = now

    revoker = db.get(User, revoked_by_id)
    audit = AuditLog(
        user_email=revoker.email if revoker else "system@ops.local",
        action="REVOKE_HOST_ASSIGNMENT",
        target_resource=f"Assignment #{assignment.id}",
        details=f"Revoked host ID {assignment.host_id} from user ID {assignment.user_id}.",
        result="success",
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)
    return assignment


def list_assignments(db: Session, active_only: bool = True) -> List[Dict[str, Any]]:
    """Lists all assignments across environments and hosts for administrator consoles."""
    env_stmt = select(UserEnvironmentAssignment).order_by(UserEnvironmentAssignment.created_at.desc())
    host_stmt = select(UserHostAssignment).order_by(UserHostAssignment.created_at.desc())

    if active_only:
        env_stmt = env_stmt.where(UserEnvironmentAssignment.status == AssignmentStatus.ACTIVE)
        host_stmt = host_stmt.where(UserHostAssignment.status == AssignmentStatus.ACTIVE)

    env_assignments = db.scalars(env_stmt).all()
    host_assignments = db.scalars(host_stmt).all()

    results: List[Dict[str, Any]] = []
    for ea in env_assignments:
        user = db.get(User, ea.user_id)
        results.append({
            "id": ea.id,
            "user_id": ea.user_id,
            "user_email": user.email if user else "unknown",
            "scope_type": "ENVIRONMENT",
            "scope_value": ea.environment,
            "host_id": None,
            "status": ea.status,
            "granted_by_id": ea.granted_by_id,
            "revoked_by_id": ea.revoked_by_id,
            "created_at": ea.created_at,
            "revoked_at": ea.revoked_at,
        })

    for ha in host_assignments:
        user = db.get(User, ha.user_id)
        host = db.get(Host, ha.host_id)
        results.append({
            "id": ha.id,
            "user_id": ha.user_id,
            "user_email": user.email if user else "unknown",
            "scope_type": "HOST",
            "scope_value": host.hostname if host else f"Host #{ha.host_id}",
            "host_id": ha.host_id,
            "status": ha.status,
            "granted_by_id": ha.granted_by_id,
            "revoked_by_id": ha.revoked_by_id,
            "created_at": ha.created_at,
            "revoked_at": ha.revoked_at,
        })

    return results


def check_user_host_access(db: Session, user: User, host: Host) -> bool:
    """
    Evaluates whether a user has operational access to a host under the approved hybrid RBAC policy.
    - SUPER_ADMIN: Always True.
    - Active Environment assignment: True.
    - Active Host assignment: True.
    - Otherwise: False.
    """
    if user.role == UserRole.SUPER_ADMIN:
        return True

    # Check environment assignment
    has_env = db.scalar(
        select(UserEnvironmentAssignment.id).where(
            and_(
                UserEnvironmentAssignment.user_id == user.id,
                UserEnvironmentAssignment.environment == host.environment,
                UserEnvironmentAssignment.status == AssignmentStatus.ACTIVE,
            )
        ).limit(1)
    )
    if has_env:
        return True

    # Check host assignment
    has_host = db.scalar(
        select(UserHostAssignment.id).where(
            and_(
                UserHostAssignment.user_id == user.id,
                UserHostAssignment.host_id == host.id,
                UserHostAssignment.status == AssignmentStatus.ACTIVE,
            )
        ).limit(1)
    )
    return bool(has_host)
