"""
Audit Log and Reporting Pydantic Schemas.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_email: str
    action: str
    target_resource: str
    details: str
    result: str
    client_ip: Optional[str] = None
    timestamp: datetime


class AuditLogCreate(BaseModel):
    user_email: str = Field(default="admin@ops.local")
    action: str
    target_resource: str
    details: str
    result: str = "success"
    client_ip: Optional[str] = None


class ReportGenerateRequest(BaseModel):
    environment: Optional[str] = None
    time_range_hours: int = Field(default=24, ge=1, le=720)
    include_metrics: bool = True
    include_anomalies: bool = True
    include_security: bool = True
    include_cost: bool = True
    include_audit_trail: bool = True


class ReportResponse(BaseModel):
    report_id: str
    title: str
    generated_at: datetime
    time_window_start: datetime
    time_window_end: datetime
    environment: str
    summary_metrics: Dict[str, Any]
    active_incidents_count: int
    anomalies_detected_count: int
    security_events_count: int
    estimated_monthly_spend_usd: float
    potential_savings_usd: float
    sections: List[Dict[str, Any]]
