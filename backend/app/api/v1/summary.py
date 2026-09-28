"""
Summary API Router.

Provides fleet-wide aggregation and individual host health status snapshots
(Section 7: /api/summary).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_viewer
from backend.app.models.user import User
from backend.app.schemas.summary import FleetSummaryResponse
from backend.app.services.metric_service import get_fleet_summary

router = APIRouter(prefix="/summary", tags=["Summary"])


@router.get("", response_model=FleetSummaryResponse)
def get_fleet_health_summary(
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Returns the latest sample and worst active alert status per host across the fleet.
    Used to populate high-level monitoring dashboard overviews.
    """
    return get_fleet_summary(db)
