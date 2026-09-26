import os
import zipfile
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(BASE_DIR, "AIClusterKPI.zip")

print("=" * 70)
print(" STEP 3: INVESTIGATION OF NEGATIVE CPU / METRIC VALUES ")
print("=" * 70)

# 1. Load all datasets including groundtruth
with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
    train1 = pd.read_csv(zip_ref.open("train1.csv"))
    train2 = pd.read_csv(zip_ref.open("train2.csv"))
    test = pd.read_csv(zip_ref.open("test.csv"))
    groundtruth = pd.read_csv(zip_ref.open("groundtruth.csv"))

# Parse timestamps
for df in [train1, train2, test]:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
groundtruth["start_time"] = pd.to_datetime(groundtruth["start_time"])
groundtruth["end_time"] = pd.to_datetime(groundtruth["end_time"])

combined_train = pd.concat([train1, train2], ignore_index=True)

# 30 metric features excluding timestamp, label, event_id, cluster_api_latency_cluster
metric_cols = [
    c for c in train1.columns 
    if c not in ["timestamp", "cluster_api_latency_cluster", "label", "event_id"]
]

# 2. Check for negative values across metric columns
print("\n[1] Columns with Negative Values in Training Set (train1 + train2):")
neg_train_cols = []
for col in metric_cols:
    neg_count = (combined_train[col] < 0).sum()
    if neg_count > 0:
        min_val = combined_train[col].min()
        max_val = combined_train[col].max()
        pct = (neg_count / len(combined_train)) * 100
        print(f"   - {col:<25} | Count: {neg_count:5d} ({pct:5.2f}%) | Min: {min_val:10.4f} | Max: {max_val:10.4f}")
        neg_train_cols.append(col)

if not neg_train_cols:
    print("   - No negative values found in training set.")

print("\n[2] Columns with Negative Values in Test Set:")
neg_test_cols = []
for col in metric_cols:
    neg_count = (test[col] < 0).sum()
    if neg_count > 0:
        min_val = test[col].min()
        max_val = test[col].max()
        pct = (neg_count / len(test)) * 100
        print(f"   - {col:<25} | Count: {neg_count:5d} ({pct:5.2f}%) | Min: {min_val:10.4f} | Max: {max_val:10.4f}")
        neg_test_cols.append(col)

if not neg_test_cols:
    print("   - No negative values found in test set.")

# 3. Analyze correlation between negative values and Anomaly Label in test set
print("\n[3] Negative Values vs. Anomaly Label in Test Set:")
test_neg_mask = (test[metric_cols] < 0).any(axis=1)
total_neg_rows_test = test_neg_mask.sum()
print(f"   - Total rows in Test with at least one negative metric: {total_neg_rows_test} ({total_neg_rows_test / len(test) * 100:.2f}%)")

if total_neg_rows_test > 0:
    neg_test_df = test[test_neg_mask]
    label_breakdown = neg_test_df["label"].value_counts()
    print("   - Label breakdown for rows with negative metrics:")
    for lbl, cnt in label_breakdown.items():
        name = "Anomaly (1)" if lbl == 1 else "Normal (0)"
        print(f"     * {name}: {cnt} rows ({cnt / total_neg_rows_test * 100:.2f}%)")

# 4. Cross-reference negative value timestamps with Groundtruth events
print("\n[4] Correlation with Groundtruth Events:")
print(f"   - Total groundtruth events: {len(groundtruth)}")
print(f"   - Groundtruth Columns: {groundtruth.columns.tolist()}")
print(f"   - Event types in groundtruth:\n{groundtruth['event'].value_counts()}")

# Check overlap of negative timestamp rows in test with groundtruth events
overlapping_events = []
for _, row in test[test_neg_mask].iterrows():
    ts = row["timestamp"]
    matching = groundtruth[(groundtruth["start_time"] <= ts) & (groundtruth["end_time"] >= ts)]
    if not matching.empty:
        for _, m_row in matching.iterrows():
            overlapping_events.append({
                "timestamp": ts,
                "node": m_row.get("node", "N/A"),
                "event": m_row.get("event", "N/A"),
                "is_anomaly": m_row.get("is_anomaly", "N/A")
            })

overlap_df = pd.DataFrame(overlapping_events)
if not overlap_df.empty:
    print(f"\n   - Found {len(overlap_df)} negative row timestamps matching active groundtruth events.")
    print("   - Breakdown by event:")
    print(overlap_df["event"].value_counts())
    print("\n   - Breakdown by is_anomaly in groundtruth:")
    print(overlap_df["is_anomaly"].value_counts())
else:
    print("\n   - No direct timestamp matches found in groundtruth for test negative rows.")

# 5. Check sample values of negative numbers to see if they are continuous float values vs fixed sentinel codes
print("\n[5] Continuous Distribution Samples of Negative Values:")
for col in ["cpu-N2", "cpu-N3", "cpu-N4", "cpu-N7"]:
    sample_train = combined_train[combined_train[col] < 0][col].head(4).tolist()
    sample_test = test[test[col] < 0][col].head(4).tolist()
    print(f"   - {col:<10} | Train neg samples: {sample_train} | Test neg samples: {sample_test}")

print("\n" + "=" * 70)
print(" STEP 3 EXECUTION COMPLETE ")
print("=" * 70)
