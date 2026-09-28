"""
Audit Logs API Router.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_admin
from backend.app.models.user import User
from backend.app.schemas.report import AuditLogRead, AuditLogCreate
from backend.app.services.audit_service import get_audit_logs, record_audit_action

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("/logs", response_model=List[AuditLogRead])
def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action name"),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retrieves recent administrative action audit records. Requires ADMIN role."""
    logs = get_audit_logs(db, action=action, limit=limit)
    return [
        AuditLogRead(
            id=l.id,
            user_email=l.user_email,
            action=l.action,
            target_resource=l.target_resource,
            details=l.details,
            result=l.result,
            client_ip=l.client_ip,
            timestamp=l.timestamp,
        )
        for l in logs
    ]


@router.post("/logs", response_model=AuditLogRead, status_code=status.HTTP_201_CREATED)
def create_audit_log(
    log_in: AuditLogCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Records an administrative event into the audit trail. Requires ADMIN role."""
    log = record_audit_action(
        db=db,
        user_email=log_in.user_email or current_user.email,
        action=log_in.action,
        target_resource=log_in.target_resource,
        details=log_in.details,
        result=log_in.result,
        client_ip=log_in.client_ip,
    )
    return AuditLogRead(
        id=log.id,
        user_email=log.user_email,
        action=log.action,
        target_resource=log.target_resource,
        details=log.details,
        result=log.result,
        client_ip=log.client_ip,
        timestamp=log.timestamp,
    )
