"""
Local Test Sensor Runner (Phase 9A.1 Interactive Verification).

Runs a local live monitoring agent for 'PC-Room1-01' (Host ID 12):
1. Pushes real-time CPU/RAM/Disk telemetry to the backend (making the host show Online).
2. Polls for Predefined Diagnostic commands dispatched from the dashboard.
3. Executes predefined diagnostics (Ping, DNS, System Summary) and reports results live.
"""

import sys
import time
from pathlib import Path

# Setup sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from monitoring_agent.agent import MonitoringAgent


def run_local_sensor():
    print("=" * 70)
    print(" CloudOps Intel — Local Interactive Diagnostic Test Sensor")
    print("=" * 70)
    print("[*] Simulating live host: PC-Room1-01 (Host ID: 12)")
    print("[*] Telemetry Target:    http://127.0.0.1:8000/api/v1/metrics")
    print("[*] Polling Interval:    5 seconds")
    print("=" * 70)
    print("[+] Sensor is starting up. In your browser dashboard:")
    print("    1. Go to Infrastructure / Fleet -> Host 'PC-Room1-01'")
    print("    2. Notice it is now ONLINE and streaming live telemetry!")
    print("    3. Click 'Run Diagnostics'")
    print("    4. Choose an action (e.g. SYSTEM_SUMMARY or PING_GATEWAY)")
    print("    5. Click 'Dispatch Diagnostic'")
    print("    6. Watch the execution output appear live on your screen!")
    print("=" * 70)
    print("[*] Press Ctrl+C in this terminal anytime to stop the test sensor.")
    print("=" * 70)

    # Use canary API key from .env.canary
    api_key = "ak_lab_room1_d1907a189f5dc549922bb4630d7fa6107ec3dce500824df4"

    agent = MonitoringAgent(
        server_url="http://127.0.0.1:8000/api/v1/metrics",
        interval=5,
        environment="lab",
        provider="bare-metal",
        region="Room 1",
        api_key=api_key,
        allow_insecure_http=True,
    )

    # Force hostname to match Host ID 12
    agent.collector.get_hostname = lambda: "PC-Room1-01"
    agent.assigned_name = "PC-Room1-01"
    if agent.diagnostic_worker:
        agent.diagnostic_worker.config["host_id"] = 12

    agent.start()


if __name__ == "__main__":
    run_local_sensor()

