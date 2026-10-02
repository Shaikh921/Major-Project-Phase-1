"""
Host Pydantic Schemas.

Data transfer objects for Host registration, updates, and serialized responses.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any


class HostBase(BaseModel):
    """Base fields shared across Host schemas."""
    hostname: str = Field(..., description="Unique hostname or instance identifier", min_length=1, max_length=255)
    ip_address: Optional[str] = Field(None, description="IP address of the host", max_length=45)
    environment: str = Field(default="local", description="Environment tier (e.g. production, staging, development, local)")
    instance_type: Optional[str] = Field(None, description="Cloud instance size or flavor")
    provider: Optional[str] = Field(default="bare-metal", description="Cloud or infrastructure provider")
    region: Optional[str] = Field(default="local", description="Cloud region or datacenter location")
    source_type: str = Field(default="UNKNOWN", description="Telemetry source classification (e.g. REAL_AGENT, SIMULATED, CLOUD_PROVIDER, UNKNOWN)")
    owner_email: Optional[str] = Field(None, description="Contact or owner email address associated with this host", max_length=255)
    tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata tags for grouping and filtering")


class HostCreate(HostBase):
    """Payload for registering a new host."""
    is_active: bool = Field(default=True, description="Active status flag")


class HostUpdate(BaseModel):
    """Payload for updating host metadata."""
    ip_address: Optional[str] = None
    environment: Optional[str] = None
    instance_type: Optional[str] = None
    provider: Optional[str] = None
    region: Optional[str] = None
    source_type: Optional[str] = None
    owner_email: Optional[str] = None
    is_active: Optional[bool] = None
    tags: Optional[Dict[str, Any]] = None


class HostRead(HostBase):
    """Response schema representing a registered host."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
