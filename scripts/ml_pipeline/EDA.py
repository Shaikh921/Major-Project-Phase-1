# ============================================================
# EXPLORATORY DATA ANALYSIS (EDA)
# Project: Cloud Anomaly Detection using LSTM
# Libraries: Python, NumPy, Pandas
# ============================================================


# ------------------------------------------------------------
# 1. IMPORT LIBRARIES
# ------------------------------------------------------------

import zipfile
import pandas as pd
import numpy as np

# zipfile : Read CSV files directly from ZIP archives.
# pandas  : Load, clean, and analyze datasets.
# numpy   : Perform numerical operations.


# ============================================================
# DATASET 1: AIClusterKPI
# ============================================================


# ------------------------------------------------------------
# 2. LOAD AIClusterKPI DATASET
# ------------------------------------------------------------

# Specify the ZIP file containing AIClusterKPI.
zip_path_1 = r"AIClusterKPI.zip"

# Open the ZIP file in read mode.
with zipfile.ZipFile(zip_path_1, "r") as z:

    # Display all files available inside the ZIP.
    print("Files inside AIClusterKPI.zip:")
    print(z.namelist())

    # Load the training datasets.
    train1 = pd.read_csv(z.open("train1.csv"))
    train2 = pd.read_csv(z.open("train2.csv"))

    # Load the test dataset.
    test = pd.read_csv(z.open("test.csv"))

    # Load the ground-truth event information.
    groundtruth = pd.read_csv(z.open("groundtruth.csv"))


# ------------------------------------------------------------
# 3. INITIAL EDA FUNCTION
# ------------------------------------------------------------

def perform_eda(df, dataset_name):
    """
    Performs basic exploratory data analysis on a DataFrame.

    Parameters:
        df            : Pandas DataFrame
        dataset_name  : Name of the dataset
    """

    print("\n" + "=" * 80)
    print(f"EDA REPORT: {dataset_name}")
    print("=" * 80)

    # --------------------------------------------------------
    # 3.1 DISPLAY FIRST FIVE ROWS
    # --------------------------------------------------------

    print("\nFirst 5 rows:")
    print(df.head())

    # --------------------------------------------------------
    # 3.2 CHECK DATASET SIZE
    # --------------------------------------------------------

    print("\nDataset shape:")
    print(df.shape)

    # --------------------------------------------------------
    # 3.3 CHECK COLUMN NAMES
    # --------------------------------------------------------

    print("\nColumn names:")
    print(df.columns.tolist())

    # --------------------------------------------------------
    # 3.4 CHECK DATA TYPES AND NON-NULL VALUES
    # --------------------------------------------------------

    print("\nDataset information:")
    df.info()

    # --------------------------------------------------------
    # 3.5 STATISTICAL SUMMARY
    # --------------------------------------------------------

    print("\nStatistical summary:")
    print(df.describe(include="all"))

    # --------------------------------------------------------
    # 3.6 MISSING VALUE ANALYSIS
    # --------------------------------------------------------

    print("\nMissing values per column:")
    print(df.isnull().sum())

    missing_percentage = (df.isnull().sum() / len(df)) * 100

    print("\nMissing-value percentage:")
    print(missing_percentage.round(2))

    # --------------------------------------------------------
    # 3.7 DUPLICATE ROW ANALYSIS
    # --------------------------------------------------------

    print("\nDuplicate rows:")
    print(df.duplicated().sum())

    # --------------------------------------------------------
    # 3.8 NUMERICAL FEATURE ANALYSIS
    # --------------------------------------------------------

    numeric_cols = df.select_dtypes(
        include=np.number
    ).columns

    # Check negative values.
    print("\nNegative values per numerical column:")
    print((df[numeric_cols] < 0).sum())

    # Check unique values.
    print("\nUnique values per numerical column:")
    print(df[numeric_cols].nunique())

    # Display constant numerical features.
    constant_features = df[numeric_cols].nunique()
    constant_features = constant_features[
        constant_features == 1
    ]

    print("\nConstant numerical features:")
    print(constant_features)

    # --------------------------------------------------------
    # 3.9 CORRELATION ANALYSIS
    # --------------------------------------------------------

    print("\nCorrelation matrix:")
    print(df[numeric_cols].corr())


# ============================================================
# 4. TIMESTAMP CONVERSION
# ============================================================

# Convert AIClusterKPI timestamp columns.
train1["timestamp"] = pd.to_datetime(
    train1["timestamp"],
    errors="coerce"
)

train2["timestamp"] = pd.to_datetime(
    train2["timestamp"],
    errors="coerce"
)

test["timestamp"] = pd.to_datetime(
    test["timestamp"],
    errors="coerce"
)

# Convert ground-truth time columns.
groundtruth["start_time"] = pd.to_datetime(
    groundtruth["start_time"],
    errors="coerce"
)

groundtruth["end_time"] = pd.to_datetime(
    groundtruth["end_time"],
    errors="coerce"
)


# ============================================================
# 5. PERFORM INITIAL EDA ON AIClusterKPI
# ============================================================

perform_eda(train1, "AIClusterKPI - train1")
perform_eda(train2, "AIClusterKPI - train2")
perform_eda(test, "AIClusterKPI - test")
perform_eda(groundtruth, "AIClusterKPI - groundtruth")


# ============================================================
# 6. TIMESTAMP VALIDATION FUNCTION
# ============================================================

def analyze_timestamps(df, timestamp_column, dataset_name):
    """
    Checks timestamp validity, ordering, range, and intervals.
    """

    print("\n" + "=" * 80)
    print(f"TIMESTAMP ANALYSIS: {dataset_name}")
    print("=" * 80)

    timestamps = df[timestamp_column]

    # --------------------------------------------------------
    # 6.1 CHECK INVALID TIMESTAMPS
    # --------------------------------------------------------

    invalid_count = timestamps.isna().sum()

    print("\nInvalid timestamps:")
    print(invalid_count)

    # Remove invalid timestamps temporarily for time analysis.
    valid_timestamps = timestamps.dropna()

    if len(valid_timestamps) == 0:
        print("No valid timestamps available.")
        return

    # --------------------------------------------------------
    # 6.2 CHECK TIME RANGE
    # --------------------------------------------------------

    print("\nFirst timestamp:")
    print(valid_timestamps.min())

    print("\nLast timestamp:")
    print(valid_timestamps.max())

    # --------------------------------------------------------
    # 6.3 CHECK WHETHER DATA IS SORTED
    # --------------------------------------------------------

    is_sorted = valid_timestamps.is_monotonic_increasing

    print("\nIs timestamp sorted?")
    print(is_sorted)

    # --------------------------------------------------------
    # 6.4 CHECK DUPLICATE TIMESTAMPS
    # --------------------------------------------------------

    duplicate_timestamp_count = timestamps.duplicated().sum()

    print("\nDuplicate timestamps:")
    print(duplicate_timestamp_count)

    # --------------------------------------------------------
    # 6.5 CHECK TIME DIFFERENCES
    # --------------------------------------------------------

    sorted_timestamps = valid_timestamps.sort_values()

    time_differences = sorted_timestamps.diff().dropna()

    print("\nMost common time intervals:")
    print(time_differences.value_counts().head(10))

    print("\nMinimum time interval:")
    print(time_differences.min())

    print("\nMaximum time interval:")
    print(time_differences.max())


# ------------------------------------------------------------
# 6.6 RUN TIMESTAMP ANALYSIS
# ------------------------------------------------------------

analyze_timestamps(
    train1,
    "timestamp",
    "AIClusterKPI - train1"
)

analyze_timestamps(
    train2,
    "timestamp",
    "AIClusterKPI - train2"
)

analyze_timestamps(
    test,
    "timestamp",
    "AIClusterKPI - test"
)


# ============================================================
# 7. INSPECT NEGATIVE CPU VALUES
# ============================================================

def inspect_negative_values(df, dataset_name):
    """
    Displays rows containing negative numerical values.
    """

    print("\n" + "=" * 80)
    print(f"NEGATIVE VALUE ANALYSIS: {dataset_name}")
    print("=" * 80)

    numeric_cols = df.select_dtypes(
        include=np.number
    ).columns

    # Create a mask for rows containing at least one negative value.
    negative_mask = (df[numeric_cols] < 0).any(axis=1)

    negative_rows = df[negative_mask]

    print("\nNumber of rows containing negative values:")
    print(len(negative_rows))

    print("\nNegative rows:")
    print(negative_rows.head(20))


inspect_negative_values(train1, "AIClusterKPI - train1")
inspect_negative_values(train2, "AIClusterKPI - train2")
inspect_negative_values(test, "AIClusterKPI - test")


# ============================================================
# 8. TEST LABEL ANALYSIS
# ============================================================

print("\n" + "=" * 80)
print("TEST LABEL ANALYSIS")
print("=" * 80)

if "label" in test.columns:

    print("\nLabel counts:")
    print(test["label"].value_counts())

    print("\nLabel percentages:")
    print(
        test["label"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
    )

    print("\nNumber of normal samples:")
    print((test["label"] == 0).sum())

    print("\nNumber of anomaly samples:")
    print((test["label"] == 1).sum())


# ============================================================
# 9. GROUND-TRUTH EVENT ANALYSIS
# ============================================================

print("\n" + "=" * 80)
print("GROUND-TRUTH EVENT ANALYSIS")
print("=" * 80)

# Check whether required columns exist.
required_groundtruth_columns = [
    "start_time",
    "end_time",
    "node",
    "event",
    "is_anomaly"
]

if all(
    column in groundtruth.columns
    for column in required_groundtruth_columns
):

    # Calculate event duration in minutes.
    groundtruth["duration_minutes"] = (
        groundtruth["end_time"]
        - groundtruth["start_time"]
    ).dt.total_seconds() / 60

    print("\nGround-truth data:")
    print(groundtruth.head())

    print("\nEvent duration statistics:")
    print(
        groundtruth["duration_minutes"].describe()
    )

    print("\nAnomaly-event counts:")
    print(
        groundtruth["is_anomaly"].value_counts()
    )

    print("\nAnomaly-event percentages:")
    print(
        groundtruth["is_anomaly"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
    )

    print("\nEvents by type:")
    print(
        groundtruth["event"].value_counts()
    )

    print("\nEvents by node:")
    print(
        groundtruth["node"].value_counts()
    )


# ============================================================
# DATASET 2: CLOUD ANOMALY DATASET
# ============================================================


# ------------------------------------------------------------
# 10. LOAD CLOUD ANOMALY DATASET
# ------------------------------------------------------------

zip_path_2 = r"archive.zip"

with zipfile.ZipFile(zip_path_2, "r") as z:

    print("\nFiles inside archive.zip:")
    print(z.namelist())

    cloud = pd.read_csv(
        z.open("Cloud_Anomaly_Dataset.csv")
    )


# ============================================================
# 11. CLOUD DATASET TIMESTAMP CONVERSION
# ============================================================

# The Cloud dataset uses day-first timestamp format,
# for example: 25-01-2023 09:10.

cloud["timestamp"] = pd.to_datetime(
    cloud["timestamp"],
    dayfirst=True,
    errors="coerce"
)


# ============================================================
# 12. PERFORM INITIAL EDA ON CLOUD DATASET
# ============================================================

perform_eda(
    cloud,
    "Cloud Anomaly Dataset"
)


# ============================================================
# 13. CLOUD DATASET TIMESTAMP ANALYSIS
# ============================================================

analyze_timestamps(
    cloud,
    "timestamp",
    "Cloud Anomaly Dataset"
)


# ============================================================
# 14. CLOUD DATASET VM-ID ANALYSIS
# ============================================================

print("\n" + "=" * 80)
print("CLOUD DATASET VM-ID ANALYSIS")
print("=" * 80)

print("\nNumber of unique non-null VM IDs:")
print(
    cloud["vm_id"].nunique(dropna=True)
)

print("\nNumber of non-null VM IDs:")
print(
    cloud["vm_id"].notna().sum()
)

print("\nNumber of missing VM IDs:")
print(
    cloud["vm_id"].isna().sum()
)

print("\nMost frequent VM IDs:")
print(
    cloud["vm_id"]
    .value_counts(dropna=True)
    .head(10)
)

# Count how many rows belong to each VM.
vm_counts = cloud["vm_id"].value_counts(
    dropna=True
)

print("\nVM occurrence statistics:")
print(vm_counts.describe())

# Check whether VM IDs repeat.
repeated_vm_ids = vm_counts[vm_counts > 1]

print("\nNumber of VM IDs appearing more than once:")
print(len(repeated_vm_ids))

print("\nRepeated VM IDs:")
print(repeated_vm_ids.head(20))


# ============================================================
# 15. CLOUD DATASET ANOMALY LABEL ANALYSIS
# ============================================================

print("\n" + "=" * 80)
print("CLOUD DATASET ANOMALY LABEL ANALYSIS")
print("=" * 80)

label_column = "Anomaly status"

if label_column in cloud.columns:

    print("\nAnomaly label counts:")
    print(
        cloud[label_column].value_counts()
    )

    print("\nAnomaly label percentages:")
    print(
        cloud[label_column]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
    )


# ============================================================
# 16. CLOUD DATASET MISSING-VALUE SUMMARY
# ============================================================

print("\n" + "=" * 80)
print("CLOUD DATASET MISSING-VALUE SUMMARY")
print("=" * 80)

cloud_missing_summary = pd.DataFrame({
    "missing_count": cloud.isnull().sum(),
    "missing_percentage": (
        cloud.isnull().mean() * 100
    ).round(2)
})

print(cloud_missing_summary)


# ============================================================
# 17. FINAL EDA SUMMARY
# ============================================================

print("\n" + "=" * 80)
print("FINAL EDA SUMMARY")
print("=" * 80)

print("""
EDA completed successfully.

The following checks were performed:

1. Dataset structure
2. Data types
3. Statistical summary
4. Missing values
5. Duplicate rows
6. Negative numerical values
7. Constant features
8. Correlation analysis
9. Timestamp conversion
10. Timestamp validity
11. Timestamp ordering
12. Time intervals
13. Test-label distribution
14. Ground-truth event duration
15. Cloud VM-ID repetition
16. Cloud anomaly-label distribution
17. Cloud missing-value summary

Next step:
Review the timestamp analysis output before creating
LSTM sequences.
""")