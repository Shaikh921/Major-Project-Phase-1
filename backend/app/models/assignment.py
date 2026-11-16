"""
Normalized Environment and Host Assignment Models (Phase 9A.1 Hybrid RBAC).

Implements authoritative normalized resource-scoping entities:
- UserEnvironmentAssignment: Grants a user operational/administrative access to an environment tier.
- UserHostAssignment: Grants a user operational/administrative access to a specific host.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base


class AssignmentStatus:
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    ALL_STATUSES = [ACTIVE, REVOKED]


class UserEnvironmentAssignment(Base):
    """
    Authoritative assignment of a user to an entire deployment environment.
    """
    __tablename__ = "user_environment_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    environment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=AssignmentStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    granted_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revoked_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    granted_by: Mapped["User"] = relationship("User", foreign_keys=[granted_by_id])
    revoked_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[revoked_by_id])

    __table_args__ = (
        Index(
            "uq_user_env_active",
            "user_id",
            "environment",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )


class UserHostAssignment(Base):
    """
    Authoritative assignment of a user to an individual host.
    """
    __tablename__ = "user_host_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    host_id: Mapped[int] = mapped_column(
        ForeignKey("hosts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=AssignmentStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    granted_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revoked_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    host: Mapped["Host"] = relationship("Host", foreign_keys=[host_id])
    granted_by: Mapped["User"] = relationship("User", foreign_keys=[granted_by_id])
    revoked_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[revoked_by_id])

    __table_args__ = (
        Index(
            "uq_user_host_active",
            "user_id",
            "host_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

