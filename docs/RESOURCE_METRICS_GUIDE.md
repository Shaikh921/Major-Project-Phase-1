# RESOURCE METRICS GUIDE

**Audit Date:** 2026-09-23

---

## CPU Utilization

**Definition:** Percentage of total CPU processing capacity currently in active use.

**Unit:** Percent (0.0 to 100.0)

**Collection Method:**
```python
import psutil
cpu = psutil.cpu_percent(interval=None)
# interval=None: non-blocking, returns delta since last call
# Returns: float (e.g., 73.2 for 73.2%)
```

**Calculation:** Sum of all CPU core utilizations divided by core count. On a 4-core system at
50% on all cores: cpu_percent = 50.0.

**Source Flow:**
```
OS Kernel CPU scheduler
  -> psutil.cpu_percent()
  -> monitoring_agent/collector.py::collect()
  -> {cpu_percent: 73.2}
  -> POST /api/v1/metrics
  -> metrics table (cpu_percent FLOAT column)
  -> GET /api/v1/metrics
  -> Dashboard time-series chart
```

**Interpretation:**
| Range | Interpretation |
|-------|---------------|
| 0-60% | Normal — adequate headroom |
| 60-75% | Elevated — watch for spikes |
| 75-85% | Warning — investigate workload |
| 85-95% | Critical — performance impact likely |
| >95% | Saturated — immediate action required |

**Alert Rules (default):**
- Elevated CPU: > 75% -> warning
- High CPU: > 85% -> critical

---

## Memory Utilization

**Definition:** Percentage of physical RAM currently allocated by processes.

**Unit:** Percent (0.0 to 100.0)

**Collection Method:**
```python
mem = psutil.virtual_memory().percent
# virtual_memory() returns: total, available, used, percent
# percent = (used / total) * 100
```

**Interpretation:**
| Range | Interpretation |
|-------|---------------|
| 0-70% | Normal |
| 70-80% | Elevated — possible memory pressure |
| 80-90% | Warning — swap may activate |
| >90% | Critical — OOM risk |

---

## Disk Utilization

**Definition:** Percentage of disk partition capacity used.

**Unit:** Percent (0.0 to 100.0)

**Collection Method:**
```python
disk = psutil.disk_usage("/").percent  # Linux
disk = psutil.disk_usage("C:\\").percent  # Windows fallback
```

**Interpretation:**
| Range | Interpretation |
|-------|---------------|
| 0-70% | Normal |
| 70-85% | Warning — plan expansion |
| 85-92% | High warning — take action |
| >92% | Critical — disk full imminent |

**Special Note:** Unlike CPU/Memory, disk rarely decreases without explicit action (file deletion, archival).
The forecaster is particularly useful for disk: "Disk full in 14 hours at current growth rate."

---

## Network Sent (MB)

**Definition:** Megabytes of data transmitted outbound since last collection interval.

**Unit:** Megabytes (MB) — DELTA, not cumulative

**Collection Method:**
```python
current_net = psutil.net_io_counters()
bytes_sent_delta = current_net.bytes_sent - last_net.bytes_sent
sent_mb = bytes_sent_delta / (1024 * 1024)
```

**Interpretation:**
- Normal: < 5 MB per 5-second interval (typical web traffic)
- Elevated: 5-50 MB per interval (active data transfer)
- Suspicious: > 150 MB per interval (security alert trigger)

**Security Significance:** Large outbound spikes (>150MB) trigger suspicious_egress security events.

---

## Network Received (MB)

**Definition:** Megabytes of data received inbound since last collection interval.

**Unit:** Megabytes (MB) — DELTA, not cumulative

**Interpretation:**
- Normal: < 20 MB per 5-second interval
- High inbound: may indicate DDoS or large data transfer

---

## Availability

**Definition:** Whether a host is actively reporting metrics within the heartbeat window.

**Calculation:** offline if no metric received in past 5 minutes (timedelta(minutes=5))

**Source:** get_fleet_summary() -> latest_metric.timestamp comparison

**Display:** Status badge: healthy / warning / critical / offline

---

## Storage in Database

All metrics stored in the `metrics` table with:
- Composite index on (host_id, timestamp) for efficient range queries
- No automatic retention/purging (grows indefinitely in current implementation)
- Recommend implementing data retention policy (e.g., delete metrics older than 90 days)
