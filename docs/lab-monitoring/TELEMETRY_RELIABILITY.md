# CloudOps Intel — Telemetry Reliability & Persistent Spooling
**Document Version:** 1.0.0  
**Target Environment:** Intermittent Collegiate WiFi, Physical Ethernet Disconnects, Windows Reboots  

---

## 1. Overview & Failure Model

In collegiate computer laboratories, network connectivity is inherently prone to disruptions:
- Scheduled network maintenance and switch reboots
- Dynamic IP reassignments and DHCP lease expirations
- Students or technicians unplugging Ethernet cables
- Lab PCs being rebooted or hard-powered off between class sessions
- Central monitoring server restarts or database maintenance

An in-memory queue (such as a Python deque) loses all accumulated telemetry whenever the agent service restarts or the workstation reboots. To guarantee enterprise-grade reliability, CloudOps Intel implements a **durable, disk-backed SQLite telemetry spooler**.

---

## 2. Spooler Architecture & Database Schema

The spooler is implemented in `monitoring_agent/buffer.py` via `MetricBuffer`. When the agent starts, it opens or creates a local SQLite database at `sensor_spool.db` (or a designated path under `C:\ProgramData\CloudOpsIntel\Sensor\sensor_spool.db`).

### Schema Definition:
```sql
CREATE TABLE IF NOT EXISTS spool_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL,
    attempts INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_spool_created ON spool_queue(created_at);
```

### High-Performance PRAGMAs:
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA busy_timeout = 5000;
```
- **Write-Ahead Logging (WAL):** Prevents writer locks from blocking read queries and guarantees ACID durability across power cuts.
- **Synchronous Normal:** Ensures sync-to-disk without causing excessive disk I/O bottlenecks during 5-second polling intervals.

---

## 3. Quota, Retention, and Eviction Policies

The spooler enforces strict operational boundaries to avoid saturating workstation storage while guaranteeing full 24-hour retention across supported polling intervals:

### 3.1 Mathematically Verified Capacity & 24-Hour Retention (REL-01)
- The queue capacity is derived dynamically or configured to guarantee 24 hours of offline telemetry:
  $$\text{Capacity} = \min\left(\max\left(5000, \left\lfloor\frac{3600}{\text{interval}} \times \text{retention\_hours} \times 1.25\right\rfloor\right), \frac{\text{Quota Bytes}}{\text{Sample Size}}\right)$$
  - **5-second polling (Default):** 720 samples/hr $\times$ 24h = 17,280 samples + 25% safety margin = **21,600 samples** (~10.8 MB).
  - **15-second polling:** 240 samples/hr $\times$ 24h = 5,760 samples + 25% safety margin = **7,200 samples** (~3.6 MB).
  - **1-second polling:** 3,600 samples/hr $\times$ 24h = 86,400 samples + 25% safety margin = 108,000 samples, bounded by the 50 MB disk quota to **102,400 samples**.
- Every time a sample is pushed, the buffer executes an expiration sweep:
  ```sql
  DELETE FROM spool_queue WHERE created_at < :cutoff;
  ```
  where `cutoff = now - (24 * 3600)`.
- Samples older than 24 hours are expired. The count of expired records is tracked in `_expired_count` and observable via `get_diagnostics()`.

### 3.2 Explicit Overflow Policy (`preserve_queued`)
- When queue capacity is reached or the 50 MB disk quota ceiling is exceeded:
  - Default policy is `preserve_queued`: The buffer strictly protects the accumulated historical backlog. New samples are safely rejected and recorded in `_dropped_count`, with `last_overflow_reason` set to `"max_size_reached"` or `"disk_quota_exceeded"`.
  - Configurable `drop_oldest` policy is available for operating environments requiring real-time immediacy over historical preservation.
  - Zero silent data drops occur; all drop events are visible to operators via agent diagnostics and server telemetry heartbeats.

---

## 4. Atomic Dispatch & Idempotent Flushing (REL-02)

### 4.1 Batch Assembly with Persistent Batch Identifier
- The spooler reads up to 1,000 samples in chronological order.
- Before dispatch, rows are tagged in SQLite with a persistent, unique `batch_id` (`batch_<uuid4>`):
  ```sql
  UPDATE spool_queue SET batch_id = :active_batch_id WHERE id IN (:ids);
  ```
- If network disruption occurs during flight, the rows remain tagged with the same `batch_id` and will be retransmitted with the identical identifier upon the next retry.
- Batches are packaged into `MetricBatchCreate`:
  ```json
  {
    "batch_id": "batch_4f3a9e...",
    "metrics": [ ...up to 1,000 samples... ]
  }
  ```

### 4.2 Verified HTTPS Delivery
- The payload is dispatched to `{server_url}/api/v1/metrics` using verified HTTPS (`requests` with CA bundle validation).
- Ingestion authentication header `X-Agent-Key` is attached.

### 4.3 Server Atomic Ingestion, Deduplication & Conflict Detection (AUD-01)
- The server processes incoming batches inside a strictly atomic database transaction (`ingest_metrics_batch`):
  - **Transaction Ownership:** Metric record preparation (`_persist_metric_record`) adds and flushes samples without committing; the batch service owns the transaction boundary.
  - **Mid-Batch Failure Safety:** If any error or exception occurs before transaction commit, `db.rollback()` executes immediately. Zero metric rows or alert records remain committed, leaving the batch eligible for a clean retry.
  - **First submission:** All metrics are flushed, the `IngestedBatch` record is added with the SHA-256 digest of the canonical payload, and a single atomic `db.commit()` is issued.
  - **Exact retry (lost ACK simulation):** The server verifies that `payload_hash` matches and immediately returns HTTP 200/201 with `is_duplicate: True`, writing zero duplicate rows into `metrics`.
  - **Payload Conflict:** If an existing `batch_id` is resubmitted with modified metrics, the server rejects it with `HTTP 409 Conflict`.
  - **Concurrent Duplicate Synchronization:** Synchronized via the unique constraint on `IngestedBatch.batch_id`. The second transaction rolls back on `IntegrityError`, verifies the matching `payload_hash`, and returns duplicate success with zero duplicate metric rows.

### 4.4 Idempotency Record Retention Policy (AUD-03)
- Because client spools hold telemetry for up to 24 hours (with exponential backoff and network blips extending the practical replay window to 48 hours), the server retains `IngestedBatch` records for **72 hours (3 days)**.
- Setting retention to 3x client spool life guarantees that no idempotency record is pruned while a valid client can still legitimately replay that batch.
- Expired idempotency records are transactionally pruned via `cleanup_expired_idempotency_records(db, retention_hours=72.0, batch_limit=1000)` without mutating or deleting `metrics`, `hosts`, `alerts`, or audit logs.

### 4.5 Atomic Removal Upon Confirmed Success
- Spooled records are deleted from SQLite **ONLY** after receiving an HTTP status code `200` or `201` from the server:
  ```sql
  DELETE FROM spool_queue WHERE id IN (?, ?, ...);
  ```
- If the connection fails, drops mid-transmission, or returns an HTTP 5xx error, the transaction is **NOT** committed, and all records remain safely stored in `sensor_spool.db` with their persistent `batch_id` intact for the next retry attempt.

---

## 5. Exponential Backoff with Jitter

To prevent "thundering herd" problems when the network or central server recovers, the spooler implements exponential backoff with randomized jitter:

```python
delay = min(base_delay * (multiplier ** failures), max_delay)
jitter = random.uniform(-0.2, 0.2) * delay
actual_backoff = max(1.0, delay + jitter)
```

| Parameter | Value |
| :--- | :--- |
| **Base Delay** | 1.0 second |
| **Backoff Multiplier** | 2.0x |
| **Maximum Delay** | 60.0 seconds |
| **Jitter Window** | ±20% randomized |

### Differentiating Error Classes:
- **Transient Failures (HTTP 500, 502, 503, 504, Connection Refused, Timeout):**
  - Increments failure counter, calculates backoff delay, and preserves data.
- **Permanent Authorization Failures (HTTP 401, 403):**
  - Logs: `[!] Device credential rejected or disabled by server.`
  - Applies maximum backoff delay (60s) to avoid spamming server authentication logs.
  - Preserves spooled data in `sensor_spool.db` until administrative re-enablement or rotation.
