"""
Alert and Rule Evaluation Service.

Implements threshold rule checking, automatic alert deduplication (Table 79),
auto-resolution on recovery, acknowledgment, and operator feedback storage.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import Session

from backend.app.models.alert import AlertRule, Alert, AlertFeedback
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.schemas.alert import AlertRuleCreate, AlertRuleUpdate, AlertFeedbackCreate


def evaluate_condition(value: float, operator: str, threshold: float) -> bool:
    """
    Evaluates whether a numeric value breaches a configured operator threshold.
    """
    if operator == ">":
        return value > threshold
    elif operator == ">=":
        return value >= threshold
    elif operator == "<":
        return value < threshold
    elif operator == "<=":
        return value <= threshold
    elif operator == "==":
        return value == threshold
    return False


def get_active_rules(db: Session, environment: Optional[str] = None) -> List[AlertRule]:
    """
    Fetches all enabled alert rules applicable to the specified environment.
    """
    statement = select(AlertRule).where(AlertRule.is_enabled == True)
    if environment:
        statement = statement.where(
            or_(AlertRule.environment == None, AlertRule.environment == environment)
        )
    return list(db.scalars(statement).all())


def evaluate_metric_sample(db: Session, host: Host, metric: Metric) -> List[Alert]:
    """
    Evaluates an incoming metric sample against all active rules.
    
    Deduplication & Lifecycle Policy:
    1. If a rule condition is breached:
       - Check if an active/acknowledged alert for (host_id, metric, 'threshold') exists.
       - If it exists, update its latest value and timestamp, but do NOT create a duplicate alert.
       - If no active alert exists, create a new Alert record with status='active'.
    2. If a rule condition is NOT breached and an active alert currently exists:
       - Automatically resolve the alert (status='resolved', resolved_at=now).
    """
    rules = get_active_rules(db, host.environment)
    generated_or_updated_alerts: List[Alert] = []

    # Map metric attributes to values
    metric_values: Dict[str, float] = {
        "cpu_percent": metric.cpu_percent,
        "memory_percent": metric.memory_percent,
        "disk_percent": metric.disk_percent,
        "network_sent_mb": metric.network_sent_mb,
        "network_received_mb": metric.network_received_mb,
    }

    for rule in rules:
        if rule.metric not in metric_values:
            continue

        val = metric_values[rule.metric]
        is_breached = evaluate_condition(val, rule.operator, rule.threshold)

        # Check existing non-resolved alert for (host_id, metric, 'threshold')
        existing_alert_stmt = select(Alert).where(
            and_(
                Alert.host_id == host.id,
                Alert.metric == rule.metric,
                Alert.kind == "threshold",
                Alert.status.in_(["active", "acknowledged"]),
            )
        )
        existing_alert = db.scalar(existing_alert_stmt)

        if is_breached:
            if existing_alert:
                # Update existing alert snapshot
                existing_alert.value = val
                existing_alert.severity = rule.severity
                # Re-elevate severity or update message if necessary
                existing_alert.message = (
                    f"Threshold breached: {rule.metric} is {val:.1f}% "
                    f"({rule.operator} {rule.threshold:.1f}%)"
                )
                db.commit()
                db.refresh(existing_alert)
                generated_or_updated_alerts.append(existing_alert)
            else:
                # Create a new alert
                new_alert = Alert(
                    host_id=host.id,
                    rule_id=rule.id,
                    metric=rule.metric,
                    kind="threshold",
                    severity=rule.severity,
                    message=(
                        f"Threshold breached: {rule.metric} is {val:.1f}% "
                        f"({rule.operator} {rule.threshold:.1f}%)"
                    ),
                    value=val,
                    threshold=rule.threshold,
                    status="active",
                    created_at=metric.timestamp or datetime.now(timezone.utc),
                )
                db.add(new_alert)
                db.commit()
                db.refresh(new_alert)
                generated_or_updated_alerts.append(new_alert)
        else:
            # Metric is now within healthy range; auto-resolve if currently open
            if existing_alert and existing_alert.rule_id == rule.id:
                existing_alert.status = "resolved"
                existing_alert.resolved_at = datetime.now(timezone.utc)
                db.commit()

    return generated_or_updated_alerts


def get_alerts(
    db: Session,
    host_id: Optional[int] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 100,
) -> List[Alert]:
    """
    Retrieves filtered alert history sorted by creation time descending.
    """
    statement = select(Alert).order_by(desc(Alert.created_at))

    if host_id:
        statement = statement.where(Alert.host_id == host_id)
    if status:
        statement = statement.where(Alert.status == status)
    if severity:
        statement = statement.where(Alert.severity == severity)
    if kind:
        statement = statement.where(Alert.kind == kind)

    statement = statement.limit(limit)
    return list(db.scalars(statement).all())


def get_alert(db: Session, alert_id: int) -> Optional[Alert]:
    """Fetches a single alert by ID."""
    return db.scalar(select(Alert).where(Alert.id == alert_id))


def acknowledge_alert(db: Session, alert_id: int) -> Optional[Alert]:
    """
    Sets alert status to 'acknowledged' and records acknowledgment timestamp.
    """
    alert = get_alert(db, alert_id)
    if alert is None:
        return None

    if alert.status == "active":
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)
    return alert


def resolve_alert(db: Session, alert_id: int) -> Optional[Alert]:
    """
    Explicitly marks an alert as 'resolved'.
    """
    alert = get_alert(db, alert_id)
    if alert is None:
        return None

    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


def record_alert_feedback(
    db: Session,
    alert_id: int,
    feedback_in: AlertFeedbackCreate,
) -> Optional[AlertFeedback]:
    """
    Records operator classification ('true_positive' / 'false_positive') on an alert.
    Supports M5-FR6 feedback recording.
    """
    alert = get_alert(db, alert_id)
    if alert is None:
        return None

    feedback = AlertFeedback(
        alert_id=alert.id,
        verdict=feedback_in.verdict,
        operator_notes=feedback_in.operator_notes,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


# --- Rule Management Functions ---

def create_alert_rule(db: Session, rule_in: AlertRuleCreate) -> AlertRule:
    """Creates a new alert threshold rule."""
    rule = AlertRule(**rule_in.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def get_rules(db: Session) -> List[AlertRule]:
    """Lists all configured alert rules."""
    return list(db.scalars(select(AlertRule).order_by(AlertRule.id)).all())


def get_rule(db: Session, rule_id: int) -> Optional[AlertRule]:
    """Fetches an alert rule by ID."""
    return db.scalar(select(AlertRule).where(AlertRule.id == rule_id))


def update_alert_rule(
    db: Session,
    rule_id: int,
    rule_in: AlertRuleUpdate,
) -> Optional[AlertRule]:
    """Updates an existing alert threshold rule."""
    rule = get_rule(db, rule_id)
    if rule is None:
        return None

    for field, val in rule_in.model_dump(exclude_unset=True).items():
        setattr(rule, field, val)

    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    return rule


def delete_alert_rule(db: Session, rule_id: int) -> bool:
    """Deletes an alert rule."""
    rule = get_rule(db, rule_id)
    if rule is None:
        return False
    db.delete(rule)
    db.commit()
    return True
