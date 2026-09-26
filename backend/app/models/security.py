"""
Security Event and Audit Log Models.

Handles authentication events, network intrusion detections, configuration changes,
and tamper-evident administrative audit records (M4-FR1 to M4-FR5).
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base

if TYPE_CHECKING:
    from backend.app.models.host import Host


class SecurityEvent(Base):
    """
    Security event detected via log analysis, flow logs, or behavioral heuristics.
    """
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    host_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("hosts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. "brute_force_ssh", "port_scan", "unauthorized_sudo", "suspicious_egress", "config_tampering"
    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False, index=True)
    # "low", "medium", "high", "critical"
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    destination_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False, index=True)
    # "open", "investigating", "mitigated", "false_positive"
    raw_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    host: Mapped[Optional["Host"]] = relationship("Host", backref="security_events")

    __table_args__ = (
        Index("ix_security_events_host_ts", "host_id", "timestamp"),
        Index("ix_security_events_sev_status", "severity", "status"),
    )


class AuditLog(Base):
    """
    Append-only administrative audit record tracking operator interventions,
    configuration adjustments, alert acknowledgments, and security policy modifications.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_email: Mapped[str] = mapped_column(String(120), default="system@ops.local", nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. "ACK_ALERT", "UPDATE_THRESHOLD", "DISMISS_RECOMMENDATION", "DEACTIVATE_HOST"
    target_resource: Mapped[str] = mapped_column(String(150), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(30), default="success", nullable=False)
    client_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
