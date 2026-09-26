import os
import zipfile
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_ZIP_PATH = os.path.join(BASE_DIR, "archive.zip")

print("=" * 70)
print(" STEP 15: SEPARATE AUDIT OF DATASET 2 (Cloud_Anomaly_Dataset.csv) ")
print("=" * 70)

# 1. Inspect archive.zip contents
with zipfile.ZipFile(ARCHIVE_ZIP_PATH, "r") as zip_ref:
    namelist = zip_ref.namelist()
    print(f"\n[1] Files in archive.zip: {namelist}")
    
    # Read Cloud_Anomaly_Dataset.csv
    csv_name = [f for f in namelist if f.endswith(".csv")][0]
    print(f"   - Loading: {csv_name} ...")
    df_cloud = pd.read_csv(zip_ref.open(csv_name))

print(f"\n[2] Shape and Schema:")
print(f"   - Total Rows: {len(df_cloud):,}")
print(f"   - Total Columns: {len(df_cloud.columns)}")
print(f"   - Columns: {df_cloud.columns.tolist()}")

# 2. Timestamp analysis
if "timestamp" in df_cloud.columns:
    df_cloud["timestamp"] = pd.to_datetime(df_cloud["timestamp"])
    print(f"\n[3] Timestamp Audit:")
    print(f"   - Min Time: {df_cloud['timestamp'].min()}")
    print(f"   - Max Time: {df_cloud['timestamp'].max()}")
    print(f"   - Is strictly sorted? {df_cloud['timestamp'].is_monotonic_increasing}")
    
    dup_ts = df_cloud["timestamp"].duplicated().sum()
    print(f"   - Duplicate Timestamps: {dup_ts:,} ({dup_ts / len(df_cloud) * 100:.2f}%)")

# 3. VM_ID / Resource Identifier Cardinality
if "vm_id" in df_cloud.columns:
    unique_vms = df_cloud["vm_id"].nunique(dropna=True)
    null_vms = df_cloud["vm_id"].isnull().sum()
    print(f"\n[4] VM ID Analysis:")
    print(f"   - Unique VM IDs: {unique_vms:,}")
    print(f"   - Null VM IDs:   {null_vms:,}")
    vm_counts = df_cloud["vm_id"].value_counts()
    print(f"   - Max observations per single VM: {vm_counts.max() if not vm_counts.empty else 'N/A'}")
    print(f"   - VM IDs with count > 1: {(vm_counts > 1).sum()}")

# 4. Label Distribution & Missing Values
label_col = [c for c in df_cloud.columns if "anomaly" in c.lower() or "label" in c.lower()][0]
print(f"\n[5] Target Column '{label_col}' Distribution:")
print(df_cloud[label_col].value_counts(dropna=False))
print(df_cloud[label_col].value_counts(normalize=True).map(lambda n: f"{n*100:.2f}%"))

print(f"\n[6] Missing Value Counts across all Columns:")
missing_series = df_cloud.isnull().sum()
for col, cnt in missing_series.items():
    if cnt > 0:
        print(f"   - {col:<25}: {cnt:,} missing ({cnt/len(df_cloud)*100:.2f}%)")

print("\n[7] Summary & Machine Learning Recommendation for Dataset 2:")
print("   - Since VM IDs occur only once and duplicate timestamps exist across different VMs/records,")
print("     this dataset represents a CROSS-SECTIONAL / TABULAR CLOUD BENCHMARK rather than a single continuous node stream.")
print("   - Recommended Models for Dataset 2: Tabular Autoencoder, Isolation Forest, XGBoost Classifier, or MLP.")
print("   - Do NOT concatenate directly with AIClusterKPI due to distinct schemas, sampling intervals, and VM structures.")

print("\n" + "=" * 70)
print(" STEP 15 EXECUTION COMPLETE ")
print("=" * 70)
