"""
Diagnostic Service for Phase 9A.1 Predefined Remote Diagnostics.

Provides:
- Atomic database-level conditional dispatch with SQLite BEGIN IMMEDIATE locking.
- Command claiming with lease windows and hard lifetime deadlines.
- Canonical SHA-256 result persistence with idempotency, conflict detection, and immutable terminal states.
- Background lease expiration sweeper.
"""

import json
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, text
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.core.config import settings
from backend.app.core.validator import validate_diagnostic_target, validate_power_action_target
from backend.app.models.user import User, UserRole
from backend.app.models.host import Host
from backend.app.models.diagnostic import (
    DiagnosticCommand,
    DiagnosticResult,
    DiagnosticAction,
    DiagnosticStatus,
)
from backend.app.models.security import AuditLog
from backend.app.schemas.diagnostic import DiagnosticDispatchCreate, DiagnosticResultCreate


LEASE_BUFFER_SECONDS = 30
LATE_GRACE_SECONDS = 300
MAX_COMMAND_LIFETIME_SECONDS = 3600
MAX_OUTPUT_BYTES = 16384


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures a datetime object is timezone-aware UTC for safe comparisons with SQLite."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_canonical_payload_hash(
    command_uuid: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    payload: Optional[Dict[str, Any]],
) -> Tuple[str, str, str]:
    """
    Truncates output at 16KB UTF-8 byte boundary, validates non-finite numbers,
    and computes a deterministic SHA-256 hash over canonical JSON serialization.
    Returns (sha256_hash, clean_stdout, clean_stderr).
    """
    stdout_bytes = (stdout or "").encode("utf-8")[:MAX_OUTPUT_BYTES]
    stderr_bytes = (stderr or "").encode("utf-8")[:MAX_OUTPUT_BYTES]

    clean_stdout = stdout_bytes.decode("utf-8", errors="ignore")
    clean_stderr = stderr_bytes.decode("utf-8", errors="ignore")

    canonical_data = {
        "command_uuid": str(command_uuid),
        "exit_code": int(exit_code),
        "stdout": clean_stdout,
        "stderr": clean_stderr,
        "payload": payload if isinstance(payload, dict) else {},
    }

    try:
        canonical_bytes = json.dumps(
            canonical_data,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            ensure_ascii=False,
        ).encode("utf-8")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload format: Non-finite floats (NaN/Infinity) are rejected: {str(e)}",
        )

    digest = hashlib.sha256(canonical_bytes).hexdigest()
    return digest, clean_stdout, clean_stderr


def dispatch_diagnostic_command(
    db: Session,
    dispatch_in: DiagnosticDispatchCreate,
    requesting_user: User,
) -> DiagnosticCommand:
    """
    Dispatches a predefined diagnostic command using atomic conditional insert.
    Guarantees writer serialization via SQLite BEGIN IMMEDIATE and eliminates
    check-then-act race conditions against host deactivation or assignment revocation.
    """
    # 1. Action Whitelist Validation
    if dispatch_in.action not in DiagnosticAction.ALL_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action '{dispatch_in.action}' is not permitted. Allowed actions: {DiagnosticAction.ALL_ACTIONS}",
        )

    # 2. Privileged Remote Power Operations Policy Gate
    if dispatch_in.action in DiagnosticAction.POWER_ACTIONS:
        if not getattr(settings, "enable_remote_power_operations", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Remote power operations (reboot/shutdown/abort) are globally disabled by system policy.",
            )
        if requesting_user.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action '{dispatch_in.action}' is privileged and strictly restricted to Administrators and Super Administrators.",
            )
        try:
            cleaned_target = validate_power_action_target(dispatch_in.action, dispatch_in.target)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Power operation parameter validation failed: {str(e)}",
            )
    else:
        # Strict RFC 1123 Target Validation for Standard Diagnostics
        try:
            cleaned_target = validate_diagnostic_target(dispatch_in.target)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target validation failed: {str(e)}",
            )

    # 3. Role Gate: Viewers are strictly prohibited
    if requesting_user.role == UserRole.VIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="VIEWER role does not have permission to dispatch diagnostic commands.",
        )

    command_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    is_super_admin = 1 if requesting_user.role == UserRole.SUPER_ADMIN else 0

    conn = db.connection()
    # Acquire SQLite RESERVED write lock immediately
    conn.exec_driver_sql("BEGIN IMMEDIATE")

    # 4. Atomic Database-Level Conditional Insert
    conditional_sql = text("""
        INSERT INTO diagnostic_commands (
            id, host_id, action, target, timeout_seconds, status,
            requested_by_user_id, created_at, updated_at
        )
        SELECT 
            :command_id, :host_id, :action, :target, :timeout_seconds, 'PENDING',
            :user_id, :now, :now
        FROM hosts h
        WHERE h.id = :host_id
          AND h.is_active = 1
          AND (
              :is_super_admin = 1
              OR EXISTS (
                  SELECT 1 FROM user_environment_assignments uea
                  WHERE uea.user_id = :user_id
                    AND uea.environment = h.environment
                    AND uea.status = 'ACTIVE'
              )
              OR EXISTS (
                  SELECT 1 FROM user_host_assignments uha
                  WHERE uha.user_id = :user_id
                    AND uha.host_id = h.id
                    AND uha.status = 'ACTIVE'
              )
          );
    """)

    result = conn.execute(
        conditional_sql,
        {
            "command_id": command_id,
            "host_id": dispatch_in.host_id,
            "action": dispatch_in.action,
            "target": cleaned_target,
            "timeout_seconds": dispatch_in.timeout_seconds,
            "user_id": requesting_user.id,
            "is_super_admin": is_super_admin,
            "now": now,
        },
    )

    if result.rowcount == 0:
        db.rollback()
        # Differentiate between host not found vs unauthorized / inactive
        host = db.get(Host, dispatch_in.host_id)
        if not host:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")
        if not host.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Host is decommissioned or inactive")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to dispatch diagnostics on this host or environment.",
        )

    # 5. Insert Audit Log in the same physical transaction
    audit_action = (
        f"REMOTE_POWER_OPERATION_{dispatch_in.action}"
        if dispatch_in.action in DiagnosticAction.POWER_ACTIONS
        else "DISPATCH_DIAGNOSTIC"
    )
    audit = AuditLog(
        user_email=requesting_user.email,
        action=audit_action,
        target_resource=f"Host #{dispatch_in.host_id} -> {dispatch_in.action}",
        details=f"Dispatched predefined diagnostic '{dispatch_in.action}' (UUID: {command_id}, parameters: '{cleaned_target}').",
        result="success",
    )
    db.add(audit)
    db.commit()

    return db.get(DiagnosticCommand, command_id)


def claim_pending_command(
    db: Session,
    host_id: int,
    agent_id: str,
) -> Optional[DiagnosticCommand]:
    """
    Atomically claims the next PENDING diagnostic command for the requesting host agent.
    Grants a bounded lease and calculates the hard deadline.
    """
    conn = db.connection()
    conn.exec_driver_sql("BEGIN IMMEDIATE")

    # Find oldest pending command for this host
    command = db.scalar(
        select(DiagnosticCommand)
        .where(
            and_(
                DiagnosticCommand.host_id == host_id,
                DiagnosticCommand.status == DiagnosticStatus.PENDING,
            )
        )
        .order_by(DiagnosticCommand.created_at.asc())
        .limit(1)
    )

    if not command:
        db.rollback()
        return None

    now = datetime.now(timezone.utc)
    lease_expires = now + timedelta(seconds=command.timeout_seconds + LEASE_BUFFER_SECONDS)
    hard_deadline = command.created_at + timedelta(seconds=MAX_COMMAND_LIFETIME_SECONDS)

    command.status = DiagnosticStatus.CLAIMED
    command.claimed_at = now
    command.claimed_by_agent_id = agent_id
    command.lease_expires_at = lease_expires
    command.hard_deadline_at = hard_deadline
    command.updated_at = now

    db.commit()
    db.refresh(command)
    return command


def record_diagnostic_result(
    db: Session,
    command_id: str,
    result_in: DiagnosticResultCreate,
) -> Tuple[DiagnosticResult, bool]:
    """
    Atomically records the execution result submitted by the sidecar.
    Returns (result, is_idempotent_ack).
    """
    conn = db.connection()
    conn.exec_driver_sql("BEGIN IMMEDIATE")

    command = db.get(DiagnosticCommand, command_id)
    if not command:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic command not found")

    server_now = datetime.now(timezone.utc)

    # 1. Compute canonical hash and clean buffers
    payload_hash, stdout_clean, stderr_clean = compute_canonical_payload_hash(
        command_uuid=command_id,
        exit_code=result_in.exit_code,
        stdout=result_in.stdout,
        stderr=result_in.stderr,
        payload=result_in.payload,
    )

    # 2. Check for duplicate submission
    existing_result = db.scalar(
        select(DiagnosticResult).where(DiagnosticResult.command_id == command_id)
    )

    if existing_result:
        db.rollback()
        if existing_result.payload_hash == payload_hash:
            # Idempotent retry: return existing result cleanly
            return existing_result, True
        else:
            # Conflicting payload submitted for already completed command!
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflicting result payload already recorded for this command.",
            )

    # 3. Check hard deadline and late grace window
    is_late = False
    hard_deadline = ensure_utc(command.hard_deadline_at)
    lease_expires = ensure_utc(command.lease_expires_at)

    if hard_deadline and server_now > hard_deadline:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Result rejected: Maximum command lifetime exceeded.",
        )

    if lease_expires and server_now > lease_expires:
        is_late = True
        if server_now > lease_expires + timedelta(seconds=LATE_GRACE_SECONDS):
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Result rejected: Grace window for late submission has expired.",
            )

    # 4. State Transition (Preserves Terminal State Immutability)
    if command.status == DiagnosticStatus.TIMED_OUT:
        # Command was already timed out: do NOT mutate terminal status
        pass
    else:
        # Transition CLAIMED to COMPLETED or FAILED
        if result_in.exit_code == 0:
            command.status = DiagnosticStatus.COMPLETED
        else:
            command.status = DiagnosticStatus.FAILED
            command.failure_reason = result_in.failure_reason or f"Process exited with code {result_in.exit_code}"

    command.completed_at = server_now
    command.updated_at = server_now

    # 5. Insert DiagnosticResult
    result = DiagnosticResult(
        command_id=command_id,
        exit_code=result_in.exit_code,
        stdout=stdout_clean,
        stderr=stderr_clean,
        payload=result_in.payload,
        payload_hash=payload_hash,
        failure_reason=result_in.failure_reason,
        is_late=is_late,
        received_at=server_now,
        created_at=server_now,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result, False


def sweep_expired_diagnostic_leases(db: Session) -> int:
    """
    Sweeps orphaned CLAIMED commands whose lease has expired without renewal or result.
    Transitions them to TIMED_OUT with failure_reason = 'LEASE_EXPIRED'.
    """
    now = datetime.now(timezone.utc)
    updated_count = db.query(DiagnosticCommand).filter(
        and_(
            DiagnosticCommand.status == DiagnosticStatus.CLAIMED,
            DiagnosticCommand.lease_expires_at < now,
        )
    ).update(
        {
            "status": DiagnosticStatus.TIMED_OUT,
            "failure_reason": "LEASE_EXPIRED",
            "updated_at": now,
        },
        synchronize_session=False,
    )
    if updated_count > 0:
        db.commit()
    return updated_count
