"""
Unit Tests for Multivariate AI Anomaly Detector and Model Registry.
"""

import os
import shutil
from ai_engine.anomaly_detector import MultivariateAnomalyDetector
from ai_engine.model_registry import ModelRegistry


def generate_synthetic_training_data(n_samples: int = 50):
    """Generates synthetic normal telemetry samples."""
    samples = []
    for i in range(n_samples):
        samples.append({
            "cpu_percent": 20.0 + (i % 10),
            "memory_percent": 45.0 + (i % 5),
            "disk_percent": 50.0 + (i * 0.05),
            "network_sent_mb": 0.5 + (i * 0.01),
            "network_received_mb": 1.2 + (i * 0.02),
        })
    return samples


def test_detector_training_and_scoring():
    """Tests fitting the Isolation Forest and scoring normal vs abnormal samples."""
    detector = MultivariateAnomalyDetector(contamination=0.05)
    train_data = generate_synthetic_training_data(60)

    train_info = detector.train(train_data)
    assert train_info["status"] == "trained"
    assert train_info["samples_trained"] == 60
    assert detector.is_trained is True

    # 1. Score normal sample (close to training distribution)
    normal_sample = {
        "cpu_percent": 22.0,
        "memory_percent": 46.0,
        "disk_percent": 51.0,
        "network_sent_mb": 0.6,
        "network_received_mb": 1.3,
    }
    normal_res = detector.score_sample(normal_sample)
    assert normal_res["is_anomaly"] is False
    assert normal_res["anomaly_score"] < 0.60

    # 2. Score abnormal sample (CPU spike + egress explosion)
    anomalous_sample = {
        "cpu_percent": 95.0,
        "memory_percent": 88.0,
        "disk_percent": 52.0,
        "network_sent_mb": 85.0,
        "network_received_mb": 1.5,
    }
    anomaly_res = detector.score_sample(anomalous_sample)
    assert anomaly_res["is_anomaly"] is True
    assert anomaly_res["anomaly_score"] >= 0.60
    assert len(anomaly_res["feature_contributions"]) == 5
    assert len(anomaly_res["explanation"]) > 0


def test_sensitivity_calibration():
    """Tests feedback-tuned dynamic sensitivity adjustments (M2-FR7)."""
    detector = MultivariateAnomalyDetector()
    initial_offset = detector.sensitivity_offset

    # False positive reduces sensitivity
    new_offset = detector.adjust_sensitivity("false_positive", step=0.05)
    assert new_offset < initial_offset

    # True positive increases sensitivity
    boosted_offset = detector.adjust_sensitivity("true_positive", step=0.05)
    assert boosted_offset > new_offset


def test_model_registry_save_and_load(tmp_path):
    """Tests serializing and restoring model checkpoints with joblib."""
    temp_dir = str(tmp_path / "test_models")
    registry = ModelRegistry(models_dir=temp_dir)

    detector = MultivariateAnomalyDetector()
    train_data = generate_synthetic_training_data(20)
    info = detector.train(train_data)

    file_path = registry.save_model("test_detector", detector, info, version="v1")
    assert os.path.exists(file_path)

    # Load back
    loaded = registry.load_model("test_detector", version="v1")
    assert loaded is not None
    assert loaded.is_trained is True
    assert loaded.sample_count == 20
