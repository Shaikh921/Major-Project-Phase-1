"""
Unit Tests for Time-Series Forecaster and Predictive Time-to-Threshold (M2-FR3 / M5-FR4).
"""

from datetime import datetime, timezone, timedelta
from ai_engine.forecaster import TimeSeriesForecaster


def test_time_to_threshold_projected_breach():
    """
    Tests that a steady growth trajectory accurately projects the countdown to threshold breach.
    """
    now = datetime.now(timezone.utc)
    # Simulate disk utilization climbing 1% per hour starting from 80%
    timestamps = [now + timedelta(hours=i) for i in range(10)]
    values = [80.0 + float(i) for i in range(10)]  # 80%, 81%, ..., 89%

    res = TimeSeriesForecaster.forecast(
        timestamps=timestamps,
        values=values,
        horizon_hours=24,
        critical_threshold=95.0,
    )

    assert res["model_status"] == "fitted"
    assert res["current_value"] == 89.0
    assert res["trend_slope_per_hour"] > 0.9  # approx ~1.0%/hr

    # Headroom remaining: 95.0 - 89.0 = 6.0%. At 1%/hr, hours remaining should be ~6 hours
    tt = res["time_to_threshold"]
    assert tt is not None
    assert tt["status"] == "projected_breach"
    assert 5.0 <= tt["hours_remaining"] <= 7.0
    assert tt["breach_eta"] is not None
    assert "will be reached in" in tt["message"]

    # Forecast points verification
    assert len(res["forecast_points"]) == 24
    assert res["forecast_points"][0]["predicted_value"] >= 89.0


def test_time_to_threshold_stable_trajectory():
    """
    Tests that a stable or decreasing metric is recognized as safe with no breach countdown.
    """
    now = datetime.now(timezone.utc)
    timestamps = [now + timedelta(hours=i) for i in range(10)]
    values = [30.0 + ((-1) ** i) * 0.5 for i in range(10)]  # flat around 30%

    res = TimeSeriesForecaster.forecast(
        timestamps=timestamps,
        values=values,
        horizon_hours=24,
        critical_threshold=90.0,
    )

    tt = res["time_to_threshold"]
    assert tt is not None
    assert tt["status"] in ["stable_or_decreasing", "safe"]
    assert tt["hours_remaining"] is None
