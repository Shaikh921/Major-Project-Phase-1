import os
import zipfile
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(BASE_DIR, "AIClusterKPI.zip")

print("=" * 70)
print(" STEP 5: FORMAL FEATURE SELECTION & STATISTICAL AUDIT ")
print("=" * 70)

# 1. Load data
with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
    train1 = pd.read_csv(zip_ref.open("train1.csv"))
    train2 = pd.read_csv(zip_ref.open("train2.csv"))
    test = pd.read_csv(zip_ref.open("test.csv"))

combined_train = pd.concat([train1, train2], ignore_index=True)

# 2. Define formal feature list
exclude_cols = ["timestamp", "cluster_api_latency_cluster", "label", "event_id"]
feature_cols = sorted([c for c in combined_train.columns if c not in exclude_cols])

# Categorize features
cpu_cols = [c for c in feature_cols if c.startswith("cpu-")]
mem_cols = [c for c in feature_cols if c.startswith("mem_gb-")]
disk_cols = [c for c in feature_cols if c.startswith("disk_io-")]
net_cols = [c for c in feature_cols if c.startswith("net_in-")]
cluster_cols = [c for c in feature_cols if c.startswith("cluster_")]

print(f"\n[1] Selected Feature Breakdown (Total: {len(feature_cols)} features):")
print(f"   - CPU Metrics ({len(cpu_cols)}):     {cpu_cols}")
print(f"   - Memory Metrics ({len(mem_cols)}):  {mem_cols}")
print(f"   - Disk I/O Metrics ({len(disk_cols)}):{disk_cols}")
print(f"   - Network Metrics ({len(net_cols)}): {net_cols}")
print(f"   - Cluster Metrics ({len(cluster_cols)}): {cluster_cols}")

# 3. Verify feature presence in Test Set
missing_in_test = [c for c in feature_cols if c not in test.columns]
print(f"\n[2] Parity Check: Features missing in Test Set: {missing_in_test if missing_in_test else 'None (100% Match)'}")

# 4. Statistical Summary on Training Data
print("\n[3] Comprehensive Statistical Audit (Training Data):")
stats_df = combined_train[feature_cols].describe().T[['mean', 'std', 'min', '25%', '50%', '75%', 'max']]
stats_df['missing'] = combined_train[feature_cols].isnull().sum()
stats_df['dtype'] = combined_train[feature_cols].dtypes

# Format and display
pd.set_option('display.max_columns', 10)
pd.set_option('display.width', 1000)
print(stats_df.to_string())

# 5. Save the official feature list to a python / json artifact for downstream training
import json
FEATURE_LIST_PATH = os.path.join(BASE_DIR, "selected_features.json")
with open(FEATURE_LIST_PATH, "w") as f:
    json.dump({
        "feature_count": len(feature_cols),
        "features": feature_cols,
        "categories": {
            "cpu": cpu_cols,
            "memory": mem_cols,
            "disk": disk_cols,
            "network": net_cols,
            "cluster": cluster_cols
        }
    }, f, indent=2)

print(f"\n[4] Saved official feature configuration to: {FEATURE_LIST_PATH}")

print("\n" + "=" * 70)
print(" STEP 5 EXECUTION COMPLETE ")
print("=" * 70)
