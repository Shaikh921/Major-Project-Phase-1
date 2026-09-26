"""
Audit Log and Administrative Tracking Service.
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.app.models.security import AuditLog
from backend.app.schemas.report import AuditLogRead, AuditLogCreate


def record_audit_action(
    db: Session,
    action: str,
    target_resource: str,
    details: str,
    user_email: str = "admin@ops.local",
    result: str = "success",
    client_ip: Optional[str] = None,
) -> AuditLog:
    """Appends an administrative operation to the audit log."""
    log = AuditLog(
        user_email=user_email,
        action=action,
        target_resource=target_resource,
        details=details,
        result=result,
        client_ip=client_ip,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_audit_logs(
    db: Session,
    action: Optional[str] = None,
    limit: int = 100,
) -> List[AuditLog]:
    """Queries recent audit log entries."""
    stmt = select(AuditLog).order_by(desc(AuditLog.timestamp))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())
