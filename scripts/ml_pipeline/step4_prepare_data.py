import os
import zipfile
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(BASE_DIR, "AIClusterKPI.zip")

print("=" * 70)
print(" STEP 4: PREPARE TRAINING & CHRONOLOGICAL VALIDATION SETS ")
print("=" * 70)

# 1. Load raw datasets
with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
    train1 = pd.read_csv(zip_ref.open("train1.csv"))
    train2 = pd.read_csv(zip_ref.open("train2.csv"))
    test = pd.read_csv(zip_ref.open("test.csv"))

# Parse datetime
train1["timestamp"] = pd.to_datetime(train1["timestamp"])
train2["timestamp"] = pd.to_datetime(train2["timestamp"])
test["timestamp"] = pd.to_datetime(test["timestamp"])

# 2. Drop constant column
cols_to_drop = ["cluster_api_latency_cluster"]
train1 = train1.drop(columns=cols_to_drop, errors="ignore")
train2 = train2.drop(columns=cols_to_drop, errors="ignore")
test = test.drop(columns=cols_to_drop, errors="ignore")

# 3. Concatenate train1 and train2 chronologically
combined_train = pd.concat([train1, train2], ignore_index=True)
combined_train = combined_train.sort_values("timestamp").reset_index(drop=True)

# 4. Check for duplicate timestamps
dup_count = combined_train["timestamp"].duplicated().sum()
print(f"\n[1] Duplicate Timestamps in Combined Train: {dup_count}")

# 5. Extract Feature Columns (30 metrics)
feature_cols = [
    c for c in combined_train.columns 
    if c not in ["timestamp", "label", "event_id"]
]

print(f"\n[2] Feature Verification:")
print(f"   - Total input features: {len(feature_cols)}")
print(f"   - Total rows in Combined Train: {len(combined_train):,}")
print(f"   - Date range: {combined_train['timestamp'].min()} to {combined_train['timestamp'].max()}")

# 6. Chronological Train / Validation Split (85% Train / 15% Val)
val_ratio = 0.15
split_idx = int(len(combined_train) * (1 - val_ratio))

df_train = combined_train.iloc[:split_idx].copy().reset_index(drop=True)
df_val = combined_train.iloc[split_idx:].copy().reset_index(drop=True)

print(f"\n[3] Chronological Split Summary:")
print(f"   - Training Set:   {len(df_train):,} rows ({len(df_train)/len(combined_train)*100:.1f}%) | {df_train['timestamp'].min()} --> {df_train['timestamp'].max()}")
print(f"   - Validation Set: {len(df_val):,} rows ({len(df_val)/len(combined_train)*100:.1f}%) | {df_val['timestamp'].min()} --> {df_val['timestamp'].max()}")
print(f"   - Test Set (held out): {len(test):,} rows | {test['timestamp'].min()} --> {test['timestamp'].max()}")

# 7. Check if train1-to-train2 gap sits inside train or val
gap_timestamp = pd.to_datetime("2026-04-08 22:00:00")
print(f"\n[4] 19-Hour Gap Boundary Location:")
if gap_timestamp <= df_train['timestamp'].max():
    print(f"   - Gap occurs inside Training Split at timestamp: {gap_timestamp}")
else:
    print(f"   - Gap occurs inside Validation Split at timestamp: {gap_timestamp}")

print("\n" + "=" * 70)
print(" STEP 4 EXECUTION COMPLETE ")
print("=" * 70)
