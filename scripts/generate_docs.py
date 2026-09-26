"""
Documentation generator for Cloud Resource Monitoring & Intelligence Platform.
Generates all required docs/* files.
"""
import os
import json

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
os.makedirs(os.path.join(DOCS, "figures"), exist_ok=True)

# ============================================================
# PROJECT_AUDIT.md
# ============================================================
PROJECT_AUDIT = """# PROJECT AUDIT — Cloud Resource Monitoring & Intelligence Platform

**Audit Date:** 2026-09-23
**Auditor:** Senior Software Architect / Project Auditor
**Repository Root:** c:\\CLoudProject

---

## 1. Complete Folder Structure

```
CLoudProject/
├── .env                          # Active environment config (SQLite, no LLM keys set)
├── .env.example                  # Environment template
├── docker-compose.yml            # Multi-service Docker config
├── requirements.txt              # Python dependencies
├── cloud_intelligence.db         # Active SQLite database (974KB, 9 tables)
├── scaler.joblib                 # Standalone MinMaxScaler from training pipeline
├── selected_features.json        # 30 features selected for LSTM input
├── sequences_data.npz            # Pre-built LSTM sequence tensors (2.2MB)
├── test_predictions.csv          # LSTM test predictions (135KB)
├── EDA.py                        # Exploratory data analysis
├── realtime_inference_engine.py  # Standalone LSTM inference engine
├── step1_continuity_check.py     # Data pipeline step 1
├── step2_feature_inspection.py   # Data pipeline step 2
├── step3_investigate_negative_values.py
├── step4_prepare_data.py
├── step5_feature_selection.py
├── step6_data_preprocessing.py
├── step7_sequence_generation.py
├── step8_9_train_lstm.py         # LSTM Autoencoder training
├── step10_11_12_evaluation_threshold_tuning.py  # LSTM evaluation
├── step13_visualizations.py
├── step14_groundtruth_event_evaluation.py
├── step15_cloud_dataset_audit.py
│
├── ai_engine/
│   ├── anomaly_detector.py       # Isolation Forest anomaly detector
│   ├── explainability.py         # Feature attribution engine
│   ├── forecaster.py             # Linear regression time-series forecaster
│   └── model_registry.py        # Model persistence registry
│
├── backend/app/
│   ├── main.py                   # FastAPI app entry point
│   ├── api/v1/                   # REST API routes (11 modules)
│   ├── core/config.py            # Pydantic-settings configuration
│   ├── database/                 # SQLAlchemy session & init_db
│   ├── models/                   # ORM models (host, metric, alert, security, cost)
│   ├── schemas/                  # Pydantic request/response schemas
│   └── services/                 # Business logic (10 services)
│
├── cost_engine/calculator.py     # Pricing catalog + rightsizing logic
│
├── data/
│   ├── Cloud_Anomaly_Dataset.csv (37MB — primary training dataset)
│   ├── groundtruth.csv           (44KB — labeled anomaly events)
│   └── train1.csv, train2.csv, test.csv
│
├── docs/                         # Documentation files (this package)
│
├── frontend/
│   ├── index.html
│   ├── css/                      # Vanilla CSS design system
│   └── js/
│       ├── api.js                # Centralized API client
│       ├── app.js                # SPA router
│       ├── config.js             # CONFIG + StateStore
│       ├── sanitizer.js          # XSS sanitizer
│       ├── components/           # 5 UI components
│       └── views/                # 11 page views
│
├── models/
│   ├── best_lstm_anomaly_detector.pt      # Trained LSTM weights (256KB)
│   ├── fleet_anomaly_detector_v1.joblib   # Fleet Isolation Forest (187KB)
│   ├── production_cloud_anomaly_model_v1.joblib  # Production IF (1.7MB)
│   ├── evaluation_metrics.json
│   ├── training_history.json
│   ├── event_level_evaluation.json
│   └── registry_metadata.json
│
├── monitoring_agent/
│   ├── agent.py                  # Main daemon process
│   ├── buffer.py                 # Ring buffer with exponential backoff
│   └── collector.py              # psutil-based system metric collector
│
├── narrator/engine.py            # Deterministic cross-module incident narrator
│
├── scripts/
│   ├── simulate_fleet.py         # Multi-host fleet simulator (SIMULATED)
│   ├── train_production_model.py
│   └── verify_live_api.py
│
├── security_engine/detector.py   # Signature-based security detector
│
└── tests/                        # 17 test files, 44 total tests
```

---

## 2. Frontend Pages / Views

| View File | Purpose | Backend Connected | Status |
|-----------|---------|-------------------|--------|
| OverviewView.js | Fleet command center | /api/v1/summary, /api/v1/alerts, /api/v1/security/summary | LIVE |
| ResourcesView.js | Host inventory, drill-down | /api/v1/hosts, /api/v1/metrics | LIVE |
| MetricsView.js | Time-series charts | /api/v1/metrics, /api/v1/forecast | LIVE |
| AnomaliesView.js | Anomaly log, feedback | /api/v1/alerts, /api/v1/ai/score | LIVE |
| IncidentsView.js | Alert lifecycle management | /api/v1/alerts | LIVE |
| SecurityView.js | Security event log | /api/v1/security/events, /api/v1/security/summary | LIVE |
| CostView.js | Cost summary, recommendations | /api/v1/cost/summary | LIVE |
| NarratorView.js | AI incident analysis | /api/v1/narrator/query | LIVE |
| ReportsView.js | Executive report generation | /api/v1/reports/generate | LIVE |
| AuditView.js | Audit log browser | /api/v1/audit/logs | LIVE (0 records) |
| SettingsView.js | Alert rule CRUD | /api/v1/alerts/rules, /api/v1/ai/models | LIVE |

---

## 3. Backend API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| GET / | GET | Root / serve frontend index.html |
| GET /health | GET | Liveness probe |
| GET /api/v1/summary | GET | Fleet health summary |
| GET /api/v1/hosts | GET | List all hosts |
| POST /api/v1/hosts | POST | Register new host |
| GET /api/v1/hosts/{id} | GET | Get host detail |
| DELETE /api/v1/hosts/{id} | DELETE | Deactivate host |
| POST /api/v1/metrics | POST | Ingest single metric sample |
| GET /api/v1/metrics | GET | Query time-series metrics |
| GET /api/v1/alerts | GET | List alerts (filterable) |
| POST /api/v1/alerts/{id}/ack | POST | Acknowledge alert |
| POST /api/v1/alerts/{id}/feedback | POST | Submit TP/FP feedback |
| GET /api/v1/alerts/rules | GET | List alert rules |
| POST /api/v1/alerts/rules | POST | Create alert rule |
| DELETE /api/v1/alerts/rules/{id} | DELETE | Delete alert rule |
| GET /api/v1/forecast | GET | Metric forecast + time-to-threshold |
| POST /api/v1/ai/score | POST | Score telemetry sample for anomaly |
| POST /api/v1/ai/train | POST | Train anomaly model from DB |
| GET /api/v1/ai/models | GET | List registered models |
| GET /api/v1/security/events | GET | List security events |
| POST /api/v1/security/events | POST | Record security event |
| PATCH /api/v1/security/events/{id} | PATCH | Update event status |
| GET /api/v1/security/summary | GET | Security summary counts |
| GET /api/v1/cost/summary | GET | Cost analysis + recommendations |
| PATCH /api/v1/cost/recommendations/{id} | PATCH | Accept/dismiss recommendation |
| POST /api/v1/narrator/query | POST | AI incident analysis |
| POST /api/v1/reports/generate | POST | Generate executive report |
| GET /api/v1/audit/logs | GET | Query audit trail |

---

## 4. Database Models (SQLAlchemy ORM)

| Model | Table | Rows (DB) | Purpose |
|-------|-------|-----------|---------|
| Host | hosts | 6 | Registered compute resources |
| Metric | metrics | 3,950 | Time-series telemetry samples |
| AlertRule | alert_rules | 6 | Threshold rule definitions |
| Alert | alerts | 156 | Active/resolved alert instances |
| AlertFeedback | alert_feedback | 2 | Operator TP/FP verdicts |
| SecurityEvent | security_events | 7 | Security incident records |
| AuditLog | audit_logs | 0 | Admin action audit trail (EMPTY) |
| PricingCatalog | pricing_catalog | 20 | Cloud instance pricing (CONFIGURATION) |
| CostRecommendation | cost_recommendations | 0 | Rightsizing recommendations (generated on-demand) |

---

## 5. Services

| Service File | Purpose |
|-------------|---------|
| metric_service.py | Metric ingestion, auto-host-discovery, fleet summary |
| alert_service.py | Threshold evaluation, deduplication, auto-resolution |
| ai_service.py | Anomaly scoring, model training, forecasting |
| host_service.py | Host CRUD, get-or-create |
| cost_service.py | Fleet cost analysis, rightsizing recommendations |
| security_service.py | Security event persistence, summary aggregation |
| narrator_service.py | Delegates to narrator engine |
| report_service.py | Executive report aggregation |
| audit_service.py | Audit log writes |

---

## 6. ML Models

| Model | File | Algorithm | Training Samples | Status |
|-------|------|-----------|-----------------|--------|
| LSTM Autoencoder | best_lstm_anomaly_detector.pt | PyTorch LSTM (seq=15, feat=30, h=64, latent=32) | ~70% of Cloud_Anomaly_Dataset.csv | TRAINED |
| Fleet Isolation Forest | fleet_anomaly_detector_v1.joblib | sklearn IsolationForest | 10 (live DB samples) | TRAINED (WEAK — 10 samples only) |
| Production Isolation Forest | production_cloud_anomaly_model_v1.joblib | sklearn IsolationForest | 222,056 | TRAINED |

---

## 7. Monitoring Agent

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Agent daemon | monitoring_agent/agent.py | IMPLEMENTED | Uses psutil for LIVE collection |
| System collector | monitoring_agent/collector.py | IMPLEMENTED | psutil CPU/MEM/DISK/NET |
| Ring buffer | monitoring_agent/buffer.py | IMPLEMENTED | Thread-safe, exponential backoff, up to 5000 buffered samples |
| Simulator | scripts/simulate_fleet.py | SEPARATE (SIMULATED) | Clearly labeled, sends synthetic data |

---

## 8. Security Engine

| Component | Status | Detection Method |
|-----------|--------|-----------------|
| security_engine/detector.py | IMPLEMENTED (limited) | Signature-based: suspicious egress (>150MB) |
| SSH brute force signatures | DEFINED | Not auto-triggered from metrics |
| Port scan signatures | DEFINED | Not auto-triggered from metrics |
| Unauthorized sudo | DEFINED | Not auto-triggered from metrics |
| Security event storage | IMPLEMENTED | Via POST /api/v1/security/events |

---

## 9. Cost Engine

| Component | Status | Data Source |
|-----------|--------|-------------|
| CostCalculator | IMPLEMENTED | ESTIMATED — pricing catalog lookup |
| Pricing catalog | CONFIGURATION (hardcoded) | 20 AWS/GCP/Azure instance types |
| Rightsizing | IMPLEMENTED | ESTIMATED — based on observed avg/peak metrics |
| Idle detection | IMPLEMENTED | ESTIMATED — avg CPU < 5%, avg MEM < 25% |

---

## 10. Narrator Component

| Component | Status | Notes |
|-----------|--------|-------|
| narrator/engine.py | IMPLEMENTED | Deterministic rule-based correlation |
| Cross-module correlation | IMPLEMENTED | Queries alerts + security + cost from DB |
| Evidence grounding | IMPLEMENTED | Cites alert and event IDs |
| LLM generation | NOT IMPLEMENTED | Requires OPENAI/GEMINI API key (not set in .env) |

---

## 11. Tests — Summary

| Test File | Tests | Result |
|-----------|-------|--------|
| test_agent_buffer.py | 4 | ALL PASS |
| test_ai_anomaly.py | 3 | ALL PASS |
| test_alert_engine.py | 3 | ALL PASS |
| test_api_ai.py | 3 | ALL PASS |
| test_api_v1.py | 3 | ALL PASS |
| test_api_v1_expanded.py | 4 | ALL PASS |
| test_config.py | 3 | ALL PASS |
| test_cost_engine.py | 2 | ALL PASS |
| test_database.py | 1 | ALL PASS |
| test_explainability.py | 2 | ALL PASS |
| test_forecaster.py | 2 | ALL PASS |
| test_health.py | 2 | ALL PASS |
| test_host_service.py | 4 | ALL PASS |
| test_metric_service.py | 4 | ALL PASS |
| test_models.py | 1 | ALL PASS |
| test_narrator_engine.py | 1 | ALL PASS |
| test_security_engine.py | 2 | ALL PASS |
| **TOTAL** | **44** | **44 PASSED / 0 FAILED** |

---

## 12. Configuration Files

| File | Purpose |
|------|---------|
| .env | Active config (SQLite URL, empty LLM keys, empty cloud credentials) |
| .env.example | Template with all supported keys |
| docker-compose.yml | Multi-service container orchestration |
| requirements.txt | Python package dependencies |
| backend/app/core/config.py | Pydantic-settings config model |

---

## 13. Known Limitations

| # | Limitation | Impact |
|---|-----------|--------|
| 1 | No LLM integration | Narrator is deterministic only; no GPT/Gemini output |
| 2 | Fleet IF model trained on 10 DB samples | Nearly meaningless anomaly detection until retrained |
| 3 | Security detector auto-triggers on egress only | Brute-force/port-scan detection requires external log ingestion |
| 4 | Cost is ESTIMATED not actual billing | No cloud provider API (AWS Cost Explorer / GCP Billing) |
| 5 | Audit log table has 0 records | API handlers do not call audit_service.write() |
| 6 | Cost recommendations not persisted proactively | Generated on-demand at /cost/summary only |
| 7 | LSTM model not connected to live alerting pipeline | Standalone evaluation pipeline; IF used live |
| 8 | No authentication or RBAC | CORS set to allow_origins=["*"] — open access |
| 9 | Dockerfiles referenced but not present | docker-compose.yml unusable without Dockerfiles |
| 10 | Redis in compose but unused in code | Redis is dead weight in current implementation |
"""

# ============================================================
# HARDCODED_DATA_AUDIT.md
# ============================================================
HARDCODED_DATA_AUDIT = """# HARDCODED DATA AUDIT

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
"""

# ============================================================
# DATA_LINEAGE.md
# ============================================================
DATA_LINEAGE = """# DATA LINEAGE — Dashboard Metrics

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
| Source | psutil.disk_usage("/").percent (Linux) or psutil.disk_usage("C:\\\\").percent (Windows) |
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
"""

# ============================================================
# API_INTEGRATION_AUDIT.md
# ============================================================
API_INTEGRATION_AUDIT = """# API INTEGRATION AUDIT

**Audit Date:** 2026-09-23

---

## Complete API Inventory

| Endpoint | Method | Purpose | Input | Output | DB Table | Frontend Consumer | Status |
|----------|--------|---------|-------|--------|----------|-------------------|--------|
| /health | GET | Liveness probe | None | {status: healthy} | None | Not used | LIVE |
| /api/v1/summary | GET | Fleet summary | None | FleetSummaryResponse | hosts, metrics, alerts | OverviewView | LIVE |
| /api/v1/hosts | GET | List hosts | active_only, environment | List[HostRead] | hosts | ResourcesView, OverviewView | LIVE |
| /api/v1/hosts | POST | Register host | HostCreate JSON | HostRead | hosts | ResourcesView | LIVE |
| /api/v1/hosts/{id} | GET | Host detail | host_id | HostRead | hosts | ResourcesView | LIVE |
| /api/v1/hosts/{id} | DELETE | Deactivate host | host_id | {message} | hosts | ResourcesView | LIVE |
| /api/v1/metrics | POST | Ingest metric | MetricCreate JSON | {metric_id, alerts} | metrics, alerts | monitoring_agent | LIVE |
| /api/v1/metrics | GET | Query metrics | host_id, limit, start_time, end_time | MetricTimeSeriesResponse | metrics | MetricsView | LIVE |
| /api/v1/alerts | GET | List alerts | host_id, status, severity, kind, limit | List[AlertRead] | alerts | AnomaliesView, IncidentsView | LIVE |
| /api/v1/alerts/{id}/ack | POST | Acknowledge alert | alert_id | AlertRead | alerts | IncidentsView | LIVE |
| /api/v1/alerts/{id}/feedback | POST | Submit feedback | verdict, notes | AlertFeedbackRead | alert_feedback | AnomaliesView | LIVE |
| /api/v1/alerts/rules | GET | List rules | None | List[AlertRuleRead] | alert_rules | SettingsView | LIVE |
| /api/v1/alerts/rules | POST | Create rule | AlertRuleCreate JSON | AlertRuleRead | alert_rules | SettingsView | LIVE |
| /api/v1/alerts/rules/{id} | DELETE | Delete rule | rule_id | {message} | alert_rules | SettingsView | LIVE |
| /api/v1/forecast | GET | Metric forecast | host_id, metric, horizon_hours | ForecastResponse | metrics | MetricsView | LIVE |
| /api/v1/ai/score | POST | Score for anomaly | AnomalyScoreRequest | AnomalyScoreResponse | None | AnomaliesView | LIVE |
| /api/v1/ai/train | POST | Train IF model | ModelTrainRequest | ModelTrainResponse | metrics | SettingsView | LIVE |
| /api/v1/ai/models | GET | List models | None | List[ModelMetadataResponse] | None (file registry) | SettingsView | LIVE |
| /api/v1/security/events | GET | List security events | severity, status | List[SecurityEventRead] | security_events | SecurityView | LIVE |
| /api/v1/security/events | POST | Record event | SecurityEventCreate | SecurityEventRead | security_events | External/agent | LIVE |
| /api/v1/security/events/{id} | PATCH | Update status | status | SecurityEventRead | security_events | SecurityView | LIVE |
| /api/v1/security/summary | GET | Security summary | None | SecuritySummaryResponse | security_events | OverviewView, SecurityView | LIVE |
| /api/v1/cost/summary | GET | Cost + recommendations | None | CostSummaryResponse | hosts, metrics, cost_recommendations | CostView | LIVE (ESTIMATED) |
| /api/v1/cost/recommendations/{id} | PATCH | Accept/dismiss recommendation | status | CostRecommendationRead | cost_recommendations | CostView | LIVE |
| /api/v1/narrator/query | POST | AI incident analysis | query, host_id, environment, time_window | NarratorResponse | alerts, security_events, cost_recommendations | NarratorView | LIVE (DETERMINISTIC) |
| /api/v1/reports/generate | POST | Generate report | time_range_hours, environment | ReportResponse | all tables | ReportsView | LIVE |
| /api/v1/audit/logs | GET | Query audit logs | action, limit | List[AuditLogRead] | audit_logs | AuditView | LIVE (0 records) |

---

## Frontend -> Backend -> DB Chain Verification

### Overview Dashboard
```
OverviewView.js
  -> api.getFleetSummary()        -> GET /api/v1/summary
     -> metric_service.get_fleet_summary(db)
     -> SELECT hosts, SELECT metrics, SELECT alerts
     -> FleetSummaryResponse (total_hosts, healthy, warning, critical, hosts[])
  -> api.getAlerts({limit:10})    -> GET /api/v1/alerts
     -> alert_service.get_alerts(db)
     -> SELECT alerts ORDER BY created_at DESC
  -> api.getSecuritySummary()     -> GET /api/v1/security/summary
     -> security_service.get_security_summary(db)
     -> SELECT security_events
STATUS: FULLY CONNECTED
```

### Metrics Chart
```
MetricsView.js
  -> api.getHostMetrics(hostId, limit, startTime, endTime)
     -> GET /api/v1/metrics?host_id=X&limit=100
     -> metric_service.get_host_metrics(db, host_id)
     -> SELECT metrics WHERE host_id=X ORDER BY timestamp DESC LIMIT N
     -> MetricTimeSeriesResponse.data -> array of {timestamp, cpu, memory, disk, net}
  -> Renders Chart.js time-series charts
STATUS: FULLY CONNECTED
```

### AI Narrator
```
NarratorView.js
  -> api.queryNarrator(query, hostId, env, windowMinutes)
     -> POST /api/v1/narrator/query
     -> narrator_service.query_narrator(db, req)
     -> IncidentNarratorEngine.analyze_incident(db, ...)
     -> Queries alerts + security_events + cost_recommendations from DB
     -> Returns structured_explanation + raw_markdown_narrative
STATUS: FULLY CONNECTED (DETERMINISTIC — NO LLM)
```

### Cost View
```
CostView.js
  -> api.getCostSummary()
     -> GET /api/v1/cost/summary
     -> cost_service.generate_fleet_cost_analysis(db)
     -> Reads active hosts from DB
     -> Calculates spend from STANDARD_PRICING_CATALOG (CONFIGURATION)
     -> Evaluates rightsizing based on recent 60 metrics
     -> Returns CostSummaryResponse with billing_status="Estimated (Telemetry Driven)"
STATUS: FULLY CONNECTED — DATA IS ESTIMATED (not live billing)
```

### Audit Trail
```
AuditView.js
  -> api.getAuditLogs()
     -> GET /api/v1/audit/logs
     -> audit_service.get_audit_logs(db)
     -> SELECT audit_logs (returns empty list — 0 records)
STATUS: CONNECTED but EMPTY — audit write calls not wired into API handlers
```

---

## Disconnected Features

| Feature | Status | Reason |
|---------|--------|--------|
| Audit log writes | NOT CONNECTED | API handlers do not call audit_service.write() |
| LLM-powered narrator | NOT CONNECTED | No API keys in .env |
| Real cloud billing | NOT CONNECTED | No AWS Cost Explorer / GCP Billing API |
| LSTM live anomaly alerts | NOT CONNECTED | LSTM evaluation is standalone; only IF is live |
| Redis cache | NOT CONNECTED | Listed in docker-compose but unused in code |
"""

# ============================================================
# DATABASE_AUDIT.md
# ============================================================
DATABASE_AUDIT = """# DATABASE AUDIT

**Audit Date:** 2026-09-23
**Database:** SQLite (cloud_intelligence.db, 974KB)
**ORM:** SQLAlchemy 2.x with mapped_column / Mapped[] syntax

---

## Tables Overview

| Table | Rows | Purpose |
|-------|------|---------|
| hosts | 6 | Registered compute resources |
| metrics | 3,950 | Time-series telemetry samples |
| alert_rules | 6 | Threshold rule definitions |
| alerts | 156 | Active/resolved alert instances |
| alert_feedback | 2 | Operator TP/FP verdicts |
| security_events | 7 | Security incident records |
| audit_logs | 0 | Admin action audit trail (EMPTY) |
| pricing_catalog | 20 | Cloud instance pricing reference |
| cost_recommendations | 0 | Rightsizing recommendations (on-demand) |

---

## hosts Table

**Purpose:** Registry of all monitored servers and virtual machines.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment primary key |
| hostname | VARCHAR(255) | Unique, indexed |
| ip_address | VARCHAR(45) | Nullable — IPv4 or IPv6 |
| environment | VARCHAR(50) | production/staging/development/local; indexed |
| instance_type | VARCHAR(100) | Cloud instance size (e.g. t3.medium); nullable |
| provider | VARCHAR(50) | aws/gcp/azure/bare-metal; default=bare-metal |
| region | VARCHAR(50) | Cloud region; default=local |
| is_active | BOOLEAN | Telemetry expected when True |
| tags | JSON | Arbitrary key-value metadata |
| created_at | DATETIME | UTC registration timestamp |
| updated_at | DATETIME | UTC last-update timestamp |

**Relationships:**
- hosts -> metrics: One-to-Many (cascade delete)
- hosts -> alerts: One-to-Many (cascade delete)
- hosts -> security_events: backref
- hosts -> cost_recommendations: backref

**Current Records (6 hosts):**
- prod-web-01 (production, aws, us-east-1)
- prod-web-02 (production, aws, us-east-1)
- prod-db-primary (production, aws, us-east-1)
- staging-api-01 (staging, gcp, us-central1)
- dev-sandbox-01 (development, bare-metal, local)
- DELL (local, bare-metal, local) — the local machine running the agent

---

## metrics Table

**Purpose:** High-frequency time-series telemetry samples.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| host_id | INTEGER FK | References hosts.id ON DELETE CASCADE |
| timestamp | DATETIME | UTC sample time; indexed |
| cpu_percent | FLOAT | 0.0-100.0 |
| memory_percent | FLOAT | 0.0-100.0 |
| disk_percent | FLOAT | 0.0-100.0 |
| network_sent_mb | FLOAT | MB delta since last sample |
| network_received_mb | FLOAT | MB delta since last sample |

**Indexes:**
- ix_metrics_host_id (host_id)
- ix_metrics_host_id_timestamp (host_id, timestamp) — composite for efficient time-range queries

**Current Records:** 3,950 rows
**Data Sources:** monitoring_agent (LIVE) + scripts/simulate_fleet.py (SIMULATED)

---

## alert_rules Table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | VARCHAR(150) | Human-readable rule name |
| metric | VARCHAR(50) | cpu_percent / memory_percent / disk_percent / network_sent_mb / network_received_mb |
| operator | VARCHAR(10) | >, >=, <, <=, == |
| threshold | FLOAT | Breach boundary |
| severity | VARCHAR(20) | info / warning / critical |
| duration_seconds | INTEGER | Grace period (0=immediate) |
| is_enabled | BOOLEAN | Active/inactive toggle |
| environment | VARCHAR(50) | Nullable — scopes rule to environment |

**Current Records:** 6 rules (seeded on startup)
- High CPU (>85%, critical)
- High Memory (>90%, critical)
- High Disk (>85%, warning)
- Critical Disk (>92%, critical)
- Elevated CPU (>75%, warning)
- Elevated Memory (>80%, warning)

---

## alerts Table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| host_id | INTEGER FK | References hosts.id |
| rule_id | INTEGER FK | References alert_rules.id (nullable for ML alerts) |
| metric | VARCHAR(50) | Metric that triggered the alert |
| kind | VARCHAR(30) | threshold / anomaly / forecast / security |
| severity | VARCHAR(20) | info / warning / critical |
| message | VARCHAR(500) | Human-readable description |
| value | FLOAT | Metric value at trigger time |
| threshold | FLOAT | Rule threshold (nullable for anomaly alerts) |
| status | VARCHAR(30) | active / acknowledged / resolved |
| created_at | DATETIME | First trigger time |
| acknowledged_at | DATETIME | Nullable |
| resolved_at | DATETIME | Auto-set when metric normalizes |

**Indexes:**
- ix_alerts_dedup_lookup (host_id, metric, kind, status) — deduplication

**Current Records:** 156 alerts
- Mix of threshold and anomaly kind alerts
- Deduplication ensures 1 active alert per (host, metric, kind)

---

## security_events Table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| host_id | INTEGER FK | Nullable — references hosts.id |
| event_type | VARCHAR(100) | brute_force_ssh / port_scan / suspicious_egress / unauthorized_sudo / etc. |
| severity | VARCHAR(20) | low / medium / high / critical |
| source_ip | VARCHAR(45) | Attack source IP |
| destination_port | INTEGER | Target port |
| description | TEXT | Human-readable event detail |
| status | VARCHAR(30) | open / investigating / mitigated / false_positive |
| raw_evidence | TEXT | Log excerpts or technical evidence |
| timestamp | DATETIME | Event detection time |
| resolved_at | DATETIME | Nullable |

**Current Records:** 7 events (from simulation)
**Note:** source_ip is hardcoded to "10.0.1.45" for detector-generated events — see HARDCODED_DATA_AUDIT.md

---

## audit_logs Table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_email | VARCHAR(120) | Actor (default: system@ops.local) |
| action | VARCHAR(100) | ACK_ALERT / UPDATE_THRESHOLD / DISMISS_RECOMMENDATION / etc. |
| target_resource | VARCHAR(150) | Affected entity |
| details | TEXT | Change description |
| result | VARCHAR(30) | success / failure |
| client_ip | VARCHAR(45) | Nullable |
| timestamp | DATETIME | Action time |

**Current Records:** 0 (EMPTY)
**Issue:** API route handlers do not call audit_service.write() — audit trail is schema-only.

---

## pricing_catalog Table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| provider | VARCHAR(50) | AWS / GCP / Azure |
| region | VARCHAR(50) | us-east-1 etc. |
| instance_type | VARCHAR(50) | t3.micro / c5.large / etc. |
| vcpus | INTEGER | vCPU count |
| memory_gb | FLOAT | RAM in GB |
| hourly_rate_usd | FLOAT | Per-hour cost |
| currency | VARCHAR(10) | USD |

**Current Records:** 20 entries (CONFIGURATION — seeded from STANDARD_PRICING_CATALOG)
**Classification:** CONFIGURATION (reference pricing, not live billing)

---

## cost_recommendations Table

**Current Records:** 0
**Note:** Generated on-demand when /api/v1/cost/summary is called.
The service persists recommendations to DB only if none exist for the host.
This means the table populates on first cost summary call.

---

## Data Quality Checks

| Check | Result |
|-------|--------|
| Duplicate metrics | ACCEPTABLE — deduplication not required for time-series |
| Missing timestamps | NONE — all rows have timestamp |
| Invalid host IDs | NONE — FK constraints enforced |
| NULL cpu/memory/disk values | NONE — columns are NOT NULL |
| Impossible metric ranges | NONE — values in range 0-100% |
| Future timestamps | NONE FOUND |
| Stale data | YES — some hosts may have stale metrics if agent stopped |
| Host-Metric relationship | VALID — all metric.host_id references exist in hosts |
"""

# ============================================================
# ML_MODEL_AUDIT.md
# ============================================================
ML_MODEL_AUDIT = """# ML MODEL AUDIT

**Audit Date:** 2026-09-23

---

## Model 1: LSTM Autoencoder (Anomaly Detection)

| Field | Details |
|-------|---------|
| Model Name | best_lstm_anomaly_detector |
| File | models/best_lstm_anomaly_detector.pt |
| Framework | PyTorch |
| Architecture | LSTM Autoencoder (Encoder-Decoder) |
| Purpose | Detect anomalous time windows by measuring reconstruction error |
| Input | 3D tensor: (batch, seq_len=15, n_features=30) |
| Output | Reconstruction of input; anomaly = MSE reconstruction error > threshold |
| Encoder | LSTM(30->64) -> Dropout(0.2) -> LSTM(64->32) -> latent vector (32-dim) |
| Decoder | Repeat latent (1,15,32) -> LSTM(32->64) -> Dropout(0.2) -> Linear(64->30) |
| Parameters | ~196,000 (estimated from architecture) |
| Training Dataset | Cloud_Anomaly_Dataset.csv (37MB) — processed into sequences |
| Train Samples | sequences_data.npz X_train shape |
| Features | 30 features (see selected_features.json) |
| Optimizer | Adam (lr=0.001, weight_decay=1e-5) |
| Loss Function | MSE (reconstruction loss) |
| Batch Size | 64 |
| Epochs Trained | 25 (all 25 completed, no early stopping triggered) |
| Best Val Loss | 0.3689 (epoch 22) |
| Anomaly Threshold | 0.7914 (optimal F1 from threshold sweep, models/evaluation_metrics.json) |

### Actual Performance Metrics (from models/evaluation_metrics.json)

These are REPRODUCED from actual experiment — NOT invented:

| Metric | Value | Notes |
|--------|-------|-------|
| ROC-AUC | 0.6106 | Threshold-independent ranking metric |
| PR-AUC | 0.4795 | Threshold-independent average precision |
| Best F1 Threshold | 0.7914 (MSE cutoff) | Selected by maximizing F1 |
| Accuracy at best threshold | 0.4206 (42.1%) | Low due to high FP rate |
| Precision at best threshold | 0.3830 (38.3%) | Low precision — many false positives |
| Recall at best threshold | 0.9344 (93.4%) | High recall — catches most anomalies |
| F1-Score at best threshold | 0.5433 (54.3%) | Best achievable F1 |
| TP | 1,039 | Correctly detected anomalies |
| FP | 1,674 | False alarms |
| TN | 229 | Correctly classified normal |
| FN | 73 | Missed anomalies |
| FPR | 0.8797 | High false positive rate at best-recall threshold |

**Interpretation:** The LSTM achieves good recall (93.4%) but at the cost of high false positives (FPR=88%).
The ROC-AUC of 0.61 suggests moderate discriminative power — better than random (0.5) but not excellent.
The dataset imbalance and complexity of cloud metrics contribute to this behavior.

**CRITICAL NOTE:** Previously reported numbers of "99.31% detection", "144/145 incidents", "0.78 minute latency",
"93.44% recall" cannot be verified from this evaluation. The actual reproduced recall is 0.9344 (93.4% at the
best F1 threshold — close to the claimed value). The other numbers are NOT reproducible from current files
and should be treated as: "Previously reported result — not independently reproducible from current repository."

---

## Model 2: Production Isolation Forest

| Field | Details |
|-------|---------|
| Model Name | production_cloud_anomaly_model |
| File | models/production_cloud_anomaly_model_v1.joblib |
| Framework | scikit-learn |
| Algorithm | IsolationForest |
| Purpose | Multivariate anomaly detection in live metric pipeline |
| Input | 5 features: [cpu_percent, memory_percent, disk_percent, network_sent_mb, network_received_mb] |
| Output | is_anomaly: bool, anomaly_score: 0.0-1.0, feature_contributions |
| Training Samples | 222,056 |
| Contamination | 0.06 (6% expected anomaly rate) |
| Trained At | 2026-09-11 |
| Baseline Mean | cpu=50.03%, mem=49.95%, disk=50.02%, net_sent=0.49MB, net_recv=250.02MB |
| Status | ACTIVE — loaded by ai_service.py at startup |

**Note:** The production_cloud_anomaly_model is NOT currently loaded by ai_service.py.
The active model is fleet_anomaly_detector_v1 (only 10 samples). This is a gap.

---

## Model 3: Fleet Isolation Forest

| Field | Details |
|-------|---------|
| Model Name | fleet_anomaly_detector |
| File | models/fleet_anomaly_detector_v1.joblib |
| Framework | scikit-learn |
| Algorithm | IsolationForest |
| Training Samples | 10 (from live DB) |
| Contamination | 0.05 |
| Trained At | 2026-09-23 |
| Status | ACTIVE (loaded by ai_service.py) but PRACTICALLY INVALID — 10 samples |

**CRITICAL WARNING:** This model has been trained on only 10 database samples.
With contamination=0.05 and 10 samples, the IsolationForest will classify 0-1 samples as anomalies.
Any anomaly detection from this model should be considered UNRELIABLE until retrained with
sufficient data (minimum 1,000+ samples recommended).

**RECOMMENDATION:** Load production_cloud_anomaly_model_v1.joblib as the default, or retrain
fleet_anomaly_detector on all 3,950+ available DB metrics.

---

## Model 4: Linear Regression Forecaster

| Field | Details |
|-------|---------|
| Implementation | ai_engine/forecaster.py (TimeSeriesForecaster) |
| Algorithm | Ordinary Least Squares (numpy.linalg.lstsq) |
| Purpose | Project future metric values and estimate time-to-threshold |
| Input | List of (timestamp, value) pairs from metrics table |
| Output | forecast_points, trend_slope_per_hour, time_to_threshold |
| Confidence Intervals | 1.96 * residual_std (growing with forecast horizon) |
| Model Status | COMPUTED ON DEMAND — no saved model file |
| Status | LIVE — connected to real DB metrics |
"""

# ============================================================
# LSTM_MODEL_REPORT.md
# ============================================================
LSTM_MODEL_REPORT = """# LSTM MODEL REPORT

**Audit Date:** 2026-09-23
**Model:** LSTM Autoencoder for Cloud Infrastructure Anomaly Detection

---

## Architecture

```
Input: (batch_size, seq_len=15, n_features=30)
          |
    ENCODER LSTM 1
    LSTM(input=30, hidden=64, batch_first=True)
          |
    Dropout(p=0.2)
          |
    ENCODER LSTM 2
    LSTM(input=64, hidden=32, batch_first=True)
          |
    Extract final hidden state hn: (1, batch, 32)
          |
    Permute + Repeat across seq_len: (batch, 15, 32)
          |
    DECODER LSTM 1
    LSTM(input=32, hidden=64, batch_first=True)
          |
    Dropout(p=0.2)
          |
    Linear(64 -> 30)
          |
Output: (batch_size, seq_len=15, n_features=30)
          |
    MSE Reconstruction Error per sample
          |
    Anomaly Score = error > threshold (0.7914)
```

---

## Training Configuration

| Parameter | Value |
|-----------|-------|
| Sequence Length | 15 time steps |
| Features | 30 (from selected_features.json) |
| Hidden Dimension (Encoder) | 64 |
| Latent Dimension | 32 |
| Dropout | 0.2 (both encoder and decoder) |
| Optimizer | Adam |
| Learning Rate | 0.001 (with ReduceLROnPlateau: factor=0.5, patience=3) |
| Weight Decay | 1e-5 |
| Loss Function | MSELoss (reconstruction) |
| Epochs | 25 |
| Early Stopping Patience | 7 (not triggered — all 25 epochs completed) |
| Batch Size | 64 |
| Gradient Clipping | max_norm=1.0 |
| Device | CPU (no GPU detected during training) |

---

## Training History (from models/training_history.json)

| Epoch | Train Loss | Val Loss |
|-------|-----------|----------|
| 1 | 0.6751 | 0.5456 |
| 5 | 0.5063 | 0.4350 |
| 10 | 0.4644 | 0.4106 |
| 15 | 0.4416 | 0.3879 |
| 20 | 0.4328 | 0.3765 |
| 22 | 0.4241 | 0.3689 (BEST) |
| 25 | 0.4197 | 0.3789 |

**Best Val Loss:** 0.3689 at epoch 22
**Observation:** Validation loss improved steadily, with slight overfitting at epoch 23-25.

---

## Anomaly Threshold Selection

The anomaly threshold was selected by:
1. Computing reconstruction errors on validation set
2. Computing reconstruction errors on test set
3. Evaluating multiple threshold candidates (percentile-based + linear sweep)
4. Selecting threshold that maximizes F1-Score on test set

**Optimal Threshold:** 0.7914 (MSE reconstruction error cutoff)
**Selection Strategy:** "Sweep-0.791" — from linear sweep over test error distribution

---

## Actual Evaluation Results (REPRODUCED from models/evaluation_metrics.json)

> These numbers are REPRODUCED from the actual saved evaluation file.
> They are NOT invented.

### Best Threshold Performance (threshold = 0.7914)

| Metric | Value |
|--------|-------|
| Accuracy | 42.1% |
| Precision | 38.3% |
| Recall | 93.4% |
| F1-Score | 54.3% |
| ROC-AUC | 61.1% |
| PR-AUC | 47.9% |
| True Positives | 1,039 |
| False Positives | 1,674 |
| True Negatives | 229 |
| False Negatives | 73 |
| FPR (False Positive Rate) | 87.97% |
| FNR (False Negative Rate) | 6.56% |

### Test Set Composition
- Total samples: 3,015 (TP+FP+TN+FN = 1039+1674+229+73)
- Anomaly samples (positive class): 1,112 (36.9%)
- Normal samples (negative class): 1,903 (63.1%)

### Confusion Matrix (At Optimal Threshold 0.7914)

```
                Predicted Normal  Predicted Anomaly
Actual Normal        229               1674
Actual Anomaly        73               1039
```

---

## Threshold Sensitivity Analysis

| Threshold Strategy | Threshold | Precision | Recall | F1 | FPR |
|-------------------|-----------|-----------|--------|-----|-----|
| Val-90th percentile | 0.5854 | 36.9% | 100.0% | 53.9% | 100% |
| Val-95th percentile | 0.9295 | 41.7% | 75.4% | 53.7% | 61.5% |
| Sweep-0.791 (OPTIMAL) | 0.7914 | 38.3% | 93.4% | 54.3% | 88.0% |
| Val-98th percentile | 1.5705 | 47.4% | 22.4% | 30.4% | 14.5% |
| Val-99th percentile | 3.7618 | 59.0% | 12.4% | 20.5% | 5.0% |
| Val-Max | 10.117 | 59.6% | 8.9% | 15.5% | 3.5% |

---

## Claims Verification

| Claimed Result | Reproducible? | Actual Result |
|---------------|---------------|---------------|
| 99.31% detection | NO — not reproducible | Best recall = 93.4% at threshold 0.7914 |
| 144/145 incidents detected | NO — not in any file | Cannot verify |
| 0.78 minute detection latency | NO — not measured | Inference is near-real-time (<1 second per batch) |
| 93.44% recall | PARTIALLY — close | Actual recall = 93.44% at best-F1 threshold |
| Confusion matrix with ~99% accuracy | NO | Actual accuracy = 42.1% at best-F1 threshold |

**CONCLUSION:** The recall figure of 93.4% is reproducible. Other performance numbers cannot be
independently reproduced from the current repository state.

---

## LSTM in Live System

**Current Status:** NOT CONNECTED TO LIVE ALERTING PIPELINE

The LSTM is evaluated in standalone scripts (step10_11_12_evaluation_threshold_tuning.py,
realtime_inference_engine.py). The live alerting pipeline uses the Isolation Forest model
(fleet_anomaly_detector_v1.joblib) via ai_engine/anomaly_detector.py.

To connect LSTM to live alerting would require:
1. Loading best_lstm_anomaly_detector.pt in ai_service.py
2. Preprocessing incoming metrics into 15-step sequences
3. Computing per-sample reconstruction errors
4. Comparing against threshold 0.7914
5. Triggering alert creation if threshold exceeded
"""

# ============================================================
# ANOMALY_DETECTION_GUIDE.md
# ============================================================
ANOMALY_DETECTION_GUIDE = """# ANOMALY DETECTION GUIDE

**Audit Date:** 2026-09-23

---

## Overview

The platform implements THREE layers of anomaly detection:

```
Telemetry (psutil / Simulator)
          |
    Preprocessing
  (normalizing + feature extraction)
          |
    Feature Vector [cpu, mem, disk, net_sent, net_recv]
          |
    +--------------------+
    | Threshold Detection|
    +--------------------+
             +
    +--------------------+
    | ML Anomaly Detector| (Isolation Forest)
    | (LIVE)             |
    +--------------------+
             +
    +--------------------+
    | LSTM Autoencoder   | (STANDALONE — not in live pipeline)
    +--------------------+
          |
    Anomaly Score
          |
    Severity (warning >= 0.60, critical >= 0.80)
          |
    Alert (deduplication check)
          |
    Incident Correlation (Narrator)
          |
    Dashboard
          |
    AI Narrator
```

---

## Layer 1: Threshold Detection

**Implementation:** backend/app/services/alert_service.py::evaluate_metric_sample()
**Type:** Rule-based / signature-based
**Status:** LIVE

### How It Works:
1. When a metric sample is ingested via POST /api/v1/metrics
2. alert_service fetches all enabled AlertRules from DB
3. For each rule, evaluates: metric_value OPERATOR threshold
   - Example: cpu_percent > 85.0 (critical)
4. If rule condition is BREACHED:
   - Check for existing active alert for (host_id, metric, 'threshold')
   - If exists: UPDATE existing alert (deduplication)
   - If not exists: CREATE new alert
5. If rule condition is NOT BREACHED but alert is active:
   - AUTO-RESOLVE the alert (status='resolved', resolved_at=now)

### Default Rules (seeded on startup):
| Rule | Metric | Operator | Threshold | Severity |
|------|--------|----------|-----------|---------|
| High CPU | cpu_percent | > | 85.0 | critical |
| High Memory | memory_percent | > | 90.0 | critical |
| High Disk | disk_percent | > | 85.0 | warning |
| Critical Disk | disk_percent | > | 92.0 | critical |
| Elevated CPU | cpu_percent | > | 75.0 | warning |
| Elevated Memory | memory_percent | > | 80.0 | warning |

### Advantages:
- Deterministic and explainable
- Low latency (DB query + comparison)
- Zero false positives for known patterns
- Configurable by operators

### Disadvantages:
- Cannot detect complex multi-metric patterns
- Cannot detect slow-burn anomalies
- Cannot adapt to changing baselines

---

## Layer 2: ML Anomaly Detection (Isolation Forest)

**Implementation:** ai_engine/anomaly_detector.py::MultivariateAnomalyDetector
**Type:** Unsupervised ML — isolation-based anomaly scoring
**Status:** LIVE (but fleet model trained on only 10 samples — see ML_MODEL_AUDIT.md)

### Algorithm: Isolation Forest

1. Build an ensemble of isolation trees from normal training data
2. For each tree, randomly select a feature and a split value
3. Samples that are isolated in fewer splits are more anomalous
4. decision_function() returns a score where negative = anomalous

### Implementation Flow:
1. Metric sample arrives at ingest_metric()
2. ai_service::evaluate_and_record_ai_anomaly(db, host, metric) is called
3. MultivariateAnomalyDetector::score_sample(sample) is called
4. Extract 5-feature vector: [cpu, mem, disk, net_sent, net_recv]
5. StandardScaler transform (fitted during training)
6. IsolationForest.decision_function() returns decision score
7. Map to anomaly_score: base_score = 0.5 - (decision_score * 1.2)
8. Clip to [0.0, 1.0]
9. is_anomaly = anomaly_score >= 0.60
10. If anomaly: severity = critical if score >= 0.80, else warning
11. Create/update alert in DB with kind='anomaly'

### Feature Attribution (Explainability):
- Computes z-score deviation: (value - baseline_mean) / baseline_std
- Ranks features by absolute deviation
- Generates plain English explanation: "CPU is 2.3 standard deviations above baseline"

### Sensitivity Calibration (M2-FR7):
- Operator can submit feedback: true_positive or false_positive
- false_positive: sensitivity_offset -= 0.05 (reduces future anomaly scores)
- true_positive: sensitivity_offset += 0.025 (increases alertness)
- Offset bounded to [-0.25, +0.25]

---

## Layer 3: LSTM Autoencoder (Standalone)

**Implementation:** step8_9_train_lstm.py, step10_11_12_evaluation_threshold_tuning.py
**Type:** Deep learning — sequence reconstruction
**Status:** STANDALONE — not integrated in live pipeline

### Algorithm: LSTM Autoencoder

1. Encoder compresses input sequence (15 time steps, 30 features) to 32-dim latent vector
2. Decoder reconstructs original sequence from latent vector
3. Anomaly score = MSE(original, reconstructed) per sample
4. If MSE > threshold (0.7914): ANOMALY

### Why LSTM for Anomaly Detection:
- Learns temporal dependencies in time-series data
- Normal sequences have low reconstruction error
- Anomalous sequences deviate from learned patterns -> high reconstruction error
- Suitable for cloud infrastructure where metrics have strong temporal autocorrelation

### Actual Performance:
- Recall: 93.4% (catches most real anomalies)
- Precision: 38.3% (high false positive rate)
- F1: 54.3%
- ROC-AUC: 61.1%

---

## Comparison: Threshold vs. ML vs. LSTM

| Dimension | Threshold | Isolation Forest | LSTM Autoencoder |
|-----------|-----------|-----------------|-----------------|
| Type | Rule-based | Unsupervised ML | Deep Learning |
| Status | LIVE | LIVE (weak model) | STANDALONE |
| Training required | NO | YES | YES |
| Pattern detection | Single-metric | Multivariate | Temporal sequences |
| Interpretability | HIGH | MEDIUM (feature attribution) | LOW (reconstruction error) |
| Sensitivity to new patterns | LOW | MEDIUM | HIGH |
| False positive control | HIGH | MEDIUM | LOW (high FPR) |
| Latency | <1ms | <10ms | <100ms |
| Requires historical data | NO | YES (>=5 samples) | YES (sequences) |
| Best for | Known thresholds | Complex multi-metric patterns | Temporal behavior |
"""

# ============================================================
# SECURITY_IMPLEMENTATION_AUDIT.md
# ============================================================
SECURITY_AUDIT = """# SECURITY IMPLEMENTATION AUDIT

**Audit Date:** 2026-09-23

---

## Executive Summary

The platform has basic security controls adequate for a development/demo environment. Several critical
production security requirements are NOT implemented, including authentication, authorization, and RBAC.

---

## Findings

### CRITICAL Findings

| ID | Finding | File | Risk | Evidence | Recommended Fix |
|----|---------|------|------|----------|-----------------|
| SEC-001 | No authentication implemented | backend/app/main.py | CRITICAL | No authentication middleware; all endpoints are publicly accessible | Implement JWT/OAuth2 authentication |
| SEC-002 | No authorization / RBAC | All API endpoints | CRITICAL | Any request can ACK alerts, delete rules, retrain models | Implement role-based access control |
| SEC-003 | CORS allows all origins | backend/app/main.py:45 | CRITICAL | allow_origins=["*"] | Restrict to known frontend origins in production |
| SEC-004 | Hardcoded secret key | backend/app/core/config.py:20 | HIGH | secret_key: str = "change-this-in-production" | Enforce secret key from env var; fail startup if default |

### HIGH Findings

| ID | Finding | File | Risk | Evidence | Recommended Fix |
|----|---------|------|------|----------|-----------------|
| SEC-005 | Hardcoded source IP in security events | security_engine/detector.py:54 | HIGH | source_ip = "10.0.1.45" | Use actual source from network flow |
| SEC-006 | No rate limiting | All POST endpoints | HIGH | No throttling on /api/v1/metrics — potential DoS | Implement SlowAPI or similar |
| SEC-007 | No input size limits on text fields | schemas/ | HIGH | Narrator query could accept arbitrary text | Add max_length validators |
| SEC-008 | AI prompt injection potential | narrator/engine.py | HIGH | Query string passed directly — no sanitization | Sanitize query input; bound LLM context |

### MEDIUM Findings

| ID | Finding | File | Risk | Evidence | Recommended Fix |
|----|---------|------|------|----------|-----------------|
| SEC-009 | Debug mode enabled by default | backend/app/core/config.py:13 | MEDIUM | debug: bool = True | Disable in production; use env var |
| SEC-010 | Audit log table empty | audit_logs table | MEDIUM | 0 records — no operator actions logged | Wire audit writes into API handlers |
| SEC-011 | No HTTPS enforcement | docker-compose.yml | MEDIUM | Plain HTTP; no TLS config | Add TLS termination (nginx + certbot) |
| SEC-012 | Error messages may leak internal details | FastAPI default behavior | MEDIUM | HTTPException includes internal error text | Custom error handlers in production |

### LOW / INFORMATIONAL

| ID | Finding | Risk | Evidence | Status |
|----|---------|------|----------|--------|
| SEC-013 | XSS prevention | LOW | frontend/js/sanitizer.js implements escapeHtml() consistently | MITIGATED |
| SEC-014 | SQL injection | LOW | All DB access via SQLAlchemy ORM with parameterized queries | MITIGATED |
| SEC-015 | Sensitive data in logs | LOW | Metric values logged but no passwords/keys | ACCEPTABLE |
| SEC-016 | LLM API keys not set | INFO | .env has empty OPENAI/GEMINI keys | NO RISK (feature disabled) |
| SEC-017 | AWS/Azure credentials not set | INFO | Empty in .env | NO RISK |
| SEC-018 | Path traversal | LOW | Static file mounting restricted to frontend/ | MITIGATED |

---

## Secret/Key Scan Results

The following secret-like patterns were found in the codebase:

| Pattern | Location | Sensitive? | Status |
|---------|----------|-----------|--------|
| SECRET_KEY=change-me-to-a-secure-secret-key-in-production | .env.example | Template only | SAFE (example) |
| secret_key: str = "change-this-in-production" | backend/app/core/config.py | DEFAULT VALUE | WARNING — must be overridden |
| POSTGRES_PASSWORD: postgrespassword | docker-compose.yml | Demo password | WARNING for production |
| OPENAI_API_KEY= | .env | Empty | SAFE |
| GEMINI_API_KEY= | .env | Empty | SAFE |
| AWS_ACCESS_KEY_ID= | .env | Empty | SAFE |

**NO REAL SECRETS FOUND IN REPOSITORY.**

---

## XSS Prevention

The frontend implements a comprehensive XSS sanitizer in `frontend/js/sanitizer.js`:
- `escapeHtml()` — converts <, >, ", ', & to HTML entities
- Applied consistently to all user-originated data before DOM insertion
- All views use `escapeHtml()` on hostnames, messages, descriptions

**STATUS: ADEQUATELY MITIGATED for current threat model**

---

## SQL Injection Prevention

All database access uses SQLAlchemy ORM with parameterized queries.
No raw SQL string construction found.

**STATUS: MITIGATED**

---

## LLM Output Validation (Narrator)

The narrator engine is currently DETERMINISTIC (no LLM calls).
When LLM is integrated, hallucination controls needed:
- Ground all claims in DB records
- Cite specific alert/event IDs
- Add disclaimer (already present in response)
- Limit output token length
- Validate output contains only expected markdown

**STATUS: DETERMINISTIC MODE — LLM RISKS NOT APPLICABLE YET**
"""

# ============================================================
# MASTER_PLAN_TRACEABILITY.md
# ============================================================
MASTER_TRACEABILITY = """# MASTER PLAN TRACEABILITY

**Audit Date:** 2026-09-23
**Reference:** Master_Requirements_Architecture_Design_Document.docx

---

## M1: Resource Monitoring

| Requirement | Description | Implementation | File | Test | Status |
|------------|-------------|----------------|------|------|--------|
| M1-FR1 | Collect CPU, Memory, Disk, Network metrics | psutil-based SystemCollector | monitoring_agent/collector.py | test_agent_buffer.py | COMPLETED |
| M1-FR2 | Auto-discover and register hosts | get_or_create_host() on first metric | backend/app/services/host_service.py | test_host_service.py | COMPLETED |
| M1-FR3 | Configurable polling interval | --interval arg + POLL_INTERVAL env | monitoring_agent/agent.py | Manual | COMPLETED |
| M1-FR4 | Retry with exponential backoff | MetricBuffer with consecutive_failures | monitoring_agent/buffer.py | test_agent_buffer.py | COMPLETED |
| M1-FR5 | Multi-host fleet support | Fleet simulator + agent per host | scripts/simulate_fleet.py | test_api_v1.py | COMPLETED |
| M1-NFR1 | Local buffering during outages | Ring buffer up to 5000 samples | monitoring_agent/buffer.py | test_agent_buffer.py | COMPLETED |
| M1-NFR2 | Distinguish Live/Simulated data | Simulator in separate scripts/ dir | N/A | Manual | COMPLETED |

---

## M2: AI Anomaly Detection & Prediction

| Requirement | Description | Implementation | File | Test | Status |
|------------|-------------|----------------|------|------|--------|
| M2-FR1 | Isolation Forest anomaly detection | MultivariateAnomalyDetector | ai_engine/anomaly_detector.py | test_ai_anomaly.py | COMPLETED |
| M2-FR2 | Real-time anomaly scoring on ingestion | evaluate_and_record_ai_anomaly() | backend/app/services/ai_service.py | test_ai_anomaly.py | COMPLETED |
| M2-FR3 | Time-series forecasting | TimeSeriesForecaster (OLS) | ai_engine/forecaster.py | test_forecaster.py | COMPLETED |
| M2-FR4 | LSTM Autoencoder training | LSTMAutoencoder architecture | step8_9_train_lstm.py | Manual | COMPLETED (standalone) |
| M2-FR5 | Model persistence and registry | ModelRegistry with joblib | ai_engine/model_registry.py | test_ai_anomaly.py | COMPLETED |
| M2-FR6 | Feature attribution explainability | FeatureAttributionEngine | ai_engine/explainability.py | test_explainability.py | COMPLETED |
| M2-FR7 | Sensitivity calibration via feedback | sensitivity_offset adjustment | ai_engine/anomaly_detector.py | test_ai_anomaly.py | COMPLETED |
| M2-NFR1 | Heuristic fallback if untrained | _heuristic_fallback() | ai_engine/anomaly_detector.py | test_ai_anomaly.py | COMPLETED |
| LSTM-Connected | LSTM integrated in live alerting | NOT IMPLEMENTED | N/A | N/A | NOT IMPLEMENTED |

---

## M3: Cost Optimization

| Requirement | Description | Implementation | File | Test | Status |
|------------|-------------|----------------|------|------|--------|
| M3-FR1 | Instance spend calculation | CostCalculator.get_instance_monthly_cost() | cost_engine/calculator.py | test_cost_engine.py | COMPLETED (ESTIMATED) |
| M3-FR2 | Idle resource detection | avg_cpu < 5% AND avg_mem < 25% | cost_engine/calculator.py | test_cost_engine.py | COMPLETED |
| M3-FR3 | Rightsizing recommendations | evaluate_rightsizing() | cost_engine/calculator.py | test_cost_engine.py | COMPLETED |
| M3-FR4 | Pricing catalog | STANDARD_PRICING_CATALOG (20 types) | cost_engine/calculator.py | Manual | COMPLETED (CONFIGURATION) |
| M3-FR5 | Recommendation persistence | CostRecommendation model in DB | backend/app/models/cost.py | test_cost_engine.py | COMPLETED |
| M3-FR6 | Accept/dismiss recommendations | update_recommendation_status() | backend/app/services/cost_service.py | test_api_v1_expanded.py | COMPLETED |
| M3-FR7 | Cost per environment breakdown | spend_by_environment in response | cost_service.py | Manual | COMPLETED |
| BILLING | Real cloud billing integration | NOT IMPLEMENTED | N/A | N/A | NOT IMPLEMENTED |

---

## M4: Intrusion Detection

| Requirement | Description | Implementation | File | Test | Status |
|------------|-------------|----------------|------|------|--------|
| M4-FR1 | Security event storage | SecurityEvent model | backend/app/models/security.py | test_security_engine.py | COMPLETED |
| M4-FR2 | Suspicious egress detection | analyze_network_sample() | security_engine/detector.py | test_security_engine.py | PARTIALLY COMPLETED |
| M4-FR3 | Security event status management | update_security_event_status() | backend/app/services/security_service.py | test_api_v1_expanded.py | COMPLETED |
| M4-FR4 | Audit log model | AuditLog model (schema only) | backend/app/models/security.py | test_database.py | PARTIALLY COMPLETED |
| M4-FR5 | Brute force / port scan detection | Signatures defined, NOT auto-triggered | security_engine/detector.py | N/A | NOT IMPLEMENTED (auto-trigger) |
| M4-FR6 | Log stream integration | NOT IMPLEMENTED | N/A | N/A | NOT IMPLEMENTED |
| M4-FR7 | Behavioral anomaly detection | NOT IMPLEMENTED | N/A | N/A | NOT IMPLEMENTED |

---

## M5: AI Incident Narrator

| Requirement | Description | Implementation | File | Test | Status |
|------------|-------------|----------------|------|------|--------|
| M5-FR1 | Cross-module signal correlation | analyze_incident() | narrator/engine.py | test_narrator_engine.py | COMPLETED |
| M5-FR2 | Evidence-grounded narrative | Citations in response | narrator/engine.py | test_narrator_engine.py | COMPLETED |
| M5-FR3 | Alert + Security + Cost correlation | Queries all three domains | narrator/engine.py | test_narrator_engine.py | COMPLETED |
| M5-FR4 | Time-to-threshold forecast | TimeSeriesForecaster | ai_engine/forecaster.py | test_forecaster.py | COMPLETED |
| M5-FR5 | Feature attribution in alerts | FeatureAttributionEngine | ai_engine/explainability.py | test_explainability.py | COMPLETED |
| M5-FR6 | Operator feedback recording | AlertFeedback model + API | backend/app/models/alert.py | test_alert_engine.py | COMPLETED |
| M5-FR7 | LLM-powered narrative generation | NOT IMPLEMENTED (no API keys) | N/A | N/A | NOT IMPLEMENTED |
| M5-FR8 | Disclaimer on AI outputs | disclaimer field in response | narrator/engine.py | test_narrator_engine.py | COMPLETED |

---

## Authentication / RBAC

| Requirement | Status |
|------------|--------|
| JWT Authentication | NOT IMPLEMENTED |
| Role-Based Access Control | NOT IMPLEMENTED |
| API Key Management | NOT IMPLEMENTED |
| Session Management | NOT IMPLEMENTED |

---

## Alerting

| Requirement | Status |
|------------|--------|
| Threshold rules with operators | COMPLETED |
| Deduplication | COMPLETED |
| Auto-resolution | COMPLETED |
| Alert acknowledgment | COMPLETED |
| Operator feedback | COMPLETED |
| Webhook/email notifications | NOT IMPLEMENTED |

---

## Overall Status Summary

| Module | Status |
|--------|--------|
| M1 Resource Monitoring | COMPLETED |
| M2 AI Anomaly Detection | PARTIALLY COMPLETED (LSTM standalone, IF active) |
| M3 Cost Optimization | PARTIALLY COMPLETED (no real billing) |
| M4 Intrusion Detection | PARTIALLY COMPLETED (egress only) |
| M5 AI Narrator | PARTIALLY COMPLETED (deterministic, no LLM) |
| Authentication | NOT IMPLEMENTED |
| RBAC | NOT IMPLEMENTED |
| Audit Trail | PARTIALLY COMPLETED (schema only, no writes) |
| Notifications | NOT IMPLEMENTED |
| Deployment (Docker) | PARTIALLY COMPLETED (no Dockerfiles) |
"""

# ============================================================
# REMAINING_MASTER_PLAN.md
# ============================================================
REMAINING_PLAN = """# REMAINING MASTER PLAN

**Audit Date:** 2026-09-23

---

## COMPLETED

- [x] Monitoring agent with psutil (CPU, MEM, DISK, NET)
- [x] Auto-host discovery on metric ingestion
- [x] Configurable polling interval
- [x] Ring buffer with exponential backoff
- [x] Fleet simulator (SIMULATED — separate from live agent)
- [x] Threshold-based alert rules (create/delete/update)
- [x] Alert deduplication policy
- [x] Alert auto-resolution
- [x] Alert acknowledgment workflow
- [x] Operator feedback (TP/FP) for sensitivity calibration
- [x] Isolation Forest multivariate anomaly detector
- [x] Feature attribution explainability
- [x] Sensitivity offset calibration
- [x] Heuristic fallback when model untrained
- [x] Model persistence and registry (joblib)
- [x] Linear regression forecaster with confidence intervals
- [x] Time-to-threshold calculation
- [x] LSTM Autoencoder training (standalone)
- [x] LSTM threshold tuning (standalone)
- [x] Cost engine with pricing catalog
- [x] Idle host detection
- [x] Rightsizing recommendations
- [x] Security event persistence and status management
- [x] Egress spike detection (basic)
- [x] Cross-module incident narrator (deterministic)
- [x] Evidence-grounded narrative with citations
- [x] Executive report generation
- [x] Complete REST API (28+ endpoints)
- [x] All frontend views (11 pages)
- [x] 44 passing unit tests
- [x] XSS prevention (sanitizer.js)
- [x] SQL injection prevention (ORM)

---

## PARTIALLY COMPLETED

- [ ] LSTM connected to live alerting pipeline
  - WHAT EXISTS: Standalone training + evaluation scripts
  - WHAT REMAINS: Load LSTM in ai_service.py, preprocess 15-step sequences, trigger alerts from reconstruction errors
  - COMPLEXITY: HIGH
  - DEFINITION OF DONE: LSTM scores every incoming metric sample; creates anomaly alerts; visible in dashboard

- [ ] Fleet Isolation Forest adequately trained
  - WHAT EXISTS: fleet_anomaly_detector_v1 trained on 10 samples
  - WHAT REMAINS: Retrain on all 3,950+ DB samples OR load production_cloud_anomaly_model_v1
  - COMPLEXITY: LOW
  - DEFINITION OF DONE: Active model trained on >=1000 representative samples

- [ ] Security detection auto-triggered from metrics
  - WHAT EXISTS: Egress spike detector in security_engine/detector.py
  - WHAT REMAINS: Call analyze_network_sample() during metric ingestion; auto-create SecurityEvent
  - COMPLEXITY: LOW
  - DEFINITION OF DONE: Large network_sent_mb metric auto-creates security event in DB

- [ ] Audit trail writes
  - WHAT EXISTS: AuditLog model + schema + get endpoint
  - WHAT REMAINS: Write audit records in API handlers (ACK alert, delete rule, update status)
  - COMPLEXITY: LOW
  - DEFINITION OF DONE: Every operator action generates an audit_logs row

- [ ] Cost recommendations auto-updated
  - WHAT EXISTS: Generated on /cost/summary call
  - WHAT REMAINS: Schedule periodic recalculation or trigger on host metric change
  - COMPLEXITY: MEDIUM

---

## REMAINING (NOT IMPLEMENTED)

### Authentication & RBAC
- **Why needed:** Prevent unauthorized access to all endpoints
- **Dependency:** FastAPI security, JWT library
- **Files:** backend/app/api/deps.py (partial), all route files
- **Complexity:** MEDIUM-HIGH
- **DoD:** All routes require valid JWT; roles: admin, operator, readonly

### LLM-Powered Narrator
- **Why needed:** Natural language incident reports beyond deterministic templates
- **Dependency:** OpenAI/Gemini/Anthropic API key
- **Files:** narrator/engine.py, narrator_service.py
- **Complexity:** MEDIUM
- **DoD:** User query returns LLM-generated narrative grounded in DB evidence

### Brute Force / Port Scan Detection
- **Why needed:** Critical for M4 intrusion detection
- **Dependency:** Authentication log stream (SSH, system logs)
- **Files:** security_engine/detector.py, metric_service.py
- **Complexity:** HIGH (requires log ingestion pipeline)
- **DoD:** SSH failed login events auto-trigger brute_force_ssh security event

### Real Cloud Billing Integration
- **Why needed:** Actual cost data instead of estimates
- **Dependency:** AWS Cost Explorer API / GCP Billing API
- **Files:** cost_engine/, backend services
- **Complexity:** HIGH
- **DoD:** Costs labeled ACTUAL BILLING; sourced from cloud provider API

### Docker Deployment
- **Why needed:** Reproducible deployment
- **Dependency:** None (just create Dockerfiles)
- **Files:** backend/Dockerfile, monitoring_agent/Dockerfile, frontend/Dockerfile
- **Complexity:** LOW
- **DoD:** docker-compose up starts all services; monitoring agent connects and sends metrics

### Webhook/Email Notifications
- **Why needed:** Operator awareness without dashboard
- **Dependency:** SMTP server or webhook URL
- **Files:** backend services, .env config
- **Complexity:** MEDIUM
- **DoD:** Critical alert triggers email or Slack webhook

### What-If Simulation
- **Why needed:** Capacity planning
- **Dependency:** Cost engine + forecaster
- **Files:** New api endpoint, frontend view
- **Complexity:** MEDIUM
- **DoD:** User inputs hypothetical metrics; sees projected cost + anomaly risk

---

## OPTIONAL FUTURE WORK

- Prometheus/Grafana integration for production observability
- Kubernetes operator for auto-scaling based on predictions
- Multi-tenant architecture
- Real-time WebSocket push instead of polling
- Mobile-responsive dashboard improvements
- CI/CD pipeline
- A/B threshold testing framework
- Model auto-retraining on schedule
"""

# ============================================================
# MASTER_TESTING_REPORT.md
# ============================================================
TESTING_REPORT = """# MASTER TESTING REPORT

**Audit Date:** 2026-09-23
**Test Runner:** pytest 9.1.1
**Python:** 3.13.5
**Platform:** Windows

---

## Test Execution Results

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
collected 44 items

tests/test_agent_buffer.py::test_system_collector PASSED
tests/test_agent_buffer.py::test_metric_buffer_push_and_overflow PASSED
tests/test_agent_buffer.py::test_metric_buffer_flush_success PASSED
tests/test_agent_buffer.py::test_metric_buffer_flush_failure_and_backoff PASSED
tests/test_ai_anomaly.py::test_detector_training_and_scoring PASSED
tests/test_ai_anomaly.py::test_sensitivity_calibration PASSED
tests/test_ai_anomaly.py::test_model_registry_save_and_load PASSED
tests/test_alert_engine.py::test_alert_threshold_breach_and_deduplication PASSED
tests/test_alert_engine.py::test_alert_auto_resolution PASSED
tests/test_alert_engine.py::test_alert_acknowledgment_and_feedback PASSED
tests/test_api_ai.py::test_ai_score_endpoint PASSED
tests/test_api_ai.py::test_ai_train_and_models_endpoints PASSED
tests/test_api_ai.py::test_forecast_endpoint PASSED
tests/test_api_v1.py::test_root_and_health PASSED
tests/test_api_v1.py::test_hosts_endpoints PASSED
tests/test_api_v1.py::test_metrics_and_summary_flow PASSED
tests/test_api_v1_expanded.py::test_api_security_endpoints PASSED
tests/test_api_v1_expanded.py::test_api_cost_endpoints PASSED
tests/test_api_v1_expanded.py::test_api_narrator_endpoint PASSED
tests/test_api_v1_expanded.py::test_api_reports_and_audit_endpoints PASSED
tests/test_config.py::test_application_name PASSED
tests/test_config.py::test_application_version PASSED
tests/test_config.py::test_environment PASSED
tests/test_cost_engine.py::test_cost_calculator_rightsizing PASSED
tests/test_cost_engine.py::test_cost_service_fleet_analysis PASSED
tests/test_database.py::test_database_connection PASSED
tests/test_explainability.py::test_compute_contributions_identifies_top_driver PASSED
tests/test_explainability.py::test_generate_explanation_text PASSED
tests/test_forecaster.py::test_time_to_threshold_projected_breach PASSED
tests/test_forecaster.py::test_time_to_threshold_stable_trajectory PASSED
tests/test_health.py::test_root PASSED
tests/test_health.py::test_health PASSED
tests/test_host_service.py::test_create_and_get_host PASSED
tests/test_host_service.py::test_get_or_create_host_auto_discovery PASSED
tests/test_host_service.py::test_get_hosts PASSED
tests/test_host_service.py::test_update_and_deactivate_host PASSED
tests/test_metric_service.py::test_ingest_single_metric_with_auto_registration PASSED
tests/test_metric_service.py::test_ingest_metrics_batch PASSED
tests/test_metric_service.py::test_get_host_metrics_timeseries PASSED
tests/test_metric_service.py::test_get_fleet_summary PASSED
tests/test_models.py::test_database_tables_created PASSED
tests/test_narrator_engine.py::test_narrator_cross_module_analysis PASSED
tests/test_security_engine.py::test_security_detector_egress_spike PASSED
tests/test_security_engine.py::test_security_service_persistence_and_summary PASSED

============================= 44 passed in 4.66s ==============================
```

---

## Test Coverage by Category

| Category | Tests | Status | Notes |
|----------|-------|--------|-------|
| Unit — Monitoring Agent | 4 | ALL PASS | Buffer push, overflow, flush, backoff |
| Unit — AI Engine | 5 | ALL PASS | Training, scoring, sensitivity, registry, explainability |
| Unit — Alert Engine | 3 | ALL PASS | Breach, deduplication, auto-resolution, ACK, feedback |
| Unit — Forecaster | 2 | ALL PASS | Projected breach, stable trajectory |
| Unit — Cost Engine | 2 | ALL PASS | Rightsizing, fleet analysis |
| Unit — Security Engine | 2 | ALL PASS | Egress spike, persistence |
| Unit — Narrator | 1 | ALL PASS | Cross-module analysis |
| Integration — API v1 | 7 | ALL PASS | Root, health, hosts, metrics, summary, security, cost, narrator, reports, audit |
| Integration — AI API | 3 | ALL PASS | Score, train, models, forecast |
| Database | 2 | ALL PASS | Connection, table creation |
| Configuration | 3 | ALL PASS | Name, version, environment |

**Total: 44 passed / 0 failed / 0 skipped**

---

## Test Quality Assessment

### Strengths
- Complete API endpoint coverage for all major features
- End-to-end data flow tests (ingest -> alert -> summary)
- Model training and inference tested
- Deduplication policy verified
- Auto-resolution tested
- Alert feedback and sensitivity calibration verified
- Cross-module narrator tested

### Gaps (Missing Test Coverage)
| Gap | Priority |
|-----|---------|
| LSTM inference tested | HIGH — LSTM evaluation is standalone, not unit tested |
| Security auto-trigger from metric ingestion | HIGH |
| Audit log write coverage | MEDIUM |
| Frontend JavaScript tests | LOW |
| Load/stress testing | LOW |
| Timeout behavior testing | MEDIUM |
| Authentication tests | HIGH (when auth is implemented) |
"""

# ============================================================
# END_TO_END_VERIFICATION.md
# ============================================================
E2E_VERIFICATION = """# END-TO-END VERIFICATION

**Audit Date:** 2026-09-23
**Method:** Automated pytest + database inspection

---

## Verification Results

| Step | Expected | Actual | Status | Evidence |
|------|----------|--------|--------|----------|
| Backend starts | FastAPI on port 8000 | Server starts (tested via TestClient) | PASS | test_health.py |
| GET /health returns 200 | {"status": "healthy"} | {"status": "healthy"} | PASS | test_health.py::test_health |
| Database initializes | 9 tables created | 9 tables confirmed: hosts, metrics, alert_rules, alerts, alert_feedback, security_events, audit_logs, pricing_catalog, cost_recommendations | PASS | test_models.py, inspect_db.py |
| Register host | POST /api/v1/hosts returns 201 | Host created with id, hostname, timestamps | PASS | test_host_service.py |
| Send metric | POST /api/v1/metrics ingests sample | Metric stored in DB; host auto-registered | PASS | test_metric_service.py |
| Retrieve metric | GET /api/v1/metrics?host_id=X | MetricTimeSeriesResponse with data[] | PASS | test_metric_service.py |
| Threshold alert fires | CPU > 85% creates alert | Alert created with kind=threshold, status=active | PASS | test_alert_engine.py |
| Alert deduplication | Second breach does NOT create duplicate | Existing alert UPDATED, not duplicated | PASS | test_alert_engine.py::test_alert_threshold_breach_and_deduplication |
| Alert auto-resolution | Metric drops below threshold | alert.status -> resolved | PASS | test_alert_engine.py::test_alert_auto_resolution |
| Fleet summary | GET /api/v1/summary | Correct host counts, latest metrics, alert severity | PASS | test_metric_service.py::test_get_fleet_summary |
| AI anomaly scoring | POST /api/v1/ai/score | is_anomaly, score, feature_contributions, explanation | PASS | test_api_ai.py |
| Model training | POST /api/v1/ai/train | Model trained, saved, registry updated | PASS | test_api_ai.py |
| Forecasting | GET /api/v1/forecast | forecast_points, time_to_threshold, trend_slope | PASS | test_api_ai.py |
| Security event creation | POST /api/v1/security/events | SecurityEvent persisted | PASS | test_security_engine.py |
| Security summary | GET /api/v1/security/summary | Counts by severity, recent events | PASS | test_api_v1_expanded.py |
| Cost analysis | GET /api/v1/cost/summary | Estimated spend, recommendations list | PASS | test_api_v1_expanded.py |
| Narrator query | POST /api/v1/narrator/query | structured_explanation with evidence | PASS | test_api_v1_expanded.py |
| Report generation | POST /api/v1/reports/generate | ReportResponse with sections | PASS | test_api_v1_expanded.py |
| Audit logs query | GET /api/v1/audit/logs | Empty list (0 records) | PASS (returns empty) | test_api_v1_expanded.py |
| Alert ACK | POST /api/v1/alerts/{id}/ack | alert.status -> acknowledged | PASS | test_alert_engine.py |
| Alert feedback | POST /api/v1/alerts/{id}/feedback | AlertFeedback record created | PASS | test_alert_engine.py |

---

## Live Data Verification

| Component | Status | Evidence |
|-----------|--------|----------|
| Database has real metrics | YES — 3,950 rows | inspect_db.py output |
| Database has real hosts | YES — 6 hosts | inspect_db.py output |
| Database has real alerts | YES — 156 rows | inspect_db.py output |
| Database has real security events | YES — 7 rows | inspect_db.py output |
| Monitoring agent sends psutil data | YES — collector.py uses actual psutil | monitoring_agent/collector.py verified |
| Simulator data clearly labeled | YES — scripts/simulate_fleet.py | Separate directory, clearly labeled |

---

## Known Failures / Gaps

| Item | Status |
|------|--------|
| Audit log records | 0 records — API handlers don't write audit logs |
| LSTM live integration | Not tested — standalone pipeline only |
| Authentication | Not implemented — all tests use unauthenticated requests |
| Frontend JavaScript | Not tested with automated tools |
"""

# ============================================================
# DASHBOARD_FEATURE_DICTIONARY.md
# ============================================================
DASHBOARD_DICT = """# DASHBOARD FEATURE DICTIONARY

**Audit Date:** 2026-09-23

---

## OVERVIEW PAGE

### Fleet Health / System Status Card
- **Meaning:** Overall operational state of the entire monitored fleet
- **Calculation:** DEGRADED if any host has critical alerts OR critical security events; else OPERATIONAL
- **Source:** GET /api/v1/summary -> has_critical_alerts, GET /api/v1/security/summary -> critical_events
- **Backend:** metric_service.get_fleet_summary() + security_service.get_security_summary()
- **Status:** LIVE (DATABASE-BACKED)

### Total Hosts / Healthy / Warning / Critical Counts
- **Meaning:** Fleet composition by health status
- **Calculation:**
  - healthy: active host + no open alerts + metric within past 5 minutes
  - warning: has active warning alert
  - critical: has active critical alert
  - offline: is_active=False OR no metric in past 5 minutes
- **Source:** GET /api/v1/summary
- **Status:** LIVE (DATABASE-BACKED)

### Active Incidents Card
- **Meaning:** Count of alerts with status='active' or 'acknowledged'
- **Source:** GET /api/v1/alerts -> filter(status=active)
- **Status:** LIVE (DATABASE-BACKED)

### Security Threats Card
- **Meaning:** Count of open security incidents
- **Source:** GET /api/v1/security/summary -> open_incidents
- **Status:** LIVE (DATABASE-BACKED)

### AI Anomaly Stream Card
- **Meaning:** Count of alerts with kind='anomaly' (ML-detected)
- **Badge label:** "LSTM + IF" — accurate (both models exist, IF is live)
- **Source:** GET /api/v1/alerts -> filter(kind=anomaly)
- **Status:** LIVE (DATABASE-BACKED) | MODEL INFERENCE (IF)

---

## INFRASTRUCTURE / INVENTORY (Resources View)

### Host List
- **Meaning:** All registered hosts with latest metrics
- **Source:** GET /api/v1/hosts with latest_metric embedded
- **Columns:** Status badge, Hostname, IP, Environment, Provider, Region, Instance Type, Last Seen
- **Status:** LIVE (DATABASE-BACKED)

### Host Detail
- **Meaning:** Drill-down for a specific host with metric sparklines
- **Source:** GET /api/v1/hosts/{id}
- **Status:** LIVE (DATABASE-BACKED)

### Host Registration
- **Meaning:** Manually register a new host
- **Source:** POST /api/v1/hosts
- **Status:** LIVE

### Host Deactivation
- **Meaning:** Mark host as inactive (is_active=False)
- **Source:** DELETE /api/v1/hosts/{id}
- **Status:** LIVE

---

## TELEMETRY (Metrics View)

### CPU Chart
- **Meaning:** Time-series line chart of CPU utilization percentage
- **Source:** GET /api/v1/metrics?host_id=X -> data[].cpu_percent
- **Interval:** Depends on agent polling interval (default 5s)
- **Display:** Chart.js line chart
- **Status:** LIVE (DATABASE-BACKED)

### Memory Chart
- **Status:** LIVE (DATABASE-BACKED) — same as CPU chart

### Disk Chart
- **Status:** LIVE (DATABASE-BACKED) — same as CPU chart

### Network Charts (Sent / Received)
- **Meaning:** MB transmitted/received per collection interval (delta, not cumulative)
- **Status:** LIVE (DATABASE-BACKED)

### Forecast Chart
- **Meaning:** Projected metric values over next 24 hours
- **Source:** GET /api/v1/forecast?host_id=X&metric=cpu_percent
- **Algorithm:** Linear regression on historical data
- **Classification:** MODEL INFERENCE (linear regression)
- **Includes:** confidence intervals (1.96 * residual_std)
- **Status:** MODEL INFERENCE (DATABASE-BACKED historical data)

### Time-to-Threshold
- **Meaning:** Estimated time until metric reaches critical threshold (e.g., disk full)
- **Calculation:** remaining_headroom / slope_per_hour
- **Classification:** MODEL INFERENCE (estimated)
- **Status:** MODEL INFERENCE

---

## ANOMALY CENTER

### Anomaly List
- **Meaning:** Alerts with kind='anomaly' from ML detection
- **Source:** GET /api/v1/alerts?kind=anomaly
- **Fields:** Metric, Score, Severity, Explanation, Timestamp, Top contributing feature
- **Status:** LIVE (DATABASE-BACKED) | MODEL INFERENCE

### Anomaly Score
- **Meaning:** Normalized anomaly likelihood (0.0=normal, 1.0=highly anomalous)
- **Calculation:** 0.5 - (IsolationForest.decision_function() * 1.2) + sensitivity_offset
- **Classification:** MODEL INFERENCE

### Feature Contributions
- **Meaning:** Which metrics contribute most to the anomaly
- **Calculation:** z-score: (value - baseline_mean) / baseline_std; ranked by absolute value
- **Classification:** MODEL INFERENCE (explainability)

### Feedback Submission
- **Meaning:** Operator labels an anomaly as true_positive or false_positive
- **Effect:** Adjusts sensitivity_offset (in-memory, not persisted across restarts)
- **Source:** POST /api/v1/alerts/{id}/feedback
- **Status:** LIVE

---

## INCIDENTS

### Incident List
- **Meaning:** All alerts with filterable status/severity/kind
- **Source:** GET /api/v1/alerts
- **Actions:** Acknowledge (POST .../ack), filter
- **Status:** LIVE (DATABASE-BACKED)

### How Alert Becomes Incident
1. Metric sample arrives via monitoring agent
2. alert_service evaluates all enabled rules
3. If metric > threshold: create Alert record (status=active)
4. Deduplication: only one active alert per (host, metric, kind)
5. Alert appears in Incidents view
6. Operator acknowledges (status -> acknowledged)
7. When metric normalizes: auto-resolved (status -> resolved)

---

## SECURITY CENTER

### Security Event List
- **Source:** GET /api/v1/security/events
- **Fields:** Type, Severity, Source IP, Description, Status, Timestamp
- **Status:** LIVE (DATABASE-BACKED)

### Detection Methods
| Event Type | Detection Method | Status |
|-----------|-----------------|--------|
| suspicious_egress | Signature-based (network_sent_mb > 150MB) | LIVE |
| brute_force_ssh | Signature defined | NOT AUTO-TRIGGERED |
| port_scan | Signature defined | NOT AUTO-TRIGGERED |
| unauthorized_sudo | Signature defined | NOT AUTO-TRIGGERED |

### Security Event Status Management
- **Transitions:** open -> investigating -> mitigated / false_positive
- **Source:** PATCH /api/v1/security/events/{id}
- **Status:** LIVE

---

## COST INTELLIGENCE

### Estimated Monthly Spend
- **Meaning:** Sum of instance hourly rates * 730 hours for all active hosts
- **Source:** STANDARD_PRICING_CATALOG (hardcoded) + host.instance_type
- **Classification:** ESTIMATED — NOT actual billing
- **Label in API response:** billing_status: "Estimated (Telemetry Driven)"
- **Status:** ESTIMATED

### Rightsizing Recommendations
- **Trigger:** avg_cpu < 5% AND avg_mem < 25% -> IDLE_TERMINATION
- **Trigger:** "*2xlarge" AND peak_cpu < 40% -> RIGHTSIZE_DOWN
- **Source:** cost_engine/calculator.py::evaluate_rightsizing()
- **Status:** ESTIMATED

### CRITICAL NOTE
Never present estimated cost as actual billing. The API response explicitly labels data as
"Estimated (Telemetry Driven)". This is correctly displayed in CostView.js.

---

## AI NARRATOR

### What the Narrator Receives
- User's free-text query string
- Optional: host_id, environment filter, time_window_minutes

### What the Narrator Queries (from DB)
- Recent Alerts (last 20, ordered by created_at DESC)
- Recent Security Events (last 20)
- Recent Cost Recommendations (last 10)

### How Context is Built
- Builds timeline_events from all three domains
- Identifies has_critical_alert and has_security_event flags
- Generates evidence_points list from actual DB records
- Selects root cause hypothesis based on signal combination

### Output
- observation: fact-based statement about counts
- evidence_points: specific alert/event details with IDs
- possible_root_cause: deterministic hypothesis
- recommended_investigation: action steps
- confidence_level: High/Medium
- cited_data_sources: list of specific alert/event IDs

### What AI Cannot Do (Current Implementation)
- Cannot execute commands or remediation actions
- Cannot access external systems (no LLM calls)
- Cannot learn from conversations
- Cannot access network topology or application logs

### Hallucination Control
- All claims grounded in specific DB records
- No LLM generation (deterministic template)
- Explicit disclaimer: "AI model inferences are analytical suggestions...must be validated by operators"

---

## REPORTS

### Report Generation
- **Input:** time_range_hours, optional environment filter
- **Source:** hosts, alerts, security_events tables + cost analysis
- **Format:** JSON with sections array
- **Status:** LIVE (DATABASE-BACKED)

---

## AUDIT TRAIL

### Audit Log
- **Meaning:** Record of operator actions
- **Status:** SCHEMA IMPLEMENTED — 0 records (writes not wired into handlers)
- **Source:** GET /api/v1/audit/logs -> audit_logs table

---

## SETTINGS / RULES

### Alert Rules CRUD
- **Actions:** View, create, delete alert threshold rules
- **Source:** GET/POST/DELETE /api/v1/alerts/rules
- **Status:** LIVE

### Model Registry
- **Meaning:** View registered ML models with training metadata
- **Source:** GET /api/v1/ai/models
- **Status:** LIVE

### Model Retraining
- **Meaning:** Retrain Isolation Forest on current DB metrics
- **Source:** POST /api/v1/ai/train
- **Status:** LIVE
"""

# ============================================================
# RESOURCE_METRICS_GUIDE.md
# ============================================================
RESOURCE_METRICS = """# RESOURCE METRICS GUIDE

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
disk = psutil.disk_usage("C:\\\\").percent  # Windows fallback
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
"""

# ============================================================
# FINAL_PROJECT_STATUS.md
# ============================================================
FINAL_STATUS = """# FINAL PROJECT STATUS

**Audit Date:** 2026-09-23
**Auditor:** Senior Software Architect

---

## Module Status

| Module | Status | Notes |
|--------|--------|-------|
| Backend API | COMPLETE | 28+ endpoints, all tested |
| Frontend Dashboard | COMPLETE | 11 views, all backend-connected |
| Database | COMPLETE | 9 tables, SQLite, 3950+ metrics |
| Monitoring Agent | COMPLETE | Real psutil collection + ring buffer |
| AI Anomaly Detection | PARTIAL | IF live but weak (10 samples); LSTM standalone |
| LSTM Model | PARTIAL | Trained and evaluated; not in live pipeline |
| Forecasting | COMPLETE | OLS linear regression, time-to-threshold |
| Cost Engine | PARTIAL | ESTIMATED costs; no real billing API |
| Security Engine | PARTIAL | Egress spike only; brute-force not auto-triggered |
| AI Narrator | PARTIAL | Deterministic; no LLM (no API keys) |
| Authentication | INCOMPLETE | Not implemented |
| RBAC | INCOMPLETE | Not implemented |
| Audit Trail | PARTIAL | Schema + read endpoint; no writes |
| Reports | COMPLETE | Executive report from live DB |
| Live Data | COMPLETE | Dashboard data is DB-backed |
| Testing | COMPLETE | 44/44 tests passing |
| Documentation | COMPLETE | This package |

---

## Test Results

| Metric | Count |
|--------|-------|
| Total tests | 44 |
| Passed | 44 |
| Failed | 0 |
| Skipped | 0 |
| Execution time | 4.66 seconds |

---

## Dashboard Feature Analysis

| Category | Count |
|----------|-------|
| Total dashboard features | 50+ |
| LIVE (real-time psutil or DB) | 35 |
| DATABASE-BACKED | 40 |
| MODEL-DERIVED (IF anomaly scoring) | 5 |
| ESTIMATED (cost figures) | 5 |
| SIMULATED (only when using fleet simulator) | N/A (separate script) |
| HARDCODED ISSUES | 2 (source_ip + destination_port in detector) |
| NOT IMPLEMENTED | 5 (LLM narrator, auth, RBAC, audit writes, real billing) |

---

## Critical Blockers

| # | Blocker | Impact |
|---|---------|--------|
| 1 | Fleet IF model trained on 10 samples | Anomaly detection unreliable |
| 2 | No authentication | All endpoints publicly accessible |
| 3 | LSTM not in live pipeline | LSTM results not visible in dashboard |
| 4 | Audit log writes not implemented | No operator accountability trail |

---

## Recommended Implementation Order

1. **IMMEDIATE:** Retrain fleet_anomaly_detector on all 3,950+ DB metrics OR switch to production model
2. **HIGH:** Wire egress spike detector into metric_service.ingest_metric()
3. **HIGH:** Add audit log writes to key API handlers
4. **MEDIUM:** Implement JWT authentication
5. **MEDIUM:** Connect LSTM to live alerting pipeline
6. **MEDIUM:** Add LLM API key and enable narrator LLM mode
7. **LOW:** Create Dockerfiles for deployment
8. **LOW:** Implement webhook/email notifications

---

## Data Authenticity Summary

| Dashboard Data Category | Classification |
|------------------------|---------------|
| CPU / Memory / Disk / Network | LIVE TELEMETRY (psutil via monitoring agent) |
| Host registration | DATABASE |
| Alerts | DATABASE (derived from threshold rules + IF model) |
| AI Anomaly Score | MODEL INFERENCE (Isolation Forest) |
| Feature Attribution | MODEL INFERENCE (z-score explainability) |
| Forecast | MODEL INFERENCE (linear regression) |
| Security Events | DATABASE |
| Cost Figures | ESTIMATED (pricing catalog lookup) |
| Narrator Output | MODEL INFERENCE (deterministic rule-based) |
| Reports | DATABASE |
| Audit Logs | NOT AVAILABLE (0 records) |
"""

# Write all files
files = {
    "PROJECT_AUDIT.md": PROJECT_AUDIT,
    "HARDCODED_DATA_AUDIT.md": HARDCODED_DATA_AUDIT,
    "DATA_LINEAGE.md": DATA_LINEAGE,
    "API_INTEGRATION_AUDIT.md": API_INTEGRATION_AUDIT,
    "DATABASE_AUDIT.md": DATABASE_AUDIT,
    "ML_MODEL_AUDIT.md": ML_MODEL_AUDIT,
    "LSTM_MODEL_REPORT.md": LSTM_MODEL_REPORT,
    "ANOMALY_DETECTION_GUIDE.md": ANOMALY_DETECTION_GUIDE,
    "SECURITY_IMPLEMENTATION_AUDIT.md": SECURITY_AUDIT,
    "MASTER_PLAN_TRACEABILITY.md": MASTER_TRACEABILITY,
    "REMAINING_MASTER_PLAN.md": REMAINING_PLAN,
    "MASTER_TESTING_REPORT.md": TESTING_REPORT,
    "END_TO_END_VERIFICATION.md": E2E_VERIFICATION,
    "DASHBOARD_FEATURE_DICTIONARY.md": DASHBOARD_DICT,
    "RESOURCE_METRICS_GUIDE.md": RESOURCE_METRICS,
    "FINAL_PROJECT_STATUS.md": FINAL_STATUS,
}

for filename, content in files.items():
    path = os.path.join(DOCS, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[+] Written: {filename} ({len(content)} chars)")

print(f"\n[DONE] Generated {len(files)} documentation files in {DOCS}/")
