"""
Metric Model.

Stores high-frequency time-series telemetry samples (CPU, memory, storage, and network)
emitted by host collection agents.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
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


class IngestedBatch(Base):
    """
    Durable record of processed metric batches to guarantee idempotent ingestion (REL-02).
    Prevents duplicate telemetry writes during client retries after network timeouts or lost ACKs.
    """
    __tablename__ = "ingested_batches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    batch_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    host_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("hosts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_alerts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )