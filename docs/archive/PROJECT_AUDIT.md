# PROJECT AUDIT — Cloud Resource Monitoring & Intelligence Platform

**Audit Date:** 2026-09-23
**Auditor:** Senior Software Architect / Project Auditor
**Repository Root:** c:\CLoudProject

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
