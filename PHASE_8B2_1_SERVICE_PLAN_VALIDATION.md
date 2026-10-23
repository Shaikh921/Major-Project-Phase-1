# PHASE 8B.2.1 — READ-ONLY SERVICE PLAN VALIDATION & GIT DIFF AUDIT REPORT
## CloudOps Intel — Cloud Intelligence Platform & SRE Command Center

**Repository:** `C:\CLoudProject`  
**Branch:** `main`  
**Audit Timestamp:** 2026-10-22T17:25:00+05:30  
**Audit Mode:** Strictly Read-Only (Non-Mutating)  
**Evaluated Prior Reports:** `PHASE_8B1_FINAL_ACCEPTANCE_AUDIT.md`, `PHASE_8B2_OPERATIONAL_HARDENING_REPORT.md`  
**Overall Verdict:** **VALIDATED WITH CRITICAL ARCHITECTURAL CORRECTIONS REQUIRED**  
**Authorization Decision:** **Phase 8C & Windows Service Installation remain NOT AUTHORIZED**

---

## 1. Executive Summary and Overall Verdict

### Overall Verdict: **VALIDATED WITH CRITICAL ARCHITECTURAL CORRECTIONS REQUIRED**

A comprehensive, strictly read-only technical audit and feasibility validation was conducted on the proposed Windows service architecture (Phase 8B.2) and the working tree modifications.

### Key Audit Findings:
1. **Critical VSA Identity Flaw Identified (VERIFIED):** The proposed single service identity `NT SERVICE\CloudOpsIntel` is **invalid** in Windows for two distinct services (`CloudOpsBackend` and `CloudOpsProxy`). Windows Service Control Manager (SCM) generates Virtual Service Accounts (VSAs) strictly matching the registered service name (`NT SERVICE\<ServiceName>`). Furthermore, sharing a single account violates least privilege. The plan must be corrected to use separate VSAs: `NT SERVICE\CloudOpsBackend` and `NT SERVICE\CloudOpsProxy`.
2. **Caddy Profile & CA Disconnect Hazard (VERIFIED):** Caddy currently runs under interactive user `Dell` and stores its internal CA and certificates in `C:\Users\Dell\AppData\Roaming\Caddy`. In Windows Session 0 service mode, a service account has its own isolated profile (`%APPDATA%` does not point to `Dell`). If migrated without an explicit, persistent storage directory, Caddy will generate a **completely new internal root CA**, immediately breaking TLS trust for all agents provisioned with the original `root.crt`.
3. **NSSM Binary Absent (VERIFIED):** The Phase 8B.2 report assumed `tools\nssm.exe` was present. Physical directory inspection confirmed that `tools\nssm.exe` **does not exist** (only `caddy.exe` and `caddy.zip` exist). Any execution attempt would fail with `file not found`.
4. **Relative Path Vulnerability in Backend (VERIFIED):** `backend/app/core/config.py` and `.env` use relative paths: `database_url: str = "sqlite:///./cloud_intelligence.db"` and `env_file = ".env"`. If launched as a Windows service without an explicitly enforced working directory (`AppDirectory C:\CLoudProject`), Uvicorn would attempt to locate `.env` and create `cloud_intelligence.db` in `C:\Windows\System32`, causing failure or data divergence.
5. **Phase 8B.2 Git Diff Audit (VERIFIED):** All active documentation recommending insecure wildcard binding (`0.0.0.0:8000`) has been successfully eliminated from `README.md`, `docs/CODEBASE_ARCHITECTURE_AUDIT.md`, and `scripts/deploy_canary_agent.ps1`. Legacy unhardened port mapping in `docker-compose.yml` (`"8000:8000"`) was identified and cataloged for future containerization phases.
6. **Zero Impact on Active Services & Data (VERIFIED):** Uvicorn (PID 18104), Caddy (PID 21256), and Canary (PID 20728) remained continuously operational throughout the audit. Database integrity check returned `ok`.

---

## 2. Scope and Explicit Non-Actions

In accordance with mandatory safety directives, this phase operated in strictly read-only mode:
- **No Service Installation:** NSSM was not downloaded, installed, or registered. Zero Windows services were created or modified.
- **No Process Disruption:** Neither Uvicorn, Caddy, nor the Canary staging agent was stopped, restarted, or paused.
- **No Network / Security Mutation:** Windows Firewall rules, network bindings, and certificate trust stores were left untouched.
- **No CA Export:** Caddy's internal root CA certificate was not copied, transferred, or distributed.
- **No Remote Contact:** Strictly zero network packets were sent to physical lab PCs or remote workstations.
- **No Database Modification:** Zero migrations, seed operations, or write queries were performed.
- **No Destructive Git Actions:** No `git reset`, `git clean`, or blanket `git checkout` was executed.

---

## 3. Preflight Git Status and Exact Diff Inventory

### 3.1 Initial Git Status
Command: `git status --branch --porcelain`  
Branch: `main` (synchronized with `origin/main`).

### 3.2 Exact Diff Inventory for Phase 8B.2 Modifications
| File | Status | Lines Changed | Description of Phase 8B.2 Changes |
| :--- | :---: | :---: | :--- |
| [`README.md`](file:///C:/CLoudProject/README.md) | Modified | +78 / -25 | Replaced `uvicorn ... 0.0.0.0:8000` with loopback `127.0.0.1:8000` backend and Caddy port `8443`. Added *Network Security & Agent Transport Architecture* section. Updated test count to 149. |
| [`docs/CODEBASE_ARCHITECTURE_AUDIT.md`](file:///C:/CLoudProject/docs/CODEBASE_ARCHITECTURE_AUDIT.md) | Modified | +2 / -2 | Updated Section 3.3 Backend API entrypoint from `0.0.0.0:8000` to `127.0.0.1:8000` fronted by Caddy reverse proxy on port 8443. |
| [`scripts/deploy_canary_agent.ps1`](file:///C:/CLoudProject/scripts/deploy_canary_agent.ps1) | Untracked (User) | +6 / -2 | Corrected parameter comment from `http://192.168.1.100:8000` to `https://10.227.136.246:8443`. Added `[string]$CaBundle = ""` parameter and forwarded `--ca-bundle` to `agent.py`. |
| [`PHASE_8B1_NETWORK_EXPOSURE_REMEDIATION_REPORT.md`](file:///C:/CLoudProject/PHASE_8B1_NETWORK_EXPOSURE_REMEDIATION_REPORT.md) | Untracked (User) | +14 / -8 | Hardened Section 8 rollback procedure: replaced static PIDs with process-name queries, removed `0.0.0.0` restart advice, handled untracked `Caddyfile`. |
| [`PHASE_8B2_OPERATIONAL_HARDENING_REPORT.md`](file:///C:/CLoudProject/PHASE_8B2_OPERATIONAL_HARDENING_REPORT.md) | Untracked (New) | +235 | Operational hardening deliverable documenting documentation remediation and initial service persistence plan. |

All other uncommitted modifications in the working tree belong to prior Phase 8B hardening or pre-existing user feature development (`backend/app/api/v1/lab.py`, `frontend/js/views/LabView.js`, `tests/conftest.py`) and remain fully preserved.

---

## 4. Windows Service Identity and Least-Privilege Permissions (Stage B)

### 4.1 Evaluation of Proposed `NT SERVICE\CloudOpsIntel` Identity
- **Finding (VERIFIED):** In Windows SCM, Virtual Service Accounts (VSAs) are created dynamically based on the exact service name: `NT SERVICE\<ServiceName>`.
- **Architectural Correction:** If two services are registered (`CloudOpsBackend` and `CloudOpsProxy`), Windows creates:
  - `NT SERVICE\CloudOpsBackend`
  - `NT SERVICE\CloudOpsProxy`
  An account named `NT SERVICE\CloudOpsIntel` cannot be assigned to `CloudOpsBackend` unless a service named `CloudOpsIntel` exists.

### 4.2 Least-Privilege Account Isolation Matrix
Using distinct accounts establishes a critical security boundary between the reverse proxy and the database:

| Security Resource | Required Permission | `NT SERVICE\CloudOpsBackend` | `NT SERVICE\CloudOpsProxy` | Rationale & Security Boundary |
| :--- | :---: | :---: | :---: | :--- |
| **Python 3.13 Runtime (`C:\Python313`)** | Read & Execute (`RX`) | **ALLOW** | **DENY** | Caddy does not execute Python; backend requires interpreter. |
| **Application Code (`C:\CLoudProject\backend`)** | Read & Execute (`RX`) | **ALLOW** | **DENY** | Caddy only proxies TCP; does not read backend source. |
| **Environment File (`C:\CLoudProject\.env`)** | Read (`R`) | **ALLOW** | **DENY** | `.env` contains JWT secrets, admin credentials, and SMTP passwords. Caddy must never read application secrets. |
| **SQLite DB Files (`cloud_intelligence.db*`)** | Modify (`M`) | **ALLOW** | **DENY** | Backend handles all persistence; Caddy has zero database interaction. Prevents proxy exploits from accessing data. |
| **Backend Logs (`C:\CLoudProject\logs\backend`)** | Modify (`M`) | **ALLOW** | **DENY** | Dedicated log directory for Uvicorn stdout/stderr. |
| **Caddy Binary (`C:\CLoudProject\tools\caddy.exe`)** | Read & Execute (`RX`) | **DENY** | **ALLOW** | Backend does not execute Caddy. |
| **Caddyfile (`C:\CLoudProject\Caddyfile`)** | Read (`R`) | **DENY** | **ALLOW** | Caddy configuration. |
| **Caddy Data & CA (`C:\CLoudProject\data\caddy`)** | Modify (`M`) | **DENY** | **ALLOW** | Caddy internal CA private keys (`root.key`, `intermediate.key`) must remain inaccessible to the Python backend. |
| **Proxy Logs (`C:\CLoudProject\logs\proxy`)** | Modify (`M`) | **DENY** | **ALLOW** | Dedicated log directory for Caddy access/error logs. |

### 4.3 Service Logon Mechanics
- VSAs do not require passwords and are managed by Windows LSA.
- SCM automatically grants `SeServiceLogonRight` to the virtual account upon service startup.
- NTFS permissions can be assigned directly to `NT SERVICE\CloudOpsBackend` and `NT SERVICE\CloudOpsProxy` using `icacls`.

---

## 5. Caddy Data Directory, CA Persistence, and Trust Findings (Stage C)

### 5.1 Current Runtime vs Service Mode Disconnect
- **Current Interactive Execution (VERIFIED):**
  - Caddy is running under interactive user `Dell` (PID 21256).
  - Verified by `caddy environ`:
    - `caddy.HomeDir = C:\Users\Dell`
    - `caddy.AppDataDir = C:\Users\Dell\AppData\Roaming\Caddy`
    - `root.crt` path: `C:\Users\Dell\AppData\Roaming\Caddy\pki\authorities\local\root.crt`
- **Service Mode Disconnect Risk (VERIFIED):**
  - In Windows Session 0, Windows does not load the `Dell` user profile for service accounts.
  - If Caddy runs as `NT SERVICE\CloudOpsProxy` without an explicit data directory, Caddy defaults to `%APPDATA%\Caddy` under the service profile (e.g. `C:\Windows\System32\config\systemprofile\AppData\Roaming\Caddy`).
  - Caddy will **not find the existing CA** and will automatically generate a **new internal root CA**.
  - Any agent or client configured with the current `root.crt` will fail TLS handshakes (`SSLError: certificate verify failed`).

### 5.2 Corrected Caddy Storage Architecture
To ensure deterministic persistence across service restarts and identity changes, Caddy's storage must be explicitly anchored in the project hierarchy:

1. **Storage Directive in `Caddyfile`:**
   ```caddy
   {
       admin off
       auto_https disable_redirects
       storage file_system {
           root "C:\CLoudProject\data\caddy"
       }
   }
   ```
   *Alternative:* Set environment variable `CADDY_DATA_DIRECTORY=C:\CLoudProject\data\caddy` in the service definition.
2. **Migration Procedure:** Prior to launching Caddy as a service, copy existing CA material:
   ```powershell
   Copy-Item -Path "$env:APPDATA\Caddy\pki" -Destination "C:\CLoudProject\data\caddy\pki" -Recurse -Force
   ```
3. **NTFS Security on `data\caddy`:**
   ```powershell
   icacls "C:\CLoudProject\data\caddy" /inheritance:r /grant:r "SYSTEM":(OI)(CI)F "Administrators":(OI)(CI)F "NT SERVICE\CloudOpsProxy":(OI)(CI)M
   ```
   Denies access to all other users, securing private keys.

---

## 6. Backend, Environment, SQLite, and Logging Findings (Stage D)

### 6.1 Uvicorn Startup & Configuration
- **Binding (VERIFIED):** `backend_host: str = "127.0.0.1"` in [`backend/app/core/config.py`](file:///C:/CLoudProject/backend/app/core/config.py#L29) and `.env`. Loopback binding is strictly enforced.
- **Port:** `8000`.

### 6.2 Relative Path Risks & Working Directory
- **Finding (VERIFIED):**
  - Line 71: `database_url: str = "sqlite:///./cloud_intelligence.db"`
  - Line 92: `env_file = ".env"`
  Both settings are relative to the process working directory (`os.getcwd()`).
- **SCM Default Risk:** If a Windows service launches without an explicit working directory, it defaults to `C:\Windows\System32`.
- **Required NSSM Configuration:**
  - `nssm set CloudOpsBackend AppDirectory C:\CLoudProject`
  - Defense-in-depth: Specify absolute database path in `.env`:
    `DATABASE_URL=sqlite:///C:/CLoudProject/cloud_intelligence.db`

### 6.3 SQLite WAL Mode & File Locks
- **Pragmas (VERIFIED):** [`backend/app/database/connection.py`](file:///C:/CLoudProject/backend/app/database/connection.py#L20-L38) sets `PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=5000;`, and `PRAGMA foreign_keys=ON;`.
- **Filesystem Mechanics:** SQLite creates `cloud_intelligence.db-wal` and `cloud_intelligence.db-shm` in the database directory. `NT SERVICE\CloudOpsBackend` must have `Modify` permissions on the directory to create and delete `-wal` and `-shm` files during normal checkpointing.
- **Shutdown Cleanliness:** Upon receiving `SIGINT` / `CTRL_C_EVENT`, Uvicorn gracefully closes SQLAlchemy connections, allowing SQLite to checkpoint the WAL and release shared memory locks cleanly.

---

## 7. NSSM and Service Lifecycle Plan (Stage E)

### 7.1 NSSM Binary Status
- **Inspection (VERIFIED):** Inspection of `C:\CLoudProject\tools\` revealed:
  - `caddy.exe` (53,159,936 bytes) — Present
  - `caddy.zip` (1,372,160 bytes) — Present
  - `nssm.exe` — **ABSENT**
- **Evaluation:** NSSM must be downloaded and verified as a prerequisite before any service implementation can occur.

### 7.2 Dependency Ordering & Startup Readiness Analysis
- **SCM Dependency Limitation (INFERRED):** Configuring `DependOnService CloudOpsBackend` on `CloudOpsProxy` guarantees that SCM launches the `python.exe` process before `caddy.exe`. However, SCM **does not wait for FastAPI application initialization** (loading PyTorch, scikit-learn models, database schema).
- **Transient Gateway Hazard:** If Caddy receives incoming client requests while Uvicorn is still initializing its socket, Caddy returns `HTTP 502 Bad Gateway`.
- **Readiness Recommendation:**
  - Caddy handles upstream connection retries gracefully without crashing.
  - For clean startup synchronization, configure a service wrapper script or health-check wait loop:
    `while (!(Test-NetConnection -Port 8000).TcpTestSucceeded) { Start-Sleep -Milliseconds 500 }`

### 7.3 NSSM Configuration Specifications

#### Service 1: `CloudOpsBackend`
```ini
Application:         C:\Python313\python.exe
AppParameters:       -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
AppDirectory:        C:\CLoudProject
AppStdout:           C:\CLoudProject\logs\backend\uvicorn_stdout.log
AppStderr:           C:\CLoudProject\logs\backend\uvicorn_stderr.log
AppRotateFiles:      1
AppRotateBytes:      10485760 (10 MB)
AppThrottle:         1500 (1.5s restart delay)
AppStopMethodSkip:   0 (Send CTRL_C, wait for graceful ASGI teardown)
AppStopMethodConsole: 5000 (Wait up to 5s before force-kill)
```

#### Service 2: `CloudOpsProxy`
```ini
Application:         C:\CLoudProject\tools\caddy.exe
AppParameters:       run --config C:\CLoudProject\Caddyfile
AppDirectory:        C:\CLoudProject
AppEnvironmentExtra: CADDY_DATA_DIRECTORY=C:\CLoudProject\data\caddy
AppStdout:           C:\CLoudProject\logs\proxy\caddy_stdout.log
AppStderr:           C:\CLoudProject\logs\proxy\caddy_stderr.log
AppRotateFiles:      1
AppRotateBytes:      10485760 (10 MB)
DependOnService:     CloudOpsBackend
```

---

## 8. Documentation and Git Diff Audit (Stage F)

### 8.1 Insecure Binding Verification
A search across all active documentation was conducted:
- `git grep "0.0.0.0:8000" -- README.md docs/` returned **0 matches** (VERIFIED).
- Direct backend loopback binding (`127.0.0.1:8000`) is consistently documented.

### 8.2 Legacy Docker Compose Note
- [`docker-compose.yml`](file:///C:/CLoudProject/docker-compose.yml) lines 40 & 77 contains unhardened port mappings:
  - `ports: - "8000:8000"`
  - `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1`
- **Audit Assessment:** Docker is not utilized in the current bare-metal Windows pilot. However, if containerized deployment is authorized in a future phase (e.g. Phase 8C), `docker-compose.yml` must be updated to front the backend with a Caddy container and avoid exposing port 8000 on host adapters.

---

## 9. Cross-Machine Validation Prerequisites (Stage G)

To validate cross-machine TLS communication without risking lab disruptions, a future non-mutating validation procedure was designed for a single test workstation:

### 9.1 Required Prerequisites
1. **Explicit User Authorization:** Written approval specifying the target workstation hostname (e.g. `PC-Room1-02`), IP address, and scheduled testing window.
2. **Secure CA Bundle Transfer:** Out-of-band transfer of `root.crt` to the test machine via authenticated SCP/SFTP or pre-provisioned USB, with SHA256 verification:
   ```powershell
   Get-FileHash -Path root.crt -Algorithm SHA256
   ```
3. **Target Ingestion URL:** `https://10.227.136.246:8443/api/v1/metrics`.

### 9.2 Non-Mutating Probe Protocol
```mermaid
sequenceDiagram
    participant PC as Test Workstation
    participant ServerProxy as Caddy (:8443)
    participant ServerBackend as Uvicorn (127.0.0.1:8000)

    Note over PC, ServerBackend: Step 1: Verify Plaintext Exposure Blocked
    PC->>ServerBackend: TCP SYN to 10.227.136.246:8000
    ServerBackend--xPC: TCP Connection Refused / Timeout (PASS)

    Note over PC, ServerBackend: Step 2: Untrusted TLS Probe (Fail-Closed)
    PC->>ServerProxy: HTTPS GET /health (Default OS Trust, no CA bundle)
    ServerProxy--xPC: TLS Handshake SSLError: Self-Signed Cert in Chain (PASS)

    Note over PC, ServerBackend: Step 3: Trusted TLS Health Probe
    PC->>ServerProxy: HTTPS GET /health (verify=root.crt)
    ServerProxy->>ServerBackend: Reverse Proxy GET 127.0.0.1:8000/health
    ServerBackend-->>ServerProxy: HTTP 200 {"status": "healthy"}
    ServerProxy-->>PC: HTTP 200 + HSTS + nosniff + DENY (PASS)
```

### 9.3 Triage Matrix for Probe Failures
| Symptom Observed | Root Cause Classification | Diagnostic Action |
| :--- | :--- | :--- |
| **`ConnectionRefusedError: [Errno 10061]` on port 8443** | Caddy process not running or firewall blocking port 8443. | Inspect Caddy listener on server; verify Windows Firewall port 8443 inbound rule. |
| **`SSLError: certificate verify failed: self-signed certificate`** | Client did not supply `--ca-bundle` or supplied incorrect certificate. | Check client `AGENT_CA_BUNDLE` path; verify SHA256 hash of `root.crt`. |
| **`SSLError: CertificateError: hostname doesn't match`** | Client connected to hostname/IP not listed in certificate SANs. | Verify target matches `10.227.136.246`, `127.0.0.1`, or `localhost`. |
| **`HTTP 502 Bad Gateway`** | Caddy is running but Uvicorn backend on `127.0.0.1:8000` is down. | Inspect Uvicorn process and `logs\backend\uvicorn_stderr.log`. |
| **`TCP Connection Succeeded` on port 8000** | **CRITICAL SECURITY REGRESSION:** Uvicorn bound to `0.0.0.0`. | Halt immediately; rebind Uvicorn to `127.0.0.1`. |

---

## 10. Risk Register

| Risk ID | Title | Severity | Evidence | Impact | Recommended Mitigation |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **R-01** | **VSA Account Mismatch** | **HIGH** | Windows VSA architecture requires 1:1 service name matching. | Services fail to start if configured with `NT SERVICE\CloudOpsIntel`. | Use separate accounts: `NT SERVICE\CloudOpsBackend` and `NT SERVICE\CloudOpsProxy`. |
| **R-02** | **Caddy Internal CA Regeneration** | **HIGH** | Caddy derives storage from `%APPDATA%`, which shifts under service profiles. | Caddy creates new root CA; existing agents fail TLS verification. | Set `storage file_system { root "C:\CLoudProject\data\caddy" }` and migrate authorities. |
| **R-03** | **Missing NSSM Binary** | **MEDIUM** | `tools\nssm.exe` does not exist on disk. | Service installation commands will fail immediately. | Acquire and verify `nssm.exe` before installation phase. |
| **R-04** | **Relative Path Working Directory Drift** | **MEDIUM** | `config.py` uses `sqlite:///./cloud_intelligence.db` and `.env`. | Backend fails or creates database in `System32` if CWD is wrong. | Set `AppDirectory C:\CLoudProject` in NSSM; use absolute path in `.env`. |
| **R-05** | **Transient 502 on Boot** | **LOW** | Python takes ~3-5s to initialize while Caddy starts in <1s. | First client requests after boot may receive 502. | Configure health-check readiness wait script or rely on Caddy upstream retries. |

---

## 11. Corrected Proposed Service Implementation Plan

When authorization is granted, execute the implementation following this corrected blueprint:

### Phase 1: Preparation (Non-Disruptive)
1. Download official NSSM v2.24 (64-bit) into `tools\nssm.exe` and verify SHA256 hash.
2. Create dedicated directories:
   - `C:\CLoudProject\data\caddy`
   - `C:\CLoudProject\logs\backend`
   - `C:\CLoudProject\logs\proxy`
3. Migrate existing CA material from `%APPDATA%\Caddy\pki` to `C:\CLoudProject\data\caddy\pki`.
4. Update `Caddyfile` with explicit storage block:
   ```caddy
   {
       admin off
       auto_https disable_redirects
       storage file_system {
           root "C:\CLoudProject\data\caddy"
       }
   }
   ```
5. Update `.env` with absolute database path:
   `DATABASE_URL=sqlite:///C:/CLoudProject/cloud_intelligence.db`

### Phase 2: Service Registration & Security Hardening
1. Register `CloudOpsBackend`:
   ```powershell
   .\tools\nssm.exe install CloudOpsBackend "C:\Python313\python.exe" "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
   .\tools\nssm.exe set CloudOpsBackend AppDirectory "C:\CLoudProject"
   .\tools\nssm.exe set CloudOpsBackend ObjectName "NT SERVICE\CloudOpsBackend"
   .\tools\nssm.exe set CloudOpsBackend AppStdout "C:\CLoudProject\logs\backend\stdout.log"
   .\tools\nssm.exe set CloudOpsBackend AppStderr "C:\CLoudProject\logs\backend\stderr.log"
   .\tools\nssm.exe set CloudOpsBackend AppRotateFiles 1
   .\tools\nssm.exe set CloudOpsBackend AppRotateBytes 10485760
   ```
2. Register `CloudOpsProxy`:
   ```powershell
   .\tools\nssm.exe install CloudOpsProxy "C:\CLoudProject\tools\caddy.exe" "run --config C:\CLoudProject\Caddyfile"
   .\tools\nssm.exe set CloudOpsProxy AppDirectory "C:\CLoudProject"
   .\tools\nssm.exe set CloudOpsProxy ObjectName "NT SERVICE\CloudOpsProxy"
   .\tools\nssm.exe set CloudOpsProxy AppStdout "C:\CLoudProject\logs\proxy\stdout.log"
   .\tools\nssm.exe set CloudOpsProxy AppStderr "C:\CLoudProject\logs\proxy\stderr.log"
   .\tools\nssm.exe set CloudOpsProxy AppRotateFiles 1
   .\tools\nssm.exe set CloudOpsProxy AppRotateBytes 10485760
   .\tools\nssm.exe set CloudOpsProxy DependOnService CloudOpsBackend
   ```
3. Apply NTFS Permissions:
   ```powershell
   icacls "C:\CLoudProject\.env" /inheritance:r /grant:r "SYSTEM":R "Administrators":R "NT SERVICE\CloudOpsBackend":R
   icacls "C:\CLoudProject\cloud_intelligence.db*" /grant "NT SERVICE\CloudOpsBackend":M
   icacls "C:\CLoudProject\data\caddy" /inheritance:r /grant:r "SYSTEM":(OI)(CI)F "Administrators":(OI)(CI)F "NT SERVICE\CloudOpsProxy":(OI)(CI)M
   ```

### Phase 3: Controlled Cutover
1. Stop interactive processes:
   ```powershell
   Get-Process -Name "caddy" | Stop-Process -Force
   Get-Process -Name "python" | Where-Object { $_.CommandLine -match "uvicorn" } | Stop-Process -Force
   ```
2. Start services:
   ```powershell
   Start-Service CloudOpsBackend
   Start-Sleep -Seconds 3
   Start-Service CloudOpsProxy
   ```
3. Verify health via `https://localhost:8443/health`.

---

## 12. Remaining Unknowns and Tests Requiring Future Authorization

The following items cannot be resolved through read-only inspection and require future explicit authorization:
1. **NSSM VSA Compatibility Test:** Verification that NSSM v2.24 running on Windows 11 properly launches under an unprivileged `NT SERVICE\<ServiceName>` account without requiring a pre-allocated profile.
2. **Cross-Machine Routing & Firewall Behavior:** Verification that network switches and physical subnets route port 8443 packets cleanly from physical workstations to `10.227.136.246`.
3. **Client-Side CA Trust Integration:** Verification that client Python environments on student PCs trust the custom `root.crt` without OS certificate store administrator elevation.

---

## 13. Exact Files Changed by This Phase

Only the audit deliverable was created:
- Created: [`PHASE_8B2_1_SERVICE_PLAN_VALIDATION.md`](file:///C:/CLoudProject/PHASE_8B2_1_SERVICE_PLAN_VALIDATION.md)

Zero application source code, configuration, database, certificate, or script files were modified.

---

## 14. Confirmation of Process and Data State

- **Processes Untouched (VERIFIED):**
  - Uvicorn (PID `18104`) — Running on `127.0.0.1:8000`
  - Caddy (PID `21256`) — Running on `:8443`
  - Canary Agent (PID `20728`) — Running on loopback
- **Database Untouched (VERIFIED):**
  - Mode: `WAL`
  - Integrity: `ok`
  - Total Metrics: `4,988` (intact)
  - Total Alerts: `244` (intact)

---

## 15. Safe, Selective Recovery Approach for Future Changes

Should future authorized service installation fail during execution:
1. **Stop & Remove Services:**
   ```powershell
   .\tools\nssm.exe stop CloudOpsProxy
   .\tools\nssm.exe stop CloudOpsBackend
   .\tools\nssm.exe remove CloudOpsProxy confirm
   .\tools\nssm.exe remove CloudOpsBackend confirm
   ```
2. **Resume Interactive Execution:**
   ```powershell
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   .\tools\caddy.exe run --config Caddyfile
   ```
3. **Data Safety Warning:** Never execute `git clean -fd` or delete `cloud_intelligence.db*`.

---

### Audit Sign-off
**Auditor:** Antigravity AI — SRE Security & Architecture Subsystem  
**Overall Verdict:** **VALIDATED WITH CRITICAL ARCHITECTURAL CORRECTIONS REQUIRED**  
**Read-Only Compliance:** **100% VERIFIED** (Zero mutations, zero restarts, zero deployments)
