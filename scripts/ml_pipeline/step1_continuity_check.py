import os
import zipfile
import pandas as pd
import numpy as np

# Path configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(BASE_DIR, "AIClusterKPI.zip")

print("=" * 70)
print(" STEP 1: DATASET TIME CONTINUITY & GAP VERIFICATION ")
print("=" * 70)

# 1. Load CSVs directly from the ZIP file
print(f"\n[1] Reading datasets from: {ZIP_PATH} ...")
with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
    train1 = pd.read_csv(zip_ref.open("train1.csv"))
    train2 = pd.read_csv(zip_ref.open("train2.csv"))
    test = pd.read_csv(zip_ref.open("test.csv"))

datasets = {
    "train1": train1,
    "train2": train2,
    "test": test
}

# 2. Convert timestamp and inspect individual ranges
print("\n[2] Dataset Time Boundaries and Row Counts:")
for name, df in datasets.items():
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    start_t = df["timestamp"].min()
    end_t = df["timestamp"].max()
    row_count = len(df)
    
    # Internal delta checks
    diffs = df["timestamp"].diff().dropna()
    is_strictly_1min = (diffs == pd.Timedelta(minutes=1)).all()
    
    print(f"\n  Dataset: {name}")
    print(f"   - Rows: {row_count:,}")
    print(f"   - Start Time: {start_t}")
    print(f"   - End Time:   {end_t}")
    print(f"   - Total Span: {end_t - start_t}")
    print(f"   - Strictly 1-min interval within dataset? {is_strictly_1min}")

# 3. Inter-dataset Gaps and Overlaps
print("\n[3] Inter-Dataset Boundary Analysis:")
gap_train1_train2 = train2["timestamp"].min() - train1["timestamp"].max()
gap_train2_test = test["timestamp"].min() - train2["timestamp"].max()

overlap_train1_train2 = len(set(train1["timestamp"]) & set(train2["timestamp"]))
overlap_train2_test = len(set(train2["timestamp"]) & set(test["timestamp"]))

print(f"   - Gap between train1 (end) and train2 (start): {gap_train1_train2}")
print(f"   - Gap between train2 (end) and test (start):   {gap_train2_test}")
print(f"   - Timestamp overlaps (train1 & train2):        {overlap_train1_train2}")
print(f"   - Timestamp overlaps (train2 & test):          {overlap_train2_test}")

# 4. Continuity check for Combined Training Data (train1 + train2)
print("\n[4] Combined Training Set (train1 + train2) Analysis:")
combined_train = pd.concat([train1, train2], ignore_index=True)
combined_train = combined_train.sort_values("timestamp").reset_index(drop=True)

combined_train["time_diff"] = combined_train["timestamp"].diff()

print(f"   - Combined Total Rows: {len(combined_train):,}")
print(f"   - Combined Start Time: {combined_train['timestamp'].min()}")
print(f"   - Combined End Time:   {combined_train['timestamp'].max()}")

print("\n[5] Time Interval Distribution in Combined Training Set:")
interval_counts = combined_train["time_diff"].value_counts(dropna=True).sort_index()
for interval, count in interval_counts.items():
    print(f"   - Interval {interval}: {count:,} occurrences")

print(f"\n   - Largest Gap in Combined Training Set: {combined_train['time_diff'].max()}")

gaps_gt_1min = combined_train[combined_train["time_diff"] > pd.Timedelta(minutes=1)][["timestamp", "time_diff"]]
if not gaps_gt_1min.empty:
    print("\n[6] Gaps greater than 1 minute in Combined Training Set:")
    for idx, row in gaps_gt_1min.iterrows():
        print(f"   - Gap at row index {idx} on {row['timestamp']}: {row['time_diff']}")
else:
    print("\n[6] No gaps greater than 1 minute found in combined training set.")

print("\n" + "=" * 70)
print(" STEP 1 EXECUTION COMPLETE ")
print("=" * 70)
