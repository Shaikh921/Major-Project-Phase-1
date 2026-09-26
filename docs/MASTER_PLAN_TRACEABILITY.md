# MASTER PLAN TRACEABILITY

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
