# PHASE 8B.3 STAGE A — PREPARATION AND CONFIGURATION VALIDATION REPORT
## CloudOps Intel — Cloud Intelligence Platform & SRE Command Center

**Repository:** `C:\CLoudProject`  
**Branch:** `main`  
**Execution Timestamp:** 2026-10-22T18:05:00+05:30  
**Phase:** Phase 8B.3 — Controlled Windows Service Implementation (Stage A: Preparation)  
**Status:** **STAGE A COMPLETE (PASS)**  
**Mandatory Stop:** **Stage B (Service Registration) and Stage C (Cutover) remain UNAUTHORIZED pending user review**

---

## 1. Executive Summary & Authorization Status

### Stage A Completion Verdict: **PASS**

In accordance with the mandatory Phase 8B.3 authorization gate, explicit user authorization was obtained before performing any mutation. Stage A executed strictly without terminating, restarting, or disrupting the active Uvicorn backend (PID `18104`), Caddy reverse proxy (PID `21256`), or Canary staging agent (PID `20728`).

### Key Accomplishments in Stage A:
1. **NSSM Acquired & Cryptographically Verified (VERIFIED):** Official NSSM v2.24 (build `2.24-101-g897c7ad`) was downloaded from `https://nssm.cc/` and verified against the official Microsoft Windows Package Manager (winget) manifest SHA-256 hash (`99f5045fffbffb745d67fe3a065a953c4a3d9c253b868892d9b685b0ee7d07b8`). The 64-bit binary was extracted to [`tools/nssm.exe`](file:///C:/CLoudProject/tools/nssm.exe) and verified via `tools\nssm.exe version`.
2. **Deterministic Caddy Storage Configured & Validated (VERIFIED):** Added `storage file_system { root "C:/CLoudProject/data/caddy" }` to [`Caddyfile`](file:///C:/CLoudProject/Caddyfile). Executed `tools\caddy.exe validate --config Caddyfile`, returning `"Valid configuration"` with exit code 0.
3. **Full Caddy CA & Storage Migration Completed (VERIFIED):** Established a complete pre-change backup of `%APPDATA%\Caddy` in `backups/caddy_full_backup_20261022_175124` with SHA-256 manifest. Replicated all 15 storage assets (including `root.crt`, `root.key`, `intermediate.crt`, and active leaf certificates) into `C:\CLoudProject\data\caddy` with 100% byte-for-byte cryptographic parity.
4. **Absolute Database URL Enforced (VERIFIED):** Updated [`.env`](file:///C:/CLoudProject/.env) to specify `DATABASE_URL=sqlite:///C:/CLoudProject/cloud_intelligence.db`. Validated via SQLAlchemy that the URL resolves directly to `C:\CLoudProject\cloud_intelligence.db`, permanently eliminating any risk of `C:\Windows\System32` directory drift during service execution.
5. **Recovery Manifest Created (VERIFIED):** Generated a timestamped recovery manifest and backup copy of all pre-change configuration files in `backups/stage_8b3_recovery_20261022_175124/`.
6. **Zero Interruption to Live Services (VERIFIED):** All active listeners and staging telemetry ingestion remained continuously live throughout Stage A.

---

## 2. Preflight Baseline State (Observed Runtime)

Before applying any preparation steps, the runtime state was recorded:

### 2.1 Active Processes
| Process Name | PID | Executable Path | Working Set | Responding | Start Time |
| :--- | :---: | :--- | :---: | :---: | :---: |
| `caddy.exe` | **21256** | `C:\CLoudProject\tools\caddy.exe` | ~60.4 MB | True | 2026-10-22 16:44:32 |
| `python.exe` (Uvicorn) | **18104** | `C:\Python313\python.exe` | ~395.9 MB | True | 2026-10-22 16:44:15 |
| `python.exe` (Canary) | **20728** | `C:\Python313\python.exe` | ~33.6 MB | True | 2026-10-22 16:50:05 |

### 2.2 Active TCP Listeners
- `127.0.0.1:8000` — Listen (OwningProcess: `18104`, Uvicorn loopback)
- `[::]:8443` — Listen (OwningProcess: `21256`, Caddy HTTPS)
- `0.0.0.0:8000` — *No listener* (Direct external plaintext HTTP eliminated)

### 2.3 Protocol Probes & Database State
- **Uvicorn Loopback Probe (`http://127.0.0.1:8000/health`):** HTTP 200 `{"status": "healthy"}`
- **Caddy HTTPS Probe (`https://localhost:8443/health`):** HTTP 200 `{"status": "healthy"}`
- **Caddy Binary Version:** `v2.11.7 h1:yj0Y4fYZGPkSvibBJ1sTWE33xC0fxztVyXEW5iIdUT4=`
- **Root CA Location:** `C:\Users\Dell\AppData\Roaming\Caddy\pki\authorities\local\root.crt` (627 bytes)
- **SQLite Database Path:** `C:\CLoudProject\cloud_intelligence.db`
- **SQLite Journal Mode:** `wal` (Write-Ahead Logging)
- **Database Integrity:** `ok`
- **Live Metric Samples:** 5,120 records (active canary ingestion ongoing)

---

## 3. Timestamped Recovery Manifest

A dedicated recovery manifest and immutable backup copy of all target files was created:
- **Manifest Location:** `C:\CLoudProject\backups\stage_8b3_recovery_20261022_175124\manifest.json`

| Target File | Original File Size | SHA-256 Checksum (Truncated) | Backup Copy Location |
| :--- | :---: | :---: | :--- |
| `C:\CLoudProject\Caddyfile` | 1,526 bytes | `41766beb65e8ba7e...` | `backups\stage_8b3_recovery_20261022_175124\Caddyfile` |
| `C:\CLoudProject\.env` | 1,397 bytes | `d09cc824fe63083a...` | `backups\stage_8b3_recovery_20261022_175124\.env` |
| `C:\CLoudProject\.env.example` | 2,140 bytes | `0df03c59242c2833...` | `backups\stage_8b3_recovery_20261022_175124\.env.example` |
| `C:\CLoudProject\cloud_intelligence.db` | 1,507,328 bytes | `be23e88afd176526...` | `backups\stage_8b3_recovery_20261022_175124\cloud_intelligence.db` |
| `root.crt` (Interactive CA) | 627 bytes | `c782936aa678496a...` | `backups\stage_8b3_recovery_20261022_175124\root.crt` |
| `intermediate.crt` | 676 bytes | `8450d07f58159a39...` | `backups\stage_8b3_recovery_20261022_175124\intermediate.crt` |

---

## 4. NSSM Acquisition and Cryptographic Provenance Verification

In strict compliance with directive safety rules, NSSM was acquired only from official origins and verified against independently trustworthy package catalog records:

### 4.1 Provenance Audit Record
- **Official Origin:** `https://nssm.cc/`
- **Package Manifest Checked:** Microsoft Windows Package Manager (`winget show NSSM.NSSM`)
- **Official Package URL:** `https://nssm.cc/ci/nssm-2.24-101-g897c7ad.zip`
- **Independently Published Expected SHA-256:** `99f5045fffbffb745d67fe3a065a953c4a3d9c253b868892d9b685b0ee7d07b8`
- **Actual Downloaded Zip SHA-256:** `99f5045fffbffb745d67fe3a065a953c4a3d9c253b868892d9b685b0ee7d07b8` (**EXACT MATCH**)

### 4.2 Extracted Binary Verification
- **Target File:** [`tools/nssm.exe`](file:///C:/CLoudProject/tools/nssm.exe)
- **Extracted Source:** `win64/nssm.exe` (Native 64-bit architecture)
- **Binary File Size:** 368,640 bytes
- **Binary SHA-256:** `eee9c44c29c2be011f1f1e43bb8c3fca888cb81053022ec5a0060035de16d848`
- **Execution Test Command:** `& "C:\CLoudProject\tools\nssm.exe" version`
- **Observed Execution Output:** `NSSM 2.24-101-g897c7ad 64-bit 2017-04-26`

---

## 5. Directory and Asset Preparation

The dedicated filesystem structure was initialized non-destructively:
- `C:\CLoudProject\data\caddy` (Caddy deterministic persistent storage)
- `C:\CLoudProject\logs\backend` (Dedicated Uvicorn stdout/stderr logs)
- `C:\CLoudProject\logs\proxy` (Dedicated Caddy access and error logs)

### Initial ACL Audit
Baseline inherited permissions verified via `icacls`:
- `BUILTIN\Administrators`: Full Control (`F`)
- `NT AUTHORITY\SYSTEM`: Full Control (`F`)
- `BUILTIN\Users`: Read & Execute (`RX`)
- `NT AUTHORITY\Authenticated Users`: Modify (`M`)

*Note: Custom service account grants (`NT SERVICE\CloudOpsBackend` and `NT SERVICE\CloudOpsProxy`) will be applied in Stage B after service creation.*

---

## 6. Caddy CA Backup & Storage Migration

### 6.1 Full Asset Tree Backup
A complete recursive backup of `%APPDATA%\Caddy` was established:
- **Backup Directory:** `C:\CLoudProject\backups\caddy_full_backup_20261022_175124`
- **Asset Count:** 15 files backed up and indexed with cryptographic hashes.

### 6.2 Target Directory Migration & Hash Verification
All 15 files were replicated into `C:\CLoudProject\data\caddy` and verified byte-for-byte:
- `pki\authorities\local\root.crt` -> SHA256: `c782936aa678496a...` (**VERIFIED MATCH**)
- `pki\authorities\local\root.key` -> Preserved
- `pki\authorities\local\intermediate.crt` -> SHA256: `8450d07f58159a39...` (**VERIFIED MATCH**)
- `pki\authorities\local\intermediate.key` -> Preserved
- `certificates\local\10.227.136.246\10.227.136.246.crt` -> SHA256: `a0e06616065eba90...` (**VERIFIED MATCH**)
- `certificates\local\127.0.0.1\127.0.0.1.crt` -> SHA256: `d12fcd82c1ead1a1...` (**VERIFIED MATCH**)
- `certificates\local\localhost\localhost.crt` -> SHA256: `7c9e9b69cd2fadde...` (**VERIFIED MATCH**)

### 6.3 Restoration Procedure (If Rollback is Required)
```powershell
Copy-Item -Path "C:\CLoudProject\backups\caddy_full_backup_20261022_175124\*" -Destination "$env:APPDATA\Caddy" -Recurse -Force
```

---

## 7. Configuration Updates and Validation

### 7.1 Caddyfile Storage Block
Updated [`Caddyfile`](file:///C:/CLoudProject/Caddyfile) global options to declare explicit storage:
```caddy
{
    admin off
    auto_https disable_redirects
    storage file_system {
        root "C:/CLoudProject/data/caddy"
    }
}
```
- **Validation Command:** `& "C:\CLoudProject\tools\caddy.exe" validate --config "C:\CLoudProject\Caddyfile"`
- **Observed Result:** `Valid configuration` (Exit code 0).

### 7.2 Absolute Database URL in `.env`
Updated [`.env`](file:///C:/CLoudProject/.env) to specify an absolute database URI:
```ini
DATABASE_URL=sqlite:///C:/CLoudProject/cloud_intelligence.db
```
- **Validation Command:** Tested with SQLAlchemy `create_engine("sqlite:///C:/CLoudProject/cloud_intelligence.db")`.
- **Observed Result:** `Connected database files: [(0, 'main', 'C:\\CLoudProject\\cloud_intelligence.db')]`.
- **Significance:** Guaranteed binding to `C:\CLoudProject\cloud_intelligence.db` regardless of the process current working directory.

---

## 8. Post-Stage A Active System Continuity Verification

Immediately following Stage A file updates, the live system state was re-probed to prove zero disruption:
- **Interactive Uvicorn (PID 18104):** **Still running**; `http://127.0.0.1:8000/health` returned HTTP 200.
- **Interactive Caddy (PID 21256):** **Still running**; `https://localhost:8443/health` returned HTTP 200.
- **Canary Staging Agent (PID 20728):** **Still running**; telemetry continuously streaming.
- **Database Integrity:** Re-checked; `PRAGMA integrity_check` returned `ok`.

---

## 9. Stage A Findings Classification

| Finding Item | Status | Classification | Evidence |
| :--- | :---: | :---: | :--- |
| **Initial Git & Working Tree** | Clean / Preserved | **VERIFIED** | Pre-existing lab views and scripts preserved untouched. |
| **Preflight System Baseline** | Recorded | **VERIFIED** | PIDs 18104, 21256, 20728 active; listeners on 8000 and 8443. |
| **Recovery Manifest** | Created | **VERIFIED** | `backups\stage_8b3_recovery_20261022_175124\manifest.json`. |
| **NSSM Acquisition & Hash** | Validated & Extracted | **VERIFIED** | Downloaded from official `nssm.cc`; matches Microsoft winget SHA-256 hash `99f5045...`. |
| **Directory Creation** | Completed | **VERIFIED** | `data\caddy`, `logs\backend`, `logs\proxy` exist. |
| **Caddy Storage Migration** | 100% Byte Parity | **VERIFIED** | 15 assets copied to `data\caddy`; hashes match backup. |
| **Caddyfile Storage Block** | Validated | **VERIFIED** | `caddy validate` returned "Valid configuration". |
| **Absolute SQLite URL** | Validated | **VERIFIED** | SQLAlchemy verified connecting to `C:\CLoudProject\cloud_intelligence.db`. |
| **Active Service Continuity** | 100% Operational | **VERIFIED** | Zero processes killed or restarted. |

---

## 10. Remaining Risks & Pre-Stage B Checklist

1. **Service Registration Pending Authorization:** No Windows services have been registered yet. Both Uvicorn and Caddy still run as interactive console processes.
2. **Virtual Account ACL Application Pending:** `icacls` grants for `NT SERVICE\CloudOpsBackend` and `NT SERVICE\CloudOpsProxy` cannot be applied until the services are registered in SCM (Windows provisions the virtual account SIDs upon registration).
3. **Cutover Window Pending:** Live cutover (stopping interactive processes and starting services) is strictly deferred to Stage C.

---

## 11. Rollback Procedure for Stage A

Should rollback of Stage A preparation changes be requested:
```powershell
# 1. Restore Caddyfile and .env from Stage A recovery backup
Copy-Item -Path "C:\CLoudProject\backups\stage_8b3_recovery_20261022_175124\Caddyfile" -Destination "C:\CLoudProject\Caddyfile" -Force
Copy-Item -Path "C:\CLoudProject\backups\stage_8b3_recovery_20261022_175124\.env" -Destination "C:\CLoudProject\.env" -Force
Copy-Item -Path "C:\CLoudProject\backups\stage_8b3_recovery_20261022_175124\.env.example" -Destination "C:\CLoudProject\.env.example" -Force

# 2. Remove downloaded NSSM binary and newly prepared directories
Remove-Item -Path "C:\CLoudProject\tools\nssm.exe", "C:\CLoudProject\tools\nssm.zip" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "C:\CLoudProject\data\caddy" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "C:\CLoudProject\logs\backend", "C:\CLoudProject\logs\proxy" -Recurse -Force -ErrorAction SilentlyContinue

# Note: Active interactive processes continue unaffected.
```

---

## 12. Mandatory Stop Condition

Stage A preparation and validation is complete. In strict adherence to prompt safety directives, execution is halted. 

**Do NOT proceed to Stage B (Service Registration and Permissions) or Stage C (Cutover) without explicit user authorization.**
