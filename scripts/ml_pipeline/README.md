# Machine Learning Offline Training & Evaluation Pipeline

This directory contains the sequential research, exploratory data analysis, and offline training pipeline for the Deep Learning LSTM Autoencoder anomaly detection model.

---

## Pipeline Execution Order

| Step Script | Objective |
|-------------|-----------|
| `EDA.py` | Exploratory data analysis across cluster KPIs and anomaly benchmarks. |
| `step1_continuity_check.py` | Dataset time continuity verification and interval boundary checks. |
| `step2_feature_inspection.py` | Feature correlation matrix and null-value distribution analysis. |
| `step3_investigate_negative_values.py` | Invariant checks and noise investigation for sensor anomalies. |
| `step4_prepare_data.py` | Partitioning and splitting of train/validation/test segments. |
| `step5_feature_selection.py` | Selection of top 30 multivariate cloud metric features (`selected_features.json`). |
| `step6_data_preprocessing.py` | MinMax scaling and fitment (`scaler.joblib`). |
| `step7_sequence_generation.py` | Construction of sliding time-series windows (`seq_len=15`). |
| `step8_9_train_lstm.py` | PyTorch LSTM Autoencoder training with early stopping & validation monitoring. |
| `step10_11_12_evaluation_threshold_tuning.py` | Reconstruction error distribution analysis and optimal threshold selection. |
| `step13_visualizations.py` | Loss curves, ROC/PR curves, and error distribution plotting. |
| `step14_groundtruth_event_evaluation.py` | Benchmarking predictions against labeled groundtruth events. |
| `step15_cloud_dataset_audit.py` | Multi-dataset consistency audit across VM schemas. |
| `realtime_inference_engine.py` | Standalone prototype inference engine demonstrating streaming sequence scoring. |

---

## Trained Model Checkpoints & Artifacts

All resulting weights and evaluation summaries are preserved canonically in:
- `models/best_lstm_anomaly_detector.pt` (Trained model weights)
- `models/lstm/` (Sequences data, scaler, feature definitions, and test predictions)
- `models/evaluation_metrics.json` (Reproduced evaluation metrics)
- `models/training_history.json` (Epoch loss logs)
