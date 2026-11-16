"""
Pydantic Schemas for Predefined Remote Diagnostics (Phase 9A.1).
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class DiagnosticDispatchCreate(BaseModel):
    host_id: int
    action: str = Field(..., min_length=1, max_length=50)
    target: Optional[str] = Field(None, max_length=253)
    timeout_seconds: int = Field(30, ge=5, le=300)


class DiagnosticResultCreate(BaseModel):
    command_id: str = Field(..., min_length=36, max_length=36)
    exit_code: int
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    payload: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None


class DiagnosticResultResponse(BaseModel):
    id: int
    command_id: str
    exit_code: int
    stdout: str
    stderr: str
    payload: Optional[Dict[str, Any]] = None
    payload_hash: str
    failure_reason: Optional[str] = None
    is_late: bool
    received_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiagnosticCommandResponse(BaseModel):
    id: str
    host_id: int
    hostname: Optional[str] = None
    action: str
    target: Optional[str] = None
    timeout_seconds: int
    status: str
    requested_by_user_id: int
    claimed_at: Optional[datetime] = None
    claimed_by_agent_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    result: Optional[DiagnosticResultResponse] = None

    model_config = ConfigDict(from_attributes=True)


class DiagnosticCommandClaim(BaseModel):
    id: str
    action: str
    target: Optional[str] = None
    timeout_seconds: int
    lease_expires_at: datetime
    hard_deadline_at: datetime

