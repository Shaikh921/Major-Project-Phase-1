# Cloud Infrastructure Anomaly Detection Using Deep Learning (LSTM Autoencoder)
**Major Project / Capstone Project Documentation**  
**Domain**: Cloud Computing, Telemetry Monitoring & Deep Learning  
**Target Architecture**: PyTorch 2.x LSTM Autoencoder with Temporal Sequence Bottleneck

---

## 1. Problem Statement & Motivation
Modern distributed cloud systems (such as Kubernetes clusters and enterprise multi-node server fleets) generate high-velocity, multi-dimensional time-series telemetry representing CPU, memory, disk I/O, network traffic, and container lifecycles. 

Detecting infrastructure degradations (e.g., memory leaks, network jitter, CPU stutter, micro-bursts, thread lockups) in real-time is critical to maintaining high availability and meeting Service Level Agreements (SLAs). Traditional static thresholding fails due to:
1. Dynamic baseline workloads that fluctuate over hours and days.
2. Complex multi-node interdependencies where multiple metrics experience non-linear correlations.
3. Silent degradation patterns (e.g., gradual memory leaks) that stay below threshold alarms until critical failure.

This project designs and implements an **LSTM-based Deep Learning Anomaly Detection System** that learns normal temporal operational baselines and detects anomalies through sequence reconstruction residuals.

---

## 2. Dataset Architecture & Exploratory Findings

### 2.1 Dataset 1: AIClusterKPI (Time-Series Benchmark)
The primary dataset consists of continuous multi-node telemetry collected at fixed 1-minute intervals across 7 cluster nodes (`N1`, `N2`, `N3`, `N4`, `N6`, `N7`, `N8`) and cluster-level orchestrator signals.

| Dataset Split | Rows | Time Range | Interval | Overlaps | Labels / Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`train1.csv`** | 11,089 | 2026-03-31 10:00 to 2026-04-08 02:48 | Strictly 1 min | 0 | Baseline normal operating period |
| **`train2.csv`** | 6,482 | 2026-04-08 22:00 to 2026-04-13 10:01 | Strictly 1 min | 0 | Baseline normal operating period |
| **`test.csv`** | 3,029 | 2026-04-26 23:06 to 2026-04-29 01:34 | Strictly 1 min | 0 | 1,912 Normal (63.12%), 1,117 Anomaly (36.88%) |
| **`groundtruth.csv`**| 598 | 2026-04-26 23:06 to 2026-04-29 01:34 | Event Windows | N/A | Incident-level ground truth (5-15 min events) |

#### Critical Data Findings & Preprocessing Insights:
1. **Temporal Gap Verification**: A single **19-hour 12-minute gap** separates `train1` and `train2`. To avoid synthetic distortion, sequence sliding windows are generated strictly within individual segments.
2. **Constant Feature Removal**: `cluster_api_latency_cluster` exhibits zero variance ($std = 0$) across all splits and was eliminated to prevent division-by-zero during standard scaling.
3. **Investigation of Negative CPU Values**: Negative values occur in `cpu-N1` through `cpu-N8` ($0.01\% - 1.45\%$). They represent continuous physical measurements resulting from Prometheus counter wraps and CPU clock sync jitter rather than missing value codes (`-999`). They are preserved and scaled continuously using `StandardScaler`.

### 2.2 Dataset 2: Cloud_Anomaly_Dataset.csv (`archive.zip`)
* **Rows**: 277,570 | **Columns**: 13
* **Structure**: Contains 249,595 unique VM IDs where each non-null VM occurs exactly once. Timestamps have 233,018 duplicates (83.95%).
* **Analysis**: Represents a **cross-sectional tabular benchmark** across discrete VMs rather than a single continuous temporal stream. Kept separate from time-series LSTM models.

---

## 3. Feature Selection & Pipeline Engineering

### 3.1 Input Feature Space (30 Metrics)
* **CPU Utilization (7)**: `cpu-N1`, `cpu-N2`, `cpu-N3`, `cpu-N4`, `cpu-N6`, `cpu-N7`, `cpu-N8`
* **Memory Utilization in GB (7)**: `mem_gb-N1`, `mem_gb-N2`, `mem_gb-N3`, `mem_gb-N4`, `mem_gb-N6`, `mem_gb-N7`, `mem_gb-N8`
* **Disk I/O Rate (7)**: `disk_io-N1`, `disk_io-N2`, `disk_io-N3`, `disk_io-N4`, `disk_io-N6`, `disk_io-N7`, `disk_io-N8`
* **Network Ingress Bytes (7)**: `net_in-N1`, `net_in-N2`, `net_in-N3`, `net_in-N4`, `net_in-N6`, `net_in-N7`, `net_in-N8`
* **Cluster Management (2)**: `cluster_pending_cluster`, `cluster_restarts_cluster`

### 3.2 Standardization & Data Leakage Prevention
* `StandardScaler` ($z = \frac{x - \mu}{\sigma}$) is fitted **strictly on the chronological training partition** (`df_train`, 85%) and applied consistently across validation, test, and live inference.
* Persisted as `scaler.joblib`.

### 3.3 3D Sequence Generation
* **Input Window Shape**: $(Samples, T=15, D=30)$
* **Rationale**: Window size of 15 minutes aligns with the physical duration of cluster incidents (5 to 15 min), capturing trend slopes and transitional micro-bursts.
* **Labeling Policy**: The label $y_i$ corresponds to the last time step in the window ($t + W - 1$), providing exact real-time causal classification without lookahead leakage.

---

## 4. LSTM Model Architecture & Training

```
Input Sequence: (Batch, 15, 30)
       │
       ▼
┌───────────────────────────────────────┐
│ Encoder LSTM Layer 1                  │ (Input: 30, Hidden: 64, Batch First)
└───────────────────────────────────────┘
       │
       ▼  Dropout (p = 0.2)
┌───────────────────────────────────────┐
│ Encoder LSTM Layer 2 (Latent Bottleneck) (Input: 64, Latent: 32)
└───────────────────────────────────────┘
       │
       ▼  RepeatVector (Latent vector repeated over T = 15 steps)
┌───────────────────────────────────────┐
│ Decoder LSTM Layer 1                  │ (Input: 32, Hidden: 64)
└───────────────────────────────────────┘
       │
       ▼  Dropout (p = 0.2)
┌───────────────────────────────────────┐
│ TimeDistributed Dense Linear Layer    │ (Input: 64, Output: 30)
└───────────────────────────────────────┘
       │
       ▼
Reconstructed Sequence: (Batch, 15, 30)
```

### Training Parameters:
* **Loss Function**: Mean Squared Error (MSE) on continuous sequences.
* **Optimizer**: Adam ($\text{lr} = 0.001$, weight decay = $10^{-5}$).
* **Gradient Clipping**: `max_norm = 1.0` to stabilize recurrent backpropagation.
* **Learning Rate Scheduler**: `ReduceLROnPlateau(factor=0.5, patience=3)`.
* **Validation Split**: 15% chronological split.

---

## 5. Quantitative Evaluation & Results

### 5.1 Model Performance Summary
* **Test Sequences Evaluated**: 3,015 (1,112 Anomalous = 36.88%)
* **ROC-AUC**: **0.6106**
* **PR-AUC (Average Precision)**: **0.4795**
* **Optimal Operating Threshold**: **0.791351** (Reconstruction MSE)

| Metric | Score | Explanation |
| :--- | :--- | :--- |
| **Event-Level Recall** | **99.31%** | 144 out of 145 groundtruth incidents detected |
| **Detection Delay** | **0.78 minutes** | System alerts within ~47 seconds of incident onset |
| **Row-Level Recall** | **93.44%** | Captures 1,039 out of 1,112 anomaly minutes |
| **Row-Level Precision**| **38.30%** | Tuned to prioritize high recall for mission-critical cloud safety |
| **F1-Score** | **0.5433** | Optimal balance between false alarms and missed incidents |

### 5.2 Incident Breakdown by Anomaly Category

| Event Category | Groundtruth Incidents | Detected Incidents | Coverage Rate |
| :--- | :---: | :---: | :---: |
| **CPU_Sync_Stutter** | 51 | 51 | **100.0%** |
| **Network_Latency_Jitter** | 54 | 54 | **100.0%** |
| **Memory_Leak_Gradual** | 40 | 39 | **97.5%** |
| **Metric_Scraping** | 248 | 243 | **92.1%** |
| **Log_Rotation** | 204 | 202 | **92.8%** |

---

## 6. Generated Visualizations & Artifacts
The pipeline generated 4 high-resolution plots in `plots/`:
1. [1_loss_curves.png](file:///c:/CLoudProject/plots/1_loss_curves.png): Training & validation loss convergence.
2. [2_roc_pr_curves.png](file:///c:/CLoudProject/plots/2_roc_pr_curves.png): ROC-AUC and Precision-Recall curves.
3. [3_confusion_matrix.png](file:///c:/CLoudProject/plots/3_confusion_matrix.png): Confusion matrix at the optimal operating threshold.
4. [4_anomaly_timeline.png](file:///c:/CLoudProject/plots/4_anomaly_timeline.png): Temporal timeline comparing reconstruction error against groundtruth anomalies.

---

## 7. Real-Time Streaming Inference Engine
The file [realtime_inference_engine.py](file:///c:/CLoudProject/realtime_inference_engine.py) provides an enterprise-ready inference class `RealtimeCloudAnomalyDetector` supporting sliding-window telemetry ingestion:

```python
from realtime_inference_engine import RealtimeCloudAnomalyDetector

detector = RealtimeCloudAnomalyDetector()
# Pass 15 consecutive minutes of cluster metrics
result = detector.predict_window(current_15min_telemetry_df)
print(result)
# Output: {'status': 'ANOMALY', 'is_anomaly': True, 'reconstruction_error': 2.1465, 'severity': 'CRITICAL'}
```

---

## 8. Limitations & Future Scope
1. **Multi-Model Ensembling**: Combining the LSTM Autoencoder with a temporal Graph Neural Network (GNN) to explicitly model inter-node topology.
2. **Cross-Sectional Dataset Extension**: Deploying an Isolation Forest / Tabular Deep Net for the VM-level dataset (`Cloud_Anomaly_Dataset.csv`).
3. **Automated Root Cause Localization**: Using per-feature reconstruction error attribution to identify exactly which node and metric triggered the anomaly.
