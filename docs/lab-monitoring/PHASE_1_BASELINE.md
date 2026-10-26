# CloudOps Intel — Phase 1 Pre-Change Security & Reliability Baseline Report
**Document Version:** 1.0.0  
**Date:** October 2026  
**Status:** Baseline Completed (Pre-Implementation)  
**Author:** Antigravity Autonomous Security & Reliability Engineering Agent  

---

## 1. Executive Summary & Verification Context

This baseline report captures the operational, cryptographic, and architectural state of the **CloudOps Intel — Cloud Intelligence Platform & SRE Command Center** codebase prior to implementing Phase 1 remediation for findings **SEC-01**, **REL-01**, **REL-02**, and **SEC-02**.

All inspections were performed in strict compliance with non-negotiable safety rules:
- **Active Database Protection:** `C:\CLoudProject\cloud_intelligence.db` was accessed exclusively via read-only URI mode (`file:...mode=ro`) for state verification. Zero test queries, writes, or schema alterations were performed on the live database.
- **Service Isolation:** Running background services (`CloudOpsBackend` on port 8000, `CloudOpsProxy` on port 8443) were undisturbed. Network bindings, ports, and certificates remain unmodified.
- **Infrastructure Safety:** Zero scans, remote connections, or deployments were directed toward physical college workstations or network switches.
- **Secret Redaction:** All sensitive tokens, hashes, passwords, and private certificate keys are strictly redacted or replaced with synthetic test placeholders throughout this report.

---

## 2. Repository & Working Tree State

- **Repository Path:** `C:\CLoudProject`
- **Current Branch:** `main` (verified)
- **Current Commit:** `e5a4124` (`feat(phase-8b): implement hardened Windows services, Lab PC monitoring, and deployment guide`)
- **Pre-Existing Modified Files (Preserved):**
  1. `backend/app/api/deps.py`
  2. `backend/app/api/v1/__init__.py`
  3. `backend/app/api/v1/metrics.py`
  4. `backend/app/database/init_db.py`
  5. `backend/app/models/__init__.py`
  6. `backend/app/models/agent_key.py`
  7. `backend/app/schemas/__init__.py`
  8. `frontend/index.html`
  9. `frontend/js/api.js`
  10. `frontend/js/app.js`
  11. `monitoring_agent/agent.py`
  12. `monitoring_agent/buffer.py`
- **Pre-Existing Untracked Files (Preserved):**
  1. `README_SENSOR.md`
  2. `backend/app/api/v1/devices.py`
  3. `backend/app/models/device.py`
  4. `backend/app/schemas/device.py`
  5. `backend/app/services/device_service.py`
  6. `docs/lab-monitoring/` (10 files)
  7. `frontend/js/views/DeviceManagementView.js`
  8. `requirements-agent.txt`
  9. `scripts/install_sensor_client.ps1`
  10. `scripts/package_sensor_agent.py`
  11. `scripts/uninstall_sensor_client.ps1`
  12. `tests/test_device_enrollment.py`

---

## 3. Database Configuration & Backup Verification

### 3.1 Database Settings
- **Configured Database URL:** `sqlite:///cloud_intelligence.db` (resolved in `backend/app/core/config.py` to `C:\CLoudProject\cloud_intelligence.db`)
- **Active DB Status:**
  - File Size: ~1,597,440 bytes
  - Active Records: 46 users, 13 hosts, 5,381 metrics, 278 alerts, 1 agent key
  - Existing duplicates for `(host_id, timestamp)`: 0 detected
  - PRAGMA Integrity Check: Verified `ok`

### 3.2 Pre-Implementation Backup Verification
- **Verified Backup File:** `C:\CLoudProject\backups\pre_phase8b\cloud_intelligence_pre_phase8b_20261023_125836.db`
- **Backup File Size:** 1,597,440 bytes
- **SHA-256 Checksum:** `1C5ACD13C570B994FABA139260A20F97E87492BDA9D4E1DD9E63C2C80D4204F8`
- **Backup Integrity Check:** `PRAGMA integrity_check;` executed on backup file copy returned `[('ok',)]`
- **Readability & Recoverability:** Confirmed readable, non-corrupt, and verified as a trustworthy offline snapshot.

---

## 4. Test Suite Baseline & Isolation Proof

### 4.1 Test Isolation Setup
Automated tests are governed by `tests/conftest.py`:
- `DATABASE_URL` is forced to `sqlite:///:memory:`.
- `StaticPool` prevents connection pooling to any persistent file.
- `verify_active_db_unaltered` autouse fixture inspects `PRAGMA database_list;` at test session start and end to strictly assert that `main` is bound to memory and never to `cloud_intelligence.db`.

### 4.2 Baseline Test Execution
- **Command:** `pytest -q`
- **Pass / Fail Counts:** **157 passed, 0 failed, 50 warnings in 17.60s**
- **Warnings:** 50 scikit-learn unpickling version warnings for anomaly models (non-blocking).
- **Active Database Verification:** Confirmed 0 modifications occurred to `cloud_intelligence.db`.

---

## 5. Pre-Change Analysis of Findings

### 5.1 SEC-01: Credential and Demonstration Cleanup
- **Current Finding:**
  - Real active user account `superadmin@ops.local` exists in `cloud_intelligence.db` (User ID 4).
  - Test file `tests/test_super_admin_service.py` uses fixed credentials (`superadmin@ops.local` and a fixed test password `[REDACTED-TEST-SECRET]`).
  - While the live database hash differs from the test password, using realistic email addresses in tests and documentation creates credential confusion and exposure risks.
  - Docstring in `backend/app/cli/bootstrap_admin.py` references `admin@ops.local`.
- **Target Remediation:**
  - Replace realistic demonstration emails with RFC 2606 / RFC 6761 reserved domain placeholders (`admin@example.invalid` or `bootstrap.superadmin@example.invalid`).
  - Ensure documentation clearly directs operators to use environment variables or secure terminal prompts (`getpass`) without exposing credentials.
  - Preserve production accounts without unauthorized rotation, mutation, or backdoor injection.

### 5.2 REL-01: Telemetry Queue Retention and Overflow
- **Current Behavior:**
  - `monitoring_agent/buffer.py` default `max_size` is set to `5000`.
  - Polling cycle generates **1 sample per cycle** (`SystemCollector.collect()`).
  - At the default 5-second polling interval:
    $$\frac{60\text{ s}}{5\text{ s}} \times 60\text{ min} = 720\text{ samples/hr} \implies 720 \times 24 = 17,280\text{ samples/24h}$$
  - A capacity of 5,000 samples represents only $\frac{5000}{720} \approx 6.94\text{ hours}$ of retention, failing the 24-hour retention requirement.
  - Overflow logic currently drops oldest records silently (`DELETE FROM spool_queue WHERE id IN (SELECT id ... LIMIT ?)`), which is non-observable to operators.
  - Disk byte limit (`max_disk_mb = 50.0`) was not reconciled with `max_size`.
- **Target Remediation:**
  - Dynamically derive capacity:
    $$\text{Capacity} = \max\left(20000, \left\lfloor\frac{3600}{\text{interval}} \times \text{retention\_hours} \times 1.25\right\rfloor\right)$$
  - Implement an explicit overflow policy: default `preserve_queued`, record drops/rejections in `_dropped_count`, and expose via `get_diagnostics()`.
  - Ensure sample count limit and 50MB disk quota agree.

### 5.3 REL-02: Idempotent Telemetry Ingestion
- **Current Behavior:**
  - In `backend/app/api/v1/metrics.py` and `backend/app/services/metric_service.py`, `ingest_metrics_batch` iterates over `metrics` and commits each row individually without deduplication keys.
  - Retrying a batch upon network timeout causes duplicate metric rows to be inserted.
  - No batch identifier exists in `MetricBatchCreate` or `MetricCreate`.
  - `monitoring_agent/buffer.py` does not retain batch identity across flush retries.
- **Target Remediation:**
  - Introduce `batch_id: Optional[str]` to `MetricBatchCreate` (and `MetricCreate`).
  - Create `IngestedBatch` ORM model (`ingested_batches` table) with `batch_id` primary key, `payload_hash` (SHA-256), `processed_samples`, and `generated_alerts`.
  - Transactionally record the batch identity during metric insertion in `ingest_metrics_batch`.
  - On retry of the same `batch_id`:
    - Same payload hash $\implies$ Return cached success / duplicate-accepted response (zero duplicate rows inserted).
    - Different payload hash $\implies$ Reject with `HTTP 409 Conflict`.
  - In `monitoring_agent/buffer.py`, tag spooled rows with a stable `batch_id` prior to dispatch and retain it until confirmed acceptance (HTTP 200/201).

### 5.4 SEC-02: Rate Limiting on Public Sensor Endpoints
- **Current Behavior:**
  - `backend/app/api/v1/devices.py`:
    - `POST /api/v1/devices/enroll`: Has NO rate limiting attached.
    - `POST /api/v1/devices/claim-credential`: Has NO rate limiting attached.
  - While existing auth endpoints utilize `rate_limit_ip` (`auth_rate_limiter` in `backend/app/core/rate_limit.py`), the public sensor endpoints are vulnerable to unauthenticated flood attacks.
- **Target Remediation:**
  - Attach `rate_limit_ip` to `POST /api/v1/devices/enroll` (e.g. 10 requests per 60s per client IP).
  - Attach `rate_limit_ip` to `POST /api/v1/devices/claim-credential` (e.g. 30 requests per 60s per client IP, safely accommodating 5s polling).
  - Preserve one-time credential delivery, HTTP 429 response formatting with `Retry-After`, and strict socket client IP resolution.

---

## 6. Proposed Implementation Plan

1. **SEC-01:**
   - Update `tests/test_super_admin_service.py` to use nonfunctional synthetic domain `bootstrap.superadmin@example.invalid` and isolated fixture secrets.
   - Update `backend/app/cli/bootstrap_admin.py` docstring to use `admin@example.invalid`.
   - Update any documentation placeholders to use RFC invalid domains.
2. **REL-01:**
   - Update `monitoring_agent/buffer.py`: Reconcile capacity calculation with polling interval, implement `preserve_queued` overflow policy, and expose overflow/expiration diagnostics in `get_diagnostics()`.
   - Update `monitoring_agent/agent.py` to pass polling interval and calculated capacity to buffer.
3. **REL-02:**
   - Add `IngestedBatch` model in `backend/app/models/metric.py`.
   - Update `backend/app/schemas/metric.py` to include `batch_id`.
   - Update `backend/app/services/metric_service.py` and `backend/app/api/v1/metrics.py` to implement transactional idempotency and 409 conflict detection.
   - Update `monitoring_agent/buffer.py` to generate and persist `batch_id` across retries.
4. **SEC-02:**
   - Update `backend/app/api/v1/devices.py` to enforce `rate_limit_ip` on `/enroll` and `/claim-credential`.
5. **Testing & Verification:**
   - Create `tests/test_phase1_remediation.py` covering queue capacity/overflow, batch idempotency, retry safety, 409 conflict, and endpoint rate limiting.
   - Execute full regression test suite (`pytest -v`).
   - Author `docs/lab-monitoring/PHASE_1_REMEDIATION_REPORT.md`.
