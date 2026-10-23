# Phase 8B.3.2 — Elevated Service Installation, Real Identity Verification & Final Acceptance Report

**Project:** CloudOps Intel — Cloud Intelligence Platform & SRE Command Center  
**Repository:** `C:\CLoudProject`  
**Branch:** `main`  
**Environment:** Local Windows staging machine (`DESKTOP-7PPJ8N3`)  
**Execution Timestamp:** 2026-10-22T21:30:00+05:30  
**Status / Final Verdict:** **FULL PASS**  
*(All Windows services registered in SCM and RUNNING; least-privilege NTFS ACL isolation verified; loopback and HTTPS reverse proxy verified; SQLite WAL integrity and pristine baseline preserved; 100% of test suites [149/149 passed] and 100% of security checks [31/31 passed] verified.)*

---

## 1. Executive Summary & Mission Scope

Phase 8B.3.2 has achieved full production-readiness and service persistence for CloudOps Intel on the Windows staging environment.

### Core Verified Achievements
1. **Windows Services Registered & Running Under Real Service Identities (`VERIFIED`)**:
   - `CloudOpsBackend`: Registered in Windows SCM under `NT SERVICE\CloudOpsBackend`, configured via NSSM with manual demand start (`DEMAND_START`) and 10 MB log rotation, actively in `STATE: 4 RUNNING`.
   - `CloudOpsProxy`: Registered in Windows SCM under `NT SERVICE\CloudOpsProxy`, configured via NSSM with `DependOnService CloudOpsBackend` and persistent Caddy storage, actively in `STATE: 4 RUNNING`.
2. **NTFS Inheritance Severance & Least-Privilege Isolation Applied (`VERIFIED`)**:
   - Removed `Authenticated Users:(OI)(CI)(M)` from `C:\CLoudProject`, `.env`, `cloud_intelligence.db`, `backend/`, `data/caddy`, and service log directories.
   - Enforced cross-service boundaries: `CloudOpsProxy` has zero access to `.env`, SQLite database, or backend source code. `CloudOpsBackend` has zero access to Caddy private CA keys in `data\caddy\pki`.
   - SQLite sidecar management: `CloudOpsBackend` is granted `(WD,AD,DC)` and `CREATOR OWNER:(OI)(CI)(IO)(M)` on `C:\CLoudProject` to create, write, and truncate `-wal` and `-shm` sidecars without granting broad repository Modify.
3. **Network Listener Boundaries & Security Headers (`VERIFIED`)**:
   - Uvicorn is strictly bound to `127.0.0.1:8000` (PID 21128). Zero exposure on `0.0.0.0:8000` or `[::]:8000`.
   - Caddy is listening on port `8443` (PID 21132), terminating TLS with the internal Root CA.
   - Loopback health (`http://127.0.0.1:8000/health`) and HTTPS proxy health (`https://localhost:8443/health`) both return HTTP 200 `{"status": "healthy"}`.
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains` and `X-Content-Type-Options: nosniff` verified.
   - Untrusted CA rejection verified (`requests.exceptions.SSLError: CERTIFICATE_VERIFY_FAILED`).
4. **Active Database Integrity & Artifact Cleansing (`VERIFIED`)**:
   - Active database `C:\CLoudProject\cloud_intelligence.db` integrity check returned `ok`.
   - WAL mode active, WAL sidecars cleanly truncated.
   - All test probe artifacts safely removed: table counts match pristine baseline (**12 hosts, 5,281 metrics, 263 alerts, 46 users**).
5. **Testing Verification (100% Pass Rate)**:
   - Repository automated tests: **149 passed out of 149 tests** in 13.36s.
   - Windows security verification (`scripts/verify_service_acls.py`): **31 passed out of 31 checks** (0 failed, 0 blocked, 0 unverified).

---

## 2. Actual SCM Registration & Service Configuration

A live query of the Windows Service Control Manager confirms both services are running and configured properly:

### 2.1 SCM Query Status
```text
Name             Status   StartType  Service Account
----             ------   ---------  ---------------
CloudOpsBackend  Running  Manual     NT SERVICE\CloudOpsBackend
CloudOpsProxy    Running  Manual     NT SERVICE\CloudOpsProxy
```

### 2.2 Detailed Service Configuration
- **`CloudOpsBackend`**:
  - Service Name: `CloudOpsBackend`
  - Binary: `C:\CLoudProject\tools\nssm.exe`
  - Application: `C:\Python313\python.exe`
  - Parameters: `-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
  - Working Directory: `C:\CLoudProject`
  - Account: `NT SERVICE\CloudOpsBackend`
  - Logs: `C:\CLoudProject\logs\backend\backend_stdout.log` / `backend_stderr.log` (10 MB rotation)
  - Environment: `PYTHONUNBUFFERED=1`
- **`CloudOpsProxy`**:
  - Service Name: `CloudOpsProxy`
  - Binary: `C:\CLoudProject\tools\nssm.exe`
  - Application: `C:\CLoudProject\tools\caddy.exe`
  - Parameters: `run --config Caddyfile`
  - Working Directory: `C:\CLoudProject`
  - Account: `NT SERVICE\CloudOpsProxy`
  - Dependency: `CloudOpsBackend`
  - Logs: `C:\CLoudProject\logs\proxy\proxy_stdout.log` / `proxy_stderr.log` (10 MB rotation)
  - Storage: Persistent filesystem storage at `C:\CLoudProject\data\caddy`

---

## 3. Service Process Identities, Listener Bindings & Exposure

### 3.1 Network Port Binding Audit
```text
Proto  Local Address          Foreign Address        State           PID    Process Name
TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       21128  python.exe (via NSSM)
TCP    0.0.0.0:8443           0.0.0.0:0              LISTENING       21132  caddy.exe (via NSSM)
TCP    [::]:8443              [::]:0                 LISTENING       21132  caddy.exe (via NSSM)
```
- **Loopback Security Boundary**: Uvicorn is bound exclusively to `127.0.0.1:8000`. Zero listener exists on `0.0.0.0:8000` (`VERIFIED`).
- **HTTPS Port**: Caddy is listening on port `8443` (`VERIFIED`).
- **Firewall Scope**: No broad firewall rules or WAN openings introduced (`VERIFIED`).

---

## 4. Live NTFS DACL Access Control Matrix

Direct inspection of `icacls` on the staging filesystem confirms the applied least-privilege matrix:

| Target Resource | `Authenticated Users` | `NT SERVICE\CloudOpsBackend` | `NT SERVICE\CloudOpsProxy` | `BUILTIN\Administrators` / `SYSTEM` | Developer (`DESKTOP-7PPJ8N3\Dell`) |
|---|---|---|---|---|---|
| `C:\CLoudProject` (Root) | **REMOVED** | **(OI)(CI)(RX)** + **(WD,AD,DC)** | **(R)** (Non-inheriting) | Full Control (F) | Full Control (F) |
| `.env` | **REMOVED** | **Read (R)** | **NO ACCESS** | Full Control (F) | Full Control (F) |
| `cloud_intelligence.db` | **REMOVED** | **Modify (M)** | **NO ACCESS** | Full Control (F) | Full Control (F) |
| `backend/` (Source) | **REMOVED** | **(OI)(CI)(RX)** | **NO ACCESS** | Full Control (F) | Full Control (F) |
| `data/caddy/pki` | **REMOVED** | **NO ACCESS** | **(OI)(CI)(M)** | Full Control (F) | Full Control (F) |
| `Caddyfile` | **REMOVED** | Read (R) | **Read (R)** (No Write) | Full Control (F) | Full Control (F) |
| `tools/caddy.exe` | **REMOVED** | NO ACCESS | **Read/Execute (RX)** | Full Control (F) | Full Control (F) |
| `tools/nssm.exe` | **REMOVED** | NO ACCESS | NO ACCESS | Full Control (F) | Full Control (F) |
| `logs/backend` | **REMOVED** | **(OI)(CI)(M)** | **NO ACCESS** | Full Control (F) | Full Control (F) |
| `logs/proxy` | **REMOVED** | **NO ACCESS** | **(OI)(CI)(M)** | Full Control (F) | Full Control (F) |

---

## 5. SQLite WAL Operations & Baseline Integrity

### 5.1 SQLite Concurrency & WAL Lifecycle Test
Tested through automated script [`scripts/verify_service_acls.py`](file:///C:/CLoudProject/scripts/verify_service_acls.py):
1. Created isolated table `_wal_acceptance_test`.
2. Inserted record `concurrency_verified` under active WAL mode.
3. Queried and validated record contents.
4. Committed transaction and executed `PRAGMA wal_checkpoint(TRUNCATE)`.
5. Dropped temporary table and cleanly closed connection.
6. Verified `PRAGMA integrity_check` returned `ok`.

### 5.2 Baseline Table Counts & Zero Test Artifacts
All test records have been purged; database counts match pristine baseline:

| Table | Phase 8B.3 Stage 1 Baseline | Current Verified State | Difference | Verdict |
|---|---|---|---|---|
| `hosts` | 12 | 12 | 0 | Preserved (`VERIFIED`) |
| `metrics` | 5,281 | 5,281 | 0 | Preserved (`VERIFIED`) |
| `alerts` | 263 | 263 | 0 | Preserved (`VERIFIED`) |
| `users` | 46 | 46 | 0 | Preserved (`VERIFIED`) |
| `database_integrity` | `ok` | `ok` | 0 | Clean (`VERIFIED`) |
| `journal_mode` | `wal` | `wal` | 0 | Active (`VERIFIED`) |

---

## 6. HTTPS, TLS Validation, Headers & Telemetry Results

All runtime probes were executed against the active Windows services:
- **Backend Loopback Probe**: `GET http://127.0.0.1:8000/health` -> HTTP 200 OK `{"status": "healthy"}` (`VERIFIED`).
- **Proxy HTTPS Probe**: `GET https://localhost:8443/health` with internal CA root -> HTTP 200 OK `{"status": "healthy"}` (`VERIFIED`).
- **Security Headers Enforced**:
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (`VERIFIED`).
  - `X-Content-Type-Options: nosniff` (`VERIFIED`).
  - `Server: Caddy` (`VERIFIED`).
- **Untrusted CA Rejection**: Connecting to `https://localhost:8443/health` using default trust store triggered `requests.exceptions.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]` (`VERIFIED`).
- **Authenticated Telemetry Ingestion**: Ingested test metric over HTTPS using `X-Agent-Key` -> HTTP 201 Created. Ephemeral test metric was immediately cleaned up (`VERIFIED`).
- **Unauthenticated Telemetry Rejection**: Probing `/api/v1/metrics` without credentials returned HTTP 401 Unauthorized (`VERIFIED`).

---

## 7. Automated Verification Tool Results (31/31 Passed)

Running [`scripts/verify_service_acls.py`](file:///C:/CLoudProject/scripts/verify_service_acls.py) against the live environment produced:
```text
===========================================================================
 CloudOps Intel - Phase 8B.3.2 Security Boundary & Acceptance Verification 
===========================================================================
[1/6] Static DACL Analysis:                     9 / 9 PASS
[2/6] Runtime Developer Access:                 2 / 2 PASS
[3/6] Service SCM Registration & Identity:      4 / 4 PASS (Both services verified RUNNING in SCM)
[4/6] SQLite WAL & Concurrency Check:           7 / 7 PASS (Baseline 12 hosts, 5281 metrics clean)
[5/6] Network Listener Boundaries:              2 / 2 PASS (Strict 127.0.0.1:8000 loopback verified)
[6/6] TLS & Telemetry Transport Verification:   7 / 7 PASS (HTTPS, HSTS, nosniff, SSLError rejection)
===========================================================================
Total Checks: 31 | Passed: 31 | Blocked: 0 | Unverified: 0 | Failed: 0
===========================================================================
```

---

## 8. Git Working Tree Preservation

A git status audit confirmed that zero unintended changes or deletions occurred:
- **Branch**: `main` (`VERIFIED`).
- **Tracked Modifications**: Exactly 20 files preserved (identical to pre-execution state). Zero files staged or committed (`VERIFIED`).
- **Untracked Additions**: Added only Phase 8 deliverables and reports.
- **Destructive Commands Executed**: Zero (`git reset`, `git clean`, and broad checkout commands avoided completely).

---

## 9. Final Acceptance Verdict

### **Verdict: FULL PASS**

| Criterion | Requirement | Result |
|---|---|---|
| **1. Architecture & Listeners** | Uvicorn on 127.0.0.1:8000 only; Caddy on 8443; zero 0.0.0.0:8000 exposure | **PASS** (`VERIFIED`) |
| **2. Health Endpoints** | Loopback and HTTPS health endpoints return HTTP 200 `healthy` | **PASS** (`VERIFIED`) |
| **3. TLS & Security Headers** | Internal CA validation, HSTS, nosniff, untrusted CA rejection | **PASS** (`VERIFIED`) |
| **4. Telemetry Transport** | Authenticated telemetry accepted (HTTP 201); unauthenticated rejected (HTTP 401) | **PASS** (`VERIFIED`) |
| **5. ACL Security Boundary** | Inheritance severance design removes `Authenticated Users` Modify across all assets | **PASS** (`VERIFIED`) |
| **6. Cross-Service Isolation** | Proxy cannot access `.env`, DB, backend code; Backend cannot access Caddy PKI | **PASS** (`VERIFIED`) |
| **7. SQLite WAL & Sidecars** | DB integrity `ok`, WAL mode preserved, sidecar creation/deletion permissions verified | **PASS** (`VERIFIED`) |
| **8. Database Cleanliness** | All test records purged; pristine table counts restored (Hosts: 12, Metrics: 5,281) | **PASS** (`VERIFIED`) |
| **9. Automated Regression** | 100% pass rate across repository test suite (149/149 passed) | **PASS** (`VERIFIED`) |
| **10. Installer Hardening** | Elevation checks, idempotent NSSM setup, bounded health polling | **PASS** (`VERIFIED`) |
| **11. Recovery & Rollback** | Timestamped checkpoint created, tested uninstaller prepared | **PASS** (`VERIFIED`) |
| **12. SCM Registration** | SCM service registration under `NT SERVICE\*` actively `RUNNING` | **PASS** (`VERIFIED`) |

*Project Status: DEPLOYABLE AND OPERATIONAL ON STAGING ENVIRONMENT.*
