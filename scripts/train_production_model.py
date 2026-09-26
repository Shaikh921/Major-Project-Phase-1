"""
Production AI Model Training & Benchmarking Pipeline.

Trains the Multivariate Isolation Forest and Explainability Engine on real-world cloud
datasets (archive (1).zip or AIClusterKPI.zip), benchmarks classification metrics
against ground truth labels, and persists production checkpoints to the Model Registry.

Usage:
    python scripts/train_production_model.py --dataset cloud --n_estimators 150 --contamination 0.06
    python scripts/train_production_model.py --dataset cluster --eval
"""

import argparse
import os
import sys
import time
import zipfile
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_engine.anomaly_detector import MultivariateAnomalyDetector
from ai_engine.explainability import FeatureAttributionEngine
from ai_engine.forecaster import TimeSeriesForecaster
from ai_engine.model_registry import ModelRegistry


def load_cloud_anomaly_dataset(zip_path: str = "archive (1).zip") -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Extracts, cleans, and prepares the 277k-sample Cloud Anomaly Dataset.
    """
    print(f"[*] Extracting and parsing {zip_path}...")
    with zipfile.ZipFile(zip_path, "r") as z:
        with z.open("Cloud_Anomaly_Dataset.csv") as f:
            df = pd.read_csv(f)

    # Feature mapping to platform dimensions
    feature_cols = [
        "cpu_usage",
        "memory_usage",
        "network_traffic",
        "power_consumption",
        "energy_efficiency",
    ]

    # Impute missing values with column median
    df[feature_cols] = df[feature_cols].fillna(df[feature_cols].median())

    X = df[feature_cols].values
    y = df["Anomaly status"].values
    return df, X, y


def load_cluster_kpi_dataset(zip_path: str = "AIClusterKPI.zip") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Extracts multi-node cluster time-series and labeled test events.
    """
    print(f"[*] Extracting and parsing {zip_path}...")
    with zipfile.ZipFile(zip_path, "r") as z:
        with z.open("train1.csv") as f:
            train1 = pd.read_csv(f)
        with z.open("train2.csv") as f:
            train2 = pd.read_csv(f)
        with z.open("test.csv") as f:
            test = pd.read_csv(f)

    train_df = pd.concat([train1, train2], ignore_index=True)
    return train_df, test, None


def run_training_pipeline(args):
    print("\n=======================================================")
    print("      CLOUD PLATFORM - PRODUCTION AI MODEL TRAINING     ")
    print("=======================================================\n")

    registry = ModelRegistry(models_dir=args.models_dir)
    start_time = time.time()

    if args.dataset == "cloud":
        zip_file = "archive (1).zip"
        if not os.path.exists(zip_file):
            print(f"[!] Error: {zip_file} not found in workspace root.")
            return

        df, X, y = load_cloud_anomaly_dataset(zip_file)
        print(f"[+] Loaded {len(X):,} total telemetry records across {df['vm_id'].nunique():,} VMs.")
        print(f"    - Baseline Normal Samples: {(y == 0).sum():,} ({((y == 0).mean() * 100):.1f}%)")
        print(f"    - Ground-Truth Anomalies:  {(y == 1).sum():,} ({((y == 1).mean() * 100):.1f}%)")

        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score

        # Map to sample dictionary format for MultivariateAnomalyDetector
        sample_dicts = []
        for row in X:
            sample_dicts.append({
                "cpu_percent": float(row[0]),
                "memory_percent": float(row[1]),
                "disk_percent": float(row[4] * 100.0),  # energy efficiency mapped as resource stress
                "network_sent_mb": float(row[2] / 1024.0),  # KB/s to MB/s
                "network_received_mb": float(row[3]),
            })

        indices = np.arange(len(sample_dicts))
        idx_train, idx_test, y_train, y_test = train_test_split(
            indices, y, test_size=args.test_size, random_state=args.seed, stratify=y
        )
        train_samples = [sample_dicts[i] for i in idx_train]
        test_samples = [sample_dicts[i] for i in idx_test]

        print(f"\n[*] Stratified Train-Test Split (test_size={args.test_size}):")
        print(f"    - Training Set: {len(train_samples):,} samples (Normal: {(y_train == 0).sum():,}, Anomaly: {(y_train == 1).sum():,})")
        print(f"    - Testing Set:  {len(test_samples):,} samples (Normal: {(y_test == 0).sum():,}, Anomaly: {(y_test == 1).sum():,})")

        print(f"\n[*] Training Multivariate Isolation Forest on Train Split ({args.n_estimators} trees, contamination={args.contamination})...")
        train_start = time.time()
        detector = MultivariateAnomalyDetector(
            contamination=args.contamination,
            n_estimators=args.n_estimators,
            random_state=args.seed,
        )
        train_info = detector.train(train_samples)
        train_duration = time.time() - train_start
        print(f"[+] Model Training Completed in {train_duration:.2f} seconds.")

        # Benchmarking & Evaluation
        if args.eval:
            print("\n" + "=" * 60)
            print("                 EVALUATION METRICS SUMMARY                 ")
            print("=" * 60)

            # 1. Training Set Evaluation
            X_train_mat = detector._extract_matrix(train_samples)
            X_train_scaled = detector.scaler.transform(X_train_mat)
            raw_preds_train = detector.model.predict(X_train_scaled)
            y_pred_train = (raw_preds_train == -1).astype(int)
            train_acc = accuracy_score(y_train, y_pred_train)
            raw_scores_train = detector.model.decision_function(X_train_scaled)
            anomaly_scores_train = 1.0 / (1.0 + np.exp(raw_scores_train * 8.0))
            train_roc_auc = roc_auc_score(y_train, anomaly_scores_train)
            cm_train = confusion_matrix(y_train, y_pred_train)

            # 2. Testing Set Evaluation
            X_test_mat = detector._extract_matrix(test_samples)
            X_test_scaled = detector.scaler.transform(X_test_mat)
            raw_preds_test = detector.model.predict(X_test_scaled)
            y_pred_test = (raw_preds_test == -1).astype(int)
            test_acc = accuracy_score(y_test, y_pred_test)
            raw_scores_test = detector.model.decision_function(X_test_scaled)
            anomaly_scores_test = 1.0 / (1.0 + np.exp(raw_scores_test * 8.0))
            test_roc_auc = roc_auc_score(y_test, anomaly_scores_test)
            cm_test = confusion_matrix(y_test, y_pred_test)

            print(f"\n[+] TRAINING ACCURACY: {train_acc * 100:.2f}%  |  TRAIN ROC-AUC: {train_roc_auc:.4f}")
            print(f"[+] TESTING ACCURACY:  {test_acc * 100:.2f}%  |  TEST ROC-AUC:  {test_roc_auc:.4f}")

            print("\n--- TEST SET CLASSIFICATION REPORT ---")
            print(classification_report(y_test, y_pred_test, target_names=["Normal (0)", "Anomaly (1)"], digits=4))

            print(f"Test Confusion Matrix:\n  TN: {cm_test[0, 0]:,} | FP: {cm_test[0, 1]:,}\n  FN: {cm_test[1, 0]:,} | TP: {cm_test[1, 1]:,}")

        # Explainability Demonstration
        print("\n[*] Testing Explainability Attribution on Sample Anomalies...")
        anomaly_indices = np.where(y_test == 1)[0]
        if len(anomaly_indices) > 0:
            test_idx = anomaly_indices[0]
            sample_eval = test_samples[test_idx]
            explanation = detector.score_sample(sample_eval)
            print(f"    - Test Sample #{test_idx} Evaluation -> Is Anomaly: {explanation['is_anomaly']} (Score: {explanation['anomaly_score']})")
            print(f"    - Root-Cause Explanation: {explanation['explanation']}")
            for c in explanation["feature_contributions"][:3]:
                print(f"       * {c['metric']:<20}: {c['value']:>6.1f} (Contribution: {c['contribution_percent']}%, Z-Score: {c['z_score']})")

        # Save to Model Registry
        model_name = "production_cloud_anomaly_model"
        file_path = registry.save_model(
            model_name=model_name,
            detector=detector,
            training_info=train_info,
            version=args.version,
        )
        print(f"\n[+] Production Checkpoint Saved: {file_path}")

    elif args.dataset == "cluster":
        zip_file = "AIClusterKPI.zip"
        if not os.path.exists(zip_file):
            print(f"[!] Error: {zip_file} not found in workspace root.")
            return

        train_df, test_df, _ = load_cluster_kpi_dataset(zip_file)
        print(f"[+] Loaded {len(train_df):,} baseline training steps & {len(test_df):,} test steps across 7 nodes.")

        # Test Time-Series Forecaster on Memory Leak incident
        print("\n[*] Validating Time-to-Threshold Forecaster on Gradual Memory Leak incident...")
        mem_leak_data = test_df[test_df["event_id"] == "Memory_Leak_Gradual"]
        if not mem_leak_data.empty:
            timestamps = pd.to_datetime(mem_leak_data["timestamp"]).tolist()
            values = mem_leak_data["mem_gb-N1"].tolist()

            fc_res = TimeSeriesForecaster.forecast(
                timestamps=timestamps,
                values=values,
                horizon_hours=24,
                critical_threshold=250.0,
            )
            print(f"    - Incident: Memory_Leak_Gradual on Node N1")
            print(f"    - Starting Memory: {fc_res['current_value']:.2f} GB")
            print(f"    - Growth Slope: {fc_res['trend_slope_per_hour']:.3f} GB/hr")
            if fc_res["time_to_threshold"]:
                tt = fc_res["time_to_threshold"]
                print(f"    - Time-to-Threshold Status: {tt['status']}")
                print(f"    - Countdown Warning: {tt['message']}")

    total_time = time.time() - start_time
    print(f"\n=======================================================")
    print(f"   MODEL PIPELINE COMPLETED SUCCESSFULLY IN {total_time:.2f}s  ")
    print(f"=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Train Production AI Models on Cloud Telemetry")
    parser.add_argument("--dataset", choices=["cloud", "cluster"], default="cloud", help="Dataset source to train on")
    parser.add_argument("--n_estimators", type=int, default=100, help="Number of trees in Isolation Forest")
    parser.add_argument("--contamination", type=float, default=0.06, help="Expected proportion of anomalies")
    parser.add_argument("--eval", action="store_true", default=True, help="Compute benchmark classification metrics")
    parser.add_argument("--test_size", type=float, default=0.20, help="Fraction of dataset for testing evaluation")
    parser.add_argument("--version", default="v1", help="Model version label")
    parser.add_argument("--models_dir", default="models", help="Directory to save model checkpoints")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()
    run_training_pipeline(args)


if __name__ == "__main__":
    main()
