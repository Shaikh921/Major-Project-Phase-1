# Production AI Model Training Plan & Execution Guide

This document provides the step-by-step plan and exact commands to manually train, evaluate, and deploy the AI Anomaly Detection & Forecasting models on the provided real-world datasets.

---

## 1. Overview of Datasets

1. **Dataset A: `archive (1).zip` -> `Cloud_Anomaly_Dataset.csv`**
   - **Scale**: **277,570** telemetry samples across **249,595** virtual machines.
   - **Features**: CPU utilization, Memory usage, Network traffic, Power consumption, and Energy efficiency.
   - **Ground Truth Anomaly Ratio**: **6.0%** (16,654 anomalies vs. 260,916 normal records).
   - **Primary Target**: Trains the **`MultivariateAnomalyDetector` (Isolation Forest)** and baseline scalers.

2. **Dataset B: `AIClusterKPI.zip`**
   - **Scale**: **20,600** time-steps across 7 Kubernetes nodes (`N1` to `N8`).
   - **Labeled Failure Modes**: `Memory_Leak_Gradual`, `CPU_Sync_Stutter`, `Network_Latency_Jitter`.
   - **Primary Target**: Validates the **`TimeSeriesForecaster`** and **Time-to-Threshold countdown**.

---

## 2. Step-by-Step Manual Training Plan

### Step 1: Execute the Training & Benchmark Pipeline

Open your terminal in `c:\CLoudProject` and execute:

```bash
# Train on the 277,570-row Cloud Anomaly Dataset with full benchmarking
python scripts/train_production_model.py --dataset cloud --n_estimators 100 --contamination 0.06
```

#### What happens during this run:
1. Automatically reads and unzips `archive (1).zip` directly in memory.
2. Imputes missing values with column medians.
3. Fits the multi-metric `StandardScaler` and `IsolationForest` using multi-core parallelism (`n_jobs=-1`).
4. Evaluates **Precision, Recall, F1-Score, and ROC-AUC** against ground-truth labels.
5. Runs the **`FeatureAttributionEngine`** to test explainability on anomalous samples.
6. Serializes the trained production checkpoint to `models/production_cloud_anomaly_model_v1.joblib` and registers metadata in `models/registry_metadata.json`.

---

### Step 2: Validate Temporal Time-Series & Failure Modes

To test the **Time-to-Threshold Forecaster** on real cluster memory leaks and CPU synchronization stutter:

```bash
python scripts/train_production_model.py --dataset cluster
```

---

### Step 3: Available Customization CLI Flags

You can customize training hyperparameters via command-line arguments:

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--dataset` | `cloud` | Dataset to train on: `cloud` or `cluster` |
| `--n_estimators` | `100` | Number of decision trees in the Isolation Forest (e.g. `100`, `150`, `200`) |
| `--contamination`| `0.06` | Expected anomaly proportion in data (0.01 - 0.20) |
| `--version` | `v1` | Checkpoint version label (e.g. `v1`, `v2`, `prod_sept2026`) |
| `--eval` | `True` | Automatically computes classification metrics against ground truth |
| `--seed` | `42` | Random seed for exact reproducibility |

---

### Step 4: Verify the Saved Model in the Registry

After training, verify that the platform recognizes the new model checkpoint:

#### Option A: Via Live REST API
```bash
curl http://127.0.0.1:8000/api/v1/ai/models
```

#### Option B: Via the Live Verification Script
```bash
python scripts/verify_live_api.py
```

#### Option C: In the Interactive Swagger UI
Open `http://localhost:8000/docs` in your browser -> Navigate to **`AI & Machine Learning`** -> **`GET /api/v1/ai/models`**.
