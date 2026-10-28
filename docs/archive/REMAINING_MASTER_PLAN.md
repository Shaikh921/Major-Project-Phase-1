# REMAINING MASTER PLAN

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
