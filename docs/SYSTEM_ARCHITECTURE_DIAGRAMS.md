# CloudOps Intel — System Architecture & Workflow Diagrams

This document consolidates all core architectural workflows, security models, data pipelines, and operational flowcharts for **CloudOps Intel — Cloud Intelligence Platform & SRE Command Center**.

---

## Table of Contents

1. [High-Level Defense-in-Depth Security Architecture](#1-high-level-defense-in-depth-security-architecture)
2. [Dual-Mode Asynchronous Email Notification Engine](#2-dual-mode-asynchronous-email-notification-engine)
3. [Multi-Step Administrative Governance & Anti-Rogue Approval Queue](#3-multi-step-administrative-governance--anti-rogue-approval-queue)
4. [3-Tier AI/ML Anomaly Detection & Explainability Pipeline](#4-3-tier-aiml-anomaly-detection--explainability-pipeline)
5. [FinOps Hybrid Cost Optimization & Currency Engine](#5-finops-hybrid-cost-optimization--currency-engine)
6. [FinOps Workload Rightsizing Decision Logic](#6-finops-workload-rightsizing-decision-logic)
7. [Cloud Virtual Machine vs Bare-Metal Architecture](#7-cloud-virtual-machine-vs-bare-metal-architecture)
8. [4-Tier Cumulative Role-Based Access Control (RBAC) Hierarchy](#8-4-tier-cumulative-role-based-access-control-rbac-hierarchy)
9. [Physical Sensor Device Enrollment & Anti-Spoofing Handshake](#9-physical-sensor-device-enrollment--anti-spoofing-handshake)
10. [Industry Readiness Evolution: Current MVP vs Enterprise Standard](#10-industry-readiness-evolution-current-mvp-vs-enterprise-standard)
11. [Operational A4 Report & PDF Export Document Layout](#11-operational-a4-report--pdf-export-document-layout)

---

## 1. High-Level Defense-in-Depth Security Architecture

CloudOps Intel implements a multi-layer security posture spanning network boundaries, hardware agent identity, cryptographic token storage, role-based governance, and application defense.

```mermaid
flowchart TD
    subgraph L1["1. Network & Transport Boundary"]
        Caddy["Caddy Reverse Proxy (TLS 1.3/1.2 on Port 8443)"]
        Loopback["FastAPI Backend bound to 127.0.0.1:8000 (Loopback Only)"]
        PKI["Custom Internal PKI (Strict root.crt CA Pinning)"]
    end

    subgraph L2["2. Sensor & Telemetry Ingestion"]
        NTFS["OS Security: icacls SYSTEM & Admin Only"]
        Handshake["2-Phase Enrollment Handshake (15-min Enrollment Codes)"]
        DeviceBound["Hardware UUID & Host ID Binding (Anti-Spoofing)"]
        RingBuffer["Offline SQLite Ring Buffer (Anti-Data Loss & DDoS Guard)"]
    end

    subgraph L3["3. Identity & Cryptography"]
        Argon2id["Argon2id Password Hashing (64 MiB RAM, 3 Iterations, 4 Parallel)"]
        JWT["Dual-Token JWT: Short-Lived Access (15m) + httpOnly Cookie Refresh (7d)"]
        TokenHash["Single-Use Tokens: SHA-256 Hashed at Rest (Zero Raw Storage)"]
    end

    subgraph L4["4. Governance & RBAC"]
        RBAC["4-Tier Hierarchical RBAC: VIEWER to SUPER_ADMIN"]
        Gov["Multi-Step Anti-Rogue Admin Approval Pipeline"]
        ImmutableAudit["Append-Only Audit Trail (All Sensitive Admin/Auth Actions)"]
    end

    subgraph L5["5. Threat & Application Defense"]
        SQLi["100% Parameterized SQLAlchemy 2.0 ORM (SQLi Immunity)"]
        XSS["XSS Immunity: Strict escapeHtml() Sanitizer in UI & Emails"]
        ThreatEngine["Security Events Engine (SSH Brute-Force, Port Scans, Tampering)"]
        AIGuards["Explainable ML (Isolation Forest + LSTM + SHAP Feature Attribution)"]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
```

- **Source Code References:**
  - Network Boundary: `Caddyfile`, [`backend/app/core/config.py`](file:///C:/CLoudProject/backend/app/core/config.py)
  - Sensor Security: [`scripts/install_sensor_client.ps1`](file:///C:/CLoudProject/scripts/install_sensor_client.ps1), [`backend/app/services/device_service.py`](file:///C:/CLoudProject/backend/app/services/device_service.py)
  - Cryptography: [`backend/app/core/security.py`](file:///C:/CLoudProject/backend/app/core/security.py)

---

## 2. Dual-Mode Asynchronous Email Notification Engine

The centralized email dispatch system prevents blocking HTTP worker processes by routing mail jobs to a background thread pool, supporting dual transport modes (live SMTP vs development outbox).

```mermaid
flowchart TD
    Trigger["Event Trigger (Critical Alert, Admin Request, Password Reset)"] --> Dispatcher["EmailService Dispatcher"]
    Dispatcher --> SmtpCheck{"Check Configuration:\nsmtp_enabled?"}

    SmtpCheck -- "smtp_enabled = false (Dev / Test Mode)" --> DevOutbox["In-Memory Dev Outbox (_dev_outbox)\n& Console Log [DEV_OUTBOX]"]
    DevOutbox --> SafeCapture["Captures message, tokens & metadata\n(Zero external traffic, unit tests pass safely)"]

    SmtpCheck -- "smtp_enabled = true (Production Mode)" --> WorkerPool["ThreadPoolExecutor Worker Pool\n(max_workers=4, Non-blocking)"]
    WorkerPool --> MimeBuilder["MIMEMultipart RFC 5322 Builder\n(Plaintext + Responsive HTML Layout)"]
    MimeBuilder --> ProtocolCheck{"Transport Selection:\nsmtp_ssl?"}
    ProtocolCheck -- "smtp_ssl = true (Port 465)" --> SslClient["smtplib.SMTP_SSL"]
    ProtocolCheck -- "smtp_ssl = false / tls = true (Port 587)" --> StartTlsClient["smtplib.SMTP + STARTTLS"]
    SslClient --> SmtpDelivery["SMTP Authentication & Message Delivery"]
    StartTlsClient --> SmtpDelivery
    SmtpDelivery --> AuditLog["Sanitized Logging & Audit Trail Record"]
```

- **Source Code References:**
  - Dispatch Service: [`backend/app/services/email_service.py`](file:///C:/CLoudProject/backend/app/services/email_service.py)
  - Responsive Templates: [`backend/app/templates/email_templates.py`](file:///C:/CLoudProject/backend/app/templates/email_templates.py)

---

## 3. Multi-Step Administrative Governance & Anti-Rogue Approval Queue

To eliminate self-provisioned administrator accounts, prospective administrators must complete email verification followed by formal approval by a verified Super Administrator.

```mermaid
flowchart TD
    A["Prospective Admin Submits Application\n(Name, Email, Org, Justification)"] --> B["Backend Generates 24h Cryptographic Token\n(SHA-256 Hashed at Rest)"]
    B --> C["Dispatches Verification Email to Applicant"]
    C --> D{"Applicant Clicks Link:\n/#verify-admin-request?token=..."}
    
    D -- "Token Expired or Invalid" --> E["400 Bad Request / Verification Denied"]
    D -- "Token Verified" --> F["Status: PENDING_SUPER_ADMIN_APPROVAL"]
    
    F --> G["Dispatches Real-Time Alert to All Active Super Admins"]
    G --> H["Application Enters Super Admin Governance Queue"]
    
    H --> Decision{"Super Admin Decision"}
    
    Decision -- "REJECTED (with reason notes)" --> I["Dispatches Formal Rejection Email\n(Account Cancelled)"]
    Decision -- "APPROVED" --> J["Status: ACTIVATION_PENDING\nGenerates Single-Use Activation Token"]
    
    J --> K["Dispatches Activation Email to Approved Applicant"]
    K --> L["Applicant Sets Password\n/#activate-admin?token=..."]
    L --> M["Password Hashed with Argon2id\nAccount Promoted to Role: ADMIN"]
```

- **Source Code References:**
  - Route Handlers: [`backend/app/api/v1/auth.py`](file:///C:/CLoudProject/backend/app/api/v1/auth.py)
  - Governance Logic: [`backend/app/services/auth_service.py`](file:///C:/CLoudProject/backend/app/services/auth_service.py)

---

## 4. 3-Tier AI/ML Anomaly Detection & Explainability Pipeline

CloudOps Intel integrates static rule gates, unsupervised spatial clustering (Isolation Forest), and deep temporal sequence reconstruction (LSTM Autoencoder) to detect micro-bursts, sequence drift, and memory leaks.

```mermaid
flowchart TD
    Sensor["Host Sensor (psutil daemon)\n[CPU, RAM, Disk, Net_Sent, Net_Recv]"] --> Ingestion["FastAPI Telemetry Ingestion\n(POST /api/v1/metrics)"]
    
    subgraph CorrelatedEngine["3-Tier Correlated Anomaly Pipeline (ai_service.py)"]
        T1["Tier 1: Safe Boundary Gate\n(CPU >= 80%, RAM >= 85%, or Disk >= 85%)"]
        T2["Tier 2: Isolation Forest (Scikit-Learn)\n5D Spatial Anomaly Scoring (0.0 to 1.0)"]
        T3["Tier 3: LSTM Autoencoder (PyTorch)\n15-Step Sliding Temporal Sequence Window"]
    end
    
    Ingestion --> T1
    T1 -- "Resource Usage Elevated" --> T2
    T2 -- "Spatial Outlier Detected" --> T3
    
    subgraph AttributionEngine["Explainability & Evidence (explainability.py)"]
        ZScore["Feature Attribution Engine\nZ-Score Standardized Deviation Breakdown"]
        Residual["Reconstruction MSE Residual Calculation\n(Optimal Threshold Cutoff: 0.79135)"]
    end

    T3 -- "Reconstruction Error Exceeded" --> AttributionEngine
    AttributionEngine --> Dashboard["Anomaly Center Dashboard (AnomaliesView.js)\n• Observed vs Expected Bound\n• Primary Root-Cause Attribution\n• Interactive True/False Positive Feedback"]
    Dashboard --> Feedback["Human-in-the-Loop Feedback\n(Dynamic Sensitivity Calibration)"]
```

- **Source Code References:**
  - Coordination: [`backend/app/services/ai_service.py`](file:///C:/CLoudProject/backend/app/services/ai_service.py)
  - Isolation Forest: [`ai_engine/anomaly_detector.py`](file:///C:/CLoudProject/ai_engine/anomaly_detector.py)
  - LSTM Autoencoder: [`ai_engine/lstm_detector.py`](file:///C:/CLoudProject/ai_engine/lstm_detector.py)
  - Explainability: [`ai_engine/explainability.py`](file:///C:/CLoudProject/ai_engine/explainability.py)

---

## 5. FinOps Hybrid Cost Optimization & Currency Engine

The cost optimization engine combines static cloud unit catalog pricing with dynamic rolling telemetry analysis and real-time European Central Bank currency conversion.

```mermaid
flowchart TD
    subgraph StaticPricing["1. Base Cloud Unit Pricing (STATIC)"]
        Catalog["Standard Reference Pricing Catalog\n(AWS, Azure, GCP On-Demand List Prices in USD)"]
        DBTable["pricing_catalog SQLite Table"]
    end

    subgraph DynamicWorkload["2. Fleet Utilization & Rightsizing (DYNAMIC)"]
        Sensors["Physical Sensor Nodes & Telemetry Ingestion"]
        Calc["60-Sample Peak & Average CPU/RAM Analyzer"]
        Recs["Automated Rightsizing & Idle Proposals"]
    end

    subgraph DynamicFX["3. Currency Conversion / FX (DYNAMIC)"]
        Frankfurter["Live Frankfurter API (ECB Daily Rates)"]
        Display["Localized Currency Display\n(INR, EUR, GBP, JPY, CAD, AUD, etc.)"]
    end

    Catalog --> DBTable
    DBTable --> Recs
    Sensors --> Calc
    Calc --> Recs
    Recs --> Display
    Frankfurter --> Display
```

- **Source Code References:**
  - Calculator: [`cost_engine/calculator.py`](file:///C:/CLoudProject/cost_engine/calculator.py)
  - Cost Service: [`backend/app/services/cost_service.py`](file:///C:/CLoudProject/backend/app/services/cost_service.py)
  - Currency Service: [`backend/app/services/currency_service.py`](file:///C:/CLoudProject/backend/app/services/currency_service.py)

---

## 6. FinOps Workload Rightsizing Decision Logic

When evaluating provisioned cloud instances against observed workloads, the engine detects over-provisioning and calculates net monthly savings.

```mermaid
flowchart LR
    Host["Host: prod-api-01\nType: c5.2xlarge\nCost: $244.80/mo\n(8 vCPU / 16GB RAM)"] --> Telemetry["Telemetry Analyzer (Last 60 Samples):\nObserved Peak CPU: 22%\nObserved Peak RAM: 34%"]
    Telemetry --> Recommendation["Engine Flags: RIGHTSIZE_DOWN\nSuggested Type: c5.large\nNew Cost: $61.20/mo\n(2 vCPU / 4GB RAM)"]
    Recommendation --> Savings["Calculated Net Savings:\n+$183.60 / month\n(75% Cost Reduction)"]
```

- **Decision Formula:**
  - If instance is `2xlarge` and Peak CPU $< 40\%$ and Peak RAM $< 45\%$ $\rightarrow$ Downsize to `large` (Confidence: 88%).
  - If Average CPU $< 5\%$ and Average RAM $< 25\%$ $\rightarrow$ Flag for `IDLE_TERMINATION` (Confidence: 95%).

---

## 7. Cloud Virtual Machine vs Bare-Metal Architecture

This diagram illustrates the architectural distinction between cloud-hosted virtual machines and physical lab computers (like `PC-lab10-18`).

```mermaid
flowchart TD
    subgraph CloudArch["1. Cloud Virtual Machine Architecture (e.g. c5.2xlarge, t3.medium)"]
        direction TB
        App1["Application & Telemetry Collector (psutil daemon)"]
        OS1["Guest Operating System (Linux / Windows Server)"]
        Hyp["Cloud Hypervisor / Virtualization Layer (AWS Nitro / KVM / Xen)"]
        HW1["Shared Physical Cloud Hardware (AWS / Azure / GCP Data Center)"]
        Cost1["Billed by Cloud Provider Hourly Metering ($/hour)"]

        App1 --> OS1 --> Hyp --> HW1 --> Cost1
    end

    subgraph BareMetalArch["2. Bare-Metal Physical PC Architecture (e.g. PC-lab10-18)"]
        direction TB
        App2["Real Agent Telemetry Daemon (psutil sensor)"]
        OS2["Host Operating System (Windows 10 / Ubuntu)"]
        HW2["Direct Physical Silicon & Hardware (Motherboard, CPU, RAM, Disk)"]
        Cost2["No Hourly Cloud Fees (On-Premises Facility Amortization)"]

        App2 --> OS2 --> HW2 --> Cost2
    end
```

- **Cloud Instance:** Billed hourly based on cloud provider catalogs (AWS/Azure/GCP).
- **Bare-Metal Node:** On-premises physical machine owned locally. Displays `bare-metal` in the UI and defaults to baseline amortized facility operational cost.

---

## 8. 4-Tier Cumulative Role-Based Access Control (RBAC) Hierarchy

CloudOps Intel enforces a strict hierarchical role structure where higher roles inherit all lower permissions.

```mermaid
flowchart TD
    subgraph Tier4["Level 4: SUPER_ADMIN (Platform Owner & Master Authority)"]
        direction TB
        SA1["Master Governance & Multi-Step Role Promotion"]
        SA2["Approve / Reject Prospective Administrator Requests"]
        SA3["Trigger Live SMTP Relay Diagnostic Self-Tests"]
    end

    subgraph Tier3["Level 3: ADMIN (Infrastructure & Policy Manager)"]
        direction TB
        AD1["Configure Alert Rules (Thresholds, Durations, Severities)"]
        AD2["Issue 15-Minute Sensor Enrollment Codes (ec_...)"]
        AD3["Inspect Immutable System & Security Audit Trail"]
        AD4["Manage Reference Cloud Pricing Catalog Tiers"]
    end

    subgraph Tier2["Level 2: OPERATOR (SRE Incident Responder & Triage)"]
        direction TB
        OP1["Acknowledge & Mark Active Alerts as Resolved"]
        OP2["Label Anomalies: True Positive / False Alarm Feedback"]
        OP3["Update Security Incidents (Investigating / Mitigated)"]
        OP4["Accept or Dismiss FinOps Rightsizing Proposals"]
    end

    subgraph Tier1["Level 1: VIEWER (Read-Only Observability)"]
        direction TB
        VI1["View Real-Time Dashboards & Live Resource Gauges"]
        VI2["Room-wise Lab PC Status & Liveness Heartbeats"]
        VI3["Generate & Export Executive Operational A4 PDF Reports"]
        VI4["Natural Language SRE Incident Narrator AI Queries"]
    end

    Tier4 --> Tier3
    Tier3 --> Tier2
    Tier2 --> Tier1
```

- **Source Code References:**
  - RBAC Guards: [`backend/app/api/deps.py`](file:///C:/CLoudProject/backend/app/api/deps.py#L228-L231)
  - User Model: [`backend/app/models/user.py`](file:///C:/CLoudProject/backend/app/models/user.py#L19-L26)

---

## 9. Physical Sensor Device Enrollment & Anti-Spoofing Handshake

Enrolling a new physical PC follows a secure two-phase handshake that prevents rogue nodes from spoofing telemetry.

```mermaid
flowchart TD
    subgraph Phase1["Phase 1: Operator Authorization & Code Generation"]
        A1["Administrator requests enrollment code in Dashboard"]
        A2["Backend generates short-lived code: ec_... (15-min expiration)"]
        A3["Code stored with SHA-256 hash in SQLite (Single-Use)"]
        A1 --> A2 --> A3
    end

    subgraph Phase2["Phase 2: Sensor Handshake & Hardware Binding"]
        B1["Sensor installer executed on Lab PC: install_sensor_client.ps1"]
        B2["Installer extracts physical Hardware UUID via PowerShell WMI/CIM"]
        B3["Sensor submits POST /api/v1/devices/enroll with Code + UUID + Hostname"]
        B1 --> B2 --> B3
    end

    subgraph Phase3["Phase 3: Cryptographic Validation & Key Provisioning"]
        C1["Backend verifies code validity and single-use status"]
        C2["Server provisions unique AgentApiKey: ag_..."]
        C3["Database permanently binds AgentApiKey to Hardware UUID & host_id"]
        C4["Sensor saves key locally with restrictive NTFS ACLs (SYSTEM & Admin only)"]
        C1 --> C2 --> C3 --> C4
    end

    subgraph Phase4["Phase 4: Authenticated High-Frequency Ingestion"]
        D1["Sensor collects OS telemetry every 5 seconds (CPU, RAM, Disk, Net)"]
        D2["Transmits POST /api/v1/metrics with X-Agent-Key header over TLS 1.3"]
        D3["Server validates key against bound UUID (Rejects spoofed requests)"]
        D1 --> D2 --> D3
    end

    Phase1 --> Phase2
    Phase2 --> Phase3
    Phase3 --> Phase4
```

- **Source Code References:**
  - Installer: [`scripts/install_sensor_client.ps1`](file:///C:/CLoudProject/scripts/install_sensor_client.ps1)
  - Device API: [`backend/app/api/v1/devices.py`](file:///C:/CLoudProject/backend/app/api/v1/devices.py)
  - Device Service: [`backend/app/services/device_service.py`](file:///C:/CLoudProject/backend/app/services/device_service.py)

---

## 10. Industry Readiness Evolution: Current MVP vs Enterprise Standard

An honest engineering roadmap illustrating the transition from the current lab prototype to an enterprise-grade commercial deployment.

```mermaid
flowchart LR
    subgraph Current["Current State (Lab / MVP Phase)"]
        DB1["SQLite WAL (Single-Writer Contention)\nCapacity: <= 50 Hosts"]
        Agent1["Python Script + psutil\n(Requires local Python runtime on PC)"]
        Proto1["HTTP REST JSON Polling\n(High HTTP header & serialization overhead)"]
        Deploy1["Single Laptop / Local Server\n(Single point of failure, no clustering)"]
        Auth1["Local Database User Auth\n(Argon2id + PyJWT)"]
    end

    subgraph Industry["Enterprise Industry Standard"]
        DB2["TimescaleDB / ClickHouse / Prometheus\n(High-throughput distributed time-series DB)"]
        Agent2["Compiled Go / Rust Binary\n(Zero runtime dependencies, signed Windows Service)"]
        Proto2["gRPC / OTLP (OpenTelemetry)\n(Protobuf binary streaming over HTTP/2)"]
        Deploy2["Kubernetes (K8s) / AWS EKS\n(Multi-AZ auto-scaling with load balancing)"]
        Auth2["SAML 2.0 / OIDC / Azure AD / Okta\n(Enterprise Single Sign-On / IAM)"]
    end

    Current -.->|Engineering Evolution| Industry
```

---

## 11. Operational A4 Report & PDF Export Document Layout

Layout structure of the browser-native A4 executive PDF export generated by the Command Center.

```mermaid
flowchart TD
    subgraph ReportDocument["CloudOps Intel — Executive & Operational SRE Audit (A4 PDF)"]
        subgraph HeaderSection["Document Header & System Status"]
            Title["Title: Cloud Infrastructure & Security Intelligence Report"]
            Status["Status Badge: HEALTHY (0 Critical Alerts) / DEGRADED"]
        end

        subgraph MetaGrid["Metadata Strip (Audit & Provenance Grid)"]
            M1["Report ID: RPT-XXXXXXXX"]
            M2["Reporting Horizon: Start UTC → End UTC"]
            M3["Telemetry Freshness & Heartbeat Cutoff: 90s"]
            M4["Environment Scope & Display Currency: USD / INR"]
        end

        subgraph KpiGrid["Executive KPI Summary (4 Metric Cards)"]
            K1["Monitored Fleet: Total (Online / Offline / No Data)"]
            K2["Active Incidents: Critical & Warning Alert Counts"]
            K3["Security Posture: No Security Events Flagged"]
            K4["Financial Impact: Potential Monthly Savings & Spend"]
        end

        subgraph Section1["Section 1: Monitored Fleet Inventory & Node Liveness Triage"]
            T1["Node Inventory Table:\nHostname | IP | Room | Status | Last Seen | CPU% | RAM% | Disk%"]
        end

        subgraph Section2["Section 2: Multi-Domain Findings & Operational Observations"]
            F1["Fleet Overview & Infrastructure Load Analysis"]
            F2["Security & Threat Observations (Auth Streams & Port Scans)"]
            F3["Cost Efficiency & Catalog Rightsizing Insights"]
        end

        subgraph Section3["Section 3: Technical Integrity & Disclaimers"]
            D1["Security Disclaimer: Absence of recorded events != proof of security"]
            D2["Dynamic Liveness Model: 90-second heartbeat cutoff threshold"]
        end

        HeaderSection --> MetaGrid --> KpiGrid --> Section1 --> Section2 --> Section3
    end
```

- **Source Code References:**
  - View Component: [`frontend/js/views/ReportsView.js`](file:///C:/CLoudProject/frontend/js/views/ReportsView.js)
  - Print Styles: [`frontend/css/command-center.css`](file:///C:/CLoudProject/frontend/css/command-center.css)
  - Backend Service: [`backend/app/services/report_service.py`](file:///C:/CLoudProject/backend/app/services/report_service.py)

