"""
Diagnostic Command and Result Models (Phase 9A.1 Predefined Remote Diagnostics).

Implements authoritative schema for:
- DiagnosticAction: Whitelist of allowed predefined diagnostics.
- DiagnosticStatus: Server-side lifecycle states (PENDING, CLAIMED, COMPLETED, FAILED, TIMED_OUT, EXPIRED).
- DiagnosticCommand: Queued and executed diagnostic command specifications.
- DiagnosticResult: Cryptographically hashed, canonical execution output records.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base


class DiagnosticAction:
    PING_GATEWAY = "PING_GATEWAY"
    DNS_LOOKUP = "DNS_LOOKUP"
    SYSTEM_SUMMARY = "SYSTEM_SUMMARY"
    SCHEDULED_TASK_STATUS = "SCHEDULED_TASK_STATUS"
    SERVICE_STATUS = "SERVICE_STATUS"

    # Privileged Remote Power Operations
    REBOOT_HOST = "REBOOT_HOST"
    SHUTDOWN_HOST = "SHUTDOWN_HOST"
    ABORT_SHUTDOWN = "ABORT_SHUTDOWN"

    STANDARD_ACTIONS = [
        PING_GATEWAY,
        DNS_LOOKUP,
        SYSTEM_SUMMARY,
        SCHEDULED_TASK_STATUS,
        SERVICE_STATUS,
    ]

    POWER_ACTIONS = [
        REBOOT_HOST,
        SHUTDOWN_HOST,
        ABORT_SHUTDOWN,
    ]

    ALL_ACTIONS = STANDARD_ACTIONS + POWER_ACTIONS


class DiagnosticStatus:
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    EXPIRED = "EXPIRED"

    ALL_STATUSES = [
        PENDING,
        CLAIMED,
        COMPLETED,
        FAILED,
        TIMED_OUT,
        EXPIRED,
    ]

    TERMINAL_STATUSES = [
        COMPLETED,
        FAILED,
        TIMED_OUT,
        EXPIRED,
    ]


class DiagnosticCommand(Base):
    """
    Server-side authoritative diagnostic command entity.
    """
    __tablename__ = "diagnostic_commands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    host_id: Mapped[int] = mapped_column(
        ForeignKey("hosts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    target: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=DiagnosticStatus.PENDING,
        nullable=False,
        index=True,
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    claimed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    claimed_by_agent_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    hard_deadline_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    host: Mapped["Host"] = relationship("Host", foreign_keys=[host_id])
    requested_by: Mapped["User"] = relationship("User", foreign_keys=[requested_by_user_id])
    result: Mapped[Optional["DiagnosticResult"]] = relationship(
        "DiagnosticResult",
        back_populates="command",
        uselist=False,
        cascade="all, delete-orphan",
    )


class DiagnosticResult(Base):
    """
    Cryptographically verifiable execution result submitted by the diagnostic agent.
    """
    __tablename__ = "diagnostic_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command_id: Mapped[str] = mapped_column(
        ForeignKey("diagnostic_commands.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    exit_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    stdout: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    stderr: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    is_late: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    command: Mapped["DiagnosticCommand"] = relationship(
        "DiagnosticCommand",
        back_populates="result",
    )

