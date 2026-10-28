# DATABASE AUDIT

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
