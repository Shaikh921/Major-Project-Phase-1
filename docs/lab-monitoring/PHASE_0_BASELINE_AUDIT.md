# Phase 0 — Full Repository Baseline & Architectural Audit

**Project:** CloudOps Intel — Cloud Intelligence Platform & SRE Command Center  
**Repository:** `C:\CLoudProject`  
**Branch:** `main` | **Head Commit:** `e5a4124`  
**Execution Mode:** Production Staging & Lab PC Monitoring Extension  
**Timestamp:** 2026-10-23T18:30:00+05:30  
**Baseline Database Backup:** `backups/pre_phase8b/cloud_intelligence_pre_phase8b_20261023_125836.db` (SHA-256: `1c5acd13c570b994faba139260a20f97e87492bda9d4e1dd9e63c2c80d4204f8`)  

---

## 1. Current Architecture and Data Flow

CloudOps Intel implements a two-tier reverse proxy and telemetry ingestion architecture:
1. **Central Server Architecture**:
   - **CloudOpsProxy (Caddy v2.9+)**: Running under virtual service account `NT SERVICE\CloudOpsProxy`. Terminates TLS on port `8443` using an internal Elliptic Curve (P-256) Certificate Authority (`tls internal`). Enforces HSTS, `nosniff`, and `DENY` frame options.
   - **CloudOpsBackend (FastAPI / Uvicorn)**: Running under virtual service account `NT SERVICE\CloudOpsBackend`. Bound strictly to loopback `127.0.0.1:8000` (zero `0.0.0.0` exposure). Serves static Single-Page Dashboard assets at `/dashboard/` and REST API endpoints at `/api/v1/`.
   - **Storage Engine (SQLite WAL)**: `cloud_intelligence.db` operating in Write-Ahead Logging (`WAL`) mode with a 30,000ms busy timeout (`PRAGMA busy_timeout=30000`). Root directory has targeted `(WD,AD,DC)` and `CREATOR OWNER:(OI)(CI)(IO)(M)` rights to isolate sidecars (`-wal`, `-shm`).
2. **Current Telemetry Flow**:
   - Client executes `monitoring_agent/agent.py`.
   - `SystemCollector` samples CPU, RAM, Disk, and Network MB deltas via `psutil`.
   - `MetricBuffer` queues samples in memory (`collections.deque(maxlen=5000)`).
   - Agent transmits HTTPS `POST` requests to `https://<SERVER_IP>:8443/api/v1/metrics` with header `X-Agent-Key`.
   - Server authenticates key against `settings.agent_ingestion_key` or `agent_api_keys` table.
   - Server validates provenance (`source_type == 'REAL_AGENT'`).
   - Server executes `get_or_create_host()` which auto-discovers and auto-registers the host by `hostname`.
   - Server commits metric sample to `metrics` table, evaluates threshold alert rules and AI anomaly detectors, and returns HTTP 201 Created.

---

## 2. Existing Features Reused in Lab PC Monitoring

The following existing modules are reused without destructive replacement:
- **`backend/app/models/user.py` & `backend/app/api/deps.py`**: Role-based access control (`SUPER_ADMIN`, `ADMIN`, `OPERATOR`, `VIEWER`), JWT access token validation, and password hashing (Argon2id).
- **`backend/app/models/agent_key.py`**: Existing `AgentApiKey` model containing `hashed_key`, `key_prefix`, `source_type`, `is_active`, and `revoked_at`.
- **`backend/app/models/host.py` & `backend/app/models/metric.py`**: Host metadata inventory and time-series telemetry persistence.
- **`backend/app/models/audit.py`**: Audit log model for tracking security-sensitive operations.
- **`backend/app/api/v1/lab.py`**: Existing room-grouped SRE overview endpoint (`/api/v1/lab/summary`) with configurable heartbeat online/offline calculation.
- **`monitoring_agent/collector.py`**: Hardware telemetry extraction using `psutil`.
- **`Caddyfile`**: TLS reverse proxy configuration with internal CA and security response headers.

---

## 3. Existing Security Controls & Verified Gaps

### Verified Security Controls:
1. **Loopback Backend Isolation**: Uvicorn is strictly bound to `127.0.0.1:8000`, preventing remote clients from bypassing TLS.
2. **Strict HTTPS Transport**: `MetricBuffer` rejects cleartext remote `http://` targets before transmitting credentials.
3. **Internal CA Verification**: Clients must provide `root.crt` to validate server identity.
4. **NTFS Service Isolation**: `NT SERVICE\CloudOpsBackend` and `NT SERVICE\CloudOpsProxy` have mutually exclusive read/write access.
5. **Argon2id & Constant-Time Auth**: Passwords hashed with Argon2id; agent keys compared using `hmac.compare_digest` and SHA-256.

### Verified Architecture & Security Gaps:
1. **GAP-01 (P0): Auto-Discovery Without Approval**: Any client possessing a valid `X-Agent-Key` is instantly created as an active host. There is no pre-approval or device authorization gate.
2. **GAP-02 (P0): Shared Pre-Shared Key Vulnerability**: Using a single shared `AGENT_INGESTION_KEY` across 30–100 lab PCs means any compromised student PC exposes the entire fleet.
3. **GAP-03 (P1): Volatile In-Memory Metric Buffer**: `MetricBuffer` stores queue in RAM. Reboots or power failures discard uncommitted telemetry.
4. **GAP-04 (P1): Hostname Collision Risk**: `get_or_create_host()` resolves hosts solely by `hostname`. Identical hostnames across different rooms will collide.
5. **GAP-05 (P1): Missing Windows Client Service Wrapper**: The agent requires manual terminal invocation; no automatic startup or service recovery exists on client PCs.
6. **GAP-06 (P2): Missing In-Dashboard Package Download**: No authenticated UI endpoint exists to download client installation archives.

---

## 4. Required Database & Schema Changes

To address the gaps while preserving all existing tables and data:
1. **New Table: `enrollment_codes`**:
   - `id`: Integer primary key.
   - `code_hash`: String(128) unique SHA-256 hash of single-use enrollment code.
   - `created_by_user_id`: Foreign key to `users.id` (`SUPER_ADMIN`).
   - `expires_at`: UTC timestamp (default 15 minutes).
   - `is_used`: Boolean (default False).
   - `used_at`: Optional UTC timestamp.
   - `revoked_at`: Optional UTC timestamp.
   - `created_at`: UTC timestamp.
2. **New Table: `device_enrollments`**:
   - `id`: Integer primary key.
   - `device_uuid`: String(64) unique immutable internal hardware identifier.
   - `reported_hostname`: String(100).
   - `assigned_name`: Optional String(100).
   - `lab_name`: Optional String(50).
   - `room_number`: Optional String(50).
   - `pc_number`: Optional String(50).
   - `ip_address`: Optional String(50).
   - `mac_address`: Optional String(50).
   - `os_version`: Optional String(100).
   - `agent_version`: Optional String(20).
   - `status`: String(30) (`PENDING`, `APPROVED`, `REJECTED`, `DISABLED`, `RETIRED`).
   - `agent_key_id`: Optional Foreign key to `agent_api_keys.id`.
   - `enrollment_code_id`: Optional Foreign key to `enrollment_codes.id`.
   - `host_id`: Optional Foreign key to `hosts.id`.
   - `requested_at`: UTC timestamp.
   - `reviewed_at`: Optional UTC timestamp.
   - `reviewed_by_user_id`: Optional Foreign key to `users.id`.
   - `last_contact_at`: Optional UTC timestamp.
   - `last_collection_at`: Optional UTC timestamp.
   - `last_upload_at`: Optional UTC timestamp.
3. **Extension to `agent_api_keys`**:
   - Add nullable `device_enrollment_id` foreign key.
   - Add `is_disabled` boolean flag.

All migrations must be non-destructive, executed via SQLAlchemy `CREATE TABLE IF NOT EXISTS` or idempotent `ALTER TABLE` checks inside `backend/app/database/init_db.py`.

---

## 5. Current Baseline Test Results

Ran baseline automated regression suite on `main` (`commit e5a4124`):
- **Command**: `pytest -q`
- **Result**: `149 passed, 50 warnings in 9.38s`
- **Pre-existing Failures**: 0 (zero).
- **Active Baseline Records in Database**:
  - `users`: 46
  - `hosts`: 13
  - `metrics`: 5,381
  - `alerts`: 278
  - `audit_logs`: 299
  - `agent_api_keys`: 1

---

## 6. Existing Working-Tree Changes

Working tree is 100% clean. No uncommitted modifications or untracked files existed at audit start.

---

## 7. Implementation Sequence and Rollback Plan

### Sequence:
1. **Phase 1**: Models & Schemas (`EnrollmentCode`, `DeviceEnrollment`, DB migrations in `init_db.py`).
2. **Phase 2**: Backend Services (`device_service.py` with enrollment code generation, pending registration, approval, rejection, disable, retire).
3. **Phase 3**: REST API Router (`backend/app/api/v1/devices.py` with strict `SUPER_ADMIN` authorization).
4. **Phase 4**: Durable Telemetry Buffer (`monitoring_agent/buffer.py` upgraded to persistent SQLite disk spool `sensor_spool.db`).
5. **Phase 5**: Health & 180s Connectivity Calculation (`backend/app/services/device_service.py` & `/api/v1/lab/summary`).
6. **Phase 6**: Windows Client Installer Package (`scripts/package_sensor_agent.py` and `scripts/install_sensor_client.ps1`).
7. **Phase 7**: Dashboard UI Integration (`frontend/js/views/DeviceManagementView.js`, updating `frontend/index.html` and `frontend/js/app.js`).
8. **Phase 8**: Automated Regression & Integration Testing.

### Rollback Plan:
- Database: Restore point-in-time snapshot `backups/pre_phase8b/cloud_intelligence_pre_phase8b_20261023_125836.db`.
- Git: Revert to commit `e5a4124`.
