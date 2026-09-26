"""
AI & Forecasting Pydantic Schemas.

Data transfer objects for AI anomaly scoring, feature attribution,
predictive time-to-threshold forecasting, and model registry lifecycle.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any


class FeatureContribution(BaseModel):
    """Percentage attribution weight and raw value of a single metric dimension."""
    metric: str
    value: float
    contribution_percent: float
    z_score: float


class AnomalyScoreRequest(BaseModel):
    """Payload to evaluate a telemetry sample for multivariate anomalies."""
    hostname: Optional[str] = None
    cpu_percent: float = Field(..., ge=0.0, le=100.0)
    memory_percent: float = Field(..., ge=0.0, le=100.0)
    disk_percent: float = Field(..., ge=0.0, le=100.0)
    network_sent_mb: float = Field(default=0.0, ge=0.0)
    network_received_mb: float = Field(default=0.0, ge=0.0)


class AnomalyScoreResponse(BaseModel):
    """Result of multivariate anomaly scoring with explainability breakdown."""
    is_anomaly: bool
    anomaly_score: float = Field(..., description="Normalized score 0.0-1.0 (>0.60 is anomalous)")
    raw_decision_score: float
    feature_contributions: List[FeatureContribution]
    explanation: str


class ForecastDataPoint(BaseModel):
    """Single projected future timestamp point with confidence intervals."""
    timestamp: str
    predicted_value: float
    upper_bound: float
    lower_bound: float


class TimeToThresholdInfo(BaseModel):
    """Predictive failure timeline countdown (M5-FR4)."""
    hours_remaining: Optional[float] = None
    breach_eta: Optional[str] = None
    status: str = Field(..., description="'projected_breach', 'already_breached', 'safe', or 'stable_or_decreasing'")
    growth_rate_per_hour: Optional[float] = None
    message: str


class ForecastResponse(BaseModel):
    """Complete time-series forecast and predictive failure timeline response (Section 7)."""
    host_id: int
    hostname: str
    metric: str
    current_value: float
    critical_threshold: float
    trend_slope_per_hour: float
    time_to_threshold: Optional[TimeToThresholdInfo] = None
    forecast_points: List[ForecastDataPoint]
    model_status: str


class ModelTrainRequest(BaseModel):
    """Payload to trigger model fitting/retraining."""
    host_id: Optional[int] = Field(None, description="Optional Host ID to train a host-specific model (defaults to global fleet)")
    contamination: float = Field(default=0.05, ge=0.01, le=0.20)
    version: str = Field(default="v1")


class ModelTrainResponse(BaseModel):
    """Result summary of model training job."""
    status: str
    model_name: str
    version: str
    samples_trained: int
    file_path: str
    baseline_mean: Dict[str, float]
    baseline_std: Dict[str, float]


class ModelMetadataResponse(BaseModel):
    """Registered model metadata record."""
    model_name: str
    version: str
    file_path: str
    trained_at: str
    sample_count: int
    contamination: float
    training_info: Dict[str, Any]
