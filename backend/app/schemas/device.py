"""
Pydantic Schemas for Device Enrollment & Workstation Lifecycle.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class EnrollmentCodeCreate(BaseModel):
    """Payload to generate a new time-limited single-use enrollment code."""
    expires_in_minutes: int = Field(default=15, ge=1, le=1440, description="Expiration in minutes (1 to 1440)")
    notes: Optional[str] = Field(default=None, max_length=255, description="Administrative reference notes")


class EnrollmentCodeGenerated(BaseModel):
    """Response returned ONLY to Super Admin upon initial generation, containing the raw code."""
    id: int
    raw_code: str
    code_prefix: str
    expires_at: datetime
    created_at: datetime


class EnrollmentCodeRead(BaseModel):
    """Public/List view of enrollment codes omitting raw secret."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    code_prefix: str
    expires_at: datetime
    is_used: bool
    used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime


class DeviceEnrollRequest(BaseModel):
    """Payload sent by client installer to request enrollment."""
    enrollment_code: str = Field(..., min_length=8, max_length=64, description="Single-use enrollment code")
    device_uuid: str = Field(..., min_length=8, max_length=64, description="Hardware UUID / MAC-derived ID")
    reported_hostname: str = Field(..., min_length=1, max_length=100, description="Windows hostname")
    ip_address: Optional[str] = Field(default=None, max_length=50)
    mac_address: Optional[str] = Field(default=None, max_length=50)
    os_version: Optional[str] = Field(default=None, max_length=100)
    agent_version: Optional[str] = Field(default="1.0.0", max_length=30)


class DeviceEnrollResponse(BaseModel):
    """Response to installer confirming enrollment request receipt."""
    status: str
    request_id: int
    device_uuid: str
    claim_token: str
    poll_interval_seconds: int = 5
    message: str


class DeviceClaimCredentialRequest(BaseModel):
    """Polling payload sent by sensor agent while awaiting Super Admin approval."""
    device_uuid: str
    claim_token: str


class DeviceClaimCredentialResponse(BaseModel):
    """Response containing credentials once approved, or current pending/rejected status."""
    status: str
    agent_key: Optional[str] = None
    assigned_name: Optional[str] = None
    lab_name: Optional[str] = None
    room_number: Optional[str] = None
    pc_number: Optional[str] = None
    rejection_reason: Optional[str] = None
    server_time: datetime


class DeviceApproveRequest(BaseModel):
    """Payload submitted by Super Admin to approve pending workstation."""
    assigned_name: str = Field(..., min_length=1, max_length=100, description="Human-assigned label, e.g. PC-Lab1-05")
    lab_name: Optional[str] = Field(default="Main Lab", max_length=100)
    room_number: Optional[str] = Field(default="Room 1", max_length=50)
    pc_number: Optional[str] = Field(default="01", max_length=50)


class DeviceRejectRequest(BaseModel):
    """Payload to reject an enrollment request."""
    reason: Optional[str] = Field(default="Administrative rejection", max_length=255)


class DeviceUninstallNoticeRequest(BaseModel):
    """Payload sent by uninstaller to request retirement."""
    device_uuid: str
    agent_key: str
    reason: Optional[str] = Field(default="Local uninstall requested by administrator", max_length=255)


class DeviceRead(BaseModel):
    """Comprehensive device record for the dashboard."""
    id: int
    device_uuid: str
    reported_hostname: str
    assigned_name: Optional[str] = None
    lab_name: Optional[str] = None
    room_number: Optional[str] = None
    pc_number: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    os_version: Optional[str] = None
    agent_version: Optional[str] = None
    status: str
    telemetry_health: str
    queue_backlog: int
    is_online: bool = True
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    last_contact_at: Optional[datetime] = None
    last_collection_at: Optional[datetime] = None
    last_upload_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    retirement_requested: bool = False
    retirement_confirmed: bool = False

    model_config = ConfigDict(from_attributes=True)


class DeviceSummaryStats(BaseModel):
    """High-level metrics for Device Management view."""
    total_devices: int
    pending_approval: int
    approved_active: int
    disabled: int
    retired: int
    online_count: int
    offline_count: int
    healthy_telemetry: int
    stale_telemetry: int
