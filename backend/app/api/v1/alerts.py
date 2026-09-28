"""
Alerts and Rules API Router.

Endpoints for managing active/historical alerts, operator acknowledgment,
feedback tagging (M5-FR6), and threshold rule configurations (M1-FR5).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    get_db,
    get_current_viewer,
    get_current_operator,
    get_current_admin,
)
from backend.app.models.user import User
from backend.app.schemas.alert import (
    AlertRead,
    AlertRuleCreate,
    AlertRuleRead,
    AlertRuleUpdate,
    AlertFeedbackCreate,
    AlertFeedbackRead,
)
from backend.app.services.alert_service import (
    get_alerts,
    get_alert,
    acknowledge_alert,
    record_alert_feedback,
    create_alert_rule,
    get_rules,
    get_rule,
    update_alert_rule,
    delete_alert_rule,
)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# --- Alert Operations ---

@router.get("", response_model=List[AlertRead])
def list_alerts(
    host_id: Optional[int] = Query(None, description="Filter by Host ID"),
    status: Optional[str] = Query(None, description="Filter by status: active, acknowledged, resolved"),
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, critical"),
    kind: Optional[str] = Query(None, description="Filter by kind: threshold, anomaly, forecast, security"),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Lists alerts matching optional filter criteria (M1-FR6).
    """
    alerts = get_alerts(
        db=db,
        host_id=host_id,
        status=status,
        severity=severity,
        kind=kind,
        limit=limit,
    )
    result = []
    for a in alerts:
        item = AlertRead(
            id=a.id,
            host_id=a.host_id,
            hostname=a.host.hostname if a.host else None,
            rule_id=a.rule_id,
            metric=a.metric,
            kind=a.kind,
            severity=a.severity,
            message=a.message,
            value=a.value,
            threshold=a.threshold,
            status=a.status,
            created_at=a.created_at,
            acknowledged_at=a.acknowledged_at,
            resolved_at=a.resolved_at,
        )
        result.append(item)
    return result


@router.post("/{alert_id}/ack", response_model=AlertRead)
def ack_alert(
    alert_id: int,
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """
    Acknowledges an active alert, updating its status to 'acknowledged' (Section 7).
    """
    alert = acknowledge_alert(db, alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found.",
        )
    return AlertRead(
        id=alert.id,
        host_id=alert.host_id,
        hostname=alert.host.hostname if alert.host else None,
        rule_id=alert.rule_id,
        metric=alert.metric,
        kind=alert.kind,
        severity=alert.severity,
        message=alert.message,
        value=alert.value,
        threshold=alert.threshold,
        status=alert.status,
        created_at=alert.created_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
    )


@router.post("/{alert_id}/feedback", response_model=AlertFeedbackRead, status_code=status.HTTP_201_CREATED)
def submit_alert_feedback(
    alert_id: int,
    feedback_in: AlertFeedbackCreate,
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """
    Records operator true/false-positive feedback on an alert for AI sensitivity calibration (M5-FR6).
    """
    feedback = record_alert_feedback(db, alert_id, feedback_in)
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found.",
        )
    return feedback


# --- Rule Management ---

@router.get("/rules", response_model=List[AlertRuleRead])
def list_alert_rules(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Retrieves all configured threshold rules (M1-FR5). Requires ADMIN role.
    """
    return get_rules(db)


@router.post("/rules", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    rule_in: AlertRuleCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Configures a new threshold alert rule. Requires ADMIN role.
    """
    return create_alert_rule(db, rule_in)


@router.patch("/rules/{rule_id}", response_model=AlertRuleRead)
def update_rule(
    rule_id: int,
    rule_in: AlertRuleUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Updates an existing threshold alert rule. Requires ADMIN role.
    """
    rule = update_alert_rule(db, rule_id, rule_in)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule with ID {rule_id} not found.",
        )
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Deletes an alert rule. Requires ADMIN role.
    """
    deleted = delete_alert_rule(db, rule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule with ID {rule_id} not found.",
        )
    return None
