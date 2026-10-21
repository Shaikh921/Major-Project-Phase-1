"""
Metric Ingestion and Query API Router.

Endpoints for telemetry agent submission and historical time-series retrieval.
"""

from datetime import datetime
from typing import Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_viewer, verify_agent_credentials
from backend.app.models.user import User
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


VALID_PROVENANCE_TYPES = {"REAL_AGENT", "SIMULATED"}


def validate_telemetry_provenance(
    payload: Union[MetricCreate, MetricBatchCreate],
    credential_source_type: str,
) -> None:
    """
    Enforces telemetry source provenance based on the authenticated agent credential.
    
    Provenance Policy:
    - REAL_AGENT credential: only permits telemetry with source_type == 'REAL_AGENT'.
    - SIMULATED credential: only permits telemetry with source_type == 'SIMULATED'.
    - ALL credential: permits explicit valid provenance ('REAL_AGENT' or 'SIMULATED').
    - Missing, None, 'UNKNOWN', or malformed source types are strictly rejected with HTTP 403.
    - For batch requests, every item is validated before any persistence. If any item is
      disallowed, the entire batch is rejected with HTTP 403, creating zero hosts or metrics.
    """
    cred_source = (credential_source_type or "").strip().upper()
    
    if cred_source == "REAL_AGENT":
        allowed = {"REAL_AGENT"}
    elif cred_source == "SIMULATED":
        allowed = {"SIMULATED"}
    elif cred_source == "ALL":
        allowed = VALID_PROVENANCE_TYPES
    else:
        allowed = {cred_source} if cred_source in VALID_PROVENANCE_TYPES else set()

    items = payload.metrics if isinstance(payload, MetricBatchCreate) else [payload]

    for idx, item in enumerate(items):
        raw_source = item.source_type
        clean_source = raw_source.strip().upper() if isinstance(raw_source, str) else None
        
        # Explicit rejection for absent, UNKNOWN, malformed, or disallowed source types
        if not clean_source or clean_source == "UNKNOWN" or clean_source not in allowed:
            item_display = raw_source if raw_source is not None else "None (absent)"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Telemetry provenance violation: Credential authority '{credential_source_type}' "
                    f"does not permit source_type '{item_display}' for item {idx} ('{item.hostname}'). "
                    f"Expected explicit valid provenance matching credential authority {sorted(allowed)}."
                ),
            )
        
        # Canonicalize casing in-place for downstream persistence
        item.source_type = clean_source


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_metrics(
    payload: Union[MetricCreate, MetricBatchCreate],
    agent_info: Dict[str, Any] = Depends(verify_agent_credentials),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Submits telemetry from an authenticated host collector agent (M1-FR1).
    Supports both single sample payloads and high-throughput batch lists.
    Auto-discovers and registers unknown hosts on arrival (M1-FR2) for authenticated agents.
    Strictly validates telemetry source provenance against authenticated agent authority.
    """
    # Enforce telemetry source provenance before host auto-registration or metric insertion
    credential_source = agent_info.get("source_type", "UNKNOWN")
    validate_telemetry_provenance(payload, credential_source)

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
    current_user: User = Depends(get_current_viewer),
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
