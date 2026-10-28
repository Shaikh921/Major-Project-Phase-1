# ML MODEL AUDIT

**Audit Date:** 2026-09-23

---

## Model 1: LSTM Autoencoder (Anomaly Detection)

| Field | Details |
|-------|---------|
| Model Name | best_lstm_anomaly_detector |
| File | models/best_lstm_anomaly_detector.pt |
| Framework | PyTorch |
| Architecture | LSTM Autoencoder (Encoder-Decoder) |
| Purpose | Detect anomalous time windows by measuring reconstruction error |
| Input | 3D tensor: (batch, seq_len=15, n_features=30) |
| Output | Reconstruction of input; anomaly = MSE reconstruction error > threshold |
| Encoder | LSTM(30->64) -> Dropout(0.2) -> LSTM(64->32) -> latent vector (32-dim) |
| Decoder | Repeat latent (1,15,32) -> LSTM(32->64) -> Dropout(0.2) -> Linear(64->30) |
| Parameters | ~196,000 (estimated from architecture) |
| Training Dataset | Cloud_Anomaly_Dataset.csv (37MB) — processed into sequences |
| Train Samples | sequences_data.npz X_train shape |
| Features | 30 features (see selected_features.json) |
| Optimizer | Adam (lr=0.001, weight_decay=1e-5) |
| Loss Function | MSE (reconstruction loss) |
| Batch Size | 64 |
| Epochs Trained | 25 (all 25 completed, no early stopping triggered) |
| Best Val Loss | 0.3689 (epoch 22) |
| Anomaly Threshold | 0.7914 (optimal F1 from threshold sweep, models/evaluation_metrics.json) |

### Actual Performance Metrics (from models/evaluation_metrics.json)

These are REPRODUCED from actual experiment — NOT invented:

| Metric | Value | Notes |
|--------|-------|-------|
| ROC-AUC | 0.6106 | Threshold-independent ranking metric |
| PR-AUC | 0.4795 | Threshold-independent average precision |
| Best F1 Threshold | 0.7914 (MSE cutoff) | Selected by maximizing F1 |
| Accuracy at best threshold | 0.4206 (42.1%) | Low due to high FP rate |
| Precision at best threshold | 0.3830 (38.3%) | Low precision — many false positives |
| Recall at best threshold | 0.9344 (93.4%) | High recall — catches most anomalies |
| F1-Score at best threshold | 0.5433 (54.3%) | Best achievable F1 |
| TP | 1,039 | Correctly detected anomalies |
| FP | 1,674 | False alarms |
| TN | 229 | Correctly classified normal |
| FN | 73 | Missed anomalies |
| FPR | 0.8797 | High false positive rate at best-recall threshold |

**Interpretation:** The LSTM achieves good recall (93.4%) but at the cost of high false positives (FPR=88%).
The ROC-AUC of 0.61 suggests moderate discriminative power — better than random (0.5) but not excellent.
The dataset imbalance and complexity of cloud metrics contribute to this behavior.

**CRITICAL NOTE:** Previously reported numbers of "99.31% detection", "144/145 incidents", "0.78 minute latency",
"93.44% recall" cannot be verified from this evaluation. The actual reproduced recall is 0.9344 (93.4% at the
best F1 threshold — close to the claimed value). The other numbers are NOT reproducible from current files
and should be treated as: "Previously reported result — not independently reproducible from current repository."

---

## Model 2: Production Isolation Forest

| Field | Details |
|-------|---------|
| Model Name | production_cloud_anomaly_model |
| File | models/production_cloud_anomaly_model_v1.joblib |
| Framework | scikit-learn |
| Algorithm | IsolationForest |
| Purpose | Multivariate anomaly detection in live metric pipeline |
| Input | 5 features: [cpu_percent, memory_percent, disk_percent, network_sent_mb, network_received_mb] |
| Output | is_anomaly: bool, anomaly_score: 0.0-1.0, feature_contributions |
| Training Samples | 222,056 |
| Contamination | 0.06 (6% expected anomaly rate) |
| Trained At | 2026-09-11 |
| Baseline Mean | cpu=50.03%, mem=49.95%, disk=50.02%, net_sent=0.49MB, net_recv=250.02MB |
| Status | ACTIVE — loaded by ai_service.py at startup |

**Note:** The production_cloud_anomaly_model is NOT currently loaded by ai_service.py.
The active model is fleet_anomaly_detector_v1 (only 10 samples). This is a gap.

---

## Model 3: Fleet Isolation Forest

| Field | Details |
|-------|---------|
| Model Name | fleet_anomaly_detector |
| File | models/fleet_anomaly_detector_v1.joblib |
| Framework | scikit-learn |
| Algorithm | IsolationForest |
| Training Samples | 10 (from live DB) |
| Contamination | 0.05 |
| Trained At | 2026-09-23 |
| Status | ACTIVE (loaded by ai_service.py) but PRACTICALLY INVALID — 10 samples |

**CRITICAL WARNING:** This model has been trained on only 10 database samples.
With contamination=0.05 and 10 samples, the IsolationForest will classify 0-1 samples as anomalies.
Any anomaly detection from this model should be considered UNRELIABLE until retrained with
sufficient data (minimum 1,000+ samples recommended).

**RECOMMENDATION:** Load production_cloud_anomaly_model_v1.joblib as the default, or retrain
fleet_anomaly_detector on all 3,950+ available DB metrics.

---

## Model 4: Linear Regression Forecaster

| Field | Details |
|-------|---------|
| Implementation | ai_engine/forecaster.py (TimeSeriesForecaster) |
| Algorithm | Ordinary Least Squares (numpy.linalg.lstsq) |
| Purpose | Project future metric values and estimate time-to-threshold |
| Input | List of (timestamp, value) pairs from metrics table |
| Output | forecast_points, trend_slope_per_hour, time_to_threshold |
| Confidence Intervals | 1.96 * residual_std (growing with forecast horizon) |
| Model Status | COMPUTED ON DEMAND — no saved model file |
| Status | LIVE — connected to real DB metrics |
