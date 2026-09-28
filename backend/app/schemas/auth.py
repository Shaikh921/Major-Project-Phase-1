"""
Authentication and Identity Pydantic Schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, description="User email address")
    password: str = Field(..., min_length=1, description="Plaintext password")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in_seconds: int = Field(..., description="Access token lifetime in seconds")
    user: "UserRead" = Field(..., description="Authenticated user metadata")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class UserCreateInternal(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    role: str = Field(default="VIEWER")
    is_active: bool = True
    is_verified: bool = False


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, description="Registered account email")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Email verification token")


class MessageResponse(BaseModel):
    message: str = Field(..., description="Status or confirmation message")
    status: str = Field(default="success", description="Status code or indicator")


# --- Point 3 Extension: Admin Request & Management Schemas ---

class AdminRegistrationRequestCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150, description="Applicant full name")
    email: str = Field(..., min_length=3, max_length=255, description="Applicant email address")
    organization: Optional[str] = Field(None, max_length=150, description="Department or organization")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for requesting administrator access")


class AdminRegistrationRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    organization: Optional[str] = None
    reason: Optional[str] = None
    status: str
    email_verified: bool
    requested_at: datetime
    verified_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by_id: Optional[int] = None
    rejection_reason: Optional[str] = None
    created_user_id: Optional[int] = None


class AdminRequestReject(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Rejection reason")


class AdminActivateAccountRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Single-use activation token")
    new_password: str = Field(..., min_length=8, description="Initial administrator password (min 8 chars)")


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    active_sessions_count: int = 0


class AdminSummaryStats(BaseModel):
    total_admins: int
    active_admins: int
    disabled_admins: int
    pending_requests: int


class SmtpTestRequest(BaseModel):
    recipient: str = Field(..., min_length=3, max_length=255, description="Target recipient email address")


class SmtpTestResponse(BaseModel):
    success: bool
    status: str
    message: str
    recipient: str
    mode: str

