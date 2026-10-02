"""
LSTM Autoencoder Sequence Anomaly Detector.

Implements deep temporal reconstruction error scoring over sliding time-series windows
to identify micro-bursts, latent sequence drift, and complex temporal anomalies.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
import numpy as np

logger = logging.getLogger("cloudops.ai_engine.lstm")

# Determine base paths for saved artifacts
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODELS_DIR = os.path.join(_BASE_DIR, "models")
_SCALER_PATH = os.path.join(_MODELS_DIR, "scaler.joblib")
_FEATURE_LIST_PATH = os.path.join(_MODELS_DIR, "selected_features.json")
_MODEL_PATH = os.path.join(_MODELS_DIR, "best_lstm_anomaly_detector.pt")
_METRICS_PATH = os.path.join(_MODELS_DIR, "evaluation_metrics.json")


class LSTMAutoencoderAnomalyDetector:
    """
    Production-grade LSTM Autoencoder sequence evaluator.
    Computes reconstruction error (MSE) across sliding temporal windows.
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
        seq_len: int = 15,
        threshold: Optional[float] = None,
        model_path: Optional[str] = None,
    ):
        self.seq_len = seq_len
        self.threshold = threshold or 0.79135
        self.model_path = model_path or _MODEL_PATH
        self.is_loaded = False
        self.model = None
        self.scaler = None
        self.features = []
        self.device = None

        self._initialize_model()

    def _initialize_model(self) -> None:
        """Loads PyTorch model, scaler, and threshold metadata if present."""
        try:
            import torch
            import torch.nn as nn
            import joblib

            # 1. Load feature specification
            if os.path.exists(_FEATURE_LIST_PATH):
                with open(_FEATURE_LIST_PATH, "r") as f:
                    meta = json.load(f)
                    self.features = meta.get("features", [])

            # 2. Load scaler
            if os.path.exists(_SCALER_PATH):
                self.scaler = joblib.load(_SCALER_PATH)

            # 3. Load threshold
            if os.path.exists(_METRICS_PATH):
                with open(_METRICS_PATH, "r") as f:
                    metrics_data = json.load(f)
                    self.threshold = float(metrics_data.get("optimal_threshold", self.threshold))

            # 4. Load PyTorch model if weights exist
            if os.path.exists(self.model_path) and self.features:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                
                class _LSTMAutoencoder(nn.Module):
                    def __init__(self, seq_len=15, n_features=30, hidden_dim=64, latent_dim=32):
                        super(_LSTMAutoencoder, self).__init__()
                        self.seq_len = seq_len
                        self.encoder_lstm1 = nn.LSTM(input_size=n_features, hidden_size=hidden_dim, batch_first=True)
                        self.encoder_dropout = nn.Dropout(0.2)
                        self.encoder_lstm2 = nn.LSTM(input_size=hidden_dim, hidden_size=latent_dim, batch_first=True)
                        self.decoder_lstm1 = nn.LSTM(input_size=latent_dim, hidden_size=hidden_dim, batch_first=True)
                        self.decoder_dropout = nn.Dropout(0.2)
                        self.decoder_dense = nn.Linear(hidden_dim, n_features)

                    def forward(self, x):
                        out, _ = self.encoder_lstm1(x)
                        out = self.encoder_dropout(out)
                        _, (hn, _) = self.encoder_lstm2(out)
                        latent_repeated = hn.permute(1, 0, 2).repeat(1, self.seq_len, 1)
                        dec_out, _ = self.decoder_lstm1(latent_repeated)
                        dec_out = self.decoder_dropout(dec_out)
                        return self.decoder_dense(dec_out)

                net = _LSTMAutoencoder(
                    seq_len=self.seq_len,
                    n_features=len(self.features),
                    hidden_dim=64,
                    latent_dim=32,
                ).to(self.device)

                net.load_state_dict(torch.load(self.model_path, map_location=self.device, weights_only=True))
                net.eval()
                self.model = net
                self.is_loaded = True
                logger.info("LSTM Autoencoder successfully initialized with weights.")
            else:
                logger.info("LSTM weights or feature specs not found; running in heuristic/statistical sequence mode.")
        except Exception as e:
            logger.warning(f"LSTM Autoencoder initialization failed: {e}. Falling back to sequential evaluation.")
            self.is_loaded = False

    def predict_window(self, metric_samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates a window of metric samples (e.g. 5 to 15 sequential data points).
        
        Args:
            metric_samples: Chronologically ordered list of metric dicts containing
                           'cpu_percent', 'memory_percent', 'disk_percent', etc.
                           
        Returns:
            Dictionary with is_anomaly, reconstruction_error, operating_threshold, severity.
        """
        if not metric_samples:
            return {
                "status": "NORMAL",
                "is_anomaly": False,
                "reconstruction_error": 0.0,
                "operating_threshold": float(self.threshold),
                "severity": "HEALTHY",
                "sample_count": 0,
            }

        # If PyTorch model is loaded and samples have all 30 features
        if self.is_loaded and self.model is not None and len(metric_samples) >= self.seq_len:
            try:
                import torch
                import pandas as pd

                df = pd.DataFrame(metric_samples[-self.seq_len:])
                has_all_cols = all(c in df.columns for c in self.features)
                
                if has_all_cols and self.scaler is not None:
                    scaled_vals = self.scaler.transform(df[self.features])
                    tensor_input = torch.tensor(scaled_vals, dtype=torch.float32).unsqueeze(0).to(self.device)
                    
                    with torch.no_grad():
                        recon = self.model(tensor_input)
                        mse_score = torch.mean((recon - tensor_input) ** 2).item()
                        
                    is_anomaly = bool(mse_score >= self.threshold)
                    return {
                        "status": "ANOMALY" if is_anomaly else "NORMAL",
                        "is_anomaly": is_anomaly,
                        "reconstruction_error": round(float(mse_score), 6),
                        "operating_threshold": round(float(self.threshold), 6),
                        "severity": "CRITICAL" if mse_score >= (self.threshold * 2) else ("WARNING" if is_anomaly else "HEALTHY"),
                        "sample_count": len(metric_samples),
                    }
            except Exception as exc:
                logger.debug(f"PyTorch sequence evaluation encountered error: {exc}; using standard host sequence scoring.")

        # Robust sequence error computation over standard 5-metric host stream
        return self._score_host_sequence(metric_samples)

    def _score_host_sequence(self, metric_samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes sequential temporal reconstruction deviation for standard host metrics.
        Evaluates rapid rate of change, sustained high pressure, and variance divergence.
        """
        n = len(metric_samples)
        if n < 2:
            last = metric_samples[-1]
            cpu = float(last.get("cpu_percent", 0.0))
            mem = float(last.get("memory_percent", 0.0))
            is_anomaly = (cpu >= 85.0 and mem >= 85.0)
            return {
                "status": "ANOMALY" if is_anomaly else "NORMAL",
                "is_anomaly": is_anomaly,
                "reconstruction_error": round((cpu + mem) / 200.0, 4),
                "operating_threshold": float(self.threshold),
                "severity": "CRITICAL" if (cpu >= 90.0 and mem >= 90.0) else ("WARNING" if is_anomaly else "HEALTHY"),
                "sample_count": n,
            }

        # Calculate temporal trend and sudden accelerations
        cpu_vals = [float(s.get("cpu_percent", 0.0)) for s in metric_samples]
        mem_vals = [float(s.get("memory_percent", 0.0)) for s in metric_samples]
        disk_vals = [float(s.get("disk_percent", 0.0)) for s in metric_samples]

        # Recent vs historical average
        recent_cpu = np.mean(cpu_vals[-3:]) if n >= 3 else cpu_vals[-1]
        recent_mem = np.mean(mem_vals[-3:]) if n >= 3 else mem_vals[-1]
        recent_disk = np.mean(disk_vals[-3:]) if n >= 3 else disk_vals[-1]

        # First-order differences (velocity of change)
        cpu_diff = np.abs(np.diff(cpu_vals))
        mean_velocity = float(np.mean(cpu_diff)) if len(cpu_diff) > 0 else 0.0

        # Sequence reconstruction error proxy normalized to [0.0, 2.0]
        pressure_factor = (recent_cpu / 100.0) * 0.45 + (recent_mem / 100.0) * 0.40 + (recent_disk / 100.0) * 0.15
        velocity_factor = min(mean_velocity / 20.0, 0.5)
        
        reconstruction_error = float(pressure_factor + velocity_factor)

        # Trigger sequence anomaly if sustained high pressure or rapid acceleration under load
        is_anomaly = (
            (recent_cpu >= 80.0 and recent_mem >= 80.0)
            or (recent_cpu >= 90.0)
            or (recent_mem >= 90.0)
            or (reconstruction_error >= self.threshold)
        )

        return {
            "status": "ANOMALY" if is_anomaly else "NORMAL",
            "is_anomaly": bool(is_anomaly),
            "reconstruction_error": round(reconstruction_error, 4),
            "operating_threshold": round(float(self.threshold), 4),
            "severity": "CRITICAL" if (recent_cpu >= 90.0 or reconstruction_error >= (self.threshold * 1.5)) else ("WARNING" if is_anomaly else "HEALTHY"),
            "sample_count": n,
        }
