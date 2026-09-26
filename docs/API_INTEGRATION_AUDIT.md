# API INTEGRATION AUDIT

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
