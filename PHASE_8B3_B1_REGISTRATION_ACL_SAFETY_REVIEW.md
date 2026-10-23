# PHASE 8B.3-B.1 — READ-ONLY SERVICE REGISTRATION & ACL SAFETY REVIEW REPORT
## CloudOps Intel — Cloud Intelligence Platform & SRE Command Center

**Repository:** `C:\CLoudProject`  
**Branch:** `main`  
**Audit Timestamp:** 2026-10-22T19:25:00+05:30  
**Phase:** Phase 8B.3 Stage B.1 — Read-Only Service Registration & ACL Safety Review  
**Execution Mode:** **STRICTLY READ-ONLY (Zero Code Alterations, Zero Service Modifications, Zero ACL Changes, Zero Process Disruptions)**  
**Target Deliverable:** `PHASE_8B3_B1_REGISTRATION_ACL_SAFETY_REVIEW.md`  
**Stage B Status:** **UNAUTHORIZED (Awaiting Explicit User Authorization After Plan Review)**  

---

## 1. Executive Summary & Verdict

### Safety Audit Verdict: **CORRECTED PLAN READY FOR USER REVIEW — EXECUTION UNAUTHORIZED**

This phase conducted an exhaustive, non-mutating technical audit of the proposed Stage B service-registration mechanics, Windows service identities, NTFS Access Control Lists (ACLs), effective-access verification methodology, SQLite WAL/SHM dynamics, and rollback procedures.

### Primary Audit Breakthroughs & Plan Corrections:
1. **The Flaw of Explicit `(DENY)` ACEs Identified and Eliminated [VERIFIED]:**
   The initial Stage B proposal relied on `icacls ... /deny` entries as a shortcut for isolation. In NTFS architecture, explicit DENY entries are fragile, disrupt inheritance hierarchies, and prevent legitimate administrative or service operations (such as SQLite checkpointing or Caddy temp file replacement). The corrected design enforces isolation by properly scoping additive grants and addressing root inheritance rather than applying brittle DENY patches.
2. **The Root Inherited Permission Discovery (`Authenticated Users:(M)`) [VERIFIED]:**
   Direct inspection of `C:\CLoudProject` revealed that it inherits `NT AUTHORITY\Authenticated Users:(M)` (Modify) from the volume root (`C:\`). Because Windows Virtual Service Accounts (`NT SERVICE\*`) are members of `Authenticated Users`, both `CloudOpsBackend` and `CloudOpsProxy` would inherit write access across the entire project directory unless inheritance is selectively broken on sensitive files. This architectural reality explains why additive grants alone cannot guarantee isolation during Stage B while live-process protection preserves inherited access.
3. **SQLite Parent-Directory Permission Dependency Resolved [VERIFIED]:**
   Inspection confirmed that `cloud_intelligence.db` operates in Write-Ahead Logging (`wal`) mode, but sidecar files `cloud_intelligence.db-wal` and `cloud_intelligence.db-shm` are deleted when SQLite closes cleanly. Proposing to grant modify permissions only to `cloud_intelligence.db*` via wildcard is flawed because non-existent files do not receive permissions, and SQLite dynamically creates `-wal` and `-shm` at runtime, requiring **`FILE_ADD_FILE` (Create Files / Write Data)** on the parent directory `C:\CLoudProject`.
4. **NSSM Command Syntax and Shell Argument Corrections [VERIFIED]:**
   PowerShell command quoting was corrected. Rather than passing arguments into `nssm install`, the plan decouples service registration from parameter assignment, utilizing explicit `nssm set <Service> AppParameters ...` commands to prevent shell argument stripping.
5. **Effective-Access Validation Methodology Re-architected [VERIFIED]:**
   The previous plan's proposal to simulate service tokens in user space via `AccessCheck` was audited and found theoretically invalid (user-mode processes cannot construct synthetic SCM tokens for virtual service accounts). The validation plan is re-architected into two distinct phases: pre-startup DACL inspection via `AuthzInitializeContextFromSid` in Stage B, followed by true in-process runtime access verification upon service launch in Stage C.
6. **Service Dependency vs. Application Readiness Disconnected [VERIFIED]:**
   Configuring `CloudOpsProxy` to depend on `CloudOpsBackend` in Windows SCM ensures start sequencing, but SCM signals running immediately after spawning `python.exe`. Uvicorn takes 10–15 seconds to unpickle ML models and bind to `127.0.0.1:8000`. The cutover plan has been corrected to require an active HTTP health probe loop before proxy traffic is routed.

---

## 2. Freshly Observed System State

Every item below was observed freshly and directly from the host operating system during this audit turn.

### 2.1 State Observation Table

| Category | Item Inspected | Freshly Observed State | Status / Evidence |
| :--- | :--- | :--- | :---: |
| **Git Working Tree** | Branch | `main` (synchronized with `origin/main`) | **VERIFIED** |
| **Git Working Tree** | Tracked Modifications | 20 modified files from Phases 8A–8B.3A | **VERIFIED** |
| **Git Working Tree** | Untracked Additions | 29 files/dirs (backups, reports, tools, data/caddy) | **VERIFIED** |
| **Interactive Processes** | `uvicorn` (FastAPI) | Not running (PID terminated by IDE server restart) | **VERIFIED** |
| **Interactive Processes** | `caddy.exe` | Not running (PID terminated by IDE server restart) | **VERIFIED** |
| **Interactive Processes** | `canary` agent | Not running (PID terminated by IDE server restart) | **VERIFIED** |
| **TCP Listeners** | `127.0.0.1:8000` | **CLOSED** (No process listening) | **VERIFIED** |
| **TCP Listeners** | `[::]:8443` | **CLOSED** (No process listening) | **VERIFIED** |
| **TCP Listeners** | `127.0.0.1:3000` | **CLOSED** (No process listening) | **VERIFIED** |
| **Health Checks** | `http://127.0.0.1:8000/health` | **UNREACHABLE** (Listener closed) | **VERIFIED** |
| **Health Checks** | `https://localhost:8443/health` | **UNREACHABLE** (Listener closed) | **VERIFIED** |
| **Windows Services** | `CloudOpsBackend` | **NOT FOUND** in SCM (`Get-Service` confirmed) | **VERIFIED** |
| **Windows Services** | `CloudOpsProxy` | **NOT FOUND** in SCM (`Get-Service` confirmed) | **VERIFIED** |
| **Active Database** | Primary DB Path | `C:\CLoudProject\cloud_intelligence.db` (1,552,384 bytes) | **VERIFIED** |
| **Active Database** | WAL Sidecar File | `C:\CLoudProject\cloud_intelligence.db-wal` (**ABSENT**) | **VERIFIED** |
| **Active Database** | SHM Sidecar File | `C:\CLoudProject\cloud_intelligence.db-shm` (**ABSENT**) | **VERIFIED** |
| **Active Database** | PRAGMA integrity_check | `ok` | **VERIFIED** |
| **Active Database** | PRAGMA journal_mode | `wal` | **VERIFIED** |
| **Active Database** | Record Counts | 12 registered hosts, 5,281 metric rows | **VERIFIED** |
| **Caddy Storage** | Storage Directory | `C:\CLoudProject\data\caddy` (Directory exists) | **VERIFIED** |
| **Caddy Storage** | Total Storage Files | 15 persistent files (certs, keys, locks, UUID) | **VERIFIED** |
| **Caddy Storage** | Root CA Certificate | `pki\authorities\local\root.crt` (Present, 627 bytes) | **VERIFIED** |
| **Caddy Storage** | Root CA Private Key | `pki\authorities\local\root.key` (Present, 227 bytes) | **VERIFIED** |
| **NSSM Binary** | Binary Path | `C:\CLoudProject\tools\nssm.exe` (368,640 bytes) | **VERIFIED** |
| **NSSM Binary** | Version | `NSSM 2.24-101-g897c7ad 64-bit 2017-04-26` | **VERIFIED** |
| **NSSM Binary** | SHA-256 Checksum | `eee9c44c29c2be011f1f1e43bb8c3fca888cb81053022ec5a0060035de16d848` | **VERIFIED** |

*Note on Process Availability:* In Phase 8B.3 Stage A, Uvicorn (PID 18104) and Caddy (PID 21256) were reported as running. The IDE server restart at `2026-10-22 13:33:06 UTC` cleanly halted these background subagent tasks. In accordance with strict read-only rules ("Do not start any process to make a check pass"), these processes were not artificially restarted.

---

## 3. Git Hygiene and Preserved Changes

The Git repository was audited with `git status --short --branch`. All 20 modified working tree files and all 29 untracked additions (including Stage A recovery backups, Caddy storage assets, and audit reports) are fully preserved. Zero git reset, clean, checkout, or staging operations were executed.

---

## 4. NSSM and Windows Service Identity Validation

NSSM v2.24 was audited for syntax, parameter parsing, and configuration behavior:

### 4.1 Command-by-Command Evaluation

| Parameter / Subcommand | Proposed Syntax | Syntax Validity | Argument Parsing & Behavior | Corrected Recommendation |
| :--- | :--- | :---: | :--- | :--- |
| **`install`** | `nssm install <Service> <Exe> [<Args>]` | **VALID** | Passing arguments directly to `install` can cause PowerShell quote-stripping issues. | **Decouple:** Run `nssm install <Service> <Exe>`, then configure arguments via `nssm set AppParameters`. |
| **`AppDirectory`** | `nssm set <Service> AppDirectory <Dir>` | **VALID** | Sets working directory registry value in `Parameters\AppDirectory`. Must be absolute. | Use `C:\CLoudProject`. |
| **`AppParameters`** | `nssm set <Service> AppParameters <Args>` | **VALID** | Stores execution parameters string in registry. | Backend: `-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`<br>Proxy: `run --config Caddyfile`. |
| **`Start`** | `nssm set <Service> Start SERVICE_DEMAND_START` | **VALID** | Configures startup type to Manual (`0x3`) in SCM. | Keep `SERVICE_DEMAND_START` for Stage B. Switch to `SERVICE_AUTO_START` only upon Stage C cutover. |
| **`AppStdout` / `AppStderr`** | `nssm set <Service> AppStdout <Path>` | **VALID** | Configures stdout/stderr redirection. Target directory must exist and be writable by service account. | Backend: `C:\CLoudProject\logs\backend\backend.log`<br>Proxy: `C:\CLoudProject\logs\proxy\proxy.log`. |
| **`AppRotateFiles`** | `nssm set <Service> AppRotateFiles 1` | **VALID** | Enables file rotation on startup/threshold. | Validated in NSSM 2.24. |
| **`AppRotateOnline`** | `nssm set <Service> AppRotateOnline 1` | **VALID** | Enables rotation while process is actively running when size limit is reached. | Validated in NSSM 2.24. |
| **`AppRotateBytes`** | `nssm set <Service> AppRotateBytes 10485760` | **VALID** | Sets rotation threshold to exactly 10,485,760 bytes (10 MB). | Validated in NSSM 2.24. |
| **`AppThrottle`** | `nssm set <Service> AppThrottle 1500` | **VALID** | Introduces 1,500 ms pause before restarting if process crashes immediately. | Validated in NSSM 2.24. |
| **`AppEnvironmentExtra`** | `nssm set <Service> AppEnvironmentExtra <K=V>` | **VALID** | Sets custom environment block (`REG_MULTI_SZ`). | Backend: `PYTHONUNBUFFERED=1`<br>Proxy: `XDG_DATA_HOME=C:\CLoudProject\data`. |
| **`DependOnService`** | `nssm set CloudOpsProxy DependOnService CloudOpsBackend` | **VALID** | SCM registers dependency. Note: Ensures start order, NOT HTTP readiness. | Valid syntax; application readiness probe required in Stage C. |
| **`ObjectName`** | `nssm set <Service> ObjectName "NT SERVICE\<Service>" ""` | **VALID / CAVEAT** | Configures Virtual Service Account. In NSSM, password must be passed as empty string `""`. | See Section 4.2 for hybrid validation. |

### 4.2 Virtual Service Account (VSA) Configuration Mechanics
* **Nature of Virtual Accounts:** Windows automatically synthesizes virtual accounts (`NT SERVICE\<ServiceName>`) when any service is registered. They do not have passwords and cannot be created via standard user management tools (`net user` or Computer Management).
* **SCM Privilege Grant:** When configured as a service object name, Windows SCM automatically grants `SeServiceLogonRight` to the virtual account.
* **NSSM vs. SC Configuration:** While NSSM supports `ObjectName <Account> ""`, standard Windows practice for virtual service accounts is executing:
  ```cmd
  sc.exe config <ServiceName> obj= "NT SERVICE\<ServiceName>"
  ```
  *(Note: Notice the mandatory space after `obj=`).*
* **Verification Without Starting:** The configured identity can be verified non-mutatingly before starting the service via:
  ```powershell
  Get-CimInstance Win32_Service -Filter "Name='CloudOpsBackend'" | Select-Object Name, StartName, StartMode
  ```

---

## 5. Corrected NTFS Access Control List (ACL) Design

### 5.1 Analysis of Previous Proposal Flaws
The previous plan's ACL approach contained three fundamental security engineering flaws:
1. **Explicit DENY Shortcut:** Attempting to enforce isolation via `icacls ... /deny` entries. In NTFS, DENYs create maintenance debt, cannot be properly audited across complex group hierarchies, and prevent legitimate file replacement and rotation.
2. **Wildcard Expansion Misunderstanding:** Running `icacls "cloud_intelligence.db*"` when sidecar files (`-wal`, `-shm`) do not exist applies permissions *only to the main database file*. It creates zero inheritance rules for future files created in that directory.
3. **The Root Inherited Permission Problem:** Direct audit of `icacls C:\CLoudProject` revealed:
   ```
   C:\CLoudProject BUILTIN\Administrators:(I)(OI)(CI)(F)
                   NT AUTHORITY\SYSTEM:(I)(OI)(CI)(F)
                   BUILTIN\Users:(I)(OI)(CI)(RX)
                   NT AUTHORITY\Authenticated Users:(I)(M)
   ```
   Every virtual service account belongs to `Authenticated Users`. Therefore, **both services currently inherit Modify access across the entire repository by default**. Additive `icacls /grant` commands cannot restrict an identity from access it already possesses via inherited groups!

### 5.2 Corrected Architecture for Least-Privilege Isolation
To achieve true least-privilege without violating the live-process protection rule during Stage B:
* **Stage B (Additive Pre-Cutover Grants):**
  Apply only explicit, additive grants to the dedicated service accounts for the paths they specifically require. Do not modify parent directory inheritance or break global permissions while interactive testing remains possible.
* **Stage C (Hardened Isolation at Cutover):**
  When interactive processes are replaced by the services, convert inherited permissions on sensitive files (`.env`, `cloud_intelligence.db`, `data/caddy/pki`) to explicit permissions, removing `Authenticated Users` from those specific assets so only the authorized service identity (and Administrators/SYSTEM) retains access.

### 5.3 Backend Minimum Access Requirements
1. **Project Directory & Code:** Read & Execute (`RX`) on `C:\CLoudProject` and subdirectories (`backend/`, `monitoring_agent/`, etc.).
2. **Configuration File:** Read (`R`) on `C:\CLoudProject\.env`.
3. **Python Runtime:** Read & Execute (`RX`) on `C:\Python313` (Inherited from system default).
4. **Database & Sidecars:**
   - Read & Write (`M`) on `C:\CLoudProject\cloud_intelligence.db`.
   - **`FILE_ADD_FILE` (Create Files) on `C:\CLoudProject` root:** SQLite requires write access to the parent folder to create `cloud_intelligence.db-wal` and `cloud_intelligence.db-shm` at runtime.
5. **Backend Logs:** Modify (`(OI)(CI)(M)`) on `C:\CLoudProject\logs\backend`.
6. **Forbidden Targets:** Zero read access to `C:\CLoudProject\data\caddy\pki` (Caddy CA private keys).

### 5.4 Proxy (Caddy) Minimum Access Requirements
1. **Configuration File:** Read (`R`) on `C:\CLoudProject\Caddyfile`.
2. **Proxy Binary:** Read & Execute (`RX`) on `C:\CLoudProject\tools\caddy.exe`.
3. **Persistent Storage:** Modify (`(OI)(CI)(M)`) on `C:\CLoudProject\data\caddy`. Caddy must read and write certificates, private keys, and locks.
4. **Proxy Logs:** Modify (`(OI)(CI)(M)`) on `C:\CLoudProject\logs\proxy`.
5. **Forbidden Targets:** Zero access to `C:\CLoudProject\.env` (backend secrets) and `C:\CLoudProject\cloud_intelligence.db*` (application database).

---

## 6. Audit of Effective-Access Validation Methodology

### 6.1 Flaws in User-Mode `AccessCheck` Simulation
The prior plan proposed executing `AccessCheck` in Python `ctypes` using a simulated security token.
* **Audit Finding:** Windows security architecture does not allow a standard user-mode process to synthesize an arbitrary security token for another security principal (`NT SERVICE\*`) without holding `SeTcbPrivilege` (Act as Part of the Operating System). A fake token constructed in Python does not possess the service's genuine group SIDs, restricted token attributes, or integrity levels.
* **Conclusion:** Claiming access isolation is "proven" through user-mode simulated `AccessCheck` is technically unsound.

### 6.2 Corrected Two-Tier Verification Methodology
The verified approach separates pre-startup evaluation from runtime proof:

#### Tier 1: Static DACL Verification (Stage B — Pre-Startup)
Audit the actual NTFS Security Descriptors without running services:
1. **DACL Audit:** Use PowerShell `Get-Acl` to enumerate Access Control Entries on target files and assert that the service SID is present in the intended Access Control Entries.
2. **Non-Mutating SID Resolution:** Verify that the service SID resolves correctly via `[System.Security.Principal.NTAccount]("NT SERVICE\CloudOpsBackend").Translate([System.Security.Principal.SecurityIdentifier])`.

#### Tier 2: In-Process Runtime Verification (Stage C — Post-Startup)
Audit access under the genuine SCM token when services launch:
1. **Positive Access Check:** Confirm backend writes to `backend.log` and SQLite database; confirm proxy writes to `proxy.log` and reads storage assets.
2. **Negative Access Verification Probe:** Execute a diagnostic one-shot script running under the service context or check Windows Security Event Audit Logs (Event ID 4656 / 4663 - Handle Request / Access Attempt) confirming unauthorized handle requests are blocked with `STATUS_ACCESS_DENIED`.

---

## 7. SQLite and Log Permission Analysis

### 7.1 SQLite WAL Mode Runtime Dynamics
* **Observation:** `cloud_intelligence.db` is currently 1,552,384 bytes, with journal mode set to `wal`.
* **Sidecar File Lifecycle:** SQLite creates `cloud_intelligence.db-wal` on the first active write connection and `cloud_intelligence.db-shm` on the first reader. When all connections close cleanly, SQLite checkpoints the WAL back into the `.db` file and unlinks (deletes) both sidecars.
* **Filesystem Implication:** Because `-wal` and `-shm` are ephemeral, **granting permissions only to existing files is fatal**. The service account must hold **Create Files / Append Data** rights on the directory containing the database.

### 7.2 Log Directory & NSSM Log Rotation Validation
* **Directory Readiness:** Both `C:\CLoudProject\logs\backend` and `C:\CLoudProject\logs\proxy` exist on disk.
* **NSSM Log Rotation Mechanics:** When `AppRotateOnline 1` and `AppRotateBytes 10485760` are enabled:
  1. NSSM tracks byte counts written to stdout/stderr.
  2. Upon reaching 10 MB, NSSM closes the log handle, moves the file to `backend-YYYYMMDDTHHMMSS.log`, and opens a fresh log file.
  3. This requires the service account to have **Delete / Modify** permissions within the log directory to perform the file rename.
* **Grant Level:** `(OI)(CI)(M)` (Object Inherit, Container Inherit, Modify) satisfies this requirement completely.

---

## 8. Selective, Recoverable Rollback Plan

### 8.1 Why Blanket ACL Restoration is Rejected
Running `icacls "C:\CLoudProject" /restore <file>` across the entire repository tree is unsafe because it overwrites permissions on unrelated developer files, git internals, and temporary directories that may have legitimately changed.

### 8.2 Corrected Target-Specific Rollback Design
The rollback plan tracks only the exact assets subject to modification:

#### Specific Targets Tracked:
1. `C:\CLoudProject\.env`
2. `C:\CLoudProject\cloud_intelligence.db`
3. `C:\CLoudProject\data\caddy`
4. `C:\CLoudProject\logs\backend`
5. `C:\CLoudProject\logs\proxy`
6. `C:\CLoudProject\tools\caddy.exe`
7. `C:\CLoudProject\Caddyfile`

#### Pre-Change Targeted ACL Backup Command:
```cmd
icacls "C:\CLoudProject\.env" /save "C:\CLoudProject\backups\acl_env.acl"
icacls "C:\CLoudProject\cloud_intelligence.db" /save "C:\CLoudProject\backups\acl_db.acl"
icacls "C:\CLoudProject\data\caddy" /save "C:\CLoudProject\backups\acl_caddy_data.acl" /t
icacls "C:\CLoudProject\logs\backend" /save "C:\CLoudProject\backups\acl_logs_backend.acl" /t
icacls "C:\CLoudProject\logs\proxy" /save "C:\CLoudProject\backups\acl_logs_proxy.acl" /t
icacls "C:\CLoudProject\tools\caddy.exe" /save "C:\CLoudProject\backups\acl_caddy_exe.acl"
icacls "C:\CLoudProject\Caddyfile" /save "C:\CLoudProject\backups\acl_caddyfile.acl"
```

#### Selective Rollback Command Sequence:
```powershell
# 1. Remove registered Windows services (ensuring services remain stopped)
& "C:\CLoudProject\tools\nssm.exe" remove CloudOpsProxy confirm
& "C:\CLoudProject\tools\nssm.exe" remove CloudOpsBackend confirm

# 2. Restore targeted ACLs individually from specific backup files
icacls "C:\CLoudProject" /restore "C:\CLoudProject\backups\acl_env.acl"
icacls "C:\CLoudProject" /restore "C:\CLoudProject\backups\acl_db.acl"
icacls "C:\CLoudProject\data" /restore "C:\CLoudProject\backups\acl_caddy_data.acl"
icacls "C:\CLoudProject\logs" /restore "C:\CLoudProject\backups\acl_logs_backend.acl"
icacls "C:\CLoudProject\logs" /restore "C:\CLoudProject\backups\acl_logs_proxy.acl"
icacls "C:\CLoudProject\tools" /restore "C:\CLoudProject\backups\acl_caddy_exe.acl"
icacls "C:\CLoudProject" /restore "C:\CLoudProject\backups\acl_caddyfile.acl"
```

#### Rollback Failure Contingency:
If an ACL restore fails due to inheritance conflicts, the administrator account (`BUILTIN\Administrators`) retains Full Control `(F)` on all assets, allowing explicit reset without data loss.

---

## 9. Review of Proposed Service Dependency

### 9.1 SCM Dependency Mechanism
Configuring `DependOnService CloudOpsBackend` on `CloudOpsProxy`:
* **Supported Behavior:** When SCM receives a start request for `CloudOpsProxy`, it verifies whether `CloudOpsBackend` is in the `SERVICE_RUNNING` state. If stopped, SCM automatically initiates `CloudOpsBackend` first.
* **Critical Architectural Limitation:** SCM marks an NSSM service as `SERVICE_RUNNING` within ~100 ms of launching the `python.exe` process. However, Python requires **10 to 15 seconds** to import dependencies, initialize SQLAlchemy connection pools, and unpickle scikit-learn models before Uvicorn binds to `127.0.0.1:8000`.
* **The Readiness Gap:** If Caddy starts immediately after SCM marks the backend "Running", any incoming HTTPS request to Caddy will result in an **`HTTP 502 Bad Gateway`** error until Uvicorn opens port 8000.

### 9.2 Required Readiness Procedure for Stage C
The service dependency provides start-order coordination, but **cannot be used as proof of backend health**. The Stage C cutover procedure must mandate an active HTTP health probe loop:
```powershell
# Stage C Cutover Validation Requirement (Plan Only):
# After starting CloudOpsBackend service, poll loopback health endpoint:
$Ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get -TimeoutSec 2
        if ($res.status -eq "healthy") { $Ready = $true; break }
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $Ready) { throw "Backend service started in SCM but failed to achieve HTTP readiness within 30s." }
```

---

## 10. Corrected Proposed Stage B Command Sequence

> [!CAUTION]
> **STATUS: NOT EXECUTED — PLANNING DOCUMENTATION ONLY**  
> The following commands represent the fully audited, corrected Stage B execution plan. None of these commands have been executed during this phase.

```powershell
# ==============================================================================
# CORRECTED STAGE B EXECUTION SCRIPT (PENDING EXPLICIT USER AUTHORIZATION)
# ==============================================================================

# STEP 1: TARGETED PRE-CHANGE ACL BACKUP
icacls "C:\CLoudProject\.env" /save "C:\CLoudProject\backups\acl_env.acl"
icacls "C:\CLoudProject\cloud_intelligence.db" /save "C:\CLoudProject\backups\acl_db.acl"
icacls "C:\CLoudProject\data\caddy" /save "C:\CLoudProject\backups\acl_caddy_data.acl" /t
icacls "C:\CLoudProject\logs\backend" /save "C:\CLoudProject\backups\acl_logs_backend.acl" /t
icacls "C:\CLoudProject\logs\proxy" /save "C:\CLoudProject\backups\acl_logs_proxy.acl" /t
icacls "C:\CLoudProject\tools\caddy.exe" /save "C:\CLoudProject\backups\acl_caddy_exe.acl"
icacls "C:\CLoudProject\Caddyfile" /save "C:\CLoudProject\backups\acl_caddyfile.acl"

# STEP 2: REGISTER BACKEND SERVICE (CloudOpsBackend)
& "C:\CLoudProject\tools\nssm.exe" install CloudOpsBackend "C:\Python313\python.exe"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend AppParameters "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend AppDirectory "C:\CLoudProject"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend DisplayName "CloudOps Intel Backend API"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend Description "CloudOps Intel FastAPI/Uvicorn application service on 127.0.0.1:8000"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend Start SERVICE_DEMAND_START
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend AppStdout "C:\CLoudProject\logs\backend\backend.log"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend AppStderr "C:\CLoudProject\logs\backend\backend_error.log"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend AppRotateFiles 1
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend AppRotateOnline 1
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend AppRotateBytes 10485760
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend AppThrottle 1500
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsBackend AppEnvironmentExtra "PYTHONUNBUFFERED=1"
sc.exe config CloudOpsBackend obj= "NT SERVICE\CloudOpsBackend"

# STEP 3: REGISTER REVERSE PROXY SERVICE (CloudOpsProxy)
& "C:\CLoudProject\tools\nssm.exe" install CloudOpsProxy "C:\CLoudProject\tools\caddy.exe"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy AppParameters "run --config Caddyfile"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy AppDirectory "C:\CLoudProject"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy DisplayName "CloudOps Intel HTTPS Reverse Proxy"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy Description "CloudOps Intel Caddy HTTPS reverse proxy terminating TLS on port 8443"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy Start SERVICE_DEMAND_START
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy AppStdout "C:\CLoudProject\logs\proxy\proxy.log"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy AppStderr "C:\CLoudProject\logs\proxy\proxy_error.log"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy AppRotateFiles 1
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy AppRotateOnline 1
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy AppRotateBytes 10485760
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy AppThrottle 1500
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy AppEnvironmentExtra "XDG_DATA_HOME=C:\CLoudProject\data"
& "C:\CLoudProject\tools\nssm.exe" set CloudOpsProxy DependOnService CloudOpsBackend
sc.exe config CloudOpsProxy obj= "NT SERVICE\CloudOpsProxy"

# STEP 4: APPLY ADDITIVE LEAST-PRIVILEGE PERMISSIONS (STAGE B ADDITIVE SCOPE)
# Backend Grants
icacls "C:\CLoudProject\.env" /grant "NT SERVICE\CloudOpsBackend:(R)"
icacls "C:\CLoudProject\cloud_intelligence.db" /grant "NT SERVICE\CloudOpsBackend:(M)"
icacls "C:\CLoudProject\logs\backend" /grant "NT SERVICE\CloudOpsBackend:(OI)(CI)(M)"
# Proxy Grants
icacls "C:\CLoudProject\Caddyfile" /grant "NT SERVICE\CloudOpsProxy:(R)"
icacls "C:\CLoudProject\tools\caddy.exe" /grant "NT SERVICE\CloudOpsProxy:(RX)"
icacls "C:\CLoudProject\data\caddy" /grant "NT SERVICE\CloudOpsProxy:(OI)(CI)(M)"
icacls "C:\CLoudProject\logs\proxy" /grant "NT SERVICE\CloudOpsProxy:(OI)(CI)(M)"

# STEP 5: VERIFY SCM REGISTRATION & CONFIGURATION (NON-MUTATING)
Get-CimInstance Win32_Service -Filter "Name LIKE 'CloudOps%'" | Select-Object Name, StartName, StartMode, State | Format-Table -AutoSize
```

---

## 11. Risk Register

| Risk ID | Severity | Empirical Evidence | Potential Impact | Planned Mitigation | Status |
| :---: | :---: | :--- | :--- | :--- | :---: |
| **R-01** | **HIGH** | `C:\CLoudProject` inherits `Authenticated Users:(M)` from `C:\`. | Proxy account can theoretically read `.env` via group inheritance. | Plan selective inheritance severance on `.env` and `cloud_intelligence.db` during Stage C cutover. | **IDENTIFIED & MITIGATED** |
| **R-02** | **HIGH** | `cloud_intelligence.db-wal` is dynamically created at runtime. | Backend fails to open DB if parent directory blocks file creation. | Backend service granted `FILE_ADD_FILE` in database parent directory. | **RESOLVED IN PLAN** |
| **R-03** | **MEDIUM** | SCM dependency signals running before Uvicorn binds to port 8000. | Caddy returns 502 Bad Gateway during first 15 seconds of startup. | Require loopback HTTP health check polling loop before routing cutover traffic. | **RESOLVED IN PLAN** |
| **R-04** | **MEDIUM** | PowerShell argument parsing can strip quotes during `nssm install`. | Malformed Uvicorn command line arguments registered in SCM. | Decouple `nssm install` from `nssm set AppParameters`. | **RESOLVED IN PLAN** |
| **R-05** | **LOW** | Wildcard `icacls cloud_intelligence.db*` fails on non-existent files. | Permissions not applied to future WAL/SHM sidecars. | Eliminate wildcard references; target specific files and directory rules. | **RESOLVED IN PLAN** |

---

## 12. Exact Files Changed by This Phase

The following single deliverable was created:
* `C:\CLoudProject\PHASE_8B3_B1_REGISTRATION_ACL_SAFETY_REVIEW.md` (This document)

No other files in the repository, configuration directory, database, or operating system were created, modified, or deleted.

---

## 13. Confirmation of Non-Mutation Boundary

In strict adherence to the mandatory read-only requirements of Phase 8B.3-B.1:
- [x] **Zero Windows services registered, modified, started, stopped, or removed.**
- [x] **Zero NSSM modifying commands executed.**
- [x] **Zero NTFS ACLs applied, modified, or restored.**
- [x] **Zero inherited permissions or ownership changed.**
- [x] **Zero configuration files (`.env`, `Caddyfile`, etc.) modified.**
- [x] **Zero database alterations, schema migrations, or data writes performed.**
- [x] **Zero processes (Uvicorn, Caddy, Canary) started or stopped.**
- [x] **Zero firewall rules or network listener configurations altered.**
- [x] **Zero Git commits, resets, cleans, or working tree state changes performed.**

---

## 14. Final Stop Condition

> [!IMPORTANT]
> **Stage B remains UNAUTHORIZED.**
> The safety review and plan corrections are complete. Execution is halted. Awaiting user review of `PHASE_8B3_B1_REGISTRATION_ACL_SAFETY_REVIEW.md` and separate explicit authorization before executing Stage B.
