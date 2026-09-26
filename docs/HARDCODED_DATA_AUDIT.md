# HARDCODED DATA AUDIT

**Audit Date:** 2026-09-23
**Method:** Full source inspection of frontend/ and backend/ directories

---

## Summary

The codebase has been carefully audited for hardcoded operational values. The results show a CLEAN architecture:
all dashboard-visible numbers originate from real backend queries. There are NO frontend-generated fake values.
However, several values are ESTIMATED or CONFIGURATION-derived rather than live telemetry.

---

## Hardcoded Value Table

| Feature | File | Hardcoded Value | Expected Source | Current Source | Classification | Required Fix |
|---------|------|-----------------|----------------|---------------|----------------|--------------|
| CPU/MEM/DISK/Network charts | All frontend views | NONE — all fetched from API | Backend DB | /api/v1/metrics | LIVE (DB-backed) | None |
| Host count, Healthy/Warning/Critical | OverviewView.js | NONE — fetched from /api/v1/summary | DB aggregation | metric_service.get_fleet_summary() | LIVE (DB-backed) | None |
| Alert count | OverviewView.js | NONE — fetched from /api/v1/alerts | DB | alert_service.get_alerts() | LIVE (DB-backed) | None |
| Security event count | OverviewView.js | NONE — fetched from /api/v1/security/summary | DB | security_service.get_security_summary() | LIVE (DB-backed) | None |
| AI Anomaly Stream badge "LSTM + IF" | OverviewView.js | Label text only | UI label | Static HTML | CONFIGURATION | Accurate — both models exist |
| POLL_INTERVAL_MS: 30000 | frontend/js/config.js | 30000 (30 seconds) | Configurable | Static JS constant | CONFIGURATION | Acceptable default |
| API_BASE_URL: "/api/v1" | frontend/js/config.js | "/api/v1" | Configurable | Static JS constant | CONFIGURATION | Correct |
| Cost billing_status: "Estimated (Telemetry Driven)" | cost_service.py | Label string | Accurate label | Hardcoded string in service | CONFIGURATION | Correct — cost IS estimated |
| Cost default fallback monthly cost $45.00 | cost_engine/calculator.py | 45.00 | Pricing catalog | Hardcoded fallback for unknown types | ESTIMATED | Acceptable fallback |
| Contamination 0.05 / 0.06 | model_registry, ai_service | 0.05, 0.06 | Hyperparameter | Hardcoded default | CONFIGURATION | Acceptable ML hyperparameter |
| IF anomaly threshold: 0.60 | ai_service.py | 0.60 | Model calibration | Hardcoded in code | CONFIGURATION | Should be configurable |
| Security egress spike 150 MB | security_engine/detector.py | 150.0 MB | Configurable rule | Hardcoded in class constant | CONFIGURATION | Should be configurable |
| Heuristic fallback defaults cpu=25%, mem=50% | monitoring_agent/collector.py | cpu=25.0, mem=50.0 | psutil | Only when psutil not installed | SIMULATED (fallback) | Acceptable fallback, clearly labeled |
| Heuristic default mean [25.0, 45.0, 50.0, 1.0, 2.0] | ai_engine/anomaly_detector.py | Default mean values | Training statistics | Hardcoded fallback when untrained | ESTIMATED (fallback) | Auto-update when model trains |
| Source IP "10.0.1.45" | security_engine/detector.py | "10.0.1.45" | Real network log | Hardcoded placeholder | HARDCODED (ISSUE) | Must come from actual network flow |
| Destination port 443 | security_engine/detector.py | 443 | Real network log | Hardcoded placeholder | HARDCODED (ISSUE) | Must come from actual network flow |
| Simulator IP addresses (10.0.1.10 etc.) | scripts/simulate_fleet.py | Synthetic IPs | Simulator | Simulator | SIMULATED | Clearly labeled SIMULATED |
| DEFAULT_FLEET hostnames | scripts/simulate_fleet.py | prod-web-01 etc. | Simulator | Simulator | SIMULATED | Clearly labeled SIMULATED |
| Heartbeat cutoff 5 minutes | metric_service.py | timedelta(minutes=5) | Config | Hardcoded constant | CONFIGURATION | Consider making configurable |
| AI anomaly score threshold 0.80 (critical) | ai_service.py | 0.80 | Model calibration | Hardcoded | CONFIGURATION | Should be in alert rules |

---

## Classification Legend

- **LIVE**: Value originates from real-time system measurement
- **DATABASE**: Value is read from the database (which was written by a live source)
- **API-DERIVED**: Value comes through an API call to a backend service
- **MODEL-DERIVED**: Value is an output of an ML model inference
- **CONFIGURATION**: Deliberate constant or parameter (acceptable)
- **SIMULATED**: Explicitly synthetic data, labeled as such
- **ESTIMATED**: Derived from heuristics or reference data, not real measurement
- **HARDCODED (ISSUE)**: Value that should come from a real source but is hardcoded — must be fixed

---

## Critical Findings

### HARDCODED ISSUE 1: Security Source IP
**File:** security_engine/detector.py line 54
**Value:** source_ip = "10.0.1.45"
**Problem:** When an egress spike triggers a security event, the source IP is hardcoded to 10.0.1.45 instead of the actual source.
**Fix Required:** Pass actual source_ip from the metric/network record that triggered the event.

### HARDCODED ISSUE 2: Security Destination Port
**File:** security_engine/detector.py line 55
**Value:** destination_port = 443
**Problem:** Hardcoded placeholder. Real destination port should come from network flow data.
**Fix Required:** Pass actual destination port.

### ESTIMATED (But Correctly Labeled)
Cost billing_status is correctly labeled "Estimated (Telemetry Driven)" in the API response.
Cost figures are derived from a hardcoded pricing catalog (STANDARD_PRICING_CATALOG) — this is acceptable
for a prototype but should be replaced with live cloud provider billing APIs in production.

---

## Data Flow Verification for Key Metrics

### CPU Utilization (Dashboard)
```
OS Kernel
  -> psutil.cpu_percent()                      [LIVE]
  -> monitoring_agent/collector.py::collect()   [LIVE]
  -> monitoring_agent/buffer.py::flush()        [LIVE]
  -> POST /api/v1/metrics                       [LIVE]
  -> backend/app/services/metric_service.py::ingest_metric()  [LIVE]
  -> metrics table (SQLite)                     [DATABASE]
  -> GET /api/v1/metrics or /api/v1/summary     [DATABASE]
  -> frontend/js/api.js::getHostMetrics()       [DATABASE]
  -> MetricsView.js or OverviewView.js chart    [DATABASE]
```
STATUS: LIVE — complete path verified

### Alert Count (Dashboard)
```
metrics table
  -> alert_service.py::evaluate_metric_sample()   [DATABASE]
  -> alerts table                                  [DATABASE]
  -> GET /api/v1/alerts                            [DATABASE]
  -> OverviewView.js activeAlerts count            [DATABASE]
```
STATUS: DATABASE — complete path verified

### Cost Spend (Dashboard)
```
hosts table (instance_type field)
  -> cost_engine/calculator.py::get_instance_monthly_cost()  [CONFIGURATION]
  -> STANDARD_PRICING_CATALOG lookup                          [CONFIGURATION]
  -> CostSummaryResponse.estimated_monthly_spend_usd         [ESTIMATED]
  -> GET /api/v1/cost/summary                                 [ESTIMATED]
  -> CostView.js                                             [ESTIMATED]
```
STATUS: ESTIMATED — correctly labeled in API response
