"""
Cost Optimization and Pricing Catalog Models.

Handles cloud instance pricing catalogs, spend estimations, and rightsizing / idle resource
recommendations (M3-FR1 to M3-FR7).
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base

if TYPE_CHECKING:
    from backend.app.models.host import Host


class PricingCatalog(Base):
    """
    Standard hourly instance unit pricing table by provider, region, and instance type.
    """
    __tablename__ = "pricing_catalog"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), default="AWS", nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(50), default="us-east-1", nullable=False)
    instance_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vcpus: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    memory_gb: Mapped[float] = mapped_column(Float, default=4.0, nullable=False)
    hourly_rate_usd: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)


class CostRecommendation(Base):
    """
    Actionable cost-optimization recommendation for idle, over-provisioned,
    or rightsizable cloud infrastructure resources.
    """
    __tablename__ = "cost_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    host_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("hosts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    recommendation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # e.g. "RIGHTSIZE_DOWN", "IDLE_TERMINATION", "RESERVED_INSTANCE_CANDIDATE"
    current_instance_type: Mapped[str] = mapped_column(String(50), nullable=False)
    suggested_instance_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    current_monthly_spend_usd: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_monthly_spend_usd: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_monthly_savings_usd: Mapped[float] = mapped_column(Float, nullable=False)
    
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False, index=True)
    # "open", "accepted", "dismissed", "implemented"
    confidence_score: Mapped[float] = mapped_column(Float, default=0.90, nullable=False)
    
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

    host: Mapped[Optional["Host"]] = relationship("Host", backref="cost_recommendations")
