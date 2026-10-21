"""
Agent API Key Model.

Stores hashed credentials for telemetry collection agents.
Raw API keys are NEVER stored in plaintext in the database or logs.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class AgentApiKey(Base):
    """
    Authorized API key record for telemetry ingestion authentication.
    
    Attributes:
        id: Primary key identifier.
        name: Human-readable identifier (e.g. 'Production Web Cluster', 'Fleet Simulator').
        key_prefix: First 8-12 characters of the key for identification/audit.
        hashed_key: Cryptographic hash (SHA-256) of the raw secret token.
        description: Optional notes or operational purpose.
        source_type: Expected telemetry provenance ('REAL_AGENT', 'SIMULATED', 'ALL').
        is_active: Whether this key is currently active and authorized.
        created_at: UTC timestamp when the key was provisioned.
        last_used_at: UTC timestamp of the most recent metric submission using this key.
        revoked_at: UTC timestamp when the key was revoked (if revoked).
    """
    __tablename__ = "agent_api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    hashed_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="ALL", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
