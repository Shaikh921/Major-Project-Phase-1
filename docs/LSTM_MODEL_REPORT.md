# LSTM MODEL REPORT

**Audit Date:** 2026-09-23
**Model:** LSTM Autoencoder for Cloud Infrastructure Anomaly Detection

---

## Architecture

```
Input: (batch_size, seq_len=15, n_features=30)
          |
    ENCODER LSTM 1
    LSTM(input=30, hidden=64, batch_first=True)
          |
    Dropout(p=0.2)
          |
    ENCODER LSTM 2
    LSTM(input=64, hidden=32, batch_first=True)
          |
    Extract final hidden state hn: (1, batch, 32)
          |
    Permute + Repeat across seq_len: (batch, 15, 32)
          |
    DECODER LSTM 1
    LSTM(input=32, hidden=64, batch_first=True)
          |
    Dropout(p=0.2)
          |
    Linear(64 -> 30)
          |
Output: (batch_size, seq_len=15, n_features=30)
          |
    MSE Reconstruction Error per sample
          |
    Anomaly Score = error > threshold (0.7914)
```

---

## Training Configuration

| Parameter | Value |
|-----------|-------|
| Sequence Length | 15 time steps |
| Features | 30 (from selected_features.json) |
| Hidden Dimension (Encoder) | 64 |
| Latent Dimension | 32 |
| Dropout | 0.2 (both encoder and decoder) |
| Optimizer | Adam |
| Learning Rate | 0.001 (with ReduceLROnPlateau: factor=0.5, patience=3) |
| Weight Decay | 1e-5 |
| Loss Function | MSELoss (reconstruction) |
| Epochs | 25 |
| Early Stopping Patience | 7 (not triggered — all 25 epochs completed) |
| Batch Size | 64 |
| Gradient Clipping | max_norm=1.0 |
| Device | CPU (no GPU detected during training) |

---

## Training History (from models/training_history.json)

| Epoch | Train Loss | Val Loss |
|-------|-----------|----------|
| 1 | 0.6751 | 0.5456 |
| 5 | 0.5063 | 0.4350 |
| 10 | 0.4644 | 0.4106 |
| 15 | 0.4416 | 0.3879 |
| 20 | 0.4328 | 0.3765 |
| 22 | 0.4241 | 0.3689 (BEST) |
| 25 | 0.4197 | 0.3789 |

**Best Val Loss:** 0.3689 at epoch 22
**Observation:** Validation loss improved steadily, with slight overfitting at epoch 23-25.

---

## Anomaly Threshold Selection

The anomaly threshold was selected by:
1. Computing reconstruction errors on validation set
2. Computing reconstruction errors on test set
3. Evaluating multiple threshold candidates (percentile-based + linear sweep)
4. Selecting threshold that maximizes F1-Score on test set

**Optimal Threshold:** 0.7914 (MSE reconstruction error cutoff)
**Selection Strategy:** "Sweep-0.791" — from linear sweep over test error distribution

---

## Actual Evaluation Results (REPRODUCED from models/evaluation_metrics.json)

> These numbers are REPRODUCED from the actual saved evaluation file.
> They are NOT invented.

### Best Threshold Performance (threshold = 0.7914)

| Metric | Value |
|--------|-------|
| Accuracy | 42.1% |
| Precision | 38.3% |
| Recall | 93.4% |
| F1-Score | 54.3% |
| ROC-AUC | 61.1% |
| PR-AUC | 47.9% |
| True Positives | 1,039 |
| False Positives | 1,674 |
| True Negatives | 229 |
| False Negatives | 73 |
| FPR (False Positive Rate) | 87.97% |
| FNR (False Negative Rate) | 6.56% |

### Test Set Composition
- Total samples: 3,015 (TP+FP+TN+FN = 1039+1674+229+73)
- Anomaly samples (positive class): 1,112 (36.9%)
- Normal samples (negative class): 1,903 (63.1%)

### Confusion Matrix (At Optimal Threshold 0.7914)

```
                Predicted Normal  Predicted Anomaly
Actual Normal        229               1674
Actual Anomaly        73               1039
```

---

## Threshold Sensitivity Analysis

| Threshold Strategy | Threshold | Precision | Recall | F1 | FPR |
|-------------------|-----------|-----------|--------|-----|-----|
| Val-90th percentile | 0.5854 | 36.9% | 100.0% | 53.9% | 100% |
| Val-95th percentile | 0.9295 | 41.7% | 75.4% | 53.7% | 61.5% |
| Sweep-0.791 (OPTIMAL) | 0.7914 | 38.3% | 93.4% | 54.3% | 88.0% |
| Val-98th percentile | 1.5705 | 47.4% | 22.4% | 30.4% | 14.5% |
| Val-99th percentile | 3.7618 | 59.0% | 12.4% | 20.5% | 5.0% |
| Val-Max | 10.117 | 59.6% | 8.9% | 15.5% | 3.5% |

---

## Claims Verification

| Claimed Result | Reproducible? | Actual Result |
|---------------|---------------|---------------|
| 99.31% detection | NO — not reproducible | Best recall = 93.4% at threshold 0.7914 |
| 144/145 incidents detected | NO — not in any file | Cannot verify |
| 0.78 minute detection latency | NO — not measured | Inference is near-real-time (<1 second per batch) |
| 93.44% recall | PARTIALLY — close | Actual recall = 93.44% at best-F1 threshold |
| Confusion matrix with ~99% accuracy | NO | Actual accuracy = 42.1% at best-F1 threshold |

**CONCLUSION:** The recall figure of 93.4% is reproducible. Other performance numbers cannot be
independently reproduced from the current repository state.

---

## LSTM in Live System

**Current Status:** NOT CONNECTED TO LIVE ALERTING PIPELINE

The LSTM is evaluated in standalone scripts (step10_11_12_evaluation_threshold_tuning.py,
realtime_inference_engine.py). The live alerting pipeline uses the Isolation Forest model
(fleet_anomaly_detector_v1.joblib) via ai_engine/anomaly_detector.py.

To connect LSTM to live alerting would require:
1. Loading best_lstm_anomaly_detector.pt in ai_service.py
2. Preprocessing incoming metrics into 15-step sequences
3. Computing per-sample reconstruction errors
4. Comparing against threshold 0.7914
5. Triggering alert creation if threshold exceeded
