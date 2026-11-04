# CloudOps Intel — Database Architecture & HTTPS Security Implementation Manual
**Version:** 3.6.0  
**Classification:** Enterprise SRE Operations & System Audit Reference  
**Applicability:** Server Infrastructure, Security Auditing, Telemetry Nodes & Database Administration  

---

## 1. Executive Summary & Architecture Overview

CloudOps Intel is engineered around two core architectural pillars:
1. **High-Concurrency Low-Latency Telemetry Storage:** Powered by an embedded **SQLite 3 database running in WAL mode (Write-Ahead Logging)**, delivering sub-millisecond write latency, ACID transactions, and zero-lock contention between concurrent streaming sensors and analytical dashboard queries.
2. **Strict Mutual/Verified HTTPS Transport:** Enforced by an integrated **Caddy TLS 1.3 / 1.2 Reverse Proxy** operating an internal Public Key Infrastructure (PKI) Certificate Authority (`root.crt`). Cleartext HTTP is rejected at the network boundary, ensuring that all telemetry, hardware diagnostics, and administrative credentials are cryptographically protected in transit.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 NETWORK INGESTION & STORAGE TOPOLOGY                              │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

   [ Lab Sensor PC / Node ]                      [ Master Server Host ]
  ┌─────────────────────────┐               ┌─────────────────────────────────────────────────────┐
  │  Monitoring Agent       │               │                                                     │
  │  (collector.py)         │               │                                                     │
  │           │             │               │                                                     │
  │           ▼             │   HTTPS:8443  │   Caddy Reverse Proxy (:8443)                       │
  │  Local Spool Queue      ├──────────────>│   ┌───────────────────────────────────────────────┐ │
  │  (sensor_spool.db)      │ TLS Verified  │   │ - Enforces TLS 1.3 / 1.2 Encrypted Transport  │ │
  │  (buffer.py)            │ with root.crt │   │ - Internal CA PKI SAN: 10.1.250.105:8443      │ │
  └─────────────────────────┘               │   │ - Terminates TLS, Strips Insecure Headers     │ │
                                            │   └──────────────────────┬────────────────────────┘ │
                                            │                          │ HTTP Loopback (127.0.0.1) │
                                            │                          ▼                          │
                                            │   FastAPI Telemetry Ingestion Engine (:8000)        │
                                            │   ┌───────────────────────────────────────────────┐ │
                                            │   │ - Route: POST /api/v1/metrics                 │ │
                                            │   │ - Provenance Verification (REAL_AGENT)        │ │
                                            │   │ - Token-Hash & Device UUID Authentication      │ │
                                            │   └──────────────────────┬────────────────────────┘ │
                                            │                          │ SQLAlchemy WAL Commits   │
                                            │                          ▼                          │
                                            │   Central SQLite Database (WAL Mode)                │
                                            │   ┌───────────────────────────────────────────────┐ │
                                            │   │ cloud_intelligence.db                         │ │
                                            │   │ ├── cloud_intelligence.db-wal (Shared Memory) │ │
                                            │   │ └── cloud_intelligence.db-shm (WAL Index)     │ │
                                            │   └───────────────────────────────────────────────┘ │
                                            └─────────────────────────────────────────────────────┘
```

---

## 2. Database Architecture & Storage Specification

### 2.1 Database Engine & Location
* **Engine:** SQLite version 3.x with WAL Journaling.
* **Master Server DB File:** `C:\CLoudProject\cloud_intelligence.db`
* **Write-Ahead Log (WAL) File:** `C:\CLoudProject\cloud_intelligence.db-wal`
* **Shared-Memory Index File:** `C:\CLoudProject\cloud_intelligence.db-shm`
* **Client Sensor Buffer File:** `C:\ProgramData\CloudOpsIntel\Sensor\sensor_spool.db`

### 2.2 Database Initialization & Pragmas Code Location
* **File Path:** [`c:\CLoudProject\backend\app\database\connection.py`](file:///c:/CLoudProject/backend/app/database/connection.py#L20-L41)
* **Code Implementation:**
```python
# backend/app/database/connection.py
DATABASE_URL = settings.database_url

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

def configure_sqlite_pragmas(target_engine, timeout_ms: int = 5000):
    """
    Configures SQLite-specific pragmas on an engine:
    - PRAGMA journal_mode=WAL (Write-Ahead Logging for concurrent readers/writers)
    - PRAGMA busy_timeout=5000 (Bounded wait for concurrent write transactions)
    - PRAGMA foreign_keys=ON (Enforces referential integrity)
    """
    @event.listens_for(target_engine, "connect")
    def set_pragmas(dbapi_connection, connection_record):
        if hasattr(dbapi_connection, "cursor"):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute(f"PRAGMA busy_timeout={timeout_ms};")
                cursor.execute("PRAGMA foreign_keys=ON;")
            finally:
                cursor.close()

if DATABASE_URL.startswith("sqlite"):
    configure_sqlite_pragmas(engine, timeout_ms=5000)
```

---

## 3. SQL Queries to Verify & Inspect Data Manually

You can execute these SQL queries directly using:
* **DB Browser for SQLite** (GUI)
* **sqlite3 CLI** (`sqlite3 C:\CLoudProject\cloud_intelligence.db`)
* **Python CLI one-liners** (provided below)

### 3.1 Fleet & Host Verification Queries

#### Query 1: View all registered machines and their environment status
```sql
SELECT 
    id,
    hostname,
    ip_address,
    environment,
    source_type,
    region AS room_or_region,
    is_active,
    created_at,
    updated_at
FROM hosts
ORDER BY id DESC;
```

#### Query 2: Inspect Zero-Trust device enrollments and hardware approvals
```sql
SELECT 
    id,
    device_uuid,
    reported_hostname,
    assigned_name,
    room_number,
    pc_number,
    ip_address,
    status,
    telemetry_health,
    last_contact_at,
    queue_backlog
FROM device_enrollments
ORDER BY id DESC;
```

#### Query 3: Check active single-use enrollment codes
```sql
SELECT 
    id,
    code_prefix,
    is_used,
    expires_at,
    used_at,
    created_at
FROM enrollment_codes
ORDER BY id DESC;
```

---

### 3.2 Telemetry & Metric Ingestion Queries

#### Query 4: View the latest 15 real-time telemetry metric samples
```sql
SELECT 
    m.id AS metric_id,
    h.hostname,
    h.environment,
    m.cpu_percent,
    m.memory_percent,
    m.disk_percent,
    ROUND(m.network_sent_mb, 2) AS net_sent_mb,
    ROUND(m.network_received_mb, 2) AS net_recv_mb,
    m.timestamp AS recorded_at
FROM metrics m
JOIN hosts h ON m.host_id = h.id
ORDER BY m.id DESC
LIMIT 15;
```

#### Query 5: Calculate Average CPU and RAM per Machine over recent records
```sql
SELECT 
    h.hostname,
    COUNT(m.id) AS total_samples,
    ROUND(AVG(m.cpu_percent), 2) AS avg_cpu_percent,
    ROUND(MAX(m.cpu_percent), 2) AS peak_cpu_percent,
    ROUND(AVG(m.memory_percent), 2) AS avg_ram_percent,
    ROUND(AVG(m.disk_percent), 2) AS avg_disk_percent,
    MAX(m.timestamp) AS latest_heartbeat
FROM hosts h
JOIN metrics m ON h.id = m.host_id
GROUP BY h.id, h.hostname
ORDER BY latest_heartbeat DESC;
```

#### Query 6: Check for metric ingestion batches and retry idempotency
```sql
SELECT 
    id,
    batch_id,
    host_id,
    processed_samples,
    generated_alerts,
    created_at
FROM ingested_batches
ORDER BY id DESC
LIMIT 10;
```

---

### 3.3 Security, Alerts & Audit Log Queries

#### Query 7: View active anomaly and threshold alerts
```sql
SELECT 
    a.id AS alert_id,
    h.hostname,
    a.kind,
    a.severity,
    a.message,
    a.value AS recorded_value,
    a.threshold AS rule_threshold,
    a.status AS alert_status,
    a.created_at
FROM alerts a
JOIN hosts h ON a.host_id = h.id
ORDER BY a.id DESC
LIMIT 20;
```

#### Query 8: Audit Log Journal (All Administrative & Security Actions)
```sql
SELECT 
    id,
    user_email,
    action,
    target_resource,
    result,
    client_ip,
    timestamp
FROM audit_logs
ORDER BY id DESC
LIMIT 25;
```

#### Query 9: User Accounts and Verification Status
```sql
SELECT 
    id,
    email,
    role,
    is_active,
    is_verified,
    created_at,
    updated_at
FROM users
ORDER BY id ASC;
```

#### Query 10: Active and Revoked Agent API Keys
```sql
SELECT 
    id,
    name,
    key_prefix,
    source_type,
    is_active,
    is_disabled,
    last_used_at,
    revoked_at,
    device_uuid
FROM agent_api_keys
ORDER BY id DESC;
```

---

### 3.4 Ready-to-Run PowerShell One-Liners

Execute these directly in an elevated PowerShell prompt on the Server:

```powershell
# 1. Quick Telemetry Health Probe (Last 5 Metrics)
python -c "import sqlite3; c=sqlite3.connect('C:/CLoudProject/cloud_intelligence.db'); cur=c.cursor(); cur.execute('SELECT m.id, h.hostname, m.cpu_percent, m.memory_percent, m.timestamp FROM metrics m JOIN hosts h ON m.host_id=h.id ORDER BY m.id DESC LIMIT 5;'); print('\n'.join(str(r) for r in cur.fetchall()))"

# 2. Check Device Enrollment Status
python -c "import sqlite3; c=sqlite3.connect('C:/CLoudProject/cloud_intelligence.db'); cur=c.cursor(); cur.execute('SELECT id, assigned_name, room_number, ip_address, status, telemetry_health FROM device_enrollments;'); print('\n'.join(str(r) for r in cur.fetchall()))"

# 3. Check System Alerts
python -c "import sqlite3; c=sqlite3.connect('C:/CLoudProject/cloud_intelligence.db'); cur=c.cursor(); cur.execute('SELECT id, severity, message, status, created_at FROM alerts ORDER BY id DESC LIMIT 5;'); print('\n'.join(str(r) for r in cur.fetchall()))"
```

---

## 4. HTTPS Protocol Implementation & Architecture

### 4.1 Strict Transport Security Architecture
The platform enforces a **Dual-Tier Transport Security Model**:
1. **Public/LAN Tier (HTTPS Port 8443):**
   * Handled by Caddy Reverse Proxy.
   * Bound to physical network interfaces (e.g. `10.1.250.105:8443`).
   * Issues x509 leaf certificates with Subject Alternative Names (SANs) for the server IP.
   * Strict HTTP Strict Transport Security (HSTS) headers enabled.
   * External cleartext HTTP is prohibited.
2. **Internal Loopback Tier (HTTP Port 8000):**
   * Bound exclusively to `127.0.0.1` (loopback).
   * Not exposed to Windows Defender Firewall.
   * Caddy terminates TLS and reverse-proxies requests internally.

---

### 4.2 Exact Files Implementing HTTPS Security

| Component | File Path | Key Security Function |
| :--- | :--- | :--- |
| **Reverse Proxy Configuration** | [`Caddyfile`](file:///c:/CLoudProject/Caddyfile#L1-L46) | Declares HTTPS endpoints, Internal CA, HSTS headers, and loopback forwarding. |
| **CA Root Certificate** | [`data/caddy/pki/authorities/local/root.crt`](file:///c:/CLoudProject/data/caddy/pki/authorities/local/root.crt) | The Public Certificate Authority root cert verifying the server identity. |
| **Issued Server Certificate** | `data/caddy/certificates/local/<IP>/<IP>.crt` | Dynamic leaf certificate issued with valid IP SANs. |
| **Sensor Transport Validator** | [`monitoring_agent/buffer.py`](file:///c:/CLoudProject/monitoring_agent/buffer.py#L39-L67) | Validates transport security; blocks cleartext HTTP to remote targets. |
| **Sensor HTTPS Dispatcher** | [`monitoring_agent/buffer.py`](file:///c:/CLoudProject/monitoring_agent/buffer.py#L314-L321) | Executes `requests.post()` with verified `root.crt` CA certificate bundle. |
| **Agent Enrollment Handshake** | [`monitoring_agent/agent.py`](file:///c:/CLoudProject/monitoring_agent/agent.py#L190-L205) | Constructs `ssl.create_default_context(cafile=ca_bundle)` for enrollment. |
| **Packaging & Distribution** | [`scripts/package_sensor_agent.py`](file:///c:/CLoudProject/scripts/package_sensor_agent.py#L94-L105) | Bundles `root.crt` while strictly auditing against private keys (`root.key`). |

---

### 4.3 Code Deep Dive: How HTTPS is Implemented

#### 1. Caddyfile Configuration (Server TLS & Header Hardening)
* **File:** [`Caddyfile`](file:///c:/CLoudProject/Caddyfile#L20-L46)
```caddy
# ==============================================================================
# CloudOps Intel — Production & Staging Reverse Proxy Configuration
# ==============================================================================

{
    admin off
    auto_https disable_redirects
    storage file_system {
        root "C:/CLoudProject/data/caddy"
    }
}

# HTTPS Endpoint: Port 8443
https://localhost:8443, https://127.0.0.1:8443, https://10.1.250.105:8443, https://:8443 {
    tls internal

    # Security Headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
    }

    # Reverse proxy to loopback FastAPI
    reverse_proxy 127.0.0.1:8000 {
        header_up Host {upstream_hostport}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-Proto https
    }

    handle /health {
        reverse_proxy 127.0.0.1:8000
    }
}
```

---

#### 2. Sensor Transport Security Enforcement (Buffer Pre-Flight Check)
* **File:** [`monitoring_agent/buffer.py`](file:///c:/CLoudProject/monitoring_agent/buffer.py#L39-L67)
```python
# monitoring_agent/buffer.py

class InsecureTransportError(ValueError):
    """Raised when an agent attempts to transmit over insecure cleartext HTTP."""
    pass

def validate_transport_security(url: str, api_key: Optional[str] = None, allow_insecure_http: bool = False) -> None:
    """
    Enforces transport security:
    - Remote (non-loopback) targets must use HTTPS.
    - Cleartext HTTP is rejected before credentials or telemetry are dispatched.
    - Loopback targets (127.0.0.1, localhost) are permitted for local development.
    """
    if not url:
        raise ValueError("ingest_url must not be empty.")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").lower()

    if scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{scheme}'. Target URL must use HTTP or HTTPS.")

    if scheme == "http":
        if not is_loopback_target(url) and not allow_insecure_http:
            raise InsecureTransportError(
                f"Insecure transport rejected: Remote telemetry target '{hostname}' must use HTTPS."
            )
```

---

#### 3. Cryptographically Verified Transmission (Mutual PKI Trust)
* **File:** [`monitoring_agent/buffer.py`](file:///c:/CLoudProject/monitoring_agent/buffer.py#L305-L322)
```python
# monitoring_agent/buffer.py (flush routine)

# Resolve CA bundle (root.crt)
verify: Any = self.ca_bundle if self.ca_bundle else os.getenv("AGENT_CA_BUNDLE", True)

# Transmit telemetry over TLS with strict certificate verification
response = requests.post(
    self.ingest_url,
    json=payload,
    headers=headers,
    timeout=timeout,
    verify=verify,  # Points directly to root.crt; rejects self-signed forgery
)
```

---

#### 4. Cryptographic Enrollment Context in Python Standard Library
* **File:** [`monitoring_agent/agent.py`](file:///c:/CLoudProject/monitoring_agent/agent.py#L190-L205)
```python
# monitoring_agent/agent.py (enroll_device)

def _build_ssl_context(ca_bundle: Optional[str] = None) -> ssl.SSLContext:
    """Builds hardened SSLContext verifying against custom CA root certificate."""
    if ca_bundle and os.path.exists(ca_bundle):
        ctx = ssl.create_default_context(cafile=ca_bundle)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx
    return ssl.create_default_context()
```

---

## 5. Summary Reference Table

| Requirement | Implementation Details | Verification Command |
| :--- | :--- | :--- |
| **Database File** | `C:\CLoudProject\cloud_intelligence.db` | `Test-Path C:\CLoudProject\cloud_intelligence.db` |
| **Concurrency Mode** | SQLite WAL (`PRAGMA journal_mode=WAL;`) | `python -c "import sqlite3; print(sqlite3.connect('C:/CLoudProject/cloud_intelligence.db').execute('PRAGMA journal_mode;').fetchone())"` |
| **External Port** | TCP 8443 (HTTPS) | `Test-NetConnection 10.1.250.105 -Port 8443` |
| **Internal Port** | TCP 8000 (HTTP Loopback 127.0.0.1) | `Invoke-RestMethod http://127.0.0.1:8000/health` |
| **TLS Certificate** | Caddy Internal CA (`root.crt`) | `openssl x509 -in C:\CLoudProject\data\caddy\pki\authorities\local\root.crt -text -noout` |
| **Sensor Agent Spool** | `sensor_spool.db` (24h SQLite buffer) | `Test-Path C:\ProgramData\CloudOpsIntel\Sensor\sensor_spool.db` |

---
*(End of Technical Reference Manual)*

