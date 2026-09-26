# DATA LINEAGE — Dashboard Metrics

**Audit Date:** 2026-09-23

This document traces the complete data path for every visible dashboard metric.

---

## CPU Utilization

| Field | Details |
|-------|---------|
| Meaning | Percentage of CPU capacity in use across all logical cores |
| Unit | Percent (0.0 - 100.0) |
| Source | Operating System kernel via psutil |
| Collection Method | psutil.cpu_percent(interval=None) — non-blocking, uses delta since last call |
| Collection Interval | Configurable (default 5 seconds via --interval arg or POLL_INTERVAL env var) |
| API Endpoint | GET /api/v1/metrics?host_id=X&limit=N |
| Database Table | metrics.cpu_percent (FLOAT) |
| Backend Service | metric_service.get_host_metrics() |
| Frontend Component | MetricsView.js — line chart using Chart.js |
| Transformation | None — raw value stored and displayed |
| Live | YES (when monitoring_agent is running) |
| Historical | YES (all past samples retained in metrics table) |
| Model-Generated | NO (raw psutil value) |
| Failure Behavior | Last known value shown; chart shows gap if no data |

**Data Flow:**
```
OS Kernel -> psutil.cpu_percent() -> collector.py::collect()
-> agent.py -> buffer.py::flush() -> POST /api/v1/metrics
-> metric_service::ingest_metric() -> metrics table
-> GET /api/v1/metrics -> api.js::getHostMetrics()
-> MetricsView.js chart
```

---

## Memory Utilization

| Field | Details |
|-------|---------|
| Meaning | Percentage of physical RAM currently in use |
| Unit | Percent (0.0 - 100.0) |
| Source | psutil.virtual_memory().percent |
| Collection Method | psutil virtual memory sampling |
| API Endpoint | GET /api/v1/metrics |
| Database Table | metrics.memory_percent |
| Live | YES (when agent running) |
| Failure Behavior | Chart gap on missing data |

---

## Disk Utilization

| Field | Details |
|-------|---------|
| Meaning | Percentage of disk partition used |
| Unit | Percent (0.0 - 100.0) |
| Source | psutil.disk_usage("/").percent (Linux) or psutil.disk_usage("C:\\").percent (Windows) |
| Collection Method | psutil disk usage sampling |
| API Endpoint | GET /api/v1/metrics |
| Database Table | metrics.disk_percent |
| Live | YES (when agent running) |

---

## Network Sent / Received

| Field | Details |
|-------|---------|
| Meaning | Megabytes transmitted/received since last collection interval |
| Unit | Megabytes (MB delta, not cumulative) |
| Source | psutil.net_io_counters() — delta between consecutive samples |
| Calculation | bytes_sent_delta / (1024*1024); delta from previous sample timestamp |
| API Endpoint | GET /api/v1/metrics |
| Database Table | metrics.network_sent_mb, metrics.network_received_mb |
| Live | YES (when agent running) |

---

## Host Status

| Field | Details |
|-------|---------|
| Meaning | Operational health status: healthy / warning / critical / offline |
| Calculation | If no metric in past 5 minutes -> offline; if critical alert -> critical; if warning alert -> warning; else -> healthy |
| Source | metrics table (last timestamp) + alerts table (active severity) |
| Backend Service | metric_service::get_fleet_summary() |
| API Endpoint | GET /api/v1/summary |
| Frontend Component | OverviewView.js host table, ResourcesView.js |

---

## Fleet Availability

| Field | Details |
|-------|---------|
| Meaning | Count of total / healthy / warning / critical / offline hosts |
| Calculation | Aggregated across all active hosts in fleet summary |
| Source | hosts + metrics + alerts tables |
| API Endpoint | GET /api/v1/summary -> total_hosts, healthy_hosts, warning_hosts, critical_hosts, offline_hosts |
| Frontend | OverviewView.js summary cards |
| Live | DATABASE-BACKED |

---

## Active Alerts / Incidents

| Field | Details |
|-------|---------|
| Meaning | Count of alerts with status='active' or status='acknowledged' |
| Source | alerts table |
| Trigger | Threshold breach in alert_service::evaluate_metric_sample() |
| API Endpoint | GET /api/v1/alerts?status=active |
| Frontend | OverviewView.js, IncidentsView.js |
| Live | DATABASE-BACKED |

---

## AI Anomaly Stream Count

| Field | Details |
|-------|---------|
| Meaning | Count of alerts where kind='anomaly' |
| Source | alerts table (kind column) |
| Trigger | AI anomaly detected in ai_service::evaluate_and_record_ai_anomaly() |
| Model | Fleet Isolation Forest (fleet_anomaly_detector_v1.joblib) |
| API Endpoint | GET /api/v1/alerts?kind=anomaly |
| Frontend | OverviewView.js "AI Anomaly Stream" card |
| Classification | MODEL INFERENCE |

---

## Security Events / Threats

| Field | Details |
|-------|---------|
| Meaning | Count of open/investigating security events |
| Source | security_events table |
| Trigger | POST /api/v1/security/events (manual or detector-triggered) |
| API Endpoint | GET /api/v1/security/summary |
| Frontend | OverviewView.js, SecurityView.js |
| Live | DATABASE-BACKED |

---

## Cost / Estimated Spend

| Field | Details |
|-------|---------|
| Meaning | Estimated monthly cloud infrastructure cost |
| Source | STANDARD_PRICING_CATALOG in cost_engine/calculator.py |
| Calculation | Sum of get_instance_monthly_cost(host.instance_type) for all active hosts |
| Classification | ESTIMATED — not real billing |
| API Endpoint | GET /api/v1/cost/summary |
| Frontend | CostView.js |
| Label in Response | billing_status: "Estimated (Telemetry Driven)" |

---

## Forecast

| Field | Details |
|-------|---------|
| Meaning | Projected future value of a metric over 24-72 hour horizon |
| Source | Historical metrics from database |
| Algorithm | Ordinary Least Squares linear regression (numpy.linalg.lstsq) |
| Output | forecast_points: [{timestamp, predicted_value, upper_bound, lower_bound}] |
| Classification | MODEL INFERENCE (linear regression) |
| API Endpoint | GET /api/v1/forecast?host_id=X&metric=cpu_percent&horizon_hours=24 |
| Frontend | MetricsView.js forecast tab |

---

## AI Narrator Output

| Field | Details |
|-------|---------|
| Meaning | Structured incident analysis correlating alerts + security + cost |
| Source | alerts, security_events, cost_recommendations tables |
| Algorithm | Rule-based correlation logic (IncidentNarratorEngine) |
| Classification | MODEL INFERENCE (deterministic rules) — NOT LLM |
| API Endpoint | POST /api/v1/narrator/query |
| Frontend | NarratorView.js |
| Hallucination Control | All claims grounded in specific DB records; IDs cited |

---

## Reports

| Field | Details |
|-------|---------|
| Meaning | Aggregated multi-domain operational summary |
| Source | hosts, alerts, security_events tables + cost analysis |
| Algorithm | Count aggregation + cost calculation |
| API Endpoint | POST /api/v1/reports/generate |
| Frontend | ReportsView.js |

---

## Audit Trail

| Field | Details |
|-------|---------|
| Meaning | Log of operator actions |
| Source | audit_logs table |
| Status | TABLE EXISTS but 0 records — API handlers do not call audit_service |
| API Endpoint | GET /api/v1/audit/logs |
| Frontend | AuditView.js |
