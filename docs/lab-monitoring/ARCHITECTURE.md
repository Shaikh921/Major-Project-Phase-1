# CloudOps Intel — Lab PC Monitoring Architecture
**Document Version:** 1.0.0  
**Target Environment:** Windows 10/11 Workstations, Windows Server, Caddy Internal TLS, SQLite WAL  

---

## 1. High-Level Architecture Overview

The CloudOps Intel Lab PC Monitoring extension provides centralized telemetry ingestion, workstation lifecycle management, and failure resilience for educational and enterprise computer laboratories.

```mermaid
graph TD
    subgraph "Lab Workstations (Client Nodes)"
        Agent["Monitoring Agent Daemon<br/>(Scheduled Task / SYSTEM)"]
        Collector["SystemCollector<br/>(psutil / OS Metrics)"]
        Spooler[("Persistent SQLite Spooler<br/>sensor_spool.db (WAL)")]
        Config["Local Config<br/>sensor_config.json + root.crt"]

        Collector -->|Samples CPU, RAM, Disk, Net| Agent
        Agent -->|Pushes Telemetry Batch| Spooler
    end

    subgraph "Network Boundary (TCP Port 8443)"
        TLS["Caddy Reverse Proxy<br/>Port 8443 (Internal ECC TLS)<br/>Validates SAN (IP / DNS)"]
    end

    subgraph "Central Server (CloudOps Intel Core)"
        Backend["FastAPI Ingestion Server<br/>Port 8000 (Local Loopback)"]
        AuthDeps["verify_agent_credentials<br/>Enforces Active Key & Device Status"]
        IngestEngine["Telemetry & Provenance Engine"]
        DeviceSvc["Device Lifecycle Service"]
        AlertEngine["Real-time Alerting & Isolation Forest"]

        AppDB[("Central SQLite Database<br/>cloud_intelligence.db (WAL)")]
    end

    subgraph "Management Plane (Super Admin)"
        Browser["CloudOps Intel Web SPA<br/>Device Management Console"]
    end

    Spooler -->|Verified HTTPS (root.crt)| TLS
    TLS -->|Cleartext Reverse Proxy| Backend
    Backend --> AuthDeps
    AuthDeps -->|Validates ak_lab_... Key| AppDB
    AuthDeps --> IngestEngine
    IngestEngine --> IngestEngine
    IngestEngine -->|Write Metrics & Update Heartbeat| AppDB
    IngestEngine --> AlertEngine
    Browser -->|Session Auth + RBAC| DeviceSvc
    DeviceSvc --> AppDB
```

---

## 2. Key Architecture Components

### 2.1 Workstation Sensor Daemon
- **Execution Model:** Configured as a native Windows Scheduled Task (`CloudOpsSensorAgent`) running under `NT AUTHORITY\SYSTEM` with highest privileges. Boots automatically with Windows without requiring interactive user login.
- **Collector Subsystem (`SystemCollector`):** Uses `psutil` to sample hardware utilization:
  - CPU Utilization percentage (multi-core average)
  - Virtual Memory utilization percentage
  - System Disk utilization percentage (handling Windows drive roots like `C:\`)
  - Network I/O megabyte deltas (calculated over elapsed polling intervals)
  - Local system identifiers (Windows hostname, primary outbound IP)
- **Persistent Spooler (`MetricBuffer`):** Local disk-backed SQLite database (`sensor_spool.db`). Guarantees zero metric loss during network outages, server restarts, or Windows reboots. Metrics are committed to disk before being considered buffered.
- **Config Storage (`sensor_config.json`):** Stores `device_uuid`, `server_url`, `api_key`, `assigned_name`, `lab_name`, `room_number`, and `ca_bundle` path with restrictive NTFS ACLs.

### 2.2 Network & TLS Transport
- **Port Binding:** Telemetry and enrollment traffic enter through TCP port `8443`.
- **TLS Termination:** Handled by Caddy using an internal ECC Root Authority (`2026 ECC Root`).
- **Mutual Trust:** Sensors validate server certificates strictly against `root.crt` (the public CA root). Remote HTTP fallback is strictly forbidden and rejected at the socket level.

### 2.3 Backend Ingestion & Authorization
- **FastAPI Endpoints:**
  - `POST /api/v1/metrics`: Telemetry submission (single sample or batch up to 1,000 samples).
  - `POST /api/v1/devices/enroll`: Client registration handshake with enrollment code.
  - `POST /api/v1/devices/claim-credential`: Polling endpoint for one-time credential delivery.
  - `POST /api/v1/devices/uninstall-notice`: Graceful uninstallation notice.
  - `GET /api/v1/devices`: Fleet directory with real-time heartbeat calculations.
  - `POST /api/v1/devices/{id}/approve`: Super Admin physical device mapping and key provisioning.
  - `POST /api/v1/devices/{id}/disable`: Immediate server-side ingestion blockage.
  - `POST /api/v1/devices/{id}/retire`: Permanent credential revocation.
- **Security Interceptor (`verify_agent_credentials`):** Evaluates incoming API keys (`X-Agent-Key` or `Bearer` tokens). Verifies that the key exists, is active, is not disabled, has not been revoked, and that its associated `DeviceEnrollment` entity is in `APPROVED` state. Disabled or retired devices are rejected with `HTTP 403 Forbidden`.

### 2.4 Database & Persistence
- **Engine:** SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and a 60-second busy timeout (`PRAGMA busy_timeout=60000`).
- **Core Tables:**
  - `device_enrollments`: Stores immutable hardware UUIDs, reported hostnames, assigned labels, location hierarchy (lab, room, PC), lifecycle status (`PENDING`, `APPROVED`, `DISABLED`, `RETIRED`), claim token hashes, and telemetry heartbeat timestamps (`last_contact_at`, `last_collection_at`, `last_upload_at`, `queue_backlog`).
  - `enrollment_codes`: Stores time-limited single-use enrollment code hashes, prefixes, expiration timestamps, and redemption state.
  - `agent_api_keys`: Stores hashed device credentials, prefix identifiers, `device_uuid` linkage, and `is_disabled` flags.
  - `hosts`: Stores logical host records linked to device enrollments for metrics aggregation.
  - `metrics`: Chronological time-series metrics.
  - `audit_logs`: Authoritative record of every enrollment, approval, rejection, state change, and key revocation.

---

## 3. Multi-Dimensional Device State Model

To avoid conflating network reachability, telemetry collection, and administrative authorization, the system tracks state across three independent dimensions:

| Dimension | Possible Values | Meaning |
| :--- | :--- | :--- |
| **Connectivity** | `ONLINE`<br/>`OFFLINE` | Server has received telemetry within the last 180 seconds.<br/>No telemetry received for &gt; 180 seconds. |
| **Telemetry Health** | `HEALTHY`<br/>`STALE`<br/>`UNKNOWN` | Telemetry timestamp is within 60s of server ingestion.<br/>Agent is reaching server, but sampled data timestamp is lagged &gt; 60s.<br/>No telemetry received yet. |
| **Lifecycle / Authorization** | `PENDING`<br/>`APPROVED`<br/>`DISABLED`<br/>`RETIRED` | Enrollment requested; awaiting Super Admin review. Ingestion blocked.<br/>Super Admin approved and key provisioned. Ingestion allowed.<br/>Temporarily suspended by Super Admin. Ingestion blocked immediately.<br/>Permanently decommissioned. Key revoked server-side. |

---

## 4. Error Classification & Recovery Strategy

1. **Transient Network Outage (DNS failure, Cable unplugged, Server reboot):**
   - Sensor buffers metrics in `sensor_spool.db`.
   - Retries dispatch using exponential backoff with jitter (initial: 1.0s, multiplier: 2.0x, jitter: ±20%, max delay: 60.0s).
   - Once connectivity restores, sensor flushes backlog in batches of 1,000 samples. Server accepts backlog idempotently.
2. **Quota / Disk Saturation:**
   - If spool file reaches 50MB or records reach 5,000, oldest uncommitted records are pruned via FIFO.
   - Dropped count is reported to server diagnostics upon reconnection.
3. **Authentication Failure (Key Revoked / Disabled):**
   - Sensor receives `HTTP 401/403`.
   - Sensor suppresses aggressive retries and applies maximum backoff delay to prevent server log inundation.
   - Spooled data is preserved locally until administrator re-enables device or rotates credentials.
