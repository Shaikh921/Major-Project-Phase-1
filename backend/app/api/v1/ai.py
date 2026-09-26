"""
AI Anomaly Scoring & Model Registry API Router.

Endpoints for multivariate anomaly evaluation, model training jobs,
and inspecting registered ML checkpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.ai import (
    AnomalyScoreRequest,
    AnomalyScoreResponse,
    ModelTrainRequest,
    ModelTrainResponse,
    ModelMetadataResponse,
)
from backend.app.services.ai_service import (
    score_telemetry_sample,
    train_anomaly_model,
    list_registered_models,
)

router = APIRouter(prefix="/ai", tags=["AI & Machine Learning"])


@router.post("/score", response_model=AnomalyScoreResponse)
def score_sample(
    payload: AnomalyScoreRequest,
):
    """
    Evaluates a single multi-metric telemetry sample in near-real-time (M2-FR2).
    Returns an anomaly score (0.0 - 1.0) and exact feature attribution percentages (M5-FR5).
    """
    return score_telemetry_sample(payload)


@router.post("/train", response_model=ModelTrainResponse, status_code=status.HTTP_201_CREATED)
def trigger_model_training(
    payload: ModelTrainRequest,
    db: Session = Depends(get_db),
):
    """
    Trains or retrains an Isolation Forest anomaly detector using historical telemetry (M2-FR1/M2-FR5).
    Saves the checkpoint to the model registry.
    """
    try:
        return train_anomaly_model(db, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/models", response_model=List[ModelMetadataResponse])
def get_registered_models():
    """
    Lists all saved model checkpoints and training parameters (M2-FR6).
    """
    return list_registered_models()
