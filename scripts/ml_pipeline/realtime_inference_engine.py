import os
import json
import joblib
import torch
import torch.nn as nn
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCALER_PATH = os.path.join(BASE_DIR, "scaler.joblib")
FEATURE_LIST_PATH = os.path.join(BASE_DIR, "selected_features.json")
MODEL_PATH = os.path.join(BASE_DIR, "models", "best_lstm_anomaly_detector.pt")
METRICS_PATH = os.path.join(BASE_DIR, "models", "evaluation_metrics.json")

class LSTMAutoencoder(nn.Module):
    def __init__(self, seq_len=15, n_features=30, hidden_dim=64, latent_dim=32):
        super(LSTMAutoencoder, self).__init__()
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

class RealtimeCloudAnomalyDetector:
    def __init__(self):
        # 1. Load feature specification
        with open(FEATURE_LIST_PATH, "r") as f:
            meta = json.load(f)
            self.features = meta["features"]
            
        # 2. Load scaler
        self.scaler = joblib.load(SCALER_PATH)
        
        # 3. Load threshold
        with open(METRICS_PATH, "r") as f:
            metrics = json.load(f)
            self.threshold = metrics["optimal_threshold"]
            
        # 4. Load PyTorch model
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = LSTMAutoencoder(seq_len=15, n_features=len(self.features), hidden_dim=64, latent_dim=32).to(self.device)
        self.model.load_state_dict(torch.load(MODEL_PATH, map_location=self.device))
        self.model.eval()
        
    def predict_window(self, window_df):
        """
        Accepts a DataFrame of exactly 15 consecutive 1-minute rows containing the 30 metric features.
        Returns anomaly classification (Normal / Anomaly) and reconstruction error score.
        """
        if len(window_df) != 15:
            raise ValueError(f"Expected 15 consecutive time steps, received {len(window_df)}.")
            
        # Verify columns
        missing = [c for c in self.features if c not in window_df.columns]
        if missing:
            raise ValueError(f"Missing required metric columns: {missing}")
            
        # Scale window features
        scaled_vals = self.scaler.transform(window_df[self.features]) # (15, 30)
        
        # Convert to Tensor (1, 15, 30)
        tensor_input = torch.tensor(scaled_vals, dtype=torch.float32).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            recon = self.model(tensor_input)
            mse_score = torch.mean((recon - tensor_input) ** 2).item()
            
        is_anomaly = mse_score >= self.threshold
        
        return {
            "status": "ANOMALY" if is_anomaly else "NORMAL",
            "is_anomaly": bool(is_anomaly),
            "reconstruction_error": round(float(mse_score), 6),
            "operating_threshold": round(float(self.threshold), 6),
            "severity": "CRITICAL" if mse_score >= (self.threshold * 2) else ("WARNING" if is_anomaly else "HEALTHY")
        }

if __name__ == "__main__":
    print("=" * 70)
    print(" TESTING REAL-TIME INFERENCE ENGINE ")
    print("=" * 70)
    
    detector = RealtimeCloudAnomalyDetector()
    print(f"[1] Detector initialized with {len(detector.features)} features. Threshold: {detector.threshold:.4f}")
    
    # Load test sequence to test live prediction
    import zipfile
    with zipfile.ZipFile(os.path.join(BASE_DIR, "AIClusterKPI.zip"), "r") as z:
        test_df = pd.read_csv(z.open("test.csv"))
        
    # Sample a normal window (first 15 rows)
    normal_window = test_df.iloc[0:15]
    res_normal = detector.predict_window(normal_window)
    print("\n[2] Live Inference on Normal Stream Window:")
    print(json.dumps(res_normal, indent=2))
    
    # Sample an anomalous window
    anom_indices = test_df[test_df["label"] == 1].index
    if len(anom_indices) > 20:
        anom_idx = anom_indices[15]
        anom_window = test_df.iloc[anom_idx-14:anom_idx+1]
        res_anom = detector.predict_window(anom_window)
        print("\n[3] Live Inference on Anomalous Stream Window:")
        print(json.dumps(res_anom, indent=2))
        
    print("\n" + "=" * 70)
    print(" REAL-TIME ENGINE VALIDATION COMPLETE ")
    print("=" * 70)
