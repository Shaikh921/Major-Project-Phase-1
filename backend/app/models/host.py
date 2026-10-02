"""
Host Model.

Represents a monitored compute resource (Virtual Machine, bare-metal server,
or container instance) across multi-cloud or on-premise environments.
"""

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, List

from backend.app.database.base import Base


class Host(Base):
    """
    Host entity representing a registered server/instance.
    
    Attributes:
        id: Primary key identifier.
        hostname: Unique hostname or instance identifier (e.g. 'prod-web-01').
        ip_address: IPv4/IPv6 address of the host.
        environment: Deployment environment ('production', 'staging', 'development', 'local').
        instance_type: Cloud instance sizing tier (e.g. 't3.medium', 'e2-standard-4').
        provider: Cloud or infrastructure provider ('aws', 'gcp', 'azure', 'bare-metal').
        region: Geographic cloud region (e.g. 'us-east-1', 'us-central1').
        is_active: Status flag indicating if telemetry is currently expected.
        tags: Key-value dictionary for grouping and organizational filtering.
        created_at: UTC timestamp when the host was first registered.
        updated_at: UTC timestamp of the last metadata update.
    """
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    environment: Mapped[str] = mapped_column(
        String(50),
        default="local",
        nullable=False,
        index=True,
    )
    instance_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), default="bare-metal", nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(50), default="local", nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(50),
        default="UNKNOWN",
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    owner_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    metrics: Mapped[List["Metric"]] = relationship("Metric", back_populates="host", cascade="all, delete-orphan")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="host", cascade="all, delete-orphan")