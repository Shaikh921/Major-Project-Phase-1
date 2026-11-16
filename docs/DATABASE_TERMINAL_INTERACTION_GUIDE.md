# 🗄️ CloudOps Intel — Database Terminal Interaction Guide

A complete, production-ready operational guide for querying, inspecting, and managing the **CloudOps Intel SQLite database (`cloud_intelligence.db`)** directly from the terminal.

---

## 📋 Table of Contents
1. [Architecture Overview & Storage Layout](#1-architecture-overview--storage-layout)
2. [Database Connection & Access Methods](#2-database-connection--access-methods)
   - [Method A: Built-in Interactive DB Shell (Recommended)](#method-a-built-in-interactive-db-shell-recommended)
   - [Method B: Single-Query CLI Execution](#method-b-single-query-cli-execution)
   - [Method C: Native Python One-Liners (PowerShell / CMD / Bash)](#method-c-native-python-one-liners)
   - [Method D: Native SQLite3 CLI Binary](#method-d-native-sqlite3-cli-binary)
3. [Database Schema & Table Catalog (23 Tables)](#3-database-schema--table-catalog)
4. [Master SQL Command Reference by Operational Category](#4-master-sql-command-reference)
   - [4.1 Database Health, WAL Mode & Concurrency Diagnostics](#41-database-health-wal-mode--concurrency-diagnostics)
   - [4.2 User Management, RBAC & Authentication](#42-user-management-rbac--authentication)
   - [4.3 Infrastructure & Monitored Host Inventory](#43-infrastructure--monitored-host-inventory)
   - [4.4 Real-Time Telemetry & Metric Logs](#44-real-time-telemetry--metric-logs)
   - [4.5 Alerts, Anomalies & Incident Management](#45-alerts-anomalies--incident-management)
   - [4.6 Device Enrollment & Sensor Hardware Verification](#46-device-enrollment--sensor-hardware-verification)
   - [4.7 Agent API Keys & Ingestion Credentials](#47-agent-api-keys--ingestion-credentials)
   - [4.8 Security Events & Audit Trails](#48-security-events--audit-trails)
   - [4.9 Cloud Cost Optimization & Rightsizing](#49-cloud-cost-optimization--rightsizing)
5. [Safe Maintenance, WAL Checkpoint & Consistent Online Backups](#5-safe-maintenance-wal-checkpoint--consistent-online-backups)

---

## 1. Architecture Overview & Storage Layout

CloudOps Intel utilizes **SQLite 3.49+** configured strictly in **Write-Ahead Logging (WAL)** mode. This design provides near-PostgreSQL level concurrent read/write throughput:

* **`cloud_intelligence.db`**: Primary database file holding committed relational pages.
* **`cloud_intelligence.db-wal`**: Write-Ahead Log storing uncheckpointed transactions. Readers read concurrently without blocking write operations from incoming sensor telemetry streams.
* **`cloud_intelligence.db-shm`**: Shared memory index coordinating concurrent connections between the Uvicorn FastAPI backend and background tasks.

### Concurrency Rules & Pragmas
Every database connection automatically executes three vital pragmas:
```sql
PRAGMA journal_mode=WAL;       -- Write-Ahead Logging for non-blocking concurrent reads/writes
PRAGMA busy_timeout=5000;      -- 5-second wait before failing on concurrent lock contention
PRAGMA foreign_keys=ON;        -- Enforces relational integrity across tables
```

---

## 2. Database Connection & Access Methods

### Method A: Built-in Interactive DB Shell (Recommended)
CloudOps Intel includes a custom, zero-dependency interactive REPL located at `scripts/db_shell.py`. It renders formatted ASCII tables and does not require external binaries.

Launch the shell from PowerShell or Command Prompt:
```powershell
python scripts\db_shell.py
```

Inside the interactive prompt:
```text
cloudops-db> .tables
cloudops-db> .schema users
cloudops-db> SELECT id, email, role, is_active FROM users;
cloudops-db> exit
```

---

### Method B: Single-Query CLI Execution
Execute any SQL query directly from your command line without entering interactive mode:

```powershell
# List registered users
python scripts\db_shell.py "SELECT id, email, role, is_active FROM users;"

# View active host status
python scripts\db_shell.py "SELECT id, hostname, ip_address, environment, is_active FROM hosts;"

# View the 5 most recent telemetry readings
python scripts\db_shell.py "SELECT id, host_id, timestamp, cpu_percent, memory_percent, disk_percent FROM metrics ORDER BY id DESC LIMIT 5;"
```

---

### Method C: Native Python One-Liners
If executing directly inside scripts or headless environments:

#### PowerShell:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('cloud_intelligence.db'); cur = conn.cursor(); cur.execute('SELECT id, email, role FROM users'); print(cur.fetchall())"
```

#### Linux / macOS:
```bash
python3 -c "import sqlite3; conn = sqlite3.connect('cloud_intelligence.db'); cur = conn.cursor(); cur.execute('SELECT id, email, role FROM users'); print(cur.fetchall())"
```

---

### Method D: Native SQLite3 CLI Binary
If you have `sqlite3.exe` installed on your path:

```powershell
sqlite3 -header -column cloud_intelligence.db "SELECT id, email, role, is_active FROM users;"
```

Or open interactive session:
```powershell
sqlite3 cloud_intelligence.db
```

---

## 3. Database Schema & Table Catalog

The platform schema consists of **23 relational tables** organized into 6 functional domains:

| Domain | Table Name | Purpose |
| :--- | :--- | :--- |
| **Authentication & RBAC** | `users` | User credentials, Argon2id password hashes, and assigned roles. |
| | `user_sessions` | Active JWT refresh tokens and device session states. |
| | `email_verification_tokens` | 24-hour cryptographic tokens for prospective admins. |
| | `password_reset_tokens` | Single-use SHA-256 tokens for secure password recovery. |
| | `admin_registration_requests`| Prospective admin application queue pending Super Admin review. |
| | `admin_activation_tokens` | One-time tokens issued upon admin application approval. |
| | `user_environment_assignments`| Fine-grained environment-level access controls. |
| | `user_host_assignments` | Host-level access permissions per user. |
| **Telemetry & Infrastructure**| `hosts` | Master inventory of cloud VMs and physical lab machines. |
| | `metrics` | High-frequency telemetry log (CPU, RAM, Disk, Network). |
| | `ingested_batches` | Batch deduplication tracking for sensor streaming. |
| **Sensor & Hardware Security**| `device_enrollments` | Physical PC hardware UUID, MAC, room, and status registry. |
| | `enrollment_codes` | 15-minute administrative pre-shared keys for zero-trust onboarding.|
| | `agent_api_keys` | Cryptographic SHA-256 hashed sensor ingestion API keys. |
| **Alerts & Anomaly Center** | `alerts` | Triggered incidents, severity, values, and lifecycle status. |
| | `alert_rules` | User-defined threshold policies and anomaly configurations. |
| | `alert_feedback` | Operator human-in-the-loop classification (True/False positive).|
| **Security & Governance** | `security_events` | Security incidents (brute force, port scan, unauthorized probes).|
| | `audit_logs` | Immutable audit trail of all sensitive admin actions. |
| **FinOps & Diagnostics** | `pricing_catalog` | Multi-cloud on-demand list pricing (AWS, GCP, Azure) in USD. |
| | `cost_recommendations` | Rightsizing and idle-termination financial advisories. |
| | `diagnostic_commands` | Pre-approved diagnostic bash/powershell runbook scripts. |
| | `diagnostic_results` | Execution logs and outputs from host diagnostic commands. |

---

## 4. Master SQL Command Reference

### 4.1 Database Health, WAL Mode & Concurrency Diagnostics

```sql
-- Check active journal mode (should return "wal")
PRAGMA journal_mode;

-- Check SQLite busy timeout in milliseconds (should be 5000 or 30000)
PRAGMA busy_timeout;

-- Verify database file integrity (should return "ok")
PRAGMA integrity_check;

-- Verify foreign key referential integrity
PRAGMA foreign_key_check;

-- Inspect database page count and page size (total size = page_count * page_size)
PRAGMA page_count;
PRAGMA page_size;

-- Check total number of records across core tables
SELECT 
    (SELECT COUNT(*) FROM users) AS total_users,
    (SELECT COUNT(*) FROM hosts) AS total_hosts,
    (SELECT COUNT(*) FROM metrics) AS total_metrics,
    (SELECT COUNT(*) FROM alerts) AS total_alerts,
    (SELECT COUNT(*) FROM device_enrollments) AS total_devices;
```

---

### 4.2 User Management, RBAC & Authentication

```sql
-- List all registered accounts with role and status
SELECT id, email, role, is_active, is_verified, created_at 
FROM users 
ORDER BY id ASC;

-- Inspect Super Administrators only
SELECT id, email, role, created_at 
FROM users 
WHERE role = 'SUPER_ADMIN';

-- Promote a user to SUPER_ADMIN directly
UPDATE users 
SET role = 'SUPER_ADMIN', is_active = 1, is_verified = 1 
WHERE email = 'admin@ops.local';

-- Activate a locked or inactive user account
UPDATE users 
SET is_active = 1 
WHERE email = 'target_user@example.com';

-- View pending prospective admin registration requests
SELECT id, email, organization, reason, email_verified, status, requested_at 
FROM admin_registration_requests 
WHERE status = 'PENDING_APPROVAL';

-- Check active password reset tokens
SELECT id, user_id, token_hash, expires_at, is_used 
FROM password_reset_tokens 
ORDER BY id DESC LIMIT 5;
```

---

### 4.3 Infrastructure & Monitored Host Inventory

```sql
-- List all active hosts, IPs, and environment classification
SELECT id, hostname, ip_address, environment, provider, source_type, is_active 
FROM hosts 
ORDER BY id ASC;

-- Filter for real physical agents vs simulated cloud hosts
SELECT id, hostname, ip_address, source_type, environment 
FROM hosts 
WHERE source_type = 'REAL_AGENT' OR environment = 'lab';

-- Check hosts that have gone inactive
SELECT id, hostname, ip_address, updated_at 
FROM hosts 
WHERE is_active = 0;

-- Manually update a host's environment tag (e.g. from local to lab)
UPDATE hosts 
SET environment = 'lab' 
WHERE hostname = 'DESKTOP-OGTK5SI';
```

---

### 4.4 Real-Time Telemetry & Metric Logs

```sql
-- Query the 10 most recent telemetry readings across all machines
SELECT m.id, h.hostname, m.timestamp, m.cpu_percent, m.memory_percent, m.disk_percent, m.network_sent_mb, m.network_received_mb
FROM metrics m
JOIN hosts h ON m.host_id = h.id
ORDER BY m.id DESC 
LIMIT 10;

-- Query average and peak CPU/Memory for a specific host (e.g., host_id = 1) over the last 100 samples
SELECT 
    AVG(cpu_percent) AS avg_cpu,
    MAX(cpu_percent) AS peak_cpu,
    AVG(memory_percent) AS avg_memory,
    MAX(memory_percent) AS peak_memory,
    COUNT(*) AS sample_count
FROM (
    SELECT cpu_percent, memory_percent 
    FROM metrics 
    WHERE host_id = 1 
    ORDER BY id DESC 
    LIMIT 100
);

-- Delete historical telemetry older than 30 days to reclaim storage
DELETE FROM metrics 
WHERE timestamp < datetime('now', '-30 days');
```

---

### 4.5 Alerts, Anomalies & Incident Management

```sql
-- View all currently active, unresolved alerts
SELECT id, host_id, metric, kind, severity, value, threshold, status, created_at
FROM alerts 
WHERE status != 'RESOLVED' 
ORDER BY id DESC;

-- View critical severity alerts only
SELECT a.id, h.hostname, a.metric, a.value, a.threshold, a.message, a.created_at
FROM alerts a
JOIN hosts h ON a.host_id = h.id
WHERE a.severity = 'CRITICAL'
ORDER BY a.id DESC;

-- Acknowledge an active alert via SQL
UPDATE alerts 
SET status = 'ACKNOWLEDGED', acknowledged_at = datetime('now') 
WHERE id = 1;

-- Resolve an alert via SQL
UPDATE alerts 
SET status = 'RESOLVED', resolved_at = datetime('now') 
WHERE id = 1;

-- View operator feedback (True Positive vs False Alarm feedback on AI anomalies)
SELECT id, alert_id, feedback_type, user_id, comments, created_at 
FROM alert_feedback 
ORDER BY id DESC;
```

---

### 4.6 Device Enrollment & Sensor Hardware Verification

```sql
-- Inspect all enrolled physical lab PCs and workstations
SELECT id, reported_hostname, assigned_name, lab_name, room_number, ip_address, status, telemetry_health, last_contact_at
FROM device_enrollments 
ORDER BY id ASC;

-- Inspect device hardware UUID and MAC bindings (Anti-Spoofing check)
SELECT id, reported_hostname, device_uuid, mac_address, agent_version, queue_backlog 
FROM device_enrollments;

-- View currently active 15-minute sensor enrollment codes
SELECT id, code, lab_name, default_room, max_uses, current_uses, expires_at, is_active 
FROM enrollment_codes 
WHERE is_active = 1 AND expires_at > datetime('now');

-- Approve a pending device enrollment request
UPDATE device_enrollments 
SET status = 'APPROVED', reviewed_at = datetime('now') 
WHERE id = 1;
```

---

### 4.7 Agent API Keys & Ingestion Credentials

```sql
-- View active agent API keys and key prefixes (hashed keys are redacted for safety)
SELECT id, name, key_prefix, source_type, is_active, last_used_at, created_at 
FROM agent_api_keys 
ORDER BY id ASC;

-- Revoke an agent ingestion key immediately
UPDATE agent_api_keys 
SET is_active = 0, revoked_at = datetime('now') 
WHERE id = 1;
```

---

### 4.8 Security Events & Audit Trails

```sql
-- Inspect the 15 most recent security events (brute force, probe attempts)
SELECT id, event_type, severity, source_ip, description, timestamp 
FROM security_events 
ORDER BY id DESC 
LIMIT 15;

-- Inspect the administrative audit trail (who changed what configuration)
SELECT id, user_id, action, resource_type, resource_id, details, ip_address, timestamp 
FROM audit_logs 
ORDER BY id DESC 
LIMIT 20;

-- Audit all password change and role promotion events
SELECT id, user_id, action, details, timestamp 
FROM audit_logs 
WHERE action LIKE '%ROLE%' OR action LIKE '%PASSWORD%' 
ORDER BY id DESC;
```

---

### 4.9 Cloud Cost Optimization & Rightsizing

```sql
-- View current rightsizing recommendations generated by the FinOps engine
SELECT id, host_id, current_instance_type, recommended_instance_type, estimated_monthly_savings, action_type, confidence_score
FROM cost_recommendations 
ORDER BY estimated_monthly_savings DESC;

-- Inspect sample pricing catalog rates (AWS, Azure, GCP reference prices)
SELECT id, provider, instance_type, vcpu, ram_gb, hourly_rate_usd, monthly_rate_usd 
FROM pricing_catalog 
ORDER BY hourly_rate_usd ASC 
LIMIT 10;
```

---

## 5. Safe Maintenance, WAL Checkpoint & Consistent Online Backups

### 5.1 Manual WAL Checkpoint (Flushing `-wal` to `.db`)
While SQLite automatically checkpoints periodically, you can safely force a checkpoint from the terminal without stopping the backend:

```powershell
python -c "import sqlite3; conn = sqlite3.connect('cloud_intelligence.db'); conn.execute('PRAGMA wal_checkpoint(TRUNCATE);'); conn.close(); print('[+] WAL flushed and truncated successfully.')"
```

### 5.2 Performing a Hot Consistent Backup
Never copy `cloud_intelligence.db` directly using Windows File Explorer or `Copy-Item` while the server is writing, as this can lead to torn reads. Always use SQLite's native online backup API:

Run the production backup script:
```powershell
python scripts\backup_active_db.py
```

Or execute via a Python one-liner:
```powershell
python -c "import sqlite3, datetime; src = sqlite3.connect('file:cloud_intelligence.db?mode=ro', uri=True); dest = sqlite3.connect(f'backups/backup_{datetime.datetime.now().strftime(\"%Y%m%d_%H%M%S\")}.db'); src.backup(dest); dest.close(); src.close(); print('[+] Online consistent backup complete.')"
```

### 5.3 Safe Vacuuming
To reclaim unused disk space after mass deletion of old telemetry:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('cloud_intelligence.db'); conn.execute('VACUUM;'); conn.close(); print('[+] Database vacuumed successfully.')"
```
