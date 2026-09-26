import os
import zipfile
import json
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(BASE_DIR, "AIClusterKPI.zip")
PRED_PATH = os.path.join(BASE_DIR, "test_predictions.csv")
EVENT_REPORT_PATH = os.path.join(BASE_DIR, "models", "event_level_evaluation.json")

print("=" * 70)
print(" STEP 14: GROUNDTRUTH INCIDENT & EVENT-LEVEL EVALUATION ")
print("=" * 70)

# 1. Load predictions and groundtruth
pred_df = pd.read_csv(PRED_PATH)
pred_df["timestamp"] = pd.to_datetime(pred_df["timestamp"])

with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
    groundtruth = pd.read_csv(zip_ref.open("groundtruth.csv"))

groundtruth["start_time"] = pd.to_datetime(groundtruth["start_time"])
groundtruth["end_time"] = pd.to_datetime(groundtruth["end_time"])

# Filter groundtruth events that overlap with test time range
test_start = pred_df["timestamp"].min()
test_end = pred_df["timestamp"].max()

test_events = groundtruth[
    (groundtruth["end_time"] >= test_start) & 
    (groundtruth["start_time"] <= test_end)
].copy().reset_index(drop=True)

print(f"\n[1] Time Window Matching:")
print(f"   - Test Time Span: {test_start} to {test_end}")
print(f"   - Total Events in Groundtruth during Test Period: {len(test_events)}")
print(f"   - Anomalous Events (is_anomaly == 1):           {(test_events['is_anomaly'] == 1).sum()}")
print(f"   - Benign/Routine Events (is_anomaly == 0):       {(test_events['is_anomaly'] == 0).sum()}")

# 2. Event-Level Detection & Delay Calculation
event_results = []
for idx, event in test_events.iterrows():
    e_start = event["start_time"]
    e_end = event["end_time"]
    e_name = event["event"]
    is_anom = event["is_anomaly"]
    node = event.get("node", "All")
    
    # Rows belonging to this event window
    in_window = pred_df[(pred_df["timestamp"] >= e_start) & (pred_df["timestamp"] <= e_end)]
    
    if len(in_window) == 0:
        continue
        
    detected_rows = in_window[in_window["predicted_label"] == 1]
    is_detected = len(detected_rows) > 0
    
    # Calculate detection delay in minutes
    if is_detected:
        first_alarm_time = detected_rows["timestamp"].min()
        delay_min = (first_alarm_time - e_start).total_seconds() / 60.0
    else:
        delay_min = None
        
    detection_ratio = len(detected_rows) / len(in_window)
    
    event_results.append({
        "event_index": idx,
        "event_name": e_name,
        "node": node,
        "is_anomaly": int(is_anom),
        "duration_min": (e_end - e_start).total_seconds() / 60.0,
        "total_rows": len(in_window),
        "detected_rows": len(detected_rows),
        "detection_ratio": round(detection_ratio, 3),
        "is_detected": bool(is_detected),
        "detection_delay_min": round(delay_min, 2) if delay_min is not None else None
    })

ev_df = pd.DataFrame(event_results)

# 3. Aggregate Performance on Anomalous Incidents
anom_events = ev_df[ev_df["is_anomaly"] == 1]
total_anom_events = len(anom_events)
detected_anom_events = anom_events["is_detected"].sum()
event_recall = (detected_anom_events / total_anom_events) * 100 if total_anom_events > 0 else 0

avg_delay = anom_events[anom_events["is_detected"]]["detection_delay_min"].mean()

print(f"\n[2] Anomalous Event Detection Summary:")
print(f"   - Total Anomalous Incidents: {total_anom_events}")
print(f"   - Successfully Detected:     {detected_anom_events} ({event_recall:.2f}%)")
print(f"   - Average Detection Delay:   {avg_delay:.2f} minutes")

# 4. Breakdown by Incident Type
print(f"\n[3] Detection Rate Breakdown by Event Type:")
summary_by_type = ev_df.groupby("event_name").agg(
    total_events=("is_detected", "count"),
    anomalous_events=("is_anomaly", "sum"),
    detected_events=("is_detected", "sum"),
    avg_coverage=("detection_ratio", "mean")
)
print(summary_by_type.to_string())

# Save event evaluation results
with open(EVENT_REPORT_PATH, "w") as f:
    json.dump({
        "total_events_in_test": len(ev_df),
        "anomalous_events_count": int(total_anom_events),
        "detected_anomalous_events": int(detected_anom_events),
        "event_recall_pct": round(float(event_recall), 2),
        "avg_detection_delay_minutes": round(float(avg_delay), 2) if not np.isnan(avg_delay) else 0,
        "event_details": event_results
    }, f, indent=2)

print(f"\n[4] Saved event-level audit to: {EVENT_REPORT_PATH}")

print("\n" + "=" * 70)
print(" STEP 14 EXECUTION COMPLETE ")
print("=" * 70)
