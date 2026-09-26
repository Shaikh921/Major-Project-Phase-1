"""
Cost Optimization API Router.

Endpoints for cloud spend breakdown and actionable rightsizing recommendations (M3).
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.cost import (
    CostSummaryResponse,
    CostRecommendationRead,
    CostRecommendationAction,
)
from backend.app.services.cost_service import (
    generate_fleet_cost_analysis,
    update_recommendation_status,
)

router = APIRouter(prefix="/cost", tags=["Cost Optimization"])


@router.get("/summary", response_model=CostSummaryResponse)
def get_cost_summary(
    db: Session = Depends(get_db),
):
    """
    Returns total estimated spend, savings opportunities, idle asset counts,
    and active rightsizing recommendations.
    """
    return generate_fleet_cost_analysis(db)


@router.patch("/recommendations/{rec_id}", response_model=CostRecommendationRead)
def update_recommendation(
    rec_id: int,
    action: CostRecommendationAction,
    db: Session = Depends(get_db),
):
    """
    Updates the status of a cost recommendation (e.g. accepted, dismissed).
    """
    rec = update_recommendation_status(db, rec_id, action)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cost recommendation with ID {rec_id} not found.",
        )
    return CostRecommendationRead(
        id=rec.id,
        host_id=rec.host_id,
        hostname=rec.host.hostname if rec.host else None,
        recommendation_type=rec.recommendation_type,
        current_instance_type=rec.current_instance_type,
        suggested_instance_type=rec.suggested_instance_type,
        current_monthly_spend_usd=rec.current_monthly_spend_usd,
        estimated_monthly_spend_usd=rec.estimated_monthly_spend_usd,
        estimated_monthly_savings_usd=rec.estimated_monthly_savings_usd,
        rationale=rec.rationale,
        status=rec.status,
        confidence_score=rec.confidence_score,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )
