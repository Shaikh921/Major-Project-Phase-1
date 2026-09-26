"""
Alert and Alert Rule Pydantic Schemas.

Data transfer objects for rule configurations, active alerts, acknowledgments,
and operator feedback records.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List


class AlertRuleBase(BaseModel):
    """Base fields for an alert threshold rule."""
    name: str = Field(..., description="Human-readable rule name", min_length=1, max_length=150)
    metric: str = Field(..., description="Metric key to evaluate (e.g. cpu_percent, memory_percent, disk_percent)")
    operator: str = Field(default=">=", description="Comparison operator ('>', '>=', '<', '<=', '==')")
    threshold: float = Field(..., description="Threshold numeric value")
    severity: str = Field(default="warning", description="Severity classification: info, warning, critical")
    duration_seconds: int = Field(default=0, ge=0, description="Duration seconds condition must persist before firing")
    is_enabled: bool = Field(default=True, description="Whether this rule is actively evaluated")
    environment: Optional[str] = Field(None, description="Optional environment filter")


class AlertRuleCreate(AlertRuleBase):
    """Payload to create an alert rule."""
    pass


class AlertRuleUpdate(BaseModel):
    """Payload to update an alert rule."""
    name: Optional[str] = None
    metric: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    severity: Optional[str] = None
    duration_seconds: Optional[int] = None
    is_enabled: Optional[bool] = None
    environment: Optional[str] = None


class AlertRuleRead(AlertRuleBase):
    """Response schema for an alert rule."""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertRead(BaseModel):
    """Response schema for an alert instance."""
    id: int
    host_id: int
    hostname: Optional[str] = None
    rule_id: Optional[int] = None
    metric: str
    kind: str
    severity: str
    message: str
    value: float
    threshold: Optional[float] = None
    status: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AlertAcknowledge(BaseModel):
    """Payload for acknowledging an active alert."""
    acknowledged: bool = True


class AlertFeedbackCreate(BaseModel):
    """Payload for recording operator verdict on an alert."""
    verdict: str = Field(..., description="'true_positive' or 'false_positive'")
    operator_notes: Optional[str] = Field(None, description="Optional investigation or remediation notes")


class AlertFeedbackRead(BaseModel):
    """Response schema for stored alert feedback."""
    id: int
    alert_id: int
    verdict: str
    operator_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
