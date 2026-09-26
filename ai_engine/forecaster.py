"""
Time-Series Telemetry Forecaster & Predictive Failure Timeline.

Projects future metric utilization curves over configurable horizons (24-72h) (M2-FR3)
and computes exact 'Time-to-Threshold' countdown estimates (M5-FR4 / Section 8),
such as 'disk-full in 14.2 hours at current growth rate'.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import numpy as np


class TimeSeriesForecaster:
    """
    Fits trend models to historical time-series metrics and forecasts future resource trajectories.
    """

    @staticmethod
    def forecast(
        timestamps: List[datetime],
        values: List[float],
        horizon_hours: int = 24,
        step_minutes: int = 60,
        critical_threshold: float = 95.0,
    ) -> Dict[str, Any]:
        """
        Calculates projected time-series and predictive time-to-threshold metrics.
        
        Args:
            timestamps: List of chronological sample datetime objects.
            values: List of metric values (e.g. CPU% or Disk%).
            horizon_hours: Projection window in hours.
            step_minutes: Frequency interval for forecasted data points.
            critical_threshold: Critical upper boundary to evaluate for failure prediction.
            
        Returns:
            Dictionary containing:
            - current_value: float
            - trend_slope_per_hour: float
            - time_to_threshold: Optional dictionary with countdown hours, eta, and status
            - forecast_points: List of projected {timestamp, predicted_value, upper_bound, lower_bound}
        """
        if len(values) < 2:
            current = values[-1] if values else 0.0
            return {
                "current_value": round(current, 2),
                "trend_slope_per_hour": 0.0,
                "time_to_threshold": None,
                "forecast_points": [],
                "model_status": "insufficient_data",
            }

        # Convert timestamps to relative hour offsets from start
        base_time = timestamps[0]
        t_hours = np.array([
            (ts - base_time).total_seconds() / 3600.0
            for ts in timestamps
        ], dtype=np.float64)

        y = np.array(values, dtype=np.float64)

        # Fit robust Linear Regression trend line y = slope * t + intercept
        # using least squares
        A = np.vstack([t_hours, np.ones(len(t_hours))]).T
        slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]

        # Calculate historical residual standard error for confidence intervals
        predictions_history = slope * t_hours + intercept
        residuals = y - predictions_history
        residual_std = float(np.std(residuals)) if len(residuals) > 2 else 2.0

        current_time = timestamps[-1]
        current_val = float(values[-1])
        current_t_hours = (current_time - base_time).total_seconds() / 3600.0

        # Generate future projection points
        total_steps = int((horizon_hours * 60) / step_minutes)
        forecast_points: List[Dict[str, Any]] = []

        for step in range(1, total_steps + 1):
            future_delta_hours = (step * step_minutes) / 60.0
            future_t = current_t_hours + future_delta_hours
            future_ts = current_time + timedelta(hours=future_delta_hours)

            # Trend projection with bounds capped between 0 and 100 for percentages
            pred = float(slope * future_t + intercept)
            # Clip between 0 and 100
            pred_clamped = float(np.clip(pred, 0.0, 100.0))
            
            margin = 1.96 * residual_std * (1.0 + (future_delta_hours / horizon_hours) * 0.5)
            upper_bound = float(np.clip(pred_clamped + margin, 0.0, 100.0))
            lower_bound = float(np.clip(pred_clamped - margin, 0.0, 100.0))

            forecast_points.append({
                "timestamp": future_ts.isoformat(),
                "predicted_value": round(pred_clamped, 2),
                "upper_bound": round(upper_bound, 2),
                "lower_bound": round(lower_bound, 2),
            })

        # Calculate Time-to-Threshold (M5-FR4 Predictive Failure Countdown)
        time_to_threshold = None
        if current_val >= critical_threshold:
            time_to_threshold = {
                "hours_remaining": 0.0,
                "breach_eta": current_time.isoformat(),
                "status": "already_breached",
                "message": f"Metric is currently at {current_val:.1f}%, exceeding the {critical_threshold:.1f}% threshold.",
            }
        elif slope > 0.001:
            # Positive growth trajectory
            remaining_headroom = critical_threshold - current_val
            hours_to_breach = remaining_headroom / slope
            
            if hours_to_breach <= horizon_hours * 3.0:  # Within foreseeable horizon
                breach_eta = current_time + timedelta(hours=hours_to_breach)
                time_to_threshold = {
                    "hours_remaining": round(hours_to_breach, 1),
                    "breach_eta": breach_eta.isoformat(),
                    "status": "projected_breach",
                    "growth_rate_per_hour": round(slope, 3),
                    "message": (
                        f"Threshold of {critical_threshold:.1f}% will be reached in "
                        f"{hours_to_breach:.1f} hours at current growth rate (+{slope:.2f}%/hr)."
                    ),
                }
            else:
                time_to_threshold = {
                    "hours_remaining": round(hours_to_breach, 1),
                    "breach_eta": None,
                    "status": "safe",
                    "growth_rate_per_hour": round(slope, 3),
                    "message": f"Growth is gradual (+{slope:.2f}%/hr). No breach expected within {horizon_hours} hours.",
                }
        else:
            time_to_threshold = {
                "hours_remaining": None,
                "breach_eta": None,
                "status": "stable_or_decreasing",
                "growth_rate_per_hour": round(slope, 3),
                "message": "Metric trajectory is stable or trending downwards. No breach projected.",
            }

        return {
            "current_value": round(current_val, 2),
            "trend_slope_per_hour": round(float(slope), 4),
            "critical_threshold": critical_threshold,
            "time_to_threshold": time_to_threshold,
            "forecast_points": forecast_points,
            "model_status": "fitted",
        }
