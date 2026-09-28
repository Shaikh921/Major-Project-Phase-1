"""
Super Administrator Management API Router.

Strictly restricted to SUPER_ADMIN authority.
Provides endpoints for:
- Viewing admin access request queue and stats.
- Approving and rejecting admin requests.
- Viewing system administrators and session counts.
- Disabling, enabling, revoking sessions, forcing password reset, and soft-deleting administrators.
- Invariant safety guards preventing removal/disabling of the last remaining Super Admin.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_super_admin
from backend.app.models.user import User
from backend.app.core.config import settings
from backend.app.schemas.auth import (
    AdminSummaryStats,
    AdminRegistrationRequestRead,
    AdminRequestReject,
    AdminUserRead,
    MessageResponse,
    SmtpTestRequest,
    SmtpTestResponse,
)
from backend.app.services.email_service import EmailService
from backend.app.services.audit_service import record_audit_action
from backend.app.services.auth_service import (
    get_admin_summary_stats,
    get_admin_requests,
    get_admin_request_by_id,
    approve_admin_request,
    reject_admin_request,
    get_all_admin_users,
    get_admin_user_details,
    disable_admin_user,
    enable_admin_user,
    revoke_admin_user_sessions,
    force_admin_password_reset,
    soft_delete_admin_user,
)

router = APIRouter(prefix="/admin", tags=["Super Administrator Management"])


@router.get("/stats", response_model=AdminSummaryStats)
def get_stats(
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Retrieves summary counts for Super Admin overview dashboard.
    """
    return get_admin_summary_stats(db)


@router.get("/requests", response_model=List[AdminRegistrationRequestRead])
def list_requests(
    status: Optional[str] = Query(None, description="Filter requests by status"),
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Lists all administrator registration requests, optionally filtered by status.
    """
    requests = get_admin_requests(db, status_filter=status)
    return [AdminRegistrationRequestRead.model_validate(r) for r in requests]


@router.get("/requests/{id}", response_model=AdminRegistrationRequestRead)
def get_request_details(
    id: int,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Retrieves full details of a specific administrator registration request.
    """
    req = get_admin_request_by_id(db, id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin request #{id} not found.",
        )
    return AdminRegistrationRequestRead.model_validate(req)


@router.post("/requests/{id}/approve", response_model=MessageResponse)
def approve_request(
    id: int,
    request: Request,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Approves a verified admin access request, provisions an inactive user,
    and dispatches a single-use activation email.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    req, user, _ = approve_admin_request(
        db=db,
        request_id=id,
        current_super_admin=current_super_admin,
        client_ip=client_ip,
    )
    return MessageResponse(
        message=f"Admin request #{id} for '{req.email}' approved. Activation instructions have been dispatched."
    )


@router.post("/requests/{id}/reject", response_model=MessageResponse)
def reject_request(
    id: int,
    reject_in: Optional[AdminRequestReject] = None,
    request: Request = None,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Rejects a pending admin access request with an optional reason and sends notification.
    """
    client_ip = request.client.host if request and request.client else "127.0.0.1"
    reason = reject_in.reason if reject_in else None
    req = reject_admin_request(
        db=db,
        request_id=id,
        current_super_admin=current_super_admin,
        reason=reason,
        client_ip=client_ip,
    )
    return MessageResponse(message=f"Admin request #{id} for '{req.email}' has been rejected.")


@router.get("/users", response_model=List[AdminUserRead])
def list_admin_users(
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Lists all administrator accounts with active session counts.
    """
    users = get_all_admin_users(db)
    return [AdminUserRead.model_validate(u) for u in users]


@router.get("/users/{id}", response_model=AdminUserRead)
def get_admin_user(
    id: int,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Retrieves detailed account information for an administrator.
    """
    details = get_admin_user_details(db, id)
    return AdminUserRead.model_validate(details)


@router.post("/users/{id}/disable", response_model=MessageResponse)
def disable_user(
    id: int,
    request: Request,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Disables an administrator account and revokes all active refresh sessions.
    Guarded by the Last Super Admin safety rule.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    target = disable_admin_user(
        db=db,
        target_user_id=id,
        current_super_admin=current_super_admin,
        client_ip=client_ip,
    )
    return MessageResponse(message=f"Administrator '{target.email}' disabled and active sessions revoked.")


@router.post("/users/{id}/enable", response_model=MessageResponse)
def enable_user(
    id: int,
    request: Request,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Reactivates an eligible disabled administrator account.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    target = enable_admin_user(
        db=db,
        target_user_id=id,
        current_super_admin=current_super_admin,
        client_ip=client_ip,
    )
    return MessageResponse(message=f"Administrator '{target.email}' successfully reactivated.")


@router.post("/users/{id}/revoke-sessions", response_model=MessageResponse)
def revoke_sessions(
    id: int,
    request: Request,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Revokes all active refresh sessions for an administrator.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    revoked_count = revoke_admin_user_sessions(
        db=db,
        target_user_id=id,
        current_super_admin=current_super_admin,
        client_ip=client_ip,
    )
    return MessageResponse(message=f"Revoked {revoked_count} active session(s).")


@router.post("/users/{id}/force-password-reset", response_model=MessageResponse)
def force_reset(
    id: int,
    request: Request,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Forces a secure password reset flow for an administrator.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    msg = force_admin_password_reset(
        db=db,
        target_user_id=id,
        current_super_admin=current_super_admin,
        client_ip=client_ip,
    )
    return MessageResponse(message=msg)


@router.delete("/users/{id}", response_model=MessageResponse)
def soft_delete_user(
    id: int,
    request: Request,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Performs a safe soft-delete / deactivation of an administrator account.
    Preserves historical audit log attribution while immediately cutting off access.
    Guarded by the Last Super Admin safety rule.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    target = soft_delete_admin_user(
        db=db,
        target_user_id=id,
        current_super_admin=current_super_admin,
        client_ip=client_ip,
    )
    return MessageResponse(message=f"Administrator '{target.email}' deactivated and soft-deleted. Audit logs preserved.")


@router.post("/email/test", response_model=SmtpTestResponse)
def test_smtp_connection(
    req: SmtpTestRequest,
    request: Request,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Diagnostic endpoint for Super Administrators to test SMTP delivery channel.
    Synchronously verifies connection and dispatches diagnostic test email.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    success, message = EmailService.send_test_email(recipient_email=str(req.recipient))
    mode = "SMTP_LIVE" if settings.smtp_enabled else "DEV_OUTBOX"

    record_audit_action(
        db=db,
        action="SMTP_DIAGNOSTIC_TEST",
        target_resource="Email Delivery Subsystem",
        details=f"Super Admin '{current_super_admin.email}' ran SMTP test to '{req.recipient}'. Result: {'SUCCESS' if success else 'FAILED'} (Mode: {mode}).",
        user_email=current_super_admin.email,
        result="success" if success else "failure",
        client_ip=client_ip,
    )

    return SmtpTestResponse(
        success=success,
        status="DELIVERED" if success else "FAILED",
        message=message,
        recipient=str(req.recipient),
        mode=mode,
    )
