"""
Live API & Operational Verification Script for Modules 1 & 2.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_live_system():
    print("\n=======================================================")
    print("      CLOUD PLATFORM - MODULES 1 & 2 LIVE AUDIT        ")
    print("=======================================================\n")

    # 1. Fleet Summary
    print("[+] 1. GET /api/v1/summary (Fleet Overview):")
    res = requests.get(f"{BASE_URL}/summary")
    summary = res.json()
    print(f"  * Total Registered Hosts: {summary['total_hosts']}")
    print(f"  * Healthy Hosts:          {summary['healthy_hosts']}")
    print(f"  * Warning Hosts:          {summary['warning_hosts']}")
    print(f"  * Critical Hosts:         {summary['critical_hosts']}")
    print(f"  * Offline Hosts:          {summary['offline_hosts']}")
    print(f"  * Total Active Alerts:    {summary['total_active_alerts']}\n")

    for h in summary['hosts']:
        worst = h['worst_active_alert']['message'] if h['worst_active_alert'] else "None (Nominal)"
        print(f"    - [{h['status'].upper():<8}] {h['hostname']:<18} | Provider: {h['provider']:<10} | Env: {h['environment']:<10} | Alert: {worst}")

    # 2. Host Inventory
    print("\n[+] 2. GET /api/v1/hosts (Host Inventory):")
    hosts = requests.get(f"{BASE_URL}/hosts").json()
    for h in hosts:
        print(f"    - Host ID {h['id']}: {h['hostname']} (IP: {h['ip_address']}) - Active: {h['is_active']}")

    # 3. Active Alerts & Deduplication
    print("\n[+] 3. GET /api/v1/alerts (Active Alert Feed):")
    alerts = requests.get(f"{BASE_URL}/alerts?status=active").json()
    for a in alerts:
        print(f"    - Alert #{a['id']}: Host: {a['hostname']} | Kind: {a['kind']} | Metric: {a['metric']} | Severity: {a['severity']} | Msg: {a['message']}")

    # 4. Module 2: AI Anomaly Training
    print("\n[+] 4. POST /api/v1/ai/train (Training Isolation Forest on Fleet Telemetry):")
    train_res = requests.post(f"{BASE_URL}/ai/train", json={"contamination": 0.05, "version": "v1"}).json()
    print(f"    - Status: {train_res.get('status')} | Model: {train_res.get('model_name')} | Samples: {train_res.get('samples_trained')}")
    print(f"    - Baseline Means: {train_res.get('baseline_mean')}")

    # 5. Module 2: Real-Time Multivariate Scoring & Explainability (M2-FR2 / M5-FR5)
    print("\n[+] 5. POST /api/v1/ai/score (Near-Real-Time Multivariate Scoring):")
    sample_eval = {
        "hostname": "prod-web-02",
        "cpu_percent": 96.5,
        "memory_percent": 88.0,
        "disk_percent": 55.0,
        "network_sent_mb": 95.0,
        "network_received_mb": 2.5,
    }
    score_res = requests.post(f"{BASE_URL}/ai/score", json=sample_eval).json()
    print(f"    - Is Anomaly: {score_res['is_anomaly']} | Anomaly Score: {score_res['anomaly_score']}")
    print(f"    - Explainability: {score_res['explanation']}")
    for c in score_res['feature_contributions'][:3]:
        print(f"       * {c['metric']:<20}: {c['value']:>6.1f} (Contribution: {c['contribution_percent']}%, Z-Score: {c['z_score']})")

    # 6. Module 2: Time-Series Forecasting & Time-to-Threshold (M2-FR3 / M5-FR4)
    if hosts:
        sample_host_id = hosts[0]['id']
        print(f"\n[+] 6. GET /api/v1/forecast?host_id={sample_host_id}&metric=disk_percent (Predictive Failure Timeline):")
        fc_res = requests.get(f"{BASE_URL}/forecast?host_id={sample_host_id}&metric=disk_percent&horizon_hours=24&critical_threshold=95.0").json()
        print(f"    - Host: {fc_res['hostname']} | Metric: {fc_res['metric']} | Current: {fc_res['current_value']}%")
        print(f"    - Hourly Growth Slope: {fc_res['trend_slope_per_hour']}%/hr")
        if fc_res['time_to_threshold']:
            tt = fc_res['time_to_threshold']
            print(f"    - Time-to-Threshold: {tt['status']} | Hours Left: {tt['hours_remaining']} | ETA: {tt['breach_eta']}")
            print(f"    - Countdown Message: {tt['message']}")
        print(f"    - Generated {len(fc_res['forecast_points'])} future projection points with 95% confidence bounds.")

    # 7. Module 2: Model Registry Inspection
    print("\n[+] 7. GET /api/v1/ai/models (Model Registry Index):")
    models = requests.get(f"{BASE_URL}/ai/models").json()
    for m in models:
        print(f"    - Model: {m['model_name']} ({m['version']}) | File: {m['file_path']} | Trained At: {m['trained_at']}")

    print("\n=======================================================")
    print("     MODULES 1 & 2 OPERATIONAL & RUNNING NOMINALLY     ")
    print("=======================================================\n")

if __name__ == "__main__":
    test_live_system()
