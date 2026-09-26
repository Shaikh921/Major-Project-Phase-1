"""
Forecast & Predictive Failure API Router.

Endpoints for retrieving future metric trajectories, growth trends,
and Time-to-Threshold countdown timelines (Section 7: /api/forecast & M2-FR3/M5-FR4).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.ai import ForecastResponse
from backend.app.services.ai_service import generate_metric_forecast

router = APIRouter(prefix="/forecast", tags=["Forecasting & AI"])


@router.get("", response_model=ForecastResponse)
def get_metric_forecast(
    host_id: int = Query(..., description="Target Host ID"),
    metric: str = Query(default="cpu_percent", description="Target metric (cpu_percent, memory_percent, disk_percent, network_sent_mb, network_received_mb)"),
    horizon_hours: int = Query(default=24, ge=1, le=168, description="Forecast horizon in hours (1h - 7d)"),
    critical_threshold: float = Query(default=95.0, ge=1.0, le=100.0, description="Critical failure threshold boundary to evaluate for countdown"),
    db: Session = Depends(get_db),
):
    """
    Generates a time-series forecast and computes the 'Time-to-Threshold' countdown.
    Provides plain-English predictive failure warnings (e.g. 'Disk full in 14.2 hours at current growth rate').
    """
    try:
        return generate_metric_forecast(
            db=db,
            host_id=host_id,
            metric_name=metric,
            horizon_hours=horizon_hours,
            critical_threshold=critical_threshold,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
