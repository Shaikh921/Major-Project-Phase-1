import os
import zipfile
import json
import joblib
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(BASE_DIR, "AIClusterKPI.zip")
SCALER_PATH = os.path.join(BASE_DIR, "scaler.joblib")
FEATURE_LIST_PATH = os.path.join(BASE_DIR, "selected_features.json")
SEQUENCES_OUT_PATH = os.path.join(BASE_DIR, "sequences_data.npz")

print("=" * 70)
print(" STEP 7: 3D TIME-SERIES SEQUENCE GENERATION FOR LSTM ")
print("=" * 70)

# 1. Load feature list and fitted scaler
with open(FEATURE_LIST_PATH, "r") as f:
    feature_meta = json.load(f)
feature_cols = feature_meta["features"]

scaler = joblib.load(SCALER_PATH)

# 2. Load raw datasets
with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
    train1 = pd.read_csv(zip_ref.open("train1.csv"))
    train2 = pd.read_csv(zip_ref.open("train2.csv"))
    test = pd.read_csv(zip_ref.open("test.csv"))

train1["timestamp"] = pd.to_datetime(train1["timestamp"])
train2["timestamp"] = pd.to_datetime(train2["timestamp"])
test["timestamp"] = pd.to_datetime(test["timestamp"])

# In train1 & train2 (unlabeled baseline / normal operating period), label = 0
train1["label"] = 0
train2["label"] = 0

# Scale features using fitted scaler
train1_scaled = scaler.transform(train1[feature_cols])
train2_scaled = scaler.transform(train2[feature_cols])
test_scaled = scaler.transform(test[feature_cols])

# 3. Define Sequence Parameters
# Window size = 15 minutes (captures micro-bursts and 5-15 min event dynamics)
WINDOW_SIZE = 15
STEP_SIZE = 1

print(f"\n[1] Sequence Configuration:")
print(f"   - Window Size (time_steps): {WINDOW_SIZE} minutes (consecutive 1-min observations)")
print(f"   - Step Size (stride):       {STEP_SIZE} minute")
print(f"   - Number of features (D):   {len(feature_cols)}")
print(f"   - Target Label Policy:      Last time step in window (y = label[t + W - 1])")

def create_sequences(scaled_data, labels, timestamps, window_size=WINDOW_SIZE, stride=STEP_SIZE):
    """
    Creates (samples, window_size, features) 3D sequences.
    Labels correspond to the last observation in each window.
    """
    X_list, y_list, ts_list = [], [], []
    num_rows = len(scaled_data)
    
    for i in range(0, num_rows - window_size + 1, stride):
        window_x = scaled_data[i : i + window_size]
        window_y = labels[i + window_size - 1]
        window_ts = timestamps[i + window_size - 1]
        
        X_list.append(window_x)
        y_list.append(window_y)
        ts_list.append(str(window_ts))
        
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32), np.array(ts_list)

# 4. Generate sequences separately for train1 and train2 to respect the 19h gap!
print("\n[2] Generating Continuous Sequences (Respecting Dataset Boundaries)...")
X_train1, y_train1, ts_train1 = create_sequences(train1_scaled, train1["label"].values, train1["timestamp"].values)
X_train2, y_train2, ts_train2 = create_sequences(train2_scaled, train2["label"].values, train2["timestamp"].values)
X_test, y_test, ts_test = create_sequences(test_scaled, test["label"].values, test["timestamp"].values)

print(f"   - train1 sequences: {X_train1.shape} (from {len(train1)} raw rows)")
print(f"   - train2 sequences: {X_train2.shape} (from {len(train2)} raw rows)")
print(f"   - test sequences:   {X_test.shape}   (from {len(test)} raw rows)")

# 5. Combine train1 and train2 sequences for overall training set
X_train_full = np.concatenate([X_train1, X_train2], axis=0)
y_train_full = np.concatenate([y_train1, y_train2], axis=0)
ts_train_full = np.concatenate([ts_train1, ts_train2], axis=0)

# Chronological split on sequences (85% Train, 15% Validation)
val_ratio = 0.15
split_idx = int(len(X_train_full) * (1 - val_ratio))

X_train, y_train, ts_train = X_train_full[:split_idx], y_train_full[:split_idx], ts_train_full[:split_idx]
X_val, y_val, ts_val = X_train_full[split_idx:], y_train_full[split_idx:], ts_train_full[split_idx:]

print(f"\n[3] Final 3D Tensor Dimensions:")
print(f"   - X_train: {X_train.shape} | y_train: {y_train.shape} (Anomalies: {np.sum(y_train)})")
print(f"   - X_val:   {X_val.shape}   | y_val:   {y_val.shape}   (Anomalies: {np.sum(y_val)})")
print(f"   - X_test:  {X_test.shape}   | y_test:  {y_test.shape}   (Anomalies: {np.sum(y_test)} = {np.mean(y_test)*100:.2f}%)")

# 6. Save sequences to compressed .npz archive
np.savez_compressed(
    SEQUENCES_OUT_PATH,
    X_train=X_train, y_train=y_train, ts_train=ts_train,
    X_val=X_val, y_val=y_val, ts_val=ts_val,
    X_test=X_test, y_test=y_test, ts_test=ts_test
)
print(f"\n[4] Saved 3D sequence tensors to: {SEQUENCES_OUT_PATH}")

print("\n" + "=" * 70)
print(" STEP 7 EXECUTION COMPLETE ")
print("=" * 70)
