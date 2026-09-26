"""
AI Intelligence & Forecasting Service.

Orchestrates model training over database metrics, real-time multivariate anomaly scoring,
predictive failure forecasting, and explainability annotations.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import Alert, AlertFeedback
from backend.app.schemas.ai import (
    AnomalyScoreRequest,
    AnomalyScoreResponse,
    FeatureContribution,
    ForecastResponse,
    TimeToThresholdInfo,
    ForecastDataPoint,
    ModelTrainRequest,
    ModelTrainResponse,
    ModelMetadataResponse,
)
from backend.app.services.host_service import get_host
from ai_engine.anomaly_detector import MultivariateAnomalyDetector
from ai_engine.forecaster import TimeSeriesForecaster
from ai_engine.model_registry import ModelRegistry

# Global singleton detector & registry cache
_registry = ModelRegistry()
_global_detector: Optional[MultivariateAnomalyDetector] = _registry.load_model("fleet_anomaly_detector", version="v1")
if _global_detector is None:
    _global_detector = _registry.load_model("production_cloud_anomaly_model", version="v1")
if _global_detector is None:
    _global_detector = MultivariateAnomalyDetector()


def get_global_detector() -> MultivariateAnomalyDetector:
    """Returns the active cached multivariate anomaly detector instance."""
    global _global_detector
    return _global_detector


def reset_global_detector() -> None:
    """Resets the in-memory global detector state (useful for test isolation)."""
    global _global_detector
    _global_detector = _registry.load_model("fleet_anomaly_detector", version="v1")
    if _global_detector is None:
        _global_detector = _registry.load_model("production_cloud_anomaly_model", version="v1")
    if _global_detector is None:
        _global_detector = MultivariateAnomalyDetector()


def train_anomaly_model(db: Session, req: ModelTrainRequest) -> ModelTrainResponse:
    """
    Fetches historical metrics from DB, trains the Isolation Forest,
    and saves the checkpoint in the model registry.
    """
    statement = select(Metric).order_by(desc(Metric.timestamp))
    if req.host_id:
        statement = statement.where(Metric.host_id == req.host_id)
    statement = statement.limit(5000)

    records = list(db.scalars(statement).all())
    if len(records) < 5:
        raise ValueError(
            f"Insufficient telemetry data for training (found {len(records)} samples, minimum 5 required)."
        )

    samples = [
        {
            "cpu_percent": r.cpu_percent,
            "memory_percent": r.memory_percent,
            "disk_percent": r.disk_percent,
            "network_sent_mb": r.network_sent_mb,
            "network_received_mb": r.network_received_mb,
        }
        for r in records
    ]

    model_name = f"host_{req.host_id}_anomaly_detector" if req.host_id else "fleet_anomaly_detector"
    detector = MultivariateAnomalyDetector(contamination=req.contamination)
    train_info = detector.train(samples)

    # Save to disk
    file_path = _registry.save_model(model_name, detector, train_info, version=req.version)

    # If fleet model, update active memory detector
    if not req.host_id:
        global _global_detector
        _global_detector = detector

    return ModelTrainResponse(
        status="success",
        model_name=model_name,
        version=req.version,
        samples_trained=train_info["samples_trained"],
        file_path=file_path,
        baseline_mean=train_info["baseline_mean"],
        baseline_std=train_info["baseline_std"],
    )


def score_telemetry_sample(sample_in: AnomalyScoreRequest) -> AnomalyScoreResponse:
    """
    Scores a single sample using the active multivariate detector and returns explainability breakdown.
    """
    detector = get_global_detector()
    result = detector.score_sample(sample_in.model_dump())

    contributions = [
        FeatureContribution(**c) for c in result["feature_contributions"]
    ]

    return AnomalyScoreResponse(
        is_anomaly=result["is_anomaly"],
        anomaly_score=result["anomaly_score"],
        raw_decision_score=result["raw_decision_score"],
        feature_contributions=contributions,
        explanation=result["explanation"],
    )


def evaluate_and_record_ai_anomaly(
    db: Session,
    host: Host,
    metric: Metric,
) -> Optional[Alert]:
    """
    Evaluates an incoming sample for AI anomalies. If anomalous, raises/updates
    a deduplicated alert with kind='anomaly' annotated with top contributing metrics (M5-FR5).
    Falls back to threshold-only alerting until model is trained with sufficient history (M2 NFR).
    """
    detector = get_global_detector()
    if not detector.is_trained:
        return None

    sample_dict = {
        "cpu_percent": metric.cpu_percent,
        "memory_percent": metric.memory_percent,
        "disk_percent": metric.disk_percent,
        "network_sent_mb": metric.network_sent_mb,
        "network_received_mb": metric.network_received_mb,
    }
    # Operational guard: Low/safe utilization (e.g. CPU/RAM/Disk <= 50%) is healthy baseline, not an incident
    if (
        metric.cpu_percent <= 50.0
        and metric.memory_percent <= 50.0
        and metric.disk_percent <= 50.0
        and (metric.network_sent_mb or 0.0) <= 20.0
    ):
        return None

    score_res = detector.score_sample(sample_dict)

    if not score_res["is_anomaly"]:
        # If active anomaly alert exists and metric returned to normal, auto-resolve
        stmt = select(Alert).where(
            Alert.host_id == host.id,
            Alert.kind == "anomaly",
            Alert.status.in_(["active", "acknowledged"]),
        )
        existing = db.scalar(stmt)
        if existing:
            existing.status = "resolved"
            existing.resolved_at = datetime.now(timezone.utc)
            db.commit()
        return None

    # Anomaly detected: find top contributing metric
    top_feature = score_res["feature_contributions"][0]["metric"] if score_res["feature_contributions"] else "multivariate"
    top_pct = score_res["feature_contributions"][0]["contribution_percent"] if score_res["feature_contributions"] else 100.0

    # Check existing open anomaly alert for deduplication
    existing_stmt = select(Alert).where(
        Alert.host_id == host.id,
        Alert.kind == "anomaly",
        Alert.status.in_(["active", "acknowledged"]),
    )
    existing_alert = db.scalar(existing_stmt)

    msg = f"AI Anomaly detected (Score: {score_res['anomaly_score']:.2f}). {score_res['explanation']}"
    severity = "critical" if score_res["anomaly_score"] >= 0.80 else "warning"

    if existing_alert:
        existing_alert.value = score_res["anomaly_score"]
        existing_alert.severity = severity
        existing_alert.message = msg
        existing_alert.metric = top_feature
        db.commit()
        db.refresh(existing_alert)
        return existing_alert
    else:
        new_alert = Alert(
            host_id=host.id,
            metric=top_feature,
            kind="anomaly",
            severity=severity,
            message=msg,
            value=score_res["anomaly_score"],
            threshold=0.60,
            status="active",
            created_at=metric.timestamp or datetime.now(timezone.utc),
        )
        db.add(new_alert)
        db.commit()
        db.refresh(new_alert)
        return new_alert


def generate_metric_forecast(
    db: Session,
    host_id: int,
    metric_name: str = "cpu_percent",
    horizon_hours: int = 24,
    critical_threshold: float = 95.0,
) -> ForecastResponse:
    """
    Fetches historical metrics for a host and calculates future trend projections and Time-to-Threshold (Section 7).
    """
    host = get_host(db, host_id)
    if not host:
        raise ValueError(f"Host with ID {host_id} not found.")

    valid_metrics = ["cpu_percent", "memory_percent", "disk_percent", "network_sent_mb", "network_received_mb"]
    if metric_name not in valid_metrics:
        raise ValueError(f"Invalid metric '{metric_name}'. Supported: {', '.join(valid_metrics)}")

    # Fetch historical points
    statement = (
        select(Metric)
        .where(Metric.host_id == host_id)
        .order_by(Metric.timestamp)
        .limit(1000)
    )
    records = list(db.scalars(statement).all())

    timestamps = [r.timestamp for r in records]
    values = [float(getattr(r, metric_name, 0.0)) for r in records]

    forecast_res = TimeSeriesForecaster.forecast(
        timestamps=timestamps,
        values=values,
        horizon_hours=horizon_hours,
        step_minutes=60,
        critical_threshold=critical_threshold,
    )

    tt_info = None
    if forecast_res["time_to_threshold"]:
        tt = forecast_res["time_to_threshold"]
        tt_info = TimeToThresholdInfo(
            hours_remaining=tt.get("hours_remaining"),
            breach_eta=tt.get("breach_eta"),
            status=tt["status"],
            growth_rate_per_hour=tt.get("growth_rate_per_hour"),
            message=tt["message"],
        )

    forecast_points = [
        ForecastDataPoint(**fp) for fp in forecast_res["forecast_points"]
    ]

    return ForecastResponse(
        host_id=host.id,
        hostname=host.hostname,
        metric=metric_name,
        current_value=forecast_res["current_value"],
        critical_threshold=critical_threshold,
        trend_slope_per_hour=forecast_res["trend_slope_per_hour"],
        time_to_threshold=tt_info,
        forecast_points=forecast_points,
        model_status=forecast_res["model_status"],
    )


def list_registered_models() -> List[ModelMetadataResponse]:
    """Lists all saved model checkpoints from the registry."""
    return [ModelMetadataResponse(**m) for m in _registry.list_models()]
