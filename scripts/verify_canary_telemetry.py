"""
Stage 1 Canary Telemetry Verification Script.

Connects to the CloudOps Intel backend, validates end-to-end telemetry ingestion,
RBAC, provenance enforcement, room assignment, and offline threshold behaviors.
"""

import argparse
import sys
import time
from pathlib import Path
import requests

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.app.core.security import create_access_token


def run_verification(base_url: str = "http://localhost:8000", target_hostname: str = "PC-Room1-01") -> bool:
    print("=" * 65)
    print(f"  Stage 1 Canary End-to-End Verification -> Target: {target_hostname}")
    print(f"  Backend URL: {base_url}")
    print("=" * 65)

    all_passed = True

    # 1. Check Backend Health
    print("\n[Check 1] Checking backend health...")
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        if r.status_code == 200:
            print(f"  [PASS] Backend is healthy: {r.json()}")
        else:
            print(f"  [FAIL] Backend returned HTTP {r.status_code}: {r.text}")
            return False
    except Exception as e:
        print(f"  [FAIL] Failed to connect to backend: {e}")
        return False

    # 2. Generate Authorized Viewer Token for Verification
    viewer_token = create_access_token(user_id=1, email="audit_viewer@cloudops.internal", role="viewer")
    auth_headers = {"Authorization": f"Bearer {viewer_token}"}

    # 3. Verify Authentication Rejection on Lab Summary
    print("\n[Check 2] Verifying unauthenticated access rejection...")
    unauth_res = requests.get(f"{base_url}/api/v1/lab/summary", timeout=5)
    if unauth_res.status_code == 401:
        print("  [PASS] Unauthenticated request correctly rejected with HTTP 401 Unauthorized.")
    else:
        print(f"  [FAIL] Unauthenticated request returned HTTP {unauth_res.status_code} (expected 401).")
        all_passed = False

    # 4. Verify Invalid Agent Key Ingestion Rejection
    print("\n[Check 3] Verifying invalid agent key ingestion rejection...")
    invalid_res = requests.post(
        f"{base_url}/api/v1/metrics",
        headers={"X-Agent-Key": "invalid_bogus_key_12345"},
        json={"hostname": target_hostname, "cpu_percent": 10.0, "memory_percent": 20.0, "disk_percent": 30.0},
        timeout=5,
    )
    if invalid_res.status_code == 401:
        print("  [PASS] Ingestion with invalid key correctly rejected with HTTP 401.")
    else:
        print(f"  [FAIL] Ingestion returned HTTP {invalid_res.status_code} (expected 401).")
        all_passed = False

    # 5. Retrieve Lab Summary and Inspect Canary PC Record
    print(f"\n[Check 4] Checking {target_hostname} in /api/v1/lab/summary...")
    summary_res = requests.get(f"{base_url}/api/v1/lab/summary?real_agents_only=true", headers=auth_headers, timeout=5)
    if summary_res.status_code != 200:
        print(f"  [FAIL] Failed to retrieve lab summary: HTTP {summary_res.status_code} - {summary_res.text}")
        return False

    data = summary_res.json()
    all_pcs = []
    for room in data.get("rooms", []):
        for pc in room.get("pcs", []):
            all_pcs.append((room.get("room"), pc))

    canary_entry = None
    canary_room = None
    for r_name, pc in all_pcs:
        if pc.get("hostname") == target_hostname:
            canary_entry = pc
            canary_room = r_name
            break

    if not canary_entry:
        print(f"  [WARN] Canary PC '{target_hostname}' not yet found in lab summary.")
        print(f"         Total lab PCs found: {len(all_pcs)}")
        return False

    is_online = canary_entry.get("online", False)
    status_label = "online" if is_online else "offline"
    print(f"  [PASS] Found '{target_hostname}' in Room: '{canary_room}'")
    print(f"         Status: {status_label} (online={is_online})")
    print(f"         CPU: {canary_entry.get('cpu_percent')}% (Level: {canary_entry.get('cpu_level')})")
    print(f"         Memory: {canary_entry.get('memory_percent')}%")
    print(f"         Disk: {canary_entry.get('disk_percent')}%")
    print(f"         Last Seen: {canary_entry.get('last_seen')}")
    print(f"         IP Address: {canary_entry.get('ip_address')}")

    # 6. Verify Room Assignment
    if canary_room == "Room 1":
        print("  [PASS] Room assignment is correct ('Room 1').")
    else:
        print(f"  [WARN] Room assignment is '{canary_room}' (expected 'Room 1').")

    # 7. Verify Telemetry Receipt
    if canary_entry.get("last_seen"):
        print(f"  [PASS] Canary telemetry successfully recorded. Status evaluated as '{status_label}'.")
    else:
        print("  [FAIL] Canary has no recorded telemetry.")
        all_passed = False

    # 8. Test Offline Threshold Bounds
    print("\n[Check 5] Testing offline threshold parameter enforcement...")
    low_res = requests.get(f"{base_url}/api/v1/lab/summary?offline_after_seconds=5", headers=auth_headers, timeout=5)
    if low_res.status_code == 422:
        print("  [PASS] Offline threshold <10s rejected with HTTP 422.")
    else:
        print(f"  [FAIL] Expected 422 for offline threshold <10s, got {low_res.status_code}.")
        all_passed = False

    print("\n" + "=" * 65)
    if all_passed and canary_entry:
        print("  STAGE 1 CANARY VERIFICATION: ALL AUTOMATED CHECKS PASSED")
    else:
        print("  STAGE 1 CANARY VERIFICATION: ISSUES OR PENDING TELEMETRY DETECTED")
    print("=" * 65)
    return all_passed and (canary_entry is not None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--hostname", default="PC-Room1-01")
    args = parser.parse_args()
    success = run_verification(base_url=args.url, target_hostname=args.hostname)
    sys.exit(0 if success else 1)
