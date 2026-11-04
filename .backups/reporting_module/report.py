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
    offline_threshold_seconds: int = Field(default=90, ge=10, le=3600, description="Cutoff seconds for evaluating host online status")


class HostInventorySummary(BaseModel):
    host_id: int
    hostname: str
    environment: str
    room: Optional[str] = None
    ip_address: Optional[str] = None
    status: str  # "ONLINE", "OFFLINE", "NO_DATA"
    last_seen: Optional[datetime] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None


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

    # Enhanced operational & security audit metadata
    data_freshness_timestamp: Optional[datetime] = None
    online_hosts_count: int = 0
    offline_hosts_count: int = 0
    unseen_hosts_count: int = 0
    host_inventories: List[HostInventorySummary] = Field(default_factory=list)
    security_audit_disclaimer: str = (
        "Absence of recorded security events indicates no active threat signatures were flagged during the window; "
        "it does not constitute a formal warranty of complete threat absence."
    )
