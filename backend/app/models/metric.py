"""
Metric Model.

Stores high-frequency time-series telemetry samples (CPU, memory, storage, and network)
emitted by host collection agents.
"""

from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from backend.app.database.base import Base

if TYPE_CHECKING:
    from backend.app.models.host import Host


class Metric(Base):
    """
    Time-series metric sample representing system resource utilization at a single point in time.
    
    Attributes:
        id: Primary key identifier.
        host_id: Foreign key referencing the monitored Host.
        timestamp: UTC timestamp when the sample was recorded.
        cpu_percent: Overall CPU utilization percentage (0.0 - 100.0).
        memory_percent: RAM utilization percentage (0.0 - 100.0).
        disk_percent: Storage partition utilization percentage (0.0 - 100.0).
        network_sent_mb: Outbound network bandwidth delta in megabytes since last sample.
        network_received_mb: Inbound network bandwidth delta in megabytes since last sample.
    """
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    host_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("hosts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_percent: Mapped[float] = mapped_column(Float, nullable=False)
    disk_percent: Mapped[float] = mapped_column(Float, nullable=False)

    network_sent_mb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    network_received_mb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Relationships
    host: Mapped["Host"] = relationship("Host", back_populates="metrics")

    # Composite index for high-throughput time-series lookups (Section 5.1 of Master Doc)
    __table_args__ = (
        Index("ix_metrics_host_id_timestamp", "host_id", "timestamp"),
    )