"""
Cost Optimization Pydantic Schemas.
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, Field


class CostRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    host_id: Optional[int] = None
    hostname: Optional[str] = None
    recommendation_type: str
    current_instance_type: str
    suggested_instance_type: Optional[str] = None
    current_monthly_spend_usd: float
    estimated_monthly_spend_usd: float
    estimated_monthly_savings_usd: float
    rationale: str
    status: str
    confidence_score: float
    created_at: datetime
    updated_at: datetime


class CostRecommendationAction(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "accepted"})  # accepted, dismissed, implemented


class CostByResource(BaseModel):
    host_id: int
    hostname: str
    environment: str
    instance_type: Optional[str] = "t3.medium"
    monthly_spend_usd: float
    utilization_score: float
    optimization_potential: float


class CostSummaryResponse(BaseModel):
    estimated_monthly_spend_usd: float
    estimated_potential_savings_usd: float
    total_monitored_resources: int
    idle_resources_count: int
    underutilized_resources_count: int
    currency: str = "USD"
    billing_status: str = "Estimated (Telemetry Driven)"
    spend_by_environment: Dict[str, float]
    top_cost_resources: List[CostByResource]
    active_recommendations: List[CostRecommendationRead]
