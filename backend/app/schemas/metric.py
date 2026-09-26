"""
Metric Pydantic Schemas.

Data transfer objects for telemetry ingestion, validation, and historical time-series queries.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List


class MetricCreate(BaseModel):
    """
    Payload for submitting a single telemetry sample.
    Supports auto-registration of hosts if hostname is provided.
    """
    hostname: str = Field(..., description="Hostname of the reporting machine", min_length=1)
    ip_address: Optional[str] = Field(None, description="Current IP address of the reporting host")
    environment: Optional[str] = Field(default="local", description="Deployment environment")
    provider: Optional[str] = Field(default="bare-metal", description="Cloud provider")
    region: Optional[str] = Field(default="local", description="Cloud region")

    timestamp: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Sample collection timestamp in UTC",
    )
    cpu_percent: float = Field(..., ge=0.0, le=100.0, description="CPU utilization percentage (0-100)")
    memory_percent: float = Field(..., ge=0.0, le=100.0, description="Memory utilization percentage (0-100)")
    disk_percent: float = Field(..., ge=0.0, le=100.0, description="Disk utilization percentage (0-100)")
    network_sent_mb: float = Field(default=0.0, ge=0.0, description="Network megabytes sent since last interval")
    network_received_mb: float = Field(default=0.0, ge=0.0, description="Network megabytes received since last interval")


class MetricBatchCreate(BaseModel):
    """Payload for submitting multiple metric samples in a single batch request."""
    metrics: List[MetricCreate] = Field(..., min_length=1, description="List of metric data points")


class MetricRead(BaseModel):
    """Serialized representation of a stored metric record."""
    id: int
    host_id: int
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_sent_mb: float
    network_received_mb: float

    model_config = ConfigDict(from_attributes=True)


class MetricTimeSeriesResponse(BaseModel):
    """Structured response for time-series charts and queries."""
    host_id: int
    hostname: str
    total_samples: int
    data: List[MetricRead]
    time_series: List[MetricRead] = Field(default_factory=list)
