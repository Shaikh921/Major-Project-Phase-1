"""
Security Event & Audit Pydantic Schemas.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class SecurityEventCreate(BaseModel):
    hostname: Optional[str] = None
    event_type: str = Field(..., json_schema_extra={"example": "brute_force_ssh"})
    severity: str = Field(default="medium", json_schema_extra={"example": "high"})
    source_ip: Optional[str] = Field(None, json_schema_extra={"example": "198.51.100.23"})
    destination_port: Optional[int] = Field(None, json_schema_extra={"example": 22})
    description: str = Field(..., json_schema_extra={"example": "Multiple failed SSH authentications from external IP"})
    raw_evidence: Optional[str] = None


class SecurityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    host_id: Optional[int] = None
    hostname: Optional[str] = None
    event_type: str
    severity: str
    source_ip: Optional[str] = None
    destination_port: Optional[int] = None
    description: str
    status: str
    raw_evidence: Optional[str] = None
    timestamp: datetime
    resolved_at: Optional[datetime] = None


class SecuritySummaryResponse(BaseModel):
    total_events: int
    critical_events: int
    high_events: int
    medium_events: int
    low_events: int
    open_incidents: int
    recent_events: List[SecurityEventRead]


class SecurityStatusUpdate(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "investigating"})  # open, investigating, mitigated, false_positive
