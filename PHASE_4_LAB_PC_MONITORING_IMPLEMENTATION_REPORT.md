# Phase 4 — Lab PC Monitoring Implementation Report

**Project:** CloudOps Intel — Cloud Intelligence Platform & SRE Command Center  
**Document Version:** 1.0.0  
**Status:** Implementation & Validation Complete (Ready for Staging Review)  
**Execution Verification:** 125 Tests Executed — 125 Passed, 0 Failed, 0 Regressions  

---

## 1. Executive Summary

Phase 4 of the **Lab PC Monitoring** feature has been implemented, validated, and verified across the backend API, frontend dashboard, and automated test suite. 

The implementation enables real-time tracking of physical computer workstations (such as academic computer labs and enterprise test benches) grouped dynamically by room coordinates. It provides automated online/offline state determination based on configurable heartbeats, live hardware resource tracking (CPU, memory, storage), busiest-machine saturation triage, and full integration into the platform's multi-tier alerting and AI anomaly detection engines.

All four Phase 3 engineering decisions were strictly followed:
1. **Preserved host metadata immutability** in `get_or_create_host` to prevent hostile environment spoofing; verified administrative reclassification via `PATCH /api/v1/hosts/{id}`.
2. **Implemented default offline threshold of 90 seconds** (`offline_after_seconds=90`), configurable from 10 to 3600 seconds.
3. **Preserved telemetry provenance enforcement** (`source_type="REAL_AGENT"`) and mandatory `verify_agent_credentials` authentication.
4. **Optimized query performance** via scoped index seeks on composite index `ix_metrics_host_id_timestamp ("host_id", "timestamp")`, validated at a median latency of 8.8 ms over 25,000 time-series records.

---

## 2. Inventory of Changes

### 2.1 Files Created
1. **`backend/app/schemas/lab.py`**: Strict Pydantic response models:
   - `LabPCEntry`: Individual workstation telemetry snapshot, status, and CPU level.
   - `LabRoomSummary`: Room-level PC list, online/offline count, and room average CPU load.
   - `LabTotalsSummary`: Fleet totals (total PCs, online, offline, fleet average CPU).
   - `LabSummaryResponse`: Root response payload containing timestamps, query parameters, totals, busiest machines, and rooms.
2. **`backend/app/api/v1/lab.py`**:
   - `GET /api/v1/lab/summary` endpoint.
   - Enforces `get_current_viewer` authentication.
   - Implements scoped subquery filtering by `Host.environment == :environment`.
   - Calculates online status using configurable cutoff `now - offline_after_seconds`.
   - Deduplicates duplicate timestamp samples.
   - Computes room-wise and fleet-wide average CPU utilization across active machines.
3. **`frontend/js/views/LabView.js`**:
   - High-density SRE dashboard view for physical lab hardware.
   - Summary stat cards with theme design tokens (`var(--status-healthy)`, `var(--status-critical)`).
   - Busiest workstations triage panel.
   - Dynamic room sections and PC cards with CPU progress bars, RAM/disk metrics, and last-seen relative timestamps.
   - Full state handling: skeleton loader, empty environment state, and error recovery banner.
   - Visibility-aware polling lifecycle: pauses requests when browser tab is hidden and tears down active intervals on navigation.
4. **`tests/test_api_lab.py`**:
   - 18 automated integration tests covering all functional, isolation, and security boundaries.

### 2.2 Files Modified
1. **`backend/app/schemas/__init__.py`**:
   - Re-exported `LabPCEntry`, `LabRoomSummary`, `LabTotalsSummary`, and `LabSummaryResponse`.
2. **`backend/app/api/v1/__init__.py`**:
   - Imported and mounted `lab_router` onto `api_router(prefix="/api/v1")` under `/lab`.
3. **`frontend/js/api.js`**:
   - Added method `getLabSummary(params)` to `ApiClient` with Bearer auth injection, timeout handling, and automatic 401 session refresh.
4. **`frontend/js/app.js`**:
   - Imported `renderLabView` and `destroyLabView`.
   - Registered `lab` in `VIEW_MAP`.
   - Wired teardown cleanup in `navigateTo()` to prevent background timer leaks when switching views.
5. **`frontend/index.html`**:
   - Added "Lab PCs" navigation item with Lucide-style workstation SVG icon under the "Operations" sidebar group.

---

## 3. API Endpoint and Response Contract

### 3.1 Endpoint Details
* **Route:** `GET /api/v1/lab/summary`
* **Tags:** `["Lab"]`
* **Authorization:** JWT Bearer token required (`Depends(get_current_viewer)`)
* **Allowed Roles:** `VIEWER`, `OPERATOR`, `ADMIN`, `SUPER_ADMIN`
* **Query Parameters:**
  * `environment: str` (default: `"lab"`) — Target deployment environment.
  * `offline_after_seconds: int` (default: `90`, range: `10`–`3600`) — Heartbeat inactivity threshold.
  * `real_agents_only: bool` (default: `True`) — Filters for telemetry with `source_type == 'REAL_AGENT'`.

### 3.2 Sample Response Schema (`LabSummaryResponse`)
```json
{
  "generated_at": "2026-10-22T07:44:00.123456Z",
  "environment": "lab",
  "offline_after_seconds": 90,
  "totals": {
    "total_pcs": 30,
    "online": 28,
    "offline": 2,
    "avg_cpu": 46.2
  },
  "busiest_pcs": [
    {
      "host_id": 14,
      "hostname": "lab1-pc14",
      "room": "lab-1",
      "ip_address": "192.168.1.114",
      "online": true,
      "last_seen": "2026-10-22T07:43:52Z",
      "cpu_percent": 96.5,
      "memory_percent": 74.0,
      "disk_percent": 42.0,
      "cpu_level": "high"
    }
  ],
  "rooms": [
    {
      "room": "lab-1",
      "total": 15,
      "online": 14,
      "offline": 1,
      "avg_cpu": 52.8,
      "pcs": [ ... ]
    }
  ]
}
```

---

## 4. Security and Authorization Validation

1. **Authentication Enforcement:**
   - Anonymous requests to `/api/v1/lab/summary` return `HTTP 401 Unauthorized`.
   - Accounts with `is_active=False` return `HTTP 403 Forbidden` ("User account is deactivated").
2. **Provenance Guard Preserved:**
   - Ingestion via `POST /api/v1/metrics` continues to strictly enforce credential authority.
   - Any agent attempting to inject disallowed or `UNKNOWN` source types receives `HTTP 403 Forbidden`.
   - Successfully ingested real telemetry (`source_type="REAL_AGENT"`) immediately updates lab summary state.
3. **Cross-Environment Isolation:**
   - Machines with `environment="production"` or `"staging"` are strictly isolated and never leak into the lab dashboard.
4. **Host Metadata Immutability:**
   - `get_or_create_host` preserves existing `environment` and `region`. Reassignments must be performed by authenticated administrators via `PATCH /api/v1/hosts/{id}`.

---

## 5. Database and Migration Status

* **Total Migrations Created:** **0**
* **Schema Alterations:** **None**
* **Index Alterations:** **None**
* **Active Database Status:** The active database `cloud_intelligence.db` remains 100% untracked and byte-for-byte immutable on disk, verified by the automated session hash guard (`test_active_database_immutability`).

---

## 6. Automated Testing Results

### 6.1 Test Suite Breakdown
The complete automated test suite was executed in an isolated in-memory SQLite environment using `pytest`:

```
====================== 125 passed, 50 warnings in 27.27s ======================
```

* **Baseline Pre-Implementation Tests:** 107 passed, 0 failed.
* **New Lab Integration Tests Added:** 18 passed, 0 failed.
* **Final Total Suite:** **125 passed, 0 failed (100% pass rate)**.

### 6.2 Specific Lab Test Coverage (`tests/test_api_lab.py`)

| Test ID | Test Name | Assertion / Behavior Verified | Result |
| :--- | :--- | :--- | :--- |
| **TEST-LAB-01** | `test_lab_summary_unauthenticated` | Missing Bearer token returns 401 Unauthorized | **PASSED** |
| **TEST-LAB-02** | `test_lab_summary_viewer_authorized` | Authenticated Viewer receives 200 OK conforming to schema | **PASSED** |
| **TEST-LAB-03** | `test_lab_summary_deactivated_user` | Deactivated user receives 403 Forbidden | **PASSED** |
| **TEST-LAB-04** | `test_lab_environment_isolation` | Non-lab hosts (production, staging) strictly excluded | **PASSED** |
| **TEST-LAB-05** | `test_lab_provenance_filter` | Filters SIMULATED hosts unless real_agents_only=False | **PASSED** |
| **TEST-LAB-06** | `test_lab_online_status_calculation` | Active telemetry (<90s) classified online=True | **PASSED** |
| **TEST-LAB-07** | `test_lab_offline_status_calculation` | Stale telemetry (>90s) classified online=False | **PASSED** |
| **TEST-LAB-08** | `test_lab_never_seen_host` | Host with 0 metrics handled gracefully with cpu_level="offline" | **PASSED** |
| **TEST-LAB-09** | `test_lab_cpu_severity_boundaries` | Boundary classifications: <80% normal, 80-94.9% warning, >=95% high | **PASSED** |
| **TEST-LAB-10** | `test_lab_room_grouping_and_sorting` | Groups by room; sorts rooms and hostnames alphabetically | **PASSED** |
| **TEST-LAB-11** | `test_lab_room_avg_cpu_calculation` | Averages online machines only; ignores offline machines | **PASSED** |
| **TEST-LAB-12** | `test_lab_busiest_pcs_ranking` | Top 5 online machines ranked descending by CPU | **PASSED** |
| **TEST-LAB-13** | `test_lab_duplicate_timestamps_guard` | Deduplicates identical metric timestamps per host | **PASSED** |
| **TEST-LAB-14** | `test_lab_inactive_host_exclusion` | Decommissioned hosts (is_active=False) excluded | **PASSED** |
| **TEST-LAB-15** | `test_lab_agent_telemetry_ingestion` | Real telemetry ingestion updates lab summary live | **PASSED** |
| **TEST-LAB-16** | `test_lab_provenance_violation_rejection` | Ingestion rejects invalid provenance with 403 Forbidden | **PASSED** |
| **TEST-LAB-17** | `test_lab_parameter_validation_bounds` | Validates offline_after_seconds bounds (ge=10, le=3600; 422 on invalid) | **PASSED** |
| **TEST-LAB-18** | `test_lab_query_performance_and_scaling` | Multi-room scale topology validated with 20 nodes | **PASSED** |

---

## 7. Performance Benchmarks and Index Validation

A benchmark was executed over a dataset of **50 hosts and 25,000 metric samples** (30 lab PCs across 3 rooms, each with 500 historical metrics, plus 20 cloud hosts):

### 7.1 SQLite `EXPLAIN QUERY PLAN`
```
-> MATERIALIZE anon_1
-> SEARCH metrics USING COVERING INDEX ix_metrics_host_id_timestamp (host_id=?)
-> LIST SUBQUERY 1
-> SEARCH hosts USING INDEX ix_hosts_source_type (source_type=?)
-> CREATE BLOOM FILTER
-> SEARCH hosts USING INDEX ix_hosts_source_type (source_type=?)
-> BLOOM FILTER ON anon_1 (host_id=?)
-> SEARCH anon_1 USING AUTOMATIC COVERING INDEX (host_id=?) LEFT-JOIN
-> SEARCH metrics USING INDEX ix_metrics_host_id_timestamp (host_id=? AND timestamp=?) LEFT-JOIN
-> USE TEMP B-TREE FOR ORDER BY
```
* **Index Seek Verification:** The scoped subquery exclusively executes index range seeks using the composite index `ix_metrics_host_id_timestamp ("host_id", "timestamp")`. Zero full table scans occurred across the 25,000 metrics.

### 7.2 Query Latency Distribution (100 Iterations)
* **Minimum Latency:** 4.659 ms
* **Median (p50):** **8.818 ms**
* **Average Latency:** 9.363 ms
* **95th Percentile (p95):** **16.400 ms**
* **99th Percentile (p99):** 30.861 ms
* **Maximum Latency:** 30.980 ms

### 7.3 Multi-PC Ingestion & Write Contention
Simulated simultaneous telemetry ingestion across 30 lab workstations (each executing host lookup, metric insert, threshold rule evaluation, and AI Isolation Forest inference):
* **Ingestion Success Rate:** **30/30 (100%)**
* **Database Lock Errors:** **0**
* **Mean Ingestion Latency:** **31.067 ms**
* **p95 Ingestion Latency:** **54.667 ms**

---

## 8. Deployment Prerequisites for Physical Lab PCs

Before physical rollout across lab workstations:
1. **Server Reachability:** Start server on all interfaces:
   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```
2. **Firewall:** Open inbound TCP port 8000 on the server host for the college lab subnet.
3. **Provision Credential:** Generate an agent key via the Admin API:
   ```http
   POST /api/v1/admin/agent-keys
   { "name": "Lab Room 1 Key", "source_type": "REAL_AGENT" }
   ```
4. **Target PC Environment Variable:** On each physical PC, store the secret in machine environment:
   ```cmd
   setx AGENT_API_KEY "sec_xxxxxxxxxxxxxxxxxxxx" /M
   ```
5. **Startup Script (`run_agent.bat`):**
   ```cmd
   @echo off
   cd /d C:\lab-agent
   call .venv\Scripts\activate
   python -m monitoring_agent.agent --url http://<SERVER_IP>:8000/api/v1/metrics --env lab --provider college-lab --region lab-1 --interval 15
   ```
6. **Task Scheduler:** Register `run_agent.bat` to execute on system boot with highest privileges.

---

## 9. Rollback Procedures

If reversion is ever requested:
1. **Backend:**
   - Remove lines 20 and 38 from `backend/app/api/v1/__init__.py`.
   - Remove `Lab*` imports from `backend/app/schemas/__init__.py`.
   - Delete `backend/app/api/v1/lab.py` and `backend/app/schemas/lab.py`.
2. **Frontend:**
   - Remove `getLabSummary` from `frontend/js/api.js`.
   - Remove `lab` view and import from `frontend/js/app.js`.
   - Remove "Lab PCs" `<a>` link from `frontend/index.html`.
   - Delete `frontend/js/views/LabView.js`.
3. **Database:** Zero action required (zero schema migrations were executed).

---

## 10. Status and Next Steps

* **Status:** Implemented and verified in local code and isolated test suite.
* **Separation of Concerns:** Zero physical lab PCs have been deployed, zero production keys have been generated, and zero production database hosts have been modified.
* **Awaiting User Review:** Implementation is complete and stopped. Standing by for user verification before any deployment steps.
