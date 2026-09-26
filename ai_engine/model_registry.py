"""
Model Registry & Checkpoint Manager.

Handles serialization, versioning, persistence, and loading of trained
ML anomaly models and baseline scalers in the models/ directory (M2-FR5).
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import joblib

from ai_engine.anomaly_detector import MultivariateAnomalyDetector


class ModelRegistry:
    """
    Manages serialized ML model artifacts and metadata checkpoints.
    """

    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)
        self.metadata_file = os.path.join(self.models_dir, "registry_metadata.json")

    def _load_metadata(self) -> Dict[str, Any]:
        """Loads model registry metadata index."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Saves updated model registry metadata index."""
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def save_model(
        self,
        model_name: str,
        detector: MultivariateAnomalyDetector,
        training_info: Dict[str, Any],
        version: str = "v1",
    ) -> str:
        """
        Serializes and saves a trained MultivariateAnomalyDetector artifact.
        
        Returns:
            Relative path to the saved checkpoint file.
        """
        filename = f"{model_name}_{version}.joblib"
        file_path = os.path.join(self.models_dir, filename)

        checkpoint_data = {
            "model": detector.model,
            "scaler": detector.scaler,
            "baseline_mean": detector.baseline_mean,
            "baseline_std": detector.baseline_std,
            "sample_count": detector.sample_count,
            "contamination": detector.contamination,
            "sensitivity_offset": detector.sensitivity_offset,
            "is_trained": detector.is_trained,
        }

        joblib.dump(checkpoint_data, file_path)

        # Update metadata registry
        meta = self._load_metadata()
        meta[model_name] = {
            "model_name": model_name,
            "version": version,
            "file_path": file_path,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "sample_count": detector.sample_count,
            "contamination": detector.contamination,
            "training_info": training_info,
        }
        self._save_metadata(meta)

        return file_path

    def load_model(self, model_name: str, version: str = "v1") -> Optional[MultivariateAnomalyDetector]:
        """
        Loads a serialized model checkpoint into a MultivariateAnomalyDetector instance.
        """
        filename = f"{model_name}_{version}.joblib"
        file_path = os.path.join(self.models_dir, filename)

        if not os.path.exists(file_path):
            return None

        checkpoint = joblib.load(file_path)
        detector = MultivariateAnomalyDetector(
            contamination=checkpoint.get("contamination", 0.05),
        )
        detector.model = checkpoint["model"]
        detector.scaler = checkpoint["scaler"]
        detector.baseline_mean = checkpoint["baseline_mean"]
        detector.baseline_std = checkpoint["baseline_std"]
        detector.sample_count = checkpoint["sample_count"]
        detector.sensitivity_offset = checkpoint.get("sensitivity_offset", 0.0)
        detector.is_trained = checkpoint.get("is_trained", True)

        return detector

    def list_models(self) -> List[Dict[str, Any]]:
        """Lists all registered models and metadata."""
        meta = self._load_metadata()
        return list(meta.values())
