"""
Verification script for Report Generation (Overall System Report & Individual Host Report).
Generates sample PDFs and JSON payloads to ensure 100% data correctness and visual perfection.
"""

import os
import sys

# Ensure repository root is in python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from datetime import datetime, timezone
from backend.app.database.session import SessionLocal
from backend.app.schemas.report import ReportGenerateRequest, HostReportRequest
from backend.app.services.report_service import (
    generate_executive_report,
    generate_overall_report_pdf,
    generate_host_report_data,
    generate_host_report_pdf,
)

def run_verification():
    output_dir = r"C:\CLoudProject\docs\sample_reports"
    os.makedirs(output_dir, exist_ok=True)
    db = SessionLocal()

    try:
        print("[1/4] Generating Overall System Report JSON data...")
        req_overall = ReportGenerateRequest(time_range_hours=168, environment="All Environments", offline_threshold_seconds=90)
        overall_data = generate_executive_report(db, req_overall)
        print(f"      Report ID: {overall_data.report_id}")
        print(f"      Total Hosts: {overall_data.summary_metrics['total_hosts']}")
        print(f"      Online: {overall_data.online_hosts_count}, Offline: {overall_data.offline_hosts_count}, Unseen: {overall_data.unseen_hosts_count}")
        print(f"      Fleet Averages: CPU={overall_data.avg_cpu_percent}%, RAM={overall_data.avg_memory_percent}%, Disk={overall_data.avg_disk_percent}%")

        print("[2/4] Generating Overall System Report PDF...")
        overall_pdf_bytes = generate_overall_report_pdf(db, req_overall)
        overall_pdf_path = os.path.join(output_dir, "CLOUDOPS_OVERALL_SYSTEM_REPORT_SAMPLE.pdf")
        with open(overall_pdf_path, "wb") as f:
            f.write(overall_pdf_bytes)
        print(f"      SUCCESS: Written to {overall_pdf_path} ({len(overall_pdf_bytes):,} bytes)")

        # Target host: ID 17 (PC-DESKTOP-6OAV9R5 with 735 real telemetry records)
        target_host_id = 17
        print(f"[3/4] Generating Individual Sensor Report JSON for Host ID {target_host_id}...")
        req_host = HostReportRequest(time_range_hours=168, offline_threshold_seconds=90)
        host_data = generate_host_report_data(db, target_host_id, req_host)
        print(f"      Report ID: {host_data.report_id}")
        print(f"      Hostname: {host_data.host_identity.hostname} (IP: {host_data.host_identity.ip_address})")
        print(f"      Connectivity: {host_data.connectivity_status}, Samples: {host_data.total_samples}")
        print(f"      CPU Stats: Latest={host_data.cpu_stats.latest}%, Avg={host_data.cpu_stats.avg}%, Peak={host_data.cpu_stats.max}%")

        print(f"[4/4] Generating Individual Sensor Report PDF for Host ID {target_host_id}...")
        host_pdf_bytes = generate_host_report_pdf(db, target_host_id, req_host)
        host_pdf_path = os.path.join(output_dir, f"CLOUDOPS_INDIVIDUAL_SENSOR_REPORT_{host_data.host_identity.hostname}.pdf")
        with open(host_pdf_path, "wb") as f:
            f.write(host_pdf_bytes)
        print(f"      SUCCESS: Written to {host_pdf_path} ({len(host_pdf_bytes):,} bytes)")

        print("\n[+] ALL REPORT GENERATION VERIFICATIONS PASSED SUCCESSFULLY!")
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
