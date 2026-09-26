# DASHBOARD FEATURE DICTIONARY

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
