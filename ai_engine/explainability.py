"""
Explainability & Feature Attribution Engine.

Computes exact percentage contribution of each metric dimension (CPU, RAM, Disk, Network)
when a multivariate anomaly is detected (M5-FR5 / Section 8), transforming opaque ML scores
into transparent, actionable insights for operators.
"""

from typing import Dict, List, Any
import numpy as np


class FeatureAttributionEngine:
    """
    Calculates feature importance and deviation attribution for multivariate telemetry samples.
    """

    FEATURE_NAMES = [
        "cpu_percent",
        "memory_percent",
        "disk_percent",
        "network_sent_mb",
        "network_received_mb",
    ]

    @staticmethod
    def compute_contributions(
        sample_features: np.ndarray,
        baseline_mean: np.ndarray,
        baseline_std: np.ndarray,
        feature_names: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculates normalized Z-score deviation contributions per feature.
        
        Args:
            sample_features: 1D array of metric values [cpu, mem, disk, net_sent, net_recv].
            baseline_mean: 1D array of mean values from training baseline.
            baseline_std: 1D array of standard deviations from training baseline.
            feature_names: Optional list of feature names.
            
        Returns:
            List of dictionaries sorted descending by contribution percentage, e.g.:
            [
                {"metric": "cpu_percent", "value": 96.0, "contribution_percent": 68.5, "z_score": 3.4},
                {"metric": "network_sent_mb", "value": 15.2, "contribution_percent": 21.0, "z_score": 2.1},
                ...
            ]
        """
        names = feature_names or FeatureAttributionEngine.FEATURE_NAMES
        
        # Guard against zero standard deviation
        safe_std = np.where(baseline_std <= 1e-6, 1.0, baseline_std)
        
        # Calculate absolute standardized deviations (Z-scores)
        z_scores = np.abs((sample_features - baseline_mean) / safe_std)
        
        # Avoid division by zero when sample exactly matches mean
        total_deviation = np.sum(z_scores)
        if total_deviation <= 1e-6:
            uniform_weight = round(100.0 / len(names), 1)
            return [
                {
                    "metric": name,
                    "value": float(sample_features[i]),
                    "contribution_percent": uniform_weight,
                    "z_score": 0.0,
                }
                for i, name in enumerate(names)
            ]

        # Calculate percentage contribution
        contributions = []
        for i, name in enumerate(names):
            pct = round(float((z_scores[i] / total_deviation) * 100.0), 1)
            contributions.append({
                "metric": name,
                "value": float(sample_features[i]),
                "contribution_percent": pct,
                "z_score": round(float(z_scores[i]), 2),
            })

        # Sort descending by highest contribution percentage
        contributions.sort(key=lambda x: x["contribution_percent"], reverse=True)
        return contributions

    @staticmethod
    def generate_explanation_text(contributions: List[Dict[str, Any]]) -> str:
        """
        Generates a concise plain-English explanation of top contributing factors.
        """
        if not contributions:
            return "No anomalous feature deviation detected."

        top_contributors = [
            f"{c['metric']} ({c['contribution_percent']}%)"
            for c in contributions
            if c["contribution_percent"] >= 15.0
        ]

        if not top_contributors:
            top = contributions[0]
            return f"Primary anomaly driver: {top['metric']} ({top['contribution_percent']}%)"

        return f"Primary anomaly drivers: {', '.join(top_contributors[:3])}"
