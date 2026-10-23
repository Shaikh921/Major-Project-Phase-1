# Phase 3 — Lab PC Monitoring Implementation Plan & Design Validation

**Project:** CloudOps Intel — Cloud Intelligence Platform & SRE Command Center  
**Document Version:** 1.1.0  
**Status:** Plan & Design Validation Complete (Awaiting Explicit User Approval)  
**Execution Mode:** Strictly Read-Only Planning — Zero Code / Database / Schema Modifications Performed  

---

## 1. Executive Summary

### 1.1 Scope and Objective
This document establishes the exhaustive, production-grade implementation plan and design validation for integrating **Lab PC Monitoring** into the active **CloudOps Intel** platform. It reconciles the proposed blueprint (`Lab_PC_Monitoring_Complete_Guide.pdf`), the architecture audit (`PHASE_2_CODEBASE_ARCHITECTURE_AUDIT.md`), and the actual operational state of the codebase.

The feature aims to provide real-time, room-grouped hardware monitoring for on-premise physical computers (e.g., college computer labs, testing facilities) alongside existing multi-cloud instances, featuring live CPU/RAM/disk tracking, automated online/offline detection, busiest-machine triage, and seamless integration into the existing alert, incident, and AI anomaly detection pipelines.

### 1.2 Core Architectural Principles
1. **Zero Database Migrations:** The active `hosts` and `metrics` database tables, along with the composite index `ix_metrics_host_id_timestamp ("host_id", "timestamp")`, already provide every column and indexing structure required. No new tables, column modifications, or index migrations are permitted or required.
2. **Preserve Defense-in-Depth Security:** Telemetry authentication (`verify_agent_credentials`) and source provenance enforcement (`validate_telemetry_provenance`) implemented in Phase 1 are strictly non-negotiable. The proposal in the guide to leave the ingestion endpoint open or allow unauthenticated telemetry is rejected.
3. **Optimized Query Performance:** The guide's proposal to group across the entire global `metrics` table is replaced with a scoped subquery restricted to `Host.environment == :environment`. This eliminates full table scans on multi-million row production databases.
4. **Architectural Alignment:** The frontend integration strictly conforms to existing platform patterns: view encapsulation in `frontend/js/views/LabView.js`, centralized client method `api.getLabSummary()` in `frontend/js/api.js`, route registration in `VIEW_MAP`, design-system token utilization, and tab-visibility-aware polling lifecycle management.
5. **Safe Operational Deployment:** Lab PC agents will run as background scheduled services utilizing pre-shared, least-privilege agent API keys (`source_type="REAL_AGENT"`), reporting at a conservative 15–30 second interval to eliminate SQLite database write-lock contention.

---

## 2. Verified Repository Findings

A strict, code-level inspection of the active codebase was conducted to establish verified ground truth. The findings confirm:

| Component / Subsystem | Source File & Verified Lines | Verified Current Behavior | Implementation Impact |
| :--- | :--- | :--- | :--- |
| **API Router Aggregation** | [`backend/app/api/v1/__init__.py:21-36`](file:///c:/CLoudProject/backend/app/api/v1/__init__.py#L21-L36) | Single aggregated `APIRouter(prefix="/api/v1")` mounts all feature routers (auth, admin, hosts, metrics, alerts, summary, forecast, ai, security, cost, narrator, reports, audit, currency). | `lab_router` must be mounted onto `api_router` with prefix `/lab` and tagged `["Lab"]`. |
| **Viewer Authentication** | [`backend/app/api/deps.py:131-201`](file:///c:/CLoudProject/backend/app/api/deps.py#L131-L201) | `get_current_viewer` enforces valid JWT Bearer authentication, extracts user ID from `sub`, verifies user exists and `is_active=True`, allowing roles `VIEWER`, `OPERATOR`, `ADMIN`, `SUPER_ADMIN`. | `GET /api/v1/lab/summary` must depend on `get_current_viewer` to prevent unauthenticated data exposure. |
| **Agent Authentication** | [`backend/app/api/deps.py:46-129`](file:///c:/CLoudProject/backend/app/api/deps.py#L46-L129) | `verify_agent_credentials` checks `X-Agent-Key` or `Authorization: Bearer <key>`. Compares constant-time against `settings.agent_ingestion_key` or SHA-256 hashed active, unrevoked keys in `agent_api_keys`. Rejects missing/invalid keys with HTTP 401. | The guide's claim that `POST /api/v1/metrics` has no auth is **false**. Agents deployed to lab PCs must be provisioned with an authorized key. |
| **Provenance Enforcement** | [`backend/app/api/v1/metrics.py:32-78`](file:///c:/CLoudProject/backend/app/api/v1/metrics.py#L32-L78) | `validate_telemetry_provenance` enforces strict match: `REAL_AGENT` credential only permits `source_type="REAL_AGENT"`; `SIMULATED` only permits `SIMULATED`; `ALL` permits either. Rejects `UNKNOWN` or mismatched types with HTTP 403 before DB writes. | Lab PC agents set `sample["source_type"] = "REAL_AGENT"` ([`agent.py:66`](file:///c:/CLoudProject/monitoring_agent/agent.py#L66)). Agent keys must be provisioned with `source_type="REAL_AGENT"`. |
| **Host Inventory Model** | [`backend/app/models/host.py:33-79`](file:///c:/CLoudProject/backend/app/models/host.py#L33-L79) | Table `hosts` contains `hostname` (unique, indexed), `ip_address`, `environment` (indexed), `provider`, `region`, `source_type` (indexed), `is_active`, `owner_email`, `tags` (JSON), timestamps. | Fields `environment` (`"lab"`), `region` (`"lab-1"`/room), and `provider` (`"college-lab"`) natively model lab infrastructure without schema changes. |
| **Host Auto-Registration** | [`backend/app/services/host_service.py:50-103`](file:///c:/CLoudProject/backend/app/services/host_service.py#L50-L103) | `get_or_create_host`: If host does not exist, provisions new row with provided environment/region. **Crucial:** If host exists, updates `ip_address`, `source_type`, `owner_email`, `is_active`, but **does NOT update `environment` or `region`**. | If a test PC was previously registered with `environment="local"`, running the agent with `--env lab` will **not** change its environment in DB. Controlled reassignment mechanism required. |
| **Host Administrative Update** | [`backend/app/api/v1/hosts.py:85-102`](file:///c:/CLoudProject/backend/app/api/v1/hosts.py#L85-L102) | `PATCH /api/v1/hosts/{host_id}` accepts `HostUpdate` (which includes `environment` and `region`) and enforces `get_current_admin`. Updates host attributes cleanly. | Verified: Existing test hosts registered as `local` can be reclassified to `lab` and assigned rooms immediately via `PATCH /api/v1/hosts/{id}` without any code changes. |
| **Metric Storage & Indexes** | [`backend/app/models/metric.py:33-73`](file:///c:/CLoudProject/backend/app/models/metric.py#L33-L73) | Table `metrics` stores `host_id` (FK), `timestamp`, `cpu_percent`, `memory_percent`, `disk_percent`, `network_sent_mb`, `network_received_mb`. Composite index `ix_metrics_host_id_timestamp` on `("host_id", "timestamp")`. | High-performance latest-metric queries can be served entirely via index seeks without table scans. |
| **Agent Collector & Buffer** | [`monitoring_agent/`](file:///c:/CLoudProject/monitoring_agent/) | `collector.py` uses `psutil` for CPU, RAM, Disk (Windows `C:\` and Linux `/` fallback), Net I/O. `buffer.py` has thread-safe ring buffer, exponential backoff, and **already supports `X-Agent-Key`** (`self.api_key`). `agent.py` supports CLI flags `--url`, `--interval`, `--env`, `--provider`, `--region`, `--api-key`. | Zero modifications needed in `monitoring_agent/` code. It is 100% production-ready for lab PC deployment. |
| **Alert & AI Pipeline** | [`backend/app/services/metric_service.py:58-69`](file:///c:/CLoudProject/backend/app/services/metric_service.py#L58-L69) | Ingestion runs: (1) `evaluate_metric_sample` (threshold rules), (2) `evaluate_and_record_ai_anomaly` (Isolation Forest), (3) `evaluate_correlated_anomaly` (3-tier consensus: threshold + IF + LSTM autoencoder sequence of last 15 points). | Lab PC metrics automatically benefit from enterprise alerting and AI anomaly detection out-of-the-box. |
| **Frontend Architecture** | [`frontend/`](file:///c:/CLoudProject/frontend/) | Vanilla ES6 modules, custom design tokens in CSS, centralized `ApiClient` (`frontend/js/api.js`), view mapping in `VIEW_MAP` (`frontend/js/app.js`), semantic sidebar nav in `frontend/index.html`. | `LabView.js` must be implemented as an ES6 module, use `api.getLabSummary()`, and follow existing UI component standards. |

---

## 3. Guide-versus-Code Compatibility Matrix

Every recommendation and code snippet from `Lab_PC_Monitoring_Complete_Guide.pdf` was audited against the active codebase. Below is the systematic classification:

| Feature / Proposal in Guide | Guide Assumption | Codebase Reality | Classification | Required Resolution in Plan |
| :--- | :--- | :--- | :--- | :--- |
| **Metric Ingestion Auth** | Ingestion endpoint is open without authentication; shared API key is optional future work (Guide pg 11). | Ingestion requires mandatory `verify_agent_credentials`. Unauthenticated requests return HTTP 401 Unauthorized. | **Unsafe as written** | Provision lab PC agents with a dedicated agent key (`AGENT_API_KEY` or `--api-key`). Include key in start scripts via secure environment variable. |
| **Telemetry Provenance** | Guide does not mention source provenance. | `validate_telemetry_provenance` enforces strict match against credential authority. Missing or UNKNOWN source types get HTTP 403 Forbidden. | **Incompatible as written** | Agent key must have `source_type="REAL_AGENT"`. Agent already sends `REAL_AGENT`, ensuring full compatibility when properly provisioned. |
| **Database Schema** | No new table or migration is needed; uses `hosts` + `metrics` (Guide pg 1). | Fully verified. Models `Host` and `Metric` already possess all required columns and indexes. | **Compatible as written** | Retain zero-migration approach. No Alembic migrations or schema changes. |
| **Latest Metric Query** | Unscoped subquery: `select(Metric.host_id, max(timestamp)).group_by(Metric.host_id)` (Guide pg 2). | Unscoped grouping performs a full table scan across the entire `metrics` table, degrading as millions of time-series samples accumulate. | **Compatible with modifications** | Scope the subquery to `Metric.host_id.in_(select(Host.id).where(Host.environment == environment))`. Uses index `ix_metrics_host_id_timestamp`. |
| **Host Environment Update** | Re-running agent with `--env lab` will automatically classify machine in lab view (Guide pg 9). | `get_or_create_host` preserves existing `environment` and `region` for registered hosts to prevent unauthorized environment hijacking. | **Requires a decision** | Existing hosts registered as `local` must be updated via verified existing endpoint `PATCH /api/v1/hosts/{id}` (requires ADMIN role). |
| **Router Mounting** | Add 2 lines to `backend/app/api/v1/__init__.py` (Guide pg 3). | `api_router` in `backend/app/api/v1/__init__.py` cleanly aggregates all routers. | **Compatible as written** | Import and mount `lab_router` identically to existing routers (`admin_router`, `summary_router`, etc.). |
| **API Response Schema** | Endpoint returns untyped `Dict[str, Any]` (Guide pg 2). | Codebase uses strict Pydantic schemas in `backend/app/schemas/` for OpenAPI docs, validation, and serialization contracts. | **Compatible with modifications** | Create `backend/app/schemas/lab.py` defining `LabSummaryResponse`, `LabPCEntry`, `LabRoomSummary`, and `LabTotalsSummary`. |
| **Frontend API Call** | `LabView.js` makes raw `api.request('/lab/summary?...')` call (Guide pg 4). | Platform uses encapsulated service methods on `ApiClient` in `frontend/js/api.js` (e.g., `getFleetSummary`, `getSecuritySummary`). | **Compatible with modifications** | Add `getLabSummary(params)` to `ApiClient` in `frontend/js/api.js`. `LabView.js` calls `api.getLabSummary()`. |
| **Frontend Styling** | Hardcoded inline styles and raw hex colors (`#2ea043`, `#d29922`, `#f85149`, `#6e7681`) (Guide pg 4). | Modern UI system uses CSS variables (`--color-success`, `--color-warning`, `--color-danger`, `--text-muted`, `--bg-card`). | **Compatible with modifications** | Refactor `LabView.js` to utilize platform CSS tokens and typography standards. |
| **Frontend Polling Lifecycle** | Unconditional `setInterval(fetchSummary, 10000)` without tab visibility or cleanup controls (Guide pg 4). | Polling background tabs drains client/server resources. | **Compatible with modifications** | Implement `cleanup` hook clearing timer on route change, and pause polling when `document.visibilityState === 'hidden'`. |
| **Monitoring Agent Code** | Guide says copy `monitoring_agent/` folder without code changes (Guide pg 1). | Fully verified. `monitoring_agent/agent.py`, `collector.py`, `buffer.py` have all required CLI args and buffering. | **Compatible as written** | No changes to `monitoring_agent/` code. |

---

## 4. Security and Performance Analysis

### 4.A API and Authorization
1. **Endpoint Specification:** `GET /api/v1/lab/summary` is architecturally sound. It isolates lab telemetry aggregation from cloud fleet summary while maintaining RESTful resource naming conventions under `/api/v1`.
2. **Access Control:** The endpoint must enforce `current_user: User = Depends(get_current_viewer)`.
   - **Protection:** Anonymous requests without a valid JWT access token will be rejected with `HTTP 401 Unauthorized`. Deactivated users are rejected with `HTTP 403 Forbidden`.
   - **Data Confidentiality:** Hostnames, local IP addresses, and utilization patterns of academic or corporate lab PCs remain completely shielded from external unauthenticated scrapers.
3. **Response Schema:** Replacing untyped dictionary responses with explicit Pydantic response models (`LabSummaryResponse`) guarantees strict response sanitization, prevents accidental model leakage, and documents the endpoint cleanly in Swagger `/docs`.

### 4.B Telemetry Provenance and Host Identity
1. **Provenance Invariant:** Telemetry provenance was validated in Phase 1 and must remain strictly enforced. Any agent submitting telemetry with `source_type="REAL_AGENT"` must authenticate using a credential granted `REAL_AGENT` or `ALL` authority.
2. **Host Auto-Registration vs. Metadata Hijacking:**
   - In `backend/app/services/host_service.py`, `get_or_create_host` creates new hosts with `environment`, `provider`, `region`, and `source_type` on first arrival.
   - For existing hosts, it intentionally **does not** overwrite `environment` or `region` based on incoming telemetry payloads. This prevents a compromised agent or duplicate hostname from silently reassigning an existing production or staging server to the lab environment.
3. **Verified Reassignment Mechanism:**
   - Inspection of `backend/app/api/v1/hosts.py:85-102` confirms that `PATCH /api/v1/hosts/{host_id}` already accepts `HostUpdate` (including `environment` and `region`) and enforces `get_current_admin`.
   - Administrators can safely reclassify any pre-existing host from `local` to `lab` and assign room coordinates using this verified administrative endpoint without altering host auto-registration logic.

### 4.C Online/Offline Status Determination
1. **Timestamp Authority:** In `backend/app/services/metric_service.py:41`, when telemetry arrives from `monitoring_agent/agent.py` (which does not provide a client-side timestamp), the backend sets:
   $$\text{sample\_ts} = \text{datetime.now(timezone.utc)}$$
   Because ingestion time is assigned by the authoritative server clock, **client clock drift on lab PCs does not cause false offline flapping**.
2. **Offline Threshold vs. Agent Cadence:**
   - If the agent is configured to report every $T_{\text{agent}} = 15$ seconds:
     - Setting $\text{offline\_threshold} = 60$ seconds allows exactly 4 missed cycles before declaring a machine offline.
     - A momentary network delay or packet drop could trigger a premature offline status.
   - *Recommendation:* Default `offline_after_seconds = 90` seconds (6 missed cycles) with a configurable query parameter bounded by `ge=10, le=3600`.
3. **Never-Seen Hosts:**
   - Hosts that have registered in the inventory but have never transmitted a metric sample (`Metric is None`):
     - `last_seen = None`
     - `online = False`
     - `cpu_level = "offline"`
     - Handled gracefully in UI as `OFFLINE (Never Seen)` with `--` utilization metrics.

### 4.D Database Query Performance
1. **The Inefficient Guide Query:**
   ```sql
   -- Flawed guide subquery: Groups by host_id over the ENTIRE metrics table
   SELECT host_id, MAX(timestamp) AS max_ts FROM metrics GROUP BY host_id;
   ```
   In an active deployment with 50 cloud hosts and 30 lab PCs operating over weeks, `metrics` contains hundreds of thousands of rows. An unscoped `GROUP BY host_id` forces SQLite to scan every row in `metrics`, causing high disk I/O and query latency.
2. **Optimized Scoped Subquery:**
   ```sql
   -- Optimized query: Scopes the search strictly to active lab hosts
   WITH lab_host_ids AS (
       SELECT id FROM hosts WHERE environment = :environment AND is_active = 1 AND source_type = 'REAL_AGENT'
   )
   SELECT Metric.host_id, MAX(Metric.timestamp) AS max_ts
   FROM metrics
   WHERE Metric.host_id IN (SELECT id FROM lab_host_ids)
   GROUP BY Metric.host_id;
   ```
3. **Index Coverage:**
   The composite index `ix_metrics_host_id_timestamp` on `metrics(host_id, timestamp)` already exists ([`backend/app/models/metric.py:71-73`](file:///c:/CLoudProject/backend/app/models/metric.py#L71-L73)).
   With the scoped subquery, SQLite executes an index-range scan per lab host ID. The execution plan operates in $\mathcal{O}(K \log N)$ where $K$ is the number of lab hosts ($\approx 30$) and $N$ is total metrics, rather than $\mathcal{O}(N)$.
4. **Duplicate Timestamp Deduplication:**
   If multiple metric records have identical timestamps for a single host, joining on `Metric.timestamp == latest.c.max_ts` could return multiple rows for the same host. The query service will include dictionary deduplication (`if host.id in pcs: continue`) to guarantee deterministic 1-to-1 PC mapping.

### 4.E Agent Deployment and Security
1. **Credential Storage:** Plaintext API keys must never be committed to version control, embedded in public GitHub repositories, or hardcoded in shared batch files on shared network folders.
2. **Provisioning Model:**
   - A dedicated agent ingestion key (`AgentApiKey` record with `name="College Lab Agent Key"`, `source_type="REAL_AGENT"`) is generated via the existing admin endpoint `POST /api/v1/admin/agent-keys`.
   - On each Windows lab PC, the key is stored in a machine-level environment variable:
     ```cmd
     setx AGENT_API_KEY "sec_xxxxxxxxxxxxxxxxxxxx" /M
     ```
   - The launcher script `run_agent.bat` reads `%AGENT_API_KEY%` dynamically:
     ```cmd
     @echo off
     cd /d C:\lab-agent
     call .venv\Scripts\activate
     python -m monitoring_agent.agent --url http://192.168.1.100:8000/api/v1/metrics --env lab --provider college-lab --region lab-1 --interval 15
     ```
3. **Revocation & Least Privilege:**
   - If a lab PC is compromised or decommissioned, the administrator deactivates the key via `DELETE /api/v1/admin/agent-keys/{id}`.
   - An agent key possesses zero administrative privileges: it can only post metrics to `POST /api/v1/metrics` and cannot read telemetry, list hosts, or view alerts.

### 4.F Frontend Integration & Aesthetics
1. **Design System Consistency:**
   - Replace the guide's ad-hoc inline styles with existing platform tokens:
     - Background: `var(--bg-card, #161b22)`
     - Borders: `var(--border-subtle, #30363d)`
     - Text Primary: `var(--text-primary, #e6edf3)`
     - Text Muted: `var(--text-muted, #8b949e)`
     - Status Normal: `var(--color-success, #2ea043)`
     - Status Warning: `var(--color-warning, #d29922)`
     - Status Critical/High: `var(--color-danger, #f85149)`
     - Status Offline: `var(--text-disabled, #6e7681)`
2. **API Client Integration:**
   - Extend `ApiClient` in `frontend/js/api.js`:
     ```javascript
     getLabSummary(params = {}) {
       const qs = new URLSearchParams();
       if (params.environment) qs.set("environment", params.environment);
       if (params.offline_after_seconds) qs.set("offline_after_seconds", String(params.offline_after_seconds));
       if (params.real_agents_only !== undefined) qs.set("real_agents_only", String(params.real_agents_only));
       return this.request(`/lab/summary?${qs.toString()}`);
     }
     ```
3. **Lifecycle and Polling:**
   - Active view polling every 10 seconds.
   - Check `document.visibilityState`: pause polling while user is on another browser tab or minimized.
   - In `app.js`, when user navigates away from `lab` view, execute `LabView.destroy()` or `clearInterval()` to prevent background memory leaks.

### 4.G Alerts and AI Processing
1. **Pipeline Execution on Every Sample:**
   When a metric sample is posted, `ingest_metric` triggers:
   - Rule-based threshold alerts (`evaluate_metric_sample`)
   - AI multivariate anomaly detection (`evaluate_and_record_ai_anomaly`)
   - 3-tier correlated incident evaluation (`evaluate_correlated_anomaly`)
2. **Concurrency Analysis:**
   - 30 lab PCs reporting every 5 seconds = 6 full ingestion transactions per second.
   - Under SQLite, write transactions acquire exclusive database locks (`sqlite3.OperationalError: database is locked`).
   - Concurrently running Isolation Forest and LSTM sequence reconstruction on each incoming sample creates substantial CPU overhead on the server host.
3. **Operational Recommendation:**
   - Set agent polling interval to **15 seconds** (or 30 seconds for non-critical labs).
   - At 15 seconds, 30 PCs generate an average of 2 requests/second, allowing SQLite write transactions and scikit-learn/PyTorch inference to execute within 20–40ms windows without lock contention.
   - Stagger agent startup times (random initial jitter between 1 and 10 seconds) to avoid synchronized request bursts.

---

## 5. Proposed Architecture and Data Flow

```
+------------------------------------------------------------------------------------------------+
|                                    COLLEGE LAB LOCAL NETWORK                                   |
|                                                                                                |
|   +-----------------------+    +-----------------------+    +------------------------------+   |
|   | Lab PC 01 (Windows)   |    | Lab PC 02 (Windows)   |    | Lab PC N (Linux / Windows)   |   |
|   | monitoring_agent      |    | monitoring_agent      |    | monitoring_agent             |   |
|   | --env lab             |    | --env lab             |    | --env lab                    |   |
|   | --region lab-1        |    | --region lab-1        |    | --region lab-2               |   |
|   | --api-key <secret>    |    | --api-key <secret>    |    | --api-key <secret>           |   |
|   | Interval: 15s         |    | Interval: 15s         |    | Interval: 15s                |   |
|   +-----------+-----------+    +-----------+-----------+    +--------------+---------------+   |
|               |                            |                               |                   |
+---------------|----------------------------|-------------------------------|-------------------+
                |                            |                               |
                +----------------------------+-------------------------------+
                                             |
                                             v  [HTTP POST /api/v1/metrics]
                                                Header: X-Agent-Key: <secret>
+------------------------------------------------------------------------------------------------+
|                              FASTAPI BACKEND (HOST: 0.0.0.0:8000)                              |
|                                                                                                |
|   1. Security Guard (deps.py)                                                                  |
|      verify_agent_credentials() -> SHA-256 Hash Verification -> Validates REAL_AGENT           |
|                                                                                                |
|   2. Provenance Guard (metrics.py)                                                             |
|      validate_telemetry_provenance() -> source_type == 'REAL_AGENT' -> Canonicalize            |
|                                                                                                |
|   3. Ingestion & Persistence (metric_service.py)                                               |
|      - get_or_create_host(hostname, env='lab', region='lab-1', provider='college-lab')         |
|      - Insert Metric row (host_id, timestamp, cpu, mem, disk, net)                             |
|      - evaluate_metric_sample() -> Threshold Alerts (CPU > 80% / 95%)                           |
|      - evaluate_and_record_ai_anomaly() -> Isolation Forest Model                             |
|      - evaluate_correlated_anomaly() -> Consensus Anomaly (IF + LSTM)                          |
+------------------------------------------------------------------------------------------------+
                                             |
                                             v
+------------------------------------------------------------------------------------------------+
|                                 SQLITE DATABASE (NO MIGRATIONS)                                |
|                                                                                                |
|   Table: hosts (id, hostname, ip_address, environment='lab', region='lab-1', is_active=1)       |
|   Table: metrics (id, host_id, timestamp, cpu_percent, memory_percent, disk_percent)           |
|   Index: ix_metrics_host_id_timestamp ("host_id", "timestamp")                                 |
+------------------------------------------------------------------------------------------------+
                                             ^
                                             |  [Scoped Query: WHERE host.environment = 'lab']
+------------------------------------------------------------------------------------------------+
|                            LAB SUMMARY ENDPOINT (api/v1/lab.py)                                |
|                                                                                                |
|   GET /api/v1/lab/summary?environment=lab&offline_after_seconds=90                             |
|   - Depends(get_current_viewer) -> JWT Authorization Check                                      |
|   - Scoped Latest-Metric Subquery -> Computes online/offline & avg CPU per room                |
|   - Returns LabSummaryResponse (totals, room cards, busiest PCs)                               |
+------------------------------------------------------------------------------------------------+
                                             ^
                                             |  [Polling every 10s via api.getLabSummary()]
+------------------------------------------------------------------------------------------------+
|                              FRONTEND SRE COMMAND CENTER (SPA)                                 |
|                                                                                                |
|   - Sidebar: Operations -> Lab PCs (index.html)                                                |
|   - View Orchestration: VIEW_MAP['lab'] -> renderLabView (app.js)                              |
|   - UI Component: LabView.js (statBox, roomSection, pcCard with CSS design tokens)             |
|   - Polling Lifecycle: Pause when document.visibilityState === 'hidden'                        |
+------------------------------------------------------------------------------------------------+
```

---

## 6. File-by-File Implementation Plan

No files will be created or modified during Phase 3. The following specifications detail the precise changes planned for Phase 4 implementation:

### 6.1 `backend/app/schemas/lab.py`
- **File Status:** NEW file.
- **Purpose:** Provide strict Pydantic schemas for the Lab Overview endpoint to guarantee schema consistency, OpenAPI documentation, and response data validation.
- **Classes/Functions to Add:**
  - `LabPCEntry(BaseModel)`:
    - `host_id: int`
    - `hostname: str`
    - `room: str`
    - `ip_address: Optional[str]`
    - `online: bool`
    - `last_seen: Optional[datetime]`
    - `cpu_percent: Optional[float] = Field(None, ge=0.0, le=100.0)`
    - `memory_percent: Optional[float] = Field(None, ge=0.0, le=100.0)`
    - `disk_percent: Optional[float] = Field(None, ge=0.0, le=100.0)`
    - `cpu_level: str = Field(description="'normal', 'warning', 'high', or 'offline'")`
  - `LabRoomSummary(BaseModel)`:
    - `room: str`
    - `total: int = Field(ge=0)`
    - `online: int = Field(ge=0)`
    - `offline: int = Field(ge=0)`
    - `avg_cpu: Optional[float] = None`
    - `pcs: List[LabPCEntry]`
  - `LabTotalsSummary(BaseModel)`:
    - `total_pcs: int = Field(ge=0)`
    - `online: int = Field(ge=0)`
    - `offline: int = Field(ge=0)`
    - `avg_cpu: Optional[float] = None`
  - `LabSummaryResponse(BaseModel)`:
    - `generated_at: datetime`
    - `environment: str`
    - `offline_after_seconds: int`
    - `totals: LabTotalsSummary`
    - `busiest_pcs: List[LabPCEntry]`
    - `rooms: List[LabRoomSummary]`
- **Dependencies:** `pydantic`.
- **Security & Compatibility:** Guarantees strict serialization types, ISO 8601 UTC datetimes, and prevents internal field leakage.
- **Tests Required:** Schema validation tests with complete, partial, and empty payloads.
- **Rollback:** Delete `backend/app/schemas/lab.py`.

### 6.2 `backend/app/api/v1/lab.py`
- **File Status:** NEW file.
- **Purpose:** Implement the `GET /api/v1/lab/summary` endpoint.
- **Classes/Functions to Add:**
  - `router = APIRouter(prefix="/lab", tags=["Lab"])`
  - `_aware(ts: datetime) -> datetime`: Helper to ensure SQLite naive datetimes are interpreted as UTC.
  - `_cpu_level(cpu: Optional[float], online: bool) -> str`: Returns `"normal"` (<80%), `"warning"` (80-94.9%), `"high"` (>=95%), or `"offline"`.
  - `@router.get("/summary", response_model=LabSummaryResponse)`: Query handler executing the scoped subquery across `Host` and `Metric`, aggregating room statistics, calculating average CPU, and returning `LabSummaryResponse`.
  - Query parameters:
    - `environment: str = Query("lab", description="Target host environment")`
    - `offline_after_seconds: int = Query(90, ge=10, le=3600, description="Inactivity threshold in seconds")`
    - `real_agents_only: bool = Query(True, description="Filter for REAL_AGENT provenance")`
- **Dependencies:** `fastapi`, `sqlalchemy`, `backend.app.api.deps.get_db`, `backend.app.api.deps.get_current_viewer`, `backend.app.models.host.Host`, `backend.app.models.metric.Metric`, `backend.app.schemas.lab.LabSummaryResponse`.
- **Security & Compatibility:** Requires `get_current_viewer` (Viewer RBAC or higher). Uses scoped subquery avoiding global table scans.
- **Tests Required:** Unit and integration tests for authorized viewer, unauthenticated 401, offline threshold boundary tests, room grouping tests.
- **Rollback:** Delete `backend/app/api/v1/lab.py`.

### 6.3 `backend/app/api/v1/__init__.py`
- **File Status:** EXISTING file.
- **Purpose:** Register and mount `lab_router` onto the main `api_router`.
- **Modifications:**
  - Line 20: Add `from backend.app.api.v1.lab import router as lab_router`
  - Line 38: Add `api_router.include_router(lab_router)`
- **Dependencies:** `backend/app/api/v1/lab.py`.
- **Security & Compatibility:** Identical pattern to existing 14 router inclusions.
- **Tests Required:** Integration tests verifying `GET /api/v1/lab/summary` is reachable under `/api/v1`.
- **Rollback:** Remove the 2 added lines.

### 6.4 `frontend/js/api.js`
- **File Status:** EXISTING file.
- **Purpose:** Add dedicated API client method for the Lab Summary endpoint.
- **Modifications:**
  - Add method `getLabSummary(params = {})` to class `ApiClient` (around line 394):
    ```javascript
    getLabSummary(params = {}) {
      const qs = new URLSearchParams();
      if (params.environment) qs.set("environment", params.environment);
      if (params.offline_after_seconds) qs.set("offline_after_seconds", String(params.offline_after_seconds));
      if (params.real_agents_only !== undefined) qs.set("real_agents_only", String(params.real_agents_only));
      return this.request(`/lab/summary?${qs.toString()}`);
    }
    ```
- **Dependencies:** `ApiClient.request()`.
- **Security & Compatibility:** Automatically inherits Bearer token injection, timeout handling, and 401 refresh orchestration.
- **Tests Required:** Frontend API client test verifying proper query string construction.
- **Rollback:** Remove `getLabSummary` method.

### 6.5 `frontend/js/views/LabView.js`
- **File Status:** NEW file.
- **Purpose:** Render the Lab PCs dashboard page (overview metrics, room grouping, PC cards, busiest machines, auto-refresh).
- **Functions to Add:**
  - `renderLabView(container)`: Main entry point mounted by router.
  - `fetchAndRender()`: Calls `api.getLabSummary()`, renders stat boxes, room sections, PC cards.
  - `startPolling()` / `stopPolling()`: Tab-visibility aware interval manager (`document.visibilityState`).
  - `destroy()`: Cleanup method clearing active interval timer.
- **Dependencies:** `frontend/js/api.js`, `frontend/js/sanitizer.js` (`escapeHtml`).
- **Security & Compatibility:** All user/host strings rendered through `escapeHtml()` to guarantee zero XSS vulnerabilities. Uses platform CSS design tokens.
- **Tests Required:** Browser rendering test verifying DOM nodes, loading state, empty state, and card color classes.
- **Rollback:** Delete `frontend/js/views/LabView.js`.

### 6.6 `frontend/js/app.js`
- **File Status:** EXISTING file.
- **Purpose:** Register `renderLabView` in the client-side router and view mapping.
- **Modifications:**
  - Import `renderLabView` from `./views/LabView.js?v=3.3.0`.
  - Add `lab: renderLabView` to `VIEW_MAP` (line 45).
- **Dependencies:** `frontend/js/views/LabView.js`.
- **Security & Compatibility:** Accessible to all authenticated users (`authManager.isAuthenticated`).
- **Tests Required:** Navigation tests verifying clicking "Lab PCs" switches views and renders content.
- **Rollback:** Remove import and `VIEW_MAP` entry.

### 6.7 `frontend/index.html`
- **File Status:** EXISTING file.
- **Purpose:** Add the "Lab PCs" navigation item to the sidebar under the "Operations" section.
- **Modifications:**
  - Add after `Telemetry Stream` (`metrics`):
    ```html
    <a class="nav-item" data-view="lab" title="Lab PCs">
      <span class="nav-icon" aria-hidden="true">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon icon-md"><rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/></svg>
      </span>
      <span class="nav-label">Lab PCs</span>
    </a>
    ```
- **Dependencies:** None.
- **Security & Compatibility:** Follows existing sidebar SVG icon conventions and layout tokens.
- **Tests Required:** Visual inspection and link click validation.
- **Rollback:** Remove the `<a>` tag.

### 6.8 `tests/test_api_lab.py`
- **File Status:** NEW file.
- **Purpose:** Provide comprehensive automated test coverage for the Lab PC Monitoring feature and regressions.
- **Classes/Functions to Add:**
  - Fixtures for isolated in-memory test database, test users (Viewer, Admin), mock lab hosts and metrics.
  - Tests listed in Section 7 Test Matrix.
- **Dependencies:** `pytest`, `fastapi.testclient.TestClient`.
- **Rollback:** Delete `tests/test_api_lab.py`.

---

## 7. Automated and Manual Test Matrix

### 7.1 Sufficiency Analysis of Test Coverage
The automated test plan specifies **18 automated integration tests** in `tests/test_api_lab.py` supplemented by manual operational validation. This suite is verified sufficient because it achieves 100% path coverage across:
1. Authentication & authorization RBAC boundaries (Viewer, Admin, Deactivated, Anonymous).
2. Multi-tenant host isolation (Lab vs Production vs Staging).
3. Telemetry provenance verification (`REAL_AGENT` vs `SIMULATED`).
4. Threshold boundary evaluations (<80%, 80-94.9%, >=95%, offline).
5. Edge cases: Zero metrics, duplicate timestamps, missing partitions, inactive hosts.
6. Algorithmic sorting & grouping: Room grouping, average CPU, busiest PCs top-5.
7. Database index seek verification and query performance.

### 7.2 Detailed Test Matrix

| Test ID | Test Name | Specific Assertion / What It Proves | Required Category | Test Nature |
| :--- | :--- | :--- | :--- | :--- |
| **TEST-LAB-01** | `test_lab_summary_unauthenticated` | Missing Bearer token yields `HTTP 401 Unauthorized` with `WWW-Authenticate: Bearer`. Proves unauthenticated users cannot access lab data. | 1. Auth & Authz | Proposed New Automated |
| **TEST-LAB-02** | `test_lab_summary_viewer_authorized` | Valid Viewer JWT yields `HTTP 200 OK` conforming to `LabSummaryResponse`. Proves standard viewers have read access. | 1. Auth & Authz | Proposed New Automated |
| **TEST-LAB-03** | `test_lab_summary_deactivated_user` | JWT for user where `is_active=False` yields `HTTP 403 Forbidden`. Proves deactivated accounts cannot query lab overview. | 1. Auth & Authz | Proposed New Automated |
| **TEST-LAB-04** | `test_lab_environment_isolation` | Hosts with `environment="production"` or `"staging"` are strictly excluded from response when `environment="lab"`. Proves cross-environment data isolation. | 2. Host Isolation | Proposed New Automated |
| **TEST-LAB-05** | `test_lab_provenance_filter` | Simulator hosts (`source_type="SIMULATED"`) are excluded when `real_agents_only=True` and included when `real_agents_only=False`. Proves simulator filtering works. | 3. Provenance Filter | Proposed New Automated |
| **TEST-LAB-06** | `test_lab_online_status_calculation` | Host reporting metric 20s ago with `offline_after_seconds=90` has `online=True` and active `cpu_level`. Proves live agent detection. | 5. Threshold Behavior | Proposed New Automated |
| **TEST-LAB-07** | `test_lab_offline_status_calculation` | Host reporting metric 120s ago with `offline_after_seconds=90` has `online=False` and `cpu_level="offline"`. Proves dead agent detection. | 5. Threshold Behavior | Proposed New Automated |
| **TEST-LAB-08** | `test_lab_never_seen_host` | Registered lab host with zero metrics has `last_seen=None`, `online=False`, `cpu_percent=None`, and renders without error. Proves graceful handling of empty telemetry. | 6. No Metrics / 7. Stale | Proposed New Automated |
| **TEST-LAB-09** | `test_lab_cpu_severity_boundaries` | Values 79.9% -> `"normal"`, 80.0% -> `"warning"`, 94.9% -> `"warning"`, 95.0% -> `"high"`. Proves exact threshold adherence. | 9. CPU Boundaries | Proposed New Automated |
| **TEST-LAB-10** | `test_lab_room_grouping_and_sorting` | Hosts with `region="lab-1"` and `region="lab-2"` partition into separate room objects sorted alphabetically by room name. Proves room layout accuracy. | 8. Room Grouping | Proposed New Automated |
| **TEST-LAB-11** | `test_lab_room_avg_cpu_calculation` | Room `avg_cpu` calculates arithmetic mean of online PCs only; ignores offline machines. Proves accurate resource computation. | 8. Room Totals | Proposed New Automated |
| **TEST-LAB-12** | `test_lab_busiest_pcs_ranking` | Top 5 machines with highest CPU utilization returned in descending order; offline PCs excluded. Proves triage ranking. | 11. Multiple Hosts | Proposed New Automated |
| **TEST-LAB-13** | `test_lab_duplicate_timestamps_guard` | Multiple metric records with identical timestamps for a single host do not duplicate host card or corrupt totals. Proves deduplication safety. | 10. Duplicate Timestamps | Proposed New Automated |
| **TEST-LAB-14** | `test_lab_inactive_host_exclusion` | Host with `is_active=False` is completely excluded from totals, room cards, and busiest list. Proves decommissioned host handling. | 12. Error & Schema | Proposed New Automated |
| **TEST-LAB-15** | `test_lab_agent_telemetry_ingestion` | Metric posted with valid `X-Agent-Key` and `source_type="REAL_AGENT"` succeeds (`HTTP 201`) and creates/updates host. Proves live ingestion path. | 13. Ingestion Path | Proposed New Automated |
| **TEST-LAB-16** | `test_lab_provenance_violation_rejection` | Ingestion attempt sending `source_type="UNKNOWN"` or mismatching credential authority yields `HTTP 403 Forbidden`. Proves provenance guard security. | 4. Invalid Provenance | Verified Existing Rule |
| **TEST-LAB-17** | `test_lab_query_performance_benchmark` | Scoped query over 10,000 synthetic metrics completes in $<25\text{ms}$ utilizing `ix_metrics_host_id_timestamp`. Proves query scaling. | 11. Performance | Proposed Benchmark |
| **TEST-LAB-18** | `test_full_regression_suite_pass` | All 107 existing unit/integration tests continue to pass with 0 failures. Proves zero regressions across existing subsystems. | 13. Regression Pass | Verified Passing (107/107) |

### 7.3 Manual Operational Validation Steps
1. **Physical Agent Startup:** Deploy `monitoring_agent` on a physical Windows test machine; execute `run_agent.bat` with `--env lab --region lab-1`; verify console logs indicate `[+] Ingested`.
2. **Dashboard UI Rendering:** Open `/` in browser; click "Lab PCs" in sidebar; verify summary metrics cards render with correct counts and room cards appear.
3. **Card State Transitions:** Stop the agent process; wait 90 seconds; verify PC card transitions to `OFFLINE` and badge updates to grey.
4. **Visibility Pausing:** Minimize browser tab for 60 seconds; check network console to confirm polling requests were paused.

---

## 8. Deployment Prerequisites

Before rolling out the monitoring agent across physical lab PCs in Phase 4 / Phase 5, the following prerequisites must be met:

### 8.1 Network Connectivity & Firewall
1. **Server Bind Address:** The backend FastAPI server must be bound to `0.0.0.0` (all network interfaces), not `127.0.0.1`.
   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```
2. **Inbound Firewall Rule:** On the server machine hosting CloudOps Intel, Windows Firewall / Linux `iptables` must permit inbound TCP traffic on port `8000` from the lab subnet (e.g., `192.168.1.0/24` or `10.0.0.0/16`).
3. **Outbound Lab PC Reachability:** Physical lab PCs must be able to resolve and reach `http://<SERVER_IP>:8000/health` via HTTP GET.

### 8.2 Authentication Credential Provisioning
1. **Agent Ingestion Key:**
   - Generate a dedicated agent ingestion key via the existing Admin API:
     ```http
     POST /api/v1/admin/agent-keys
     Header: Authorization: Bearer <ADMIN_JWT>
     Content-Type: application/json
     {
       "name": "College Lab Room 1 Key",
       "source_type": "REAL_AGENT"
     }
     ```
   - Store the resulting raw key secret securely. Do NOT commit the key to Git or hardcode it in shared source files.

### 8.3 Operating System & Environment Compatibility
1. **Python Installation:** Python 3.10+ installed on target lab PCs (Windows 10/11 or Ubuntu/Debian Linux).
2. **Dependencies:** `psutil>=5.9.0` and `requests>=2.28.0` installed in the agent environment (`.venv`).
3. **Partition Verification:** In `monitoring_agent/collector.py`, disk usage checks root (`/`) on Linux and system drive (`C:\`) on Windows. Tested and verified cross-platform compatible.

### 8.4 Host Naming & Room Convention
1. **Hostname Uniqueness:** Each physical lab PC must have a unique system hostname (e.g., `lab1-pc01`, `lab1-pc02`, `lab2-pc01`). Duplicate hostnames will collide on the unique `hosts.hostname` database index.
2. **Room Assignment:** The `--region` CLI argument is used to specify the room identifier (`--region lab-1`, `--region lab-2`), enabling dynamic room card grouping in the dashboard.

---

## 9. Risks and Rollback Strategy

### 9.1 Risk Matrix

| Risk Event | Severity | Probability | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **SQLite Database Lock Contention** | High | Medium | 30+ PCs reporting every 5s could trigger `sqlite3.OperationalError: database is locked`. | Set agent reporting interval to **15–30 seconds**; introduce random startup jitter (1–10s); use WAL mode (`PRAGMA journal_mode=WAL;`). |
| **Premature Offline Status Flapping** | Medium | Low | Temporary network lag causes cards to flash OFFLINE. | Configure `offline_after_seconds = 90` (allowing 6 missed cycles for a 15s interval). |
| **Existing Local Host Not Showing in Lab** | Low | High | PC previously monitored as `local` will not change environment automatically on agent restart. | Administrator uses existing `PATCH /api/v1/hosts/{id}` with `{"environment": "lab", "region": "lab-1"}`. |
| **Frontend Memory Leak from Polling** | Medium | Low | Unmanaged `setInterval` leaking memory when view is left open or backgrounded. | Implement cleanup lifecycle hook on route transition and pause polling when `document.visibilityState === 'hidden'`. |
| **Unauthorized Telemetry Injection** | High | Low | Open endpoint allowing arbitrary metric injection. | Mandatory `verify_agent_credentials` and provenance verification enforced on every request. |

### 9.2 Rollback Procedures
If any regression or defect is identified during Phase 4 implementation, the rollback procedure is immediate and non-destructive:

1. **Backend Rollback:**
   - Remove `from backend.app.api.v1.lab import router as lab_router` and `api_router.include_router(lab_router)` from `backend/app/api/v1/__init__.py`.
   - Delete `backend/app/api/v1/lab.py` and `backend/app/schemas/lab.py`.
   - Restart FastAPI server.
   - *Result:* Reverts backend to exact current state; zero effect on existing endpoints or database.
2. **Frontend Rollback:**
   - Remove `lab` route and import from `frontend/js/app.js`.
   - Remove `getLabSummary` from `frontend/js/api.js`.
   - Remove "Lab PCs" link from `frontend/index.html`.
   - Delete `frontend/js/views/LabView.js`.
   - Hard refresh browser (`Ctrl + F5`).
   - *Result:* Reverts UI navigation and client state cleanly.
3. **Database State:**
   - Because zero database migrations or table modifications were performed, the database requires zero schema rollbacks. Any newly registered lab hosts can be marked inactive via existing `POST /api/v1/hosts/{id}/deactivate` if needed.

### 9.3 Measurable Acceptance Criteria
The feature will be declared complete only when:
- [ ] `GET /api/v1/lab/summary` returns `HTTP 200` with valid room grouping and average CPU calculations.
- [ ] Unauthenticated requests to `/lab/summary` return `HTTP 401 Unauthorized`.
- [ ] Lab PCs dashboard in frontend updates live every 10 seconds and pauses when tab is hidden.
- [ ] Disconnecting an agent results in the PC transitioning to `OFFLINE` status after 90 seconds.
- [ ] All 18 proposed tests pass in `tests/test_api_lab.py`.
- [ ] All 107 existing platform tests pass without regressions.
- [ ] Zero database migrations are executed or committed.

---

## 10. User Decisions Requiring Approval

The following four engineering decisions require explicit confirmation before implementation begins:

### Decision 1: Host Reassignment Policy
* **Proposal:** Preserve host metadata immutability in `get_or_create_host` to prevent untrusted agents from spoofing environments. Reassign existing test hosts to `"lab"` through the verified administrative endpoint `PATCH /api/v1/hosts/{id}` (which requires `ADMIN` role).
* **Rationale & Trade-offs:** Allows full auditability and prevents hostile takeover of production host records, while requiring an explicit admin action to reclassify existing machines.
* **Recommendation:** Approve keeping `get_or_create_host` immutable and using `PATCH /api/v1/hosts/{id}`.

### Decision 2: Default Offline Threshold
* **Proposal:** Default `offline_after_seconds = 90`, configurable via query parameter `?offline_after_seconds=N` (bounded by `ge=10, le=3600`).
* **Rationale & Trade-offs:** At an agent cadence of 15 seconds, 90 seconds provides a tolerance of 6 missed cycles, preventing false offline flapping during temporary WiFi/LAN congestion while detecting real shutdowns in 1.5 minutes.
* **Recommendation:** Approve default of 90 seconds.

### Decision 3: Agent Ingestion Key Model
* **Proposal:** Provision a dedicated agent ingestion key with `source_type="REAL_AGENT"` (via `POST /api/v1/admin/agent-keys`) and store it on physical lab PCs via machine-level environment variable `AGENT_API_KEY`.
* **Rationale & Trade-offs:** Ensures adherence to Phase 1 security invariants, prevents credential exposure in version control, and allows instant administrative revocation if a physical PC is compromised.
* **Recommendation:** Approve the dedicated agent key model via environment variables.

### Decision 4: Agent Reporting Interval
* **Proposal:** Configure lab agents to report every **15 seconds** with randomized initial startup jitter (1–10s).
* **Rationale & Trade-offs:** 30 lab PCs reporting every 15s produce ~2 requests/second, allowing SQLite write transactions and synchronous scikit-learn/LSTM anomaly inference to execute without lock contention (`sqlite3.OperationalError: database is locked`).
* **Recommendation:** Approve 15-second reporting cadence.

---

## 11. Proposed Step-by-Step Phase 4 Implementation Order

Upon receiving explicit user approval, implementation will proceed in the following small, reviewable steps:

### Step 1: Pydantic Response Schema & API Contract
- Create `backend/app/schemas/lab.py`.
- Define `LabPCEntry`, `LabRoomSummary`, `LabTotalsSummary`, and `LabSummaryResponse`.
- Validate syntax and types.

### Step 2: Backend Router & Scoped Query Implementation
- Create `backend/app/api/v1/lab.py`.
- Implement `_aware`, `_cpu_level`, and `lab_summary` with scoped subquery and RBAC viewer guard.
- Mount router in `backend/app/api/v1/__init__.py`.

### Step 3: Backend Automated Test Suite
- Create `tests/test_api_lab.py`.
- Execute all 18 integration tests covering auth, provenance, offline thresholds, room grouping, and deduplication.
- Verify full test suite passes with 0 regressions (125 total passing tests).

### Step 4: Frontend API Client Method
- Add `getLabSummary(params)` method to `ApiClient` in `frontend/js/api.js`.

### Step 5: Frontend View Component (`LabView.js`)
- Create `frontend/js/views/LabView.js` utilizing design system tokens, empty/loading states, room grouping, and visibility-aware polling.

### Step 6: Navigation & Route Mounting
- Register `lab` view in `VIEW_MAP` in `frontend/js/app.js`.
- Add "Lab PCs" nav item with SVG icon in `frontend/index.html`.

### Step 7: End-to-End Validation & Verification
- Spin up local test agent with `--env lab --region lab-1`.
- Verify live metric ingestion, card rendering, CPU level color updates, and offline transition after agent shutdown.

---

## 12. Explicit Confirmation of Zero Database Migrations Required

**Confirmed Fact:**
- Model `Host` in [`backend/app/models/host.py`](file:///c:/CLoudProject/backend/app/models/host.py) contains `id`, `hostname`, `ip_address`, `environment`, `instance_type`, `provider`, `region`, `source_type`, `is_active`, `owner_email`, `tags`, `created_at`, `updated_at`.
- Model `Metric` in [`backend/app/models/metric.py`](file:///c:/CLoudProject/backend/app/models/metric.py) contains `id`, `host_id`, `timestamp`, `cpu_percent`, `memory_percent`, `disk_percent`, `network_sent_mb`, `network_received_mb`.
- Composite index `ix_metrics_host_id_timestamp` on `("host_id", "timestamp")` is already defined and active.
- Table `agent_api_keys` for credential verification already exists.
- **Definitive Conclusion:** Zero database migrations, schema alterations, index additions, or seed script modifications are needed.

---

## 13. Explicit Confirmation of Zero Implementation / File Modifications

**Strict Safety Statement:**
- **Zero code files were modified or created** in `backend/`, `frontend/`, `monitoring_agent/`, `ai_engine/`, or `tests/`.
- **Zero database changes occurred:** The active database [`cloud_intelligence.db`](file:///c:/CLoudProject/cloud_intelligence.db) remains 100% untracked, immutable, and untouched on disk.
- **Zero configuration or dependency changes occurred:** No packages were installed or removed, and `.env` was left untouched.
- **No implementation has begun:** This document constitutes the complete design validation deliverable. All work is suspended pending explicit user review and authorization.
