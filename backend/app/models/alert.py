"""
Alert and Alert Rule Models.

Handles threshold configuration rules, active/resolved alert lifecycles,
and operator feedback for sensitivity tuning.
"""

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List, TYPE_CHECKING

from backend.app.database.base import Base

if TYPE_CHECKING:
    from backend.app.models.host import Host


class AlertRule(Base):
    """
    Configurable threshold rule evaluating metric telemetry.
    
    Attributes:
        id: Primary key identifier.
        name: Human-readable rule name (e.g. 'High CPU Utilization').
        metric: Target metric to evaluate ('cpu_percent', 'memory_percent', etc.).
        operator: Comparison operator ('>', '>=', '<', '<=', '==').
        threshold: Critical value boundary triggering the alert.
        severity: Alert severity classification ('info', 'warning', 'critical').
        duration_seconds: Grace period duration before firing (0 = immediate).
        is_enabled: Toggle flag to activate/deactivate rule evaluation.
        environment: Optional filter restricting rule to specific environments.
    """
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    operator: Mapped[str] = mapped_column(String(10), default=">", nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="warning", nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    environment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="rule")


class Alert(Base):
    """
    Alert instance generated when a metric violates an active rule or ML anomaly detection.
    
    Deduplication Policy (Section 5.1 & Table 79):
        Only one active alert can exist for any unique combination of (host_id, metric, kind).
    
    Attributes:
        id: Primary key identifier.
        host_id: Foreign key to the affected Host.
        rule_id: Foreign key to the triggering AlertRule (optional for ML anomalies).
        metric: Metric name triggering the alert.
        kind: Alert category ('threshold', 'anomaly', 'forecast', 'security').
        severity: 'info', 'warning', or 'critical'.
        message: Descriptive summary of the issue.
        value: Metric value recorded when the alert fired.
        threshold: Target threshold configured on the rule.
        status: Current alert state ('active', 'acknowledged', 'resolved').
        created_at: Time when the alert first triggered.
        acknowledged_at: Time when an operator acknowledged the alert.
        resolved_at: Time when the metric normalized and the alert resolved.
    """
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    host_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("hosts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    metric: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), default="threshold", nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="warning", nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    host: Mapped["Host"] = relationship("Host", back_populates="alerts")
    rule: Mapped[Optional["AlertRule"]] = relationship("AlertRule", back_populates="alerts")
    feedbacks: Mapped[List["AlertFeedback"]] = relationship("AlertFeedback", back_populates="alert", cascade="all, delete-orphan")

    # Index for fast deduplication lookups
    __table_args__ = (
        Index("ix_alerts_dedup_lookup", "host_id", "metric", "kind", "status"),
    )


class AlertFeedback(Base):
    """
    Human feedback recording true/false positive verdicts on alerts.
    Used by Module 5 (M5-FR6/FR7) to tune alert sensitivity without full retraining.
    
    Attributes:
        id: Primary key identifier.
        alert_id: Foreign key to the reviewed Alert.
        verdict: Operator classification ('true_positive', 'false_positive').
        operator_notes: Optional explanation provided by the operator.
        created_at: UTC timestamp when feedback was recorded.
    """
    __tablename__ = "alert_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    operator_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    alert: Mapped["Alert"] = relationship("Alert", back_populates="feedbacks")
