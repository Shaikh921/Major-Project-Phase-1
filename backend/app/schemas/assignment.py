"""
Pydantic Schemas for Phase 9A.1 Hybrid RBAC Assignments.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class EnvironmentAssignmentCreate(BaseModel):
    user_id: int
    environment: str = Field(..., min_length=1, max_length=50)


class HostAssignmentCreate(BaseModel):
    user_id: int
    host_id: int


class AssignmentResponse(BaseModel):
    id: int
    user_id: int
    scope_type: str  # "ENVIRONMENT" or "HOST"
    scope_value: str  # Environment name or Hostname
    host_id: Optional[int] = None
    status: str
    granted_by_id: int
    revoked_by_id: Optional[int] = None
    created_at: datetime
    revoked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserAssignmentsSummary(BaseModel):
    user_id: int
    user_email: str
    user_role: str
    is_super_admin: bool
    active_environments: List[str]
    active_host_ids: List[int]
    assignments: List[AssignmentResponse]

    model_config = ConfigDict(from_attributes=True)

