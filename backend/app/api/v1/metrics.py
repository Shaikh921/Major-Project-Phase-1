"""
Metric Ingestion and Query API Router.

Endpoints for telemetry agent submission and historical time-series retrieval.
"""

from datetime import datetime
from typing import Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.metric import (
    MetricCreate,
    MetricBatchCreate,
    MetricRead,
    MetricTimeSeriesResponse,
)
from backend.app.services.metric_service import (
    ingest_metric,
    ingest_metrics_batch,
    get_host_metrics,
)

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_metrics(
    payload: Union[MetricCreate, MetricBatchCreate],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Submits telemetry from a host collector agent (M1-FR1).
    Supports both single sample payloads and high-throughput batch lists.
    Auto-discovers and registers unknown hosts on arrival (M1-FR2).
    """
    if isinstance(payload, MetricBatchCreate):
        return ingest_metrics_batch(db, payload)
    else:
        metric, alerts = ingest_metric(db, payload)
        return {
            "status": "success",
            "metric": MetricRead.model_validate(metric),
            "generated_alerts": len(alerts),
        }


@router.get("", response_model=MetricTimeSeriesResponse)
def get_metrics_timeseries(
    host_id: int = Query(..., description="Target host ID"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max sample points to return"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (UTC)"),
    db: Session = Depends(get_db),
):
    """
    Retrieves chronological time-series telemetry for charting and historical inspection (M1-FR4).
    """
    try:
        return get_host_metrics(
            db=db,
            host_id=host_id,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
