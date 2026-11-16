"""
Diagnostics API Router (Phase 9A.1 Predefined Remote Diagnostics).

Provides secure endpoints for:
- Dispatching predefined diagnostics with atomic conditional validation.
- Agent polling and command claiming with lease bounds.
- Idempotent and cryptographically verified result reporting.
- Diagnostic execution history inspection.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.api.deps import (
    get_db,
    get_current_user,
    get_current_operator,
    get_current_viewer,
    get_current_super_admin,
    verify_agent_credentials,
)
from backend.app.models.user import User, UserRole
from backend.app.models.host import Host
from backend.app.models.device import DeviceEnrollment
from backend.app.models.diagnostic import (
    DiagnosticCommand,
    DiagnosticResult,
    DiagnosticAction,
    DiagnosticStatus,
)
from backend.app.schemas.diagnostic import (
    DiagnosticDispatchCreate,
    DiagnosticResultCreate,
    DiagnosticCommandResponse,
    DiagnosticResultResponse,
    DiagnosticCommandClaim,
)
from backend.app.services.assignment_service import check_user_host_access
from backend.app.services.diagnostic_service import (
    dispatch_diagnostic_command,
    claim_pending_command,
    record_diagnostic_result,
    sweep_expired_diagnostic_leases,
)

router = APIRouter(prefix="/diagnostics", tags=["Remote Diagnostics"])


@router.get("/actions", response_model=List[str])
def get_allowed_actions(current_user: User = Depends(get_current_viewer)):
    """Returns the strict whitelist of predefined diagnostic actions based on user role and system policy."""
    actions = list(DiagnosticAction.STANDARD_ACTIONS)
    if getattr(settings, "enable_remote_power_operations", True):
        if current_user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
            actions.extend(DiagnosticAction.POWER_ACTIONS)
    return actions


@router.post("/dispatch", response_model=DiagnosticCommandResponse, status_code=status.HTTP_201_CREATED)
def dispatch_command(
    req: DiagnosticDispatchCreate,
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """
    Dispatches a predefined diagnostic command to a target host.
    Requires OPERATOR, ADMIN, or SUPER_ADMIN role with active host/environment assignment.
    """
    cmd = dispatch_diagnostic_command(db=db, dispatch_in=req, requesting_user=current_user)
    host = db.get(Host, cmd.host_id)
    cmd_dict = {
        "id": cmd.id,
        "host_id": cmd.host_id,
        "hostname": host.hostname if host else None,
        "action": cmd.action,
        "target": cmd.target,
        "timeout_seconds": cmd.timeout_seconds,
        "status": cmd.status,
        "requested_by_user_id": cmd.requested_by_user_id,
        "claimed_at": cmd.claimed_at,
        "claimed_by_agent_id": cmd.claimed_by_agent_id,
        "completed_at": cmd.completed_at,
        "failure_reason": cmd.failure_reason,
        "created_at": cmd.created_at,
        "updated_at": cmd.updated_at,
        "result": None,
    }
    return cmd_dict


@router.get("/commands/poll", response_model=Optional[DiagnosticCommandClaim])
def poll_pending_command(
    host_id: Optional[int] = Query(None, description="Host ID (optional if resolved from agent credentials)"),
    agent_info: Dict[str, Any] = Depends(verify_agent_credentials),
    db: Session = Depends(get_db),
):
    """
    Polled by the host sidecar agent to claim the next queued diagnostic command.
    Authenticates via agent credentials and reserves command under a bounded lease.
    """
    target_host_id = host_id

    # If host_id is not provided, resolve from agent credentials or enrollment
    if target_host_id is None:
        device_uuid = agent_info.get("device_uuid")
        if device_uuid:
            dev = db.scalar(select(DeviceEnrollment).where(DeviceEnrollment.device_uuid == device_uuid))
            if dev and dev.assigned_name:
                h = db.scalar(select(Host).where(Host.hostname == dev.assigned_name))
                if h:
                    target_host_id = h.id

    if target_host_id is None:
        agent_name = str(agent_info.get("name") or "")
        # Match against Host.hostname (e.g. PC-Room1-01 in PC-Room1-01-Canary)
        for h in db.scalars(select(Host)).all():
            if h.hostname and (h.hostname in agent_name or agent_name.startswith(h.hostname)):
                target_host_id = h.id
                break

    if target_host_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to resolve target host ID from agent credentials.",
        )

    agent_id = str(agent_info.get("name") or agent_info.get("device_uuid") or "agent")
    cmd = claim_pending_command(db=db, host_id=target_host_id, agent_id=agent_id)
    if not cmd:
        return None

    return {
        "id": cmd.id,
        "action": cmd.action,
        "target": cmd.target,
        "timeout_seconds": cmd.timeout_seconds,
        "lease_expires_at": cmd.lease_expires_at,
        "hard_deadline_at": cmd.hard_deadline_at,
    }


@router.post("/commands/{command_id}/result", response_model=DiagnosticResultResponse)
def submit_command_result(
    command_id: str,
    result_in: DiagnosticResultCreate,
    agent_info: Dict[str, Any] = Depends(verify_agent_credentials),
    db: Session = Depends(get_db),
):
    """
    Submits execution output from the diagnostic worker.
    Enforces canonical payload hashing, idempotency, conflict detection, and lease deadlines.
    """
    if result_in.command_id != command_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload command_id does not match URL path parameter.",
        )

    result, is_idempotent = record_diagnostic_result(
        db=db,
        command_id=command_id,
        result_in=result_in,
    )
    return result


@router.get("/commands/{command_id}", response_model=DiagnosticCommandResponse)
def get_command_details(
    command_id: str,
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Retrieves full details and output result for a specific diagnostic command.
    Enforces hybrid RBAC scoping on the target host.
    """
    cmd = db.get(DiagnosticCommand, command_id)
    if not cmd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic command not found")

    host = db.get(Host, cmd.host_id)
    if not host or not check_user_host_access(db, current_user, host):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to host diagnostics")

    cmd_dict = {
        "id": cmd.id,
        "host_id": cmd.host_id,
        "hostname": host.hostname if host else None,
        "action": cmd.action,
        "target": cmd.target,
        "timeout_seconds": cmd.timeout_seconds,
        "status": cmd.status,
        "requested_by_user_id": cmd.requested_by_user_id,
        "claimed_at": cmd.claimed_at,
        "claimed_by_agent_id": cmd.claimed_by_agent_id,
        "completed_at": cmd.completed_at,
        "failure_reason": cmd.failure_reason,
        "created_at": cmd.created_at,
        "updated_at": cmd.updated_at,
        "result": cmd.result,
    }
    return cmd_dict


@router.get("/history", response_model=List[DiagnosticCommandResponse])
def get_diagnostic_history(
    host_id: Optional[int] = Query(None, description="Filter by Host ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Queries historical diagnostic commands with role-based scoping and filtering.
    """
    stmt = select(DiagnosticCommand).order_by(desc(DiagnosticCommand.created_at))

    if host_id is not None:
        host = db.get(Host, host_id)
        if not host or not check_user_host_access(db, current_user, host):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this host")
        stmt = stmt.where(DiagnosticCommand.host_id == host_id)
    else:
        # If not super admin, restrict to assigned environments and hosts
        if current_user.role != UserRole.SUPER_ADMIN:
            from backend.app.models.assignment import (
                UserEnvironmentAssignment,
                UserHostAssignment,
                AssignmentStatus,
            )
            stmt = stmt.join(Host, DiagnosticCommand.host_id == Host.id).where(
                (
                    Host.id.in_(
                        select(UserHostAssignment.host_id).where(
                            and_(
                                UserHostAssignment.user_id == current_user.id,
                                UserHostAssignment.status == AssignmentStatus.ACTIVE,
                            )
                        )
                    )
                )
                | (
                    Host.environment.in_(
                        select(UserEnvironmentAssignment.environment).where(
                            and_(
                                UserEnvironmentAssignment.user_id == current_user.id,
                                UserEnvironmentAssignment.status == AssignmentStatus.ACTIVE,
                            )
                        )
                    )
                )
            )

    if status_filter:
        stmt = stmt.where(DiagnosticCommand.status == status_filter)

    stmt = stmt.limit(limit).offset(offset)
    commands = db.scalars(stmt).all()

    results = []
    for c in commands:
        h = db.get(Host, c.host_id)
        results.append({
            "id": c.id,
            "host_id": c.host_id,
            "hostname": h.hostname if h else None,
            "action": c.action,
            "target": c.target,
            "timeout_seconds": c.timeout_seconds,
            "status": c.status,
            "requested_by_user_id": c.requested_by_user_id,
            "claimed_at": c.claimed_at,
            "claimed_by_agent_id": c.claimed_by_agent_id,
            "completed_at": c.completed_at,
            "failure_reason": c.failure_reason,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "result": c.result,
        })
    return results


@router.post("/sweep", response_model=Dict[str, Any])
def trigger_lease_sweeper(
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Sweeps abandoned or expired diagnostic leases. Requires SUPER_ADMIN role.
    """
    swept = sweep_expired_diagnostic_leases(db)
    return {"status": "ok", "swept_count": swept}

