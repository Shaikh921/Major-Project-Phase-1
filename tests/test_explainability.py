"""
Unit Tests for AI Explainability & Feature Attribution Engine.
"""

import numpy as np
from ai_engine.explainability import FeatureAttributionEngine


def test_compute_contributions_identifies_top_driver():
    """Tests that the feature attribution engine correctly identifies the primary anomalous metric."""
    # Baseline: mean = [20, 40, 50, 1, 2], std = [5, 10, 10, 1, 1]
    baseline_mean = np.array([20.0, 40.0, 50.0, 1.0, 2.0])
    baseline_std = np.array([5.0, 10.0, 10.0, 1.0, 1.0])

    # Sample where CPU spikes significantly (95.0 vs 20.0)
    sample = np.array([95.0, 42.0, 51.0, 1.2, 2.1])

    contributions = FeatureAttributionEngine.compute_contributions(
        sample_features=sample,
        baseline_mean=baseline_mean,
        baseline_std=baseline_std,
    )

    assert len(contributions) == 5
    # CPU should be the highest contributing factor
    assert contributions[0]["metric"] == "cpu_percent"
    assert contributions[0]["contribution_percent"] > 70.0
    assert contributions[0]["z_score"] > 10.0


def test_generate_explanation_text():
    """Tests plain-English summary generation of top contributors."""
    contributions = [
        {"metric": "network_sent_mb", "contribution_percent": 65.0, "z_score": 5.2, "value": 150.0},
        {"metric": "cpu_percent", "contribution_percent": 25.0, "z_score": 2.0, "value": 75.0},
        {"metric": "memory_percent", "contribution_percent": 10.0, "z_score": 0.8, "value": 55.0},
    ]

    text = FeatureAttributionEngine.generate_explanation_text(contributions)
    assert "network_sent_mb (65.0%)" in text
    assert "cpu_percent (25.0%)" in text
