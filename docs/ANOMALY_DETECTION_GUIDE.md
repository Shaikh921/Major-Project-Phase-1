# ANOMALY DETECTION GUIDE

**Audit Date:** 2026-09-23

---

## Overview

The platform implements THREE layers of anomaly detection:

```
Telemetry (psutil / Simulator)
          |
    Preprocessing
  (normalizing + feature extraction)
          |
    Feature Vector [cpu, mem, disk, net_sent, net_recv]
          |
    +--------------------+
    | Threshold Detection|
    +--------------------+
             +
    +--------------------+
    | ML Anomaly Detector| (Isolation Forest)
    | (LIVE)             |
    +--------------------+
             +
    +--------------------+
    | LSTM Autoencoder   | (STANDALONE — not in live pipeline)
    +--------------------+
          |
    Anomaly Score
          |
    Severity (warning >= 0.60, critical >= 0.80)
          |
    Alert (deduplication check)
          |
    Incident Correlation (Narrator)
          |
    Dashboard
          |
    AI Narrator
```

---

## Layer 1: Threshold Detection

**Implementation:** backend/app/services/alert_service.py::evaluate_metric_sample()
**Type:** Rule-based / signature-based
**Status:** LIVE

### How It Works:
1. When a metric sample is ingested via POST /api/v1/metrics
2. alert_service fetches all enabled AlertRules from DB
3. For each rule, evaluates: metric_value OPERATOR threshold
   - Example: cpu_percent > 85.0 (critical)
4. If rule condition is BREACHED:
   - Check for existing active alert for (host_id, metric, 'threshold')
   - If exists: UPDATE existing alert (deduplication)
   - If not exists: CREATE new alert
5. If rule condition is NOT BREACHED but alert is active:
   - AUTO-RESOLVE the alert (status='resolved', resolved_at=now)

### Default Rules (seeded on startup):
| Rule | Metric | Operator | Threshold | Severity |
|------|--------|----------|-----------|---------|
| High CPU | cpu_percent | > | 85.0 | critical |
| High Memory | memory_percent | > | 90.0 | critical |
| High Disk | disk_percent | > | 85.0 | warning |
| Critical Disk | disk_percent | > | 92.0 | critical |
| Elevated CPU | cpu_percent | > | 75.0 | warning |
| Elevated Memory | memory_percent | > | 80.0 | warning |

### Advantages:
- Deterministic and explainable
- Low latency (DB query + comparison)
- Zero false positives for known patterns
- Configurable by operators

### Disadvantages:
- Cannot detect complex multi-metric patterns
- Cannot detect slow-burn anomalies
- Cannot adapt to changing baselines

---

## Layer 2: ML Anomaly Detection (Isolation Forest)

**Implementation:** ai_engine/anomaly_detector.py::MultivariateAnomalyDetector
**Type:** Unsupervised ML — isolation-based anomaly scoring
**Status:** LIVE (but fleet model trained on only 10 samples — see ML_MODEL_AUDIT.md)

### Algorithm: Isolation Forest

1. Build an ensemble of isolation trees from normal training data
2. For each tree, randomly select a feature and a split value
3. Samples that are isolated in fewer splits are more anomalous
4. decision_function() returns a score where negative = anomalous

### Implementation Flow:
1. Metric sample arrives at ingest_metric()
2. ai_service::evaluate_and_record_ai_anomaly(db, host, metric) is called
3. MultivariateAnomalyDetector::score_sample(sample) is called
4. Extract 5-feature vector: [cpu, mem, disk, net_sent, net_recv]
5. StandardScaler transform (fitted during training)
6. IsolationForest.decision_function() returns decision score
7. Map to anomaly_score: base_score = 0.5 - (decision_score * 1.2)
8. Clip to [0.0, 1.0]
9. is_anomaly = anomaly_score >= 0.60
10. If anomaly: severity = critical if score >= 0.80, else warning
11. Create/update alert in DB with kind='anomaly'

### Feature Attribution (Explainability):
- Computes z-score deviation: (value - baseline_mean) / baseline_std
- Ranks features by absolute deviation
- Generates plain English explanation: "CPU is 2.3 standard deviations above baseline"

### Sensitivity Calibration (M2-FR7):
- Operator can submit feedback: true_positive or false_positive
- false_positive: sensitivity_offset -= 0.05 (reduces future anomaly scores)
- true_positive: sensitivity_offset += 0.025 (increases alertness)
- Offset bounded to [-0.25, +0.25]

---

## Layer 3: LSTM Autoencoder (Standalone)

**Implementation:** step8_9_train_lstm.py, step10_11_12_evaluation_threshold_tuning.py
**Type:** Deep learning — sequence reconstruction
**Status:** STANDALONE — not integrated in live pipeline

### Algorithm: LSTM Autoencoder

1. Encoder compresses input sequence (15 time steps, 30 features) to 32-dim latent vector
2. Decoder reconstructs original sequence from latent vector
3. Anomaly score = MSE(original, reconstructed) per sample
4. If MSE > threshold (0.7914): ANOMALY

### Why LSTM for Anomaly Detection:
- Learns temporal dependencies in time-series data
- Normal sequences have low reconstruction error
- Anomalous sequences deviate from learned patterns -> high reconstruction error
- Suitable for cloud infrastructure where metrics have strong temporal autocorrelation

### Actual Performance:
- Recall: 93.4% (catches most real anomalies)
- Precision: 38.3% (high false positive rate)
- F1: 54.3%
- ROC-AUC: 61.1%

---

## Comparison: Threshold vs. ML vs. LSTM

| Dimension | Threshold | Isolation Forest | LSTM Autoencoder |
|-----------|-----------|-----------------|-----------------|
| Type | Rule-based | Unsupervised ML | Deep Learning |
| Status | LIVE | LIVE (weak model) | STANDALONE |
| Training required | NO | YES | YES |
| Pattern detection | Single-metric | Multivariate | Temporal sequences |
| Interpretability | HIGH | MEDIUM (feature attribution) | LOW (reconstruction error) |
| Sensitivity to new patterns | LOW | MEDIUM | HIGH |
| False positive control | HIGH | MEDIUM | LOW (high FPR) |
| Latency | <1ms | <10ms | <100ms |
| Requires historical data | NO | YES (>=5 samples) | YES (sequences) |
| Best for | Known thresholds | Complex multi-metric patterns | Temporal behavior |
