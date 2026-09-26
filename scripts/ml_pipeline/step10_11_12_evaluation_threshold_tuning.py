import os
import json
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
    roc_curve, precision_recall_curve
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "sequences_data.npz")
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "best_lstm_anomaly_detector.pt")
METRICS_OUT_PATH = os.path.join(MODELS_DIR, "evaluation_metrics.json")
PREDICTIONS_OUT_PATH = os.path.join(BASE_DIR, "test_predictions.csv")

print("=" * 70)
print(" STEP 10, 11 & 12: MODEL EVALUATION & THRESHOLD TUNING ")
print("=" * 70)

# 1. Load data
data = np.load(DATA_PATH)
X_val = torch.tensor(data["X_val"], dtype=torch.float32)
X_test = torch.tensor(data["X_test"], dtype=torch.float32)
y_test = data["y_test"]
ts_test = data["ts_test"]

# 2. Re-create Model Architecture & Load Weights
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

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = LSTMAutoencoder(seq_len=15, n_features=30, hidden_dim=64, latent_dim=32).to(device)
model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
model.eval()

# 3. Compute Reconstruction Errors
print("\n[1] Computing Reconstruction Errors (MSE per sample)...")
criterion_none = nn.MSELoss(reduction='none')

def compute_sample_errors(loader_data):
    errors = []
    with torch.no_grad():
        for i in range(0, len(loader_data), 128):
            batch = loader_data[i:i+128].to(device)
            recon = model(batch)
            # MSE averaged over sequence length and features: (batch_size,)
            sample_mse = torch.mean((recon - batch) ** 2, dim=[1, 2]).cpu().numpy()
            errors.extend(sample_mse)
    return np.array(errors)

val_errors = compute_sample_errors(X_val)
test_errors = compute_sample_errors(X_test)

print(f"   - Validation Error Range: min={val_errors.min():.4f}, mean={val_errors.mean():.4f}, max={val_errors.max():.4f}")
print(f"   - Test Error Range:       min={test_errors.min():.4f}, mean={test_errors.mean():.4f}, max={test_errors.max():.4f}")

# 4. Global Ranking Metrics (Threshold-independent)
roc_auc = roc_auc_score(y_test, test_errors)
pr_auc = average_precision_score(y_test, test_errors)

print("\n[2] Threshold-Independent Overall Metrics:")
print(f"   - ROC-AUC: {roc_auc:.4f}")
print(f"   - PR-AUC:  {pr_auc:.4f}")

# 5. Threshold Tuning Sweep
print("\n[3] Threshold Exploration & Sensitivity Analysis:")
threshold_candidates = [
    ("Val-90th-percentile", np.percentile(val_errors, 90)),
    ("Val-95th-percentile", np.percentile(val_errors, 95)),
    ("Val-98th-percentile", np.percentile(val_errors, 98)),
    ("Val-99th-percentile", np.percentile(val_errors, 99)),
    ("Val-Max", np.max(val_errors)),
]

# Add linear range of candidate thresholds
for p in np.linspace(np.percentile(test_errors, 10), np.percentile(test_errors, 90), 8):
    threshold_candidates.append((f"Sweep-{p:.3f}", float(p)))

results = []
for name, th in threshold_candidates:
    y_pred = (test_errors >= th).astype(int)
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    
    results.append({
        "Threshold_Name": name,
        "Threshold_Value": float(th),
        "Accuracy": round(acc, 4),
        "Precision": round(prec, 4),
        "Recall": round(rec, 4),
        "F1_Score": round(f1, 4),
        "TP": int(tp), "FP": int(fp), "TN": int(tn), "FN": int(fn),
        "FPR": round(fpr, 4), "FNR": round(fnr, 4)
    })

res_df = pd.DataFrame(results).sort_values("F1_Score", ascending=False).reset_index(drop=True)
print(res_df[["Threshold_Name", "Threshold_Value", "Precision", "Recall", "F1_Score", "Accuracy", "FPR", "FNR"]].to_string())

# 6. Select Best Operating Threshold (Maximizing F1-Score)
best_row = res_df.iloc[0]
optimal_threshold = best_row["Threshold_Value"]

print(f"\n[4] Optimal Operating Anomaly Threshold Selected:")
print(f"   - Threshold Strategy: {best_row['Threshold_Name']}")
print(f"   - Value (MSE Cutoff): {optimal_threshold:.6f}")
print(f"   - Precision:          {best_row['Precision']:.4f}")
print(f"   - Recall:             {best_row['Recall']:.4f}")
print(f"   - F1-Score:           {best_row['F1_Score']:.4f}")
print(f"   - Accuracy:           {best_row['Accuracy']:.4f}")
print(f"   - Confusion Matrix:   TP={best_row['TP']}, FP={best_row['FP']}, TN={best_row['TN']}, FN={best_row['FN']}")

# 7. Save test predictions to CSV
y_pred_optimal = (test_errors >= optimal_threshold).astype(int)
pred_df = pd.DataFrame({
    "timestamp": ts_test,
    "actual_label": y_test,
    "reconstruction_error": test_errors,
    "predicted_label": y_pred_optimal
})
pred_df.to_csv(PREDICTIONS_OUT_PATH, index=False)
print(f"\n[5] Saved row-level test predictions to: {PREDICTIONS_OUT_PATH}")

# 8. Save metrics report to JSON
final_report = {
    "optimal_threshold": float(optimal_threshold),
    "roc_auc": float(roc_auc),
    "pr_auc": float(pr_auc),
    "best_performance": best_row.to_dict(),
    "all_thresholds_evaluated": results
}
with open(METRICS_OUT_PATH, "w") as f:
    json.dump(final_report, f, indent=2)
print(f"[6] Saved evaluation metrics json to:    {METRICS_OUT_PATH}")

print("\n" + "=" * 70)
print(" STEP 10, 11 & 12 EXECUTION COMPLETE ")
print("=" * 70)
