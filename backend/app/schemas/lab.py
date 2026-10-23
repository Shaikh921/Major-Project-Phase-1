"""
Lab PC Monitoring Pydantic Schemas.

Data transfer objects for the Lab Overview endpoint, room-wise PC grouping,
online/offline status determination, and aggregate resource utilization.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class LabPCEntry(BaseModel):
    """
    Summary representation of an individual lab PC.
    """
    host_id: int = Field(..., description="Unique host primary key identifier")
    hostname: str = Field(..., description="Hostname or physical machine label")
    room: str = Field(..., description="Room identifier extracted from host region")
    ip_address: Optional[str] = Field(None, description="Primary network IP address")
    online: bool = Field(..., description="True if host has reported telemetry within offline threshold")
    last_seen: Optional[datetime] = Field(None, description="UTC timestamp of the latest received metric sample")
    cpu_percent: Optional[float] = Field(None, ge=0.0, le=100.0, description="Latest CPU utilization percentage")
    memory_percent: Optional[float] = Field(None, ge=0.0, le=100.0, description="Latest RAM utilization percentage")
    disk_percent: Optional[float] = Field(None, ge=0.0, le=100.0, description="Latest storage partition utilization percentage")
    cpu_level: str = Field(..., description="Operational status: 'normal', 'warning', 'high', or 'offline'")

    model_config = ConfigDict(from_attributes=True)


class LabRoomSummary(BaseModel):
    """
    Aggregated summary for an individual lab room grouping.
    """
    room: str = Field(..., description="Room identifier")
    total: int = Field(..., ge=0, description="Total number of registered PCs in this room")
    online: int = Field(..., ge=0, description="Number of currently online PCs")
    offline: int = Field(..., ge=0, description="Number of currently offline PCs")
    avg_cpu: Optional[float] = Field(None, ge=0.0, le=100.0, description="Mean CPU percentage across online PCs")
    pcs: List[LabPCEntry] = Field(default_factory=list, description="List of PC entries in this room")


class LabTotalsSummary(BaseModel):
    """
    Fleet-level summary totals across all monitored lab PCs in the requested environment.
    """
    total_pcs: int = Field(..., ge=0, description="Total number of registered lab PCs")
    online: int = Field(..., ge=0, description="Total number of currently online lab PCs")
    offline: int = Field(..., ge=0, description="Total number of currently offline lab PCs")
    avg_cpu: Optional[float] = Field(None, ge=0.0, le=100.0, description="Mean CPU percentage across all online lab PCs")


class LabSummaryResponse(BaseModel):
    """
    Complete response payload for GET /api/v1/lab/summary.
    """
    generated_at: datetime = Field(..., description="UTC timestamp when this summary was generated")
    environment: str = Field(..., description="Target host environment (e.g. 'lab')")
    offline_after_seconds: int = Field(..., ge=10, le=3600, description="Inactivity threshold in seconds used to evaluate offline status")
    totals: LabTotalsSummary = Field(..., description="Aggregate PC status counts and average CPU")
    busiest_pcs: List[LabPCEntry] = Field(default_factory=list, description="Top 5 busiest online PCs ordered by CPU utilization descending")
    rooms: List[LabRoomSummary] = Field(default_factory=list, description="Lab PCs grouped and sorted by room identifier")
