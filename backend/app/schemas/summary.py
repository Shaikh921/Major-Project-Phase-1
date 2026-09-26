"""
Fleet and Host Summary Pydantic Schemas.

Data transfer objects for the aggregate fleet overview and single-host status snapshots
(Section 7: /api/summary).
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List
from backend.app.schemas.alert import AlertRead
from backend.app.schemas.metric import MetricRead


class HostStatusSummary(BaseModel):
    """
    Summary snapshot of a single host: its metadata, latest recorded telemetry sample,
    and highest severity active alert (if any).
    """
    host_id: int
    hostname: str
    ip_address: Optional[str] = None
    environment: str
    provider: Optional[str] = None
    region: Optional[str] = None
    is_active: bool
    status: str = Field(default="healthy", description="'healthy', 'warning', 'critical', or 'offline'")
    last_seen: Optional[datetime] = None
    latest_metric: Optional[MetricRead] = None
    latest_metrics: Optional[MetricRead] = None
    worst_active_alert: Optional[AlertRead] = None
    active_alert_count: int = 0


class FleetSummaryResponse(BaseModel):
    """
    Comprehensive fleet status overview for dashboard headers.
    """
    total_hosts: int
    healthy_hosts: int
    warning_hosts: int
    critical_hosts: int
    offline_hosts: int
    total_active_alerts: int
    hosts_with_warnings: int = 0
    hosts_with_critical_alerts: int = 0
    hosts: List[HostStatusSummary]
