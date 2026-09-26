import os
import zipfile
import json
import joblib
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(BASE_DIR, "AIClusterKPI.zip")
SCALER_PATH = os.path.join(BASE_DIR, "scaler.joblib")
FEATURE_LIST_PATH = os.path.join(BASE_DIR, "selected_features.json")

print("=" * 70)
print(" STEP 6: DATA PREPROCESSING & FEATURE SCALING (StandardScaler) ")
print("=" * 70)

# 1. Load feature list
with open(FEATURE_LIST_PATH, "r") as f:
    feature_meta = json.load(f)
feature_cols = feature_meta["features"]

# 2. Load raw datasets
with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
    train1 = pd.read_csv(zip_ref.open("train1.csv"))
    train2 = pd.read_csv(zip_ref.open("train2.csv"))
    test = pd.read_csv(zip_ref.open("test.csv"))

train1["timestamp"] = pd.to_datetime(train1["timestamp"])
train2["timestamp"] = pd.to_datetime(train2["timestamp"])
test["timestamp"] = pd.to_datetime(test["timestamp"])

# Concatenate training partitions
combined_train = pd.concat([train1, train2], ignore_index=True)
combined_train = combined_train.sort_values("timestamp").reset_index(drop=True)

# 3. Chronological split (85% train, 15% validation)
val_ratio = 0.15
split_idx = int(len(combined_train) * (1 - val_ratio))

train_df = combined_train.iloc[:split_idx].copy().reset_index(drop=True)
val_df = combined_train.iloc[split_idx:].copy().reset_index(drop=True)
test_df = test.copy().reset_index(drop=True)

print(f"\n[1] Split Dimensions:")
print(f"   - Training subset:   {train_df.shape} (from {train_df['timestamp'].min()} to {train_df['timestamp'].max()})")
print(f"   - Validation subset: {val_df.shape} (from {val_df['timestamp'].min()} to {val_df['timestamp'].max()})")
print(f"   - Test set:          {test_df.shape} (from {test_df['timestamp'].min()} to {test_df['timestamp'].max()})")

# 4. Fit StandardScaler strictly on Training subset to avoid data leakage
print(f"\n[2] Fitting StandardScaler strictly on Training subset (30 features)...")
scaler = StandardScaler()
scaler.fit(train_df[feature_cols])

# 5. Transform all splits using the fitted scaler
train_scaled = scaler.transform(train_df[feature_cols])
val_scaled = scaler.transform(val_df[feature_cols])
test_scaled = scaler.transform(test_df[feature_cols])

# 6. Verify Scaled Means and Standard Deviations
scaled_train_mean = np.mean(train_scaled, axis=0)
scaled_train_std = np.std(train_scaled, axis=0)
scaled_test_mean = np.mean(test_scaled, axis=0)
scaled_test_std = np.std(test_scaled, axis=0)

print(f"\n[3] Scaled Statistics Verification:")
print(f"   - Training set: Mean across features ~ {np.mean(scaled_train_mean):.4f} (Ideal: 0.0), Std ~ {np.mean(scaled_train_std):.4f} (Ideal: 1.0)")
print(f"   - Test set:     Mean across features ~ {np.mean(scaled_test_mean):.4f}, Std ~ {np.mean(scaled_test_std):.4f}")

# 7. Save fitted scaler to disk
joblib.dump(scaler, SCALER_PATH)
print(f"\n[4] Fitted scaler saved successfully to: {SCALER_PATH}")

# 8. Check for any NaNs or Infs introduced during scaling
print(f"\n[5] Numerical Integrity Check:")
print(f"   - Train NaN/Inf count: {np.isnan(train_scaled).sum()} / {np.isinf(train_scaled).sum()}")
print(f"   - Val NaN/Inf count:   {np.isnan(val_scaled).sum()} / {np.isinf(val_scaled).sum()}")
print(f"   - Test NaN/Inf count:  {np.isnan(test_scaled).sum()} / {np.isinf(test_scaled).sum()}")

print("\n" + "=" * 70)
print(" STEP 6 EXECUTION COMPLETE ")
print("=" * 70)
