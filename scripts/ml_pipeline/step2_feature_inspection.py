import os
import zipfile
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(BASE_DIR, "AIClusterKPI.zip")

print("=" * 70)
print(" STEP 2: FEATURE INSPECTION & CONSTANT COLUMN ANALYSIS ")
print("=" * 70)

# 1. Load the raw datasets
with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
    train1 = pd.read_csv(zip_ref.open("train1.csv"))
    train2 = pd.read_csv(zip_ref.open("train2.csv"))
    test = pd.read_csv(zip_ref.open("test.csv"))

print("\n[1] Schema and Shape Comparison:")
print(f"   - train1 shape: {train1.shape}")
print(f"   - train2 shape: {train2.shape}")
print(f"   - test shape:   {test.shape}")

train1_cols = set(train1.columns)
train2_cols = set(train2.columns)
test_cols = set(test.columns)

print(f"\n   - Columns in train1 but not train2: {train1_cols - train2_cols}")
print(f"   - Columns in train2 but not train1: {train2_cols - train1_cols}")
print(f"   - Columns in test but not train1:   {test_cols - train1_cols}")

# 2. Check for constant/zero-variance features across datasets
print("\n[2] Checking for Constant (Zero-Variance) Features:")
combined_train = pd.concat([train1, train2], ignore_index=True)

constant_features_train = []
for col in combined_train.columns:
    if col in ["timestamp", "label", "event_id"]:
        continue
    unique_cnt = combined_train[col].nunique()
    std_val = combined_train[col].std() if np.issubdtype(combined_train[col].dtype, np.number) else None
    if unique_cnt <= 1:
        constant_features_train.append((col, unique_cnt, std_val))

print(f"   - Constant features in Training Data (unique <= 1): {constant_features_train}")

constant_features_test = []
for col in test.columns:
    if col in ["timestamp", "label", "event_id"]:
        continue
    unique_cnt = test[col].nunique()
    std_val = test[col].std() if np.issubdtype(test[col].dtype, np.number) else None
    if unique_cnt <= 1:
        constant_features_test.append((col, unique_cnt, std_val))

print(f"   - Constant features in Test Data (unique <= 1):     {constant_features_test}")

# 3. Categorize columns into Meta/Labels and Numeric Metrics
meta_cols = ["timestamp", "label", "event_id"]
present_meta = [c for c in meta_cols if c in test.columns]

# Exclude meta columns and known constant columns
cols_to_drop = ["cluster_api_latency_cluster"]
candidate_metric_cols = [
    col for col in train1.columns 
    if col not in meta_cols and col not in cols_to_drop
]

print("\n[3] Candidate Metric Features for LSTM Input:")
print(f"   - Total input features selected: {len(candidate_metric_cols)}")
for i, col in enumerate(candidate_metric_cols, 1):
    dtype = combined_train[col].dtype
    n_unique = combined_train[col].nunique()
    print(f"   {i:2d}. {col:<42} | Type: {str(dtype):<8} | Unique: {n_unique:,}")

# 4. Check for any non-numeric / categorical columns in candidate metrics
non_numeric = [col for col in candidate_metric_cols if not np.issubdtype(combined_train[col].dtype, np.number)]
print(f"\n[4] Non-numeric candidate features requiring encoding: {non_numeric if non_numeric else 'None (All are numeric)'}")

# 5. Check missing values in candidate features
missing_train = combined_train[candidate_metric_cols].isnull().sum().sum()
missing_test = test[candidate_metric_cols].isnull().sum().sum()
print(f"\n[5] Missing Value Check:")
print(f"   - Total missing in combined train candidate metrics: {missing_train}")
print(f"   - Total missing in test candidate metrics:           {missing_test}")

# 6. Check label distribution in test set
if "label" in test.columns:
    print("\n[6] Test Label Distribution:")
    print(test["label"].value_counts(dropna=False))
    print(test["label"].value_counts(normalize=True).map(lambda n: f"{n*100:.2f}%"))

print("\n" + "=" * 70)
print(" STEP 2 EXECUTION COMPLETE ")
print("=" * 70)
