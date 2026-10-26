# CloudOps Intel — Lab PC Monitoring Implementation Report
**Document Version:** 1.0.0  
**Date:** October 2026  
**Status:** Implemented & Verified (Isolated Local Environment)  
**Author:** CloudOps Intel Core Engineering Team  

---

## 1. Executive Summary

This report documents the architectural extension and implementation of the **Secure Lab PC Monitoring System** within the existing CloudOps Intel platform (`C:\CLoudProject`). The implementation enables Super Administrators to authorize, physically map, monitor, and govern Windows lab workstations across collegiate and enterprise computing environments without disrupting existing services, compromising database integrity, or deploying untrusted packages to physical network infrastructure.

The implementation strictly respects all mandatory execution rules:
- **Zero Production Disruption:** Active background services (`CloudOpsBackend` on port 8000, `CloudOpsProxy` on port 8443) remained uninterrupted and stable.
- **Zero Data Loss:** All 46 existing user accounts, 13 hosts, 5,381 metrics, 278 alerts, and audit logs were preserved. A full online SQLite backup was completed and verified prior to any migration.
- **Zero Remote HTTP Fallback:** Strict TLS verification with local authority certificate validation (`root.crt`) is enforced across all endpoints and sensors.
- **Zero Secret Leakage:** The CA private key (`root.key`), `.env` secrets, and database files were verified to be excluded from client distributions and logs.
- **Zero Physical Network Modifications:** All testing occurred in isolated environments; no physical college PCs were touched.

---

## 2. Implemented Features & Enhancements

### 2.1 Cryptographic Enrollment & One-Time Credential Delivery (Phase 1)
- **Time-Limited Single-Use Enrollment Codes:** Implemented in `backend/app/services/device_service.py` and `backend/app/models/device.py`. Super Admins can generate cryptographically random 32-character enrollment codes expiring in 15 minutes by default. Only the SHA-256 hash is persisted in `enrollment_codes`. Codes are rate-limited, single-use (`is_used=True`), and revocable.
- **Pending Device Ingestion Barrier:** When a sensor initiates enrollment (`POST /api/v1/devices/enroll`), the server records a pending workstation in `device_enrollments` and returns a non-sensitive `claim_token`. Devices in `PENDING` status cannot submit telemetry (strictly rejected with `HTTP 403 Forbidden`).
- **Physical Device Mapping:** Super Admins inspect the reported Windows hostname, hardware UUID, and IP address in the Web UI, assign an authoritative label (e.g. `PC-Lab1-05`), lab name, room number, and PC number, and issue approval.
- **One-Time Credential Delivery Protocol:** Upon approval, a unique `ak_lab_...` API key is generated and stored as a hash in `agent_api_keys`. The raw key is temporarily cached in `pending_raw_key` on the device record. When the sensor presents its valid `claim_token` via `POST /api/v1/devices/claim-credential`, the raw key is delivered exactly once, after which `pending_raw_key` is nullified and `credential_claimed` is set to `True`. Subsequent claims fail with `HTTP 401/410`.

### 2.2 Device Management Dashboard & Fleet Governance (Phase 2 & 8)
- **Super Admin Frontend View (`DeviceManagementView.js`):** Built into the existing vanilla JS SPA architecture. Features tabbed navigation:
  - *Active Fleet:* Workstation table with live online/offline heartbeat status, telemetry freshness, agent version, local spool backlog, and action buttons.
  - *Pending Approval:* Quarantine table displaying unapproved devices with physical mapping modals and rejection triggers.
  - *Enrollment Codes:* List of active, used, expired, and revoked codes with one-click revocation.
  - *Inactive / Retired:* Directory of disabled and decommissioned workstations with re-enablement and audit inspection.
- **Role-Based Access Control:** Sidebar link and view routing are restricted exclusively to `SUPER_ADMIN` in `frontend/js/app.js` and `frontend/index.html`. Unauthenticated users and normal admins cannot access the panel.

### 2.3 Windows Sensor Daemon & Installer Package (Phase 3 & 6)
- **Lightweight Sensor Client (`monitoring_agent/agent.py`):** Extended with `--enroll`, `--notify-uninstall`, persistent configuration (`sensor_config.json`), stable hardware UUID generation, and integration with the persistent SQLite spool buffer.
- **Windows Automated Installer (`scripts/install_sensor_client.ps1`):** PowerShell automation that validates administrative privileges, copies agent files to `C:\ProgramData\CloudOpsIntel\Sensor`, configures restrictive NTFS ACLs (SYSTEM and Administrators only), executes enrollment, and registers a Windows Scheduled Task (`CloudOpsSensorAgent`) configured to run non-interactively at boot under `NT AUTHORITY\SYSTEM`.
- **Clean Uninstaller (`scripts/uninstall_sensor_client.ps1`):** Stops and removes the scheduled task, kills agent processes, notifies the server (`POST /api/v1/devices/uninstall-notice`), warns prominently if remote connectivity is unavailable, and cleans up local binaries while preserving server-side telemetry history.
- **Packaging Utility (`scripts/package_sensor_agent.py`):** Produces `dist/cloudops-sensor-package.zip` with automated security verification ensuring `root.key`, `.env`, and database files are excluded, along with an authoritative SHA-256 checksum file.

### 2.4 Durable SQLite Telemetry Spooler (Phase 4)
- **Persistent Local Spooler (`monitoring_agent/buffer.py`):** Replaced ephemeral in-memory deque with a robust SQLite database queue (`spool_queue` in WAL mode). Unsent metrics survive service crashes, process termination, and Windows reboots.
- **Retention & Quota Management:** Enforces a 24-hour retention ceiling (records older than 24h are expired) and a configurable 50MB disk quota with automated FIFO pruning.
- **Reliable Dispatch:** Batches up to 1,000 metrics per atomic push, uses exponential backoff with jitter on network failure, and removes spooled records only after receiving a confirmed `HTTP 201 Created` server response.

### 2.5 Multi-Dimensional Telemetry & Connectivity Health (Phase 5)
- **Heartbeat Calculation:** Devices report telemetry samples which update `last_upload_at`, `last_collection_at`, and `queue_backlog` on `device_enrollments`.
- **180-Second Threshold:** Devices are flagged `OFFLINE` if no telemetry reaches the server for more than 180 seconds.
- **Freshness Classification:** Distinct indicators for `ONLINE_HEALTHY`, `STALE_TELEMETRY` (telemetry lag > 60s), `OFFLINE`, `DISABLED`, and `RETIRED`.

---

## 3. Files Created & Modified

### New Files Created
1. `backend/app/models/device.py` — SQLAlchemy ORM models: `EnrollmentCode`, `DeviceEnrollment`, `DeviceStatus`, `TelemetryHealthStatus`.
2. `backend/app/schemas/device.py` — Pydantic schemas for codes, enrollment requests, claims, approvals, and fleet statistics.
3. `backend/app/services/device_service.py` — Business logic for codes, claim token validation, physical mapping, key provisioning, and health metrics.
4. `backend/app/api/v1/devices.py` — FastAPI REST endpoints for Super Admin fleet operations and sensor enrollment.
5. `frontend/js/views/DeviceManagementView.js` — Super Admin SPA view for fleet governance.
6. `scripts/install_sensor_client.ps1` — Windows PowerShell unattended installer.
7. `scripts/uninstall_sensor_client.ps1` — Windows PowerShell uninstaller with remote notification.
8. `scripts/package_sensor_agent.py` — Packaging script for client zip distribution.
9. `requirements-agent.txt` — Minimal client workstation dependencies (`psutil`).
10. `README_SENSOR.md` — Client setup instructions.
11. `tests/test_device_enrollment.py` — Complete test suite for device lifecycle and buffer persistence.
12. `docs/lab-monitoring/PHASE_0_BASELINE_AUDIT.md` — Baseline audit document.
13. `docs/lab-monitoring/IMPLEMENTATION_REPORT.md` — This report.

### Existing Files Modified
1. `backend/app/models/agent_key.py` — Added `device_uuid` and `is_disabled` columns.
2. `backend/app/models/__init__.py` — Exported `EnrollmentCode` and `DeviceEnrollment`.
3. `backend/app/database/init_db.py` — Added schema migration hooks for device tables and columns.
4. `backend/app/schemas/__init__.py` — Exported device schemas.
5. `backend/app/api/v1/__init__.py` — Registered `devices.py` router on `/devices`.
6. `backend/app/api/deps.py` — Added key disabling and device lifecycle verification to `verify_agent_credentials`.
7. `backend/app/api/v1/metrics.py` — Wired telemetry heartbeat and upload timestamp updates.
8. `monitoring_agent/agent.py` — Added enrollment flow, version reporting, and config loading.
9. `monitoring_agent/buffer.py` — Replaced in-memory deque with persistent SQLite spooler.
10. `frontend/index.html` — Added `device-management` navigation item.
11. `frontend/js/app.js` — Registered `device-management` view and role guards.
12. `frontend/js/api.js` — Added API client methods for device management.

---

## 4. Test Verification Summary

- **Baseline Test Suite:** 149 passed, 0 failed (9.38s).
- **New Device Suite (`tests/test_device_enrollment.py`):** 8 passed, 0 failed (1.02s).
- **Full Regression Test Suite (`pytest -v`):** 157 passed, 0 failed (11.32s).
- **Test Database Isolation:** 100% verified. Active production database `cloud_intelligence.db` remained strictly untouched throughout all test executions.
