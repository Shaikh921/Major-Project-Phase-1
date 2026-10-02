"""
Multivariate AI Anomaly Detection Engine.

Implements Isolation Forest scoring (M2-FR1/M2-FR2) on multi-dimensional telemetry
vectors [cpu, memory, disk, network_sent, network_received], combined with dynamic
sensitivity calibration (M2-FR7) and explainability attribution (M5-FR5).
"""

from typing import Dict, List, Any, Optional
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ai_engine.explainability import FeatureAttributionEngine


class MultivariateAnomalyDetector:
    """
    Multivariate Anomaly Detector using Isolation Forests and baseline statistical scaling.
    """

    FEATURE_NAMES = [
        "cpu_percent",
        "memory_percent",
        "disk_percent",
        "network_sent_mb",
        "network_received_mb",
    ]

    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state

        self.model: Optional[IsolationForest] = None
        self.scaler = StandardScaler()
        self.is_trained = False

        # Baseline statistics for explainability and normalization
        self.baseline_mean: Optional[np.ndarray] = None
        self.baseline_std: Optional[np.ndarray] = None
        self.sample_count: int = 0
        self.sensitivity_offset: float = 0.0  # Dynamic offset adjusted by operator feedback

    def _extract_matrix(self, samples: List[Dict[str, Any]]) -> np.ndarray:
        """Extracts a 2D numpy array [N, 5] from a list of metric sample dictionaries."""
        rows = []
        for s in samples:
            row = [
                float(s.get("cpu_percent", 0.0)),
                float(s.get("memory_percent", 0.0)),
                float(s.get("disk_percent", 0.0)),
                float(s.get("network_sent_mb", 0.0)),
                float(s.get("network_received_mb", 0.0)),
            ]
            rows.append(row)
        return np.array(rows, dtype=np.float64)

    def train(self, historical_samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fits the Isolation Forest and computes baseline feature distributions.
        
        Args:
            historical_samples: List of metric sample dictionaries with at least 10 entries.
            
        Returns:
            Dictionary summarizing training metrics and baseline parameters.
        """
        if len(historical_samples) < 5:
            raise ValueError(f"Insufficient historical samples for training: {len(historical_samples)} (minimum 5 required).")

        X = self._extract_matrix(historical_samples)
        self.sample_count = len(X)

        # Compute baseline statistical profile
        self.baseline_mean = np.mean(X, axis=0)
        self.baseline_std = np.std(X, axis=0)

        # Fit Scaler and Isolation Forest
        X_scaled = self.scaler.fit_transform(X)
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
        )
        self.model.fit(X_scaled)
        self.is_trained = True

        return {
            "status": "trained",
            "samples_trained": self.sample_count,
            "features": self.FEATURE_NAMES,
            "baseline_mean": {name: round(float(self.baseline_mean[i]), 2) for i, name in enumerate(self.FEATURE_NAMES)},
            "baseline_std": {name: round(float(self.baseline_std[i]), 2) for i, name in enumerate(self.FEATURE_NAMES)},
            "contamination": self.contamination,
        }

    def score_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scores a single telemetry sample in near-real-time.
        
        Returns:
            Dictionary containing:
            - is_anomaly: bool
            - anomaly_score: float (0.0 to 1.0, where >0.6 is anomalous)
            - raw_score: float (decision function score)
            - feature_contributions: List of metric attribution breakdown
            - explanation: Plain English summary of top drivers
        """
        if not self.is_trained or self.model is None:
            # Fallback heuristic if ML model is not yet trained with sufficient history
            return self._heuristic_fallback(sample)

        X_sample = self._extract_matrix([sample])
        X_scaled = self.scaler.transform(X_sample)

        # IsolationForest decision_function: negative means anomalous, positive means normal
        decision_score = float(self.model.decision_function(X_scaled)[0])
        is_model_anomaly = bool(self.model.predict(X_scaled)[0] == -1)

        # Map [-0.5, 0.5] linearly to [1.0, 0.0]
        # e.g., decision_score=-0.2 -> 0.70; decision_score=0.2 -> 0.30
        base_score = 0.5 - (decision_score * 1.2)
        base_score = float(np.clip(base_score + self.sensitivity_offset, 0.0, 1.0))

        cpu = float(sample.get("cpu_percent", 0.0))
        mem = float(sample.get("memory_percent", 0.0))
        disk = float(sample.get("disk_percent", 0.0))

        # Check for multi-dimensional extreme pressure
        is_extreme_pressure = (cpu >= 85.0 and mem >= 85.0) or (cpu >= 90.0 and disk >= 85.0)

        if is_model_anomaly or is_extreme_pressure or base_score >= 0.60:
            anomaly_score = max(base_score, 0.70 if is_extreme_pressure else 0.65)
            is_anomaly = True
        else:
            anomaly_score = min(base_score, 0.55)
            is_anomaly = False

        # Compute feature attribution explainability
        contributions = FeatureAttributionEngine.compute_contributions(
            sample_features=X_sample[0],
            baseline_mean=self.baseline_mean,
            baseline_std=self.baseline_std,
            feature_names=self.FEATURE_NAMES,
        )
        explanation = FeatureAttributionEngine.generate_explanation_text(contributions)

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": round(anomaly_score, 4),
            "raw_decision_score": round(decision_score, 4),
            "feature_contributions": contributions,
            "explanation": explanation,
        }

    def adjust_sensitivity(self, verdict: str, step: float = 0.05) -> float:
        """
        Calibrates the detection threshold based on operator feedback (M2-FR7):
        - 'false_positive': Decreases sensitivity offset to reduce future noise.
        - 'true_positive': Reinforces current sensitivity or slightly increases alertness.
        """
        if verdict == "false_positive":
            self.sensitivity_offset = max(-0.25, self.sensitivity_offset - step)
        elif verdict == "true_positive":
            self.sensitivity_offset = min(0.25, self.sensitivity_offset + (step / 2.0))
        return self.sensitivity_offset

    def _heuristic_fallback(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Heuristic fallback when no model is trained yet (M2 NFR fallback requirement).
        """
        cpu = float(sample.get("cpu_percent", 0.0))
        mem = float(sample.get("memory_percent", 0.0))
        disk = float(sample.get("disk_percent", 0.0))
        net_sent = float(sample.get("network_sent_mb", 0.0))
        net_recv = float(sample.get("network_received_mb", 0.0))

        # Check for multivariate pressure (e.g., both CPU and RAM elevated simultaneously)
        is_anomaly = False
        score = 0.1

        if (cpu > 75.0 and mem > 80.0) or (net_sent > 50.0 and cpu > 70.0) or disk > 90.0:
            is_anomaly = True
            score = 0.75

        features = np.array([cpu, mem, disk, net_sent, net_recv])
        default_mean = np.array([25.0, 45.0, 50.0, 1.0, 2.0])
        default_std = np.array([15.0, 20.0, 20.0, 5.0, 5.0])

        contributions = FeatureAttributionEngine.compute_contributions(
            sample_features=features,
            baseline_mean=default_mean,
            baseline_std=default_std,
            feature_names=self.FEATURE_NAMES,
        )

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": score,
            "raw_decision_score": 0.0,
            "feature_contributions": contributions,
            "explanation": FeatureAttributionEngine.generate_explanation_text(contributions),
        }
