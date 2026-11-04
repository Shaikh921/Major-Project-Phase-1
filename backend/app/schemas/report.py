"""
Audit Log and Reporting Pydantic Schemas.
Supports both:
1. Overall Infrastructure Monitoring Reports
2. Individual Sensor / PC Performance Reports
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

    # Extended fleet resource analytics & recommendations
    avg_cpu_percent: Optional[float] = None
    avg_memory_percent: Optional[float] = None
    avg_disk_percent: Optional[float] = None
    critical_alerts_count: int = 0
    warning_alerts_count: int = 0
    alerts_by_category: Dict[str, int] = Field(default_factory=dict)
    recent_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    recent_security_events: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


# ==============================================================================
# INDIVIDUAL SENSOR / PC REPORT SCHEMAS
# ==============================================================================

class HostReportRequest(BaseModel):
    time_range_hours: int = Field(default=24, ge=1, le=720, description="Reporting horizon in hours")
    offline_threshold_seconds: int = Field(default=90, ge=10, le=3600, description="Cutoff seconds for evaluating host online status")


class HostIdentityInfo(BaseModel):
    host_id: int
    hostname: str
    assigned_name: Optional[str] = None
    device_uuid: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    os_version: Optional[str] = None
    agent_version: Optional[str] = None
    environment: str
    room: Optional[str] = None
    lab_name: Optional[str] = None
    source_type: Optional[str] = None
    is_active: bool = True


class ResourceMetricStats(BaseModel):
    avg: Optional[float] = None
    max: Optional[float] = None
    min: Optional[float] = None
    peak_timestamp: Optional[datetime] = None
    latest: Optional[float] = None
    sample_count: int = 0


class HostReportAlertItem(BaseModel):
    id: int
    timestamp: datetime
    severity: str
    kind: str
    metric: str
    message: str
    value: float
    threshold: Optional[float] = None
    status: str


class HostReportSecurityItem(BaseModel):
    id: int
    timestamp: datetime
    event_type: str
    severity: str
    description: str
    status: str
    raw_evidence: Optional[str] = None


class HostReportResponse(BaseModel):
    report_id: str
    title: str
    generated_at: datetime
    time_window_start: datetime
    time_window_end: datetime
    reporting_period_hours: int
    host_identity: HostIdentityInfo
    connectivity_status: str  # "ONLINE", "OFFLINE", "NO_DATA"
    last_heartbeat: Optional[datetime] = None
    telemetry_freshness_seconds: Optional[int] = None
    telemetry_availability_pct: Optional[float] = None
    total_samples: int = 0

    # Resource Metrics Statistics
    cpu_stats: ResourceMetricStats
    memory_stats: ResourceMetricStats
    disk_stats: ResourceMetricStats
    network_sent_stats: ResourceMetricStats
    network_recv_stats: ResourceMetricStats

    # Incidents & Security
    total_alerts: int = 0
    active_alerts_count: int = 0
    alerts: List[HostReportAlertItem] = Field(default_factory=list)
    security_events_count: int = 0
    security_events: List[HostReportSecurityItem] = Field(default_factory=list)

    # Assessments & Observations
    technical_assessment: str
    recommendations: List[str] = Field(default_factory=list)
    security_disclaimer: str = (
        "Absence of recorded security events indicates no active threat signatures were flagged during the window; "
        "it does not constitute a formal warranty of complete threat absence."
    )
