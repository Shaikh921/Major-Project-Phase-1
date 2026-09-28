# 🌐 Cloud Intelligence Platform & SRE Command Center

An intelligent, multi-cloud observability, AI-driven anomaly detection, multi-currency cost optimization, role-based access control (RBAC), production SMTP notification, and narrative synthesis platform.

---

## 📋 Table of Contents
- [✨ Key Features](#-key-features)
- [🧩 Architecture & Implemented Modules](#-architecture--implemented-modules)
  - [Module 1: SVG Vector Design System](#module-1-svg-vector-design-system)
  - [Module 2: Multi-Currency Conversion Engine](#module-2-multi-currency-conversion-engine)
  - [Module 3: RBAC & Super Admin Lifecycle](#module-3-rbac--super-admin-lifecycle)
  - [Module 4: Production SMTP & Email Notification System](#module-4-production-smtp--email-notification-system)
- [📁 Repository Structure](#-repository-structure)
- [🚀 Quick Start Guide](#-quick-start-guide)
  - [1. Clone Repository](#1-clone-repository)
  - [2. Set Up Virtual Environment](#2-set-up-virtual-environment)
  - [3. Install Dependencies](#3-install-dependencies)
  - [4. Environment Variables Configuration](#4-environment-variables-configuration)
  - [5. Bootstrap Initial Super Admin](#5-bootstrap-initial-super-admin)
  - [6. Run the Application](#6-run-the-application)
- [🌐 Accessing Services & Dashboard](#-accessing-services--dashboard)
- [📧 Email & SMTP Configuration Guide](#-email--smtp-configuration-guide)
- [🧪 Running Tests & Regression Suite (81 Tests)](#-running-tests--regression-suite-81-tests)
- [🐳 Running with Docker](#-running-with-docker)
- [📄 License](#-license)

---

## ✨ Key Features

- **⚡ Real-Time Telemetry & Health Monitoring**: Multi-cloud resource metric collection (CPU, Memory, Disk, Network) with automated anomaly ingestion.
- **🤖 AI & Deep Learning Anomaly Detection**: Multivariate Isolation Forest and LSTM Autoencoder for predictive incident detection.
- **📈 Predictive Forecasting**: Time-series regression forecasting with time-to-threshold countdowns and confidence intervals.
- **🛡️ Enterprise RBAC & Super Admin Management**: Role-based access hierarchy (`SUPER_ADMIN`, `ADMIN`, `OPERATOR`, `VIEWER`), prospective admin registration, verification, approval/rejection workflows, and audit logging.
- **📧 Production SMTP & Email Notification Engine**: STARTTLS/SSL delivery, responsive HTML + plaintext templates, anti-storm alert deduplication, and Super Admin live diagnostics.
- **💱 Multi-Currency Cost Intelligence**: Real-time currency conversion (USD, EUR, GBP, JPY, CAD, AUD, INR, CHF) with base USD storage integrity and spend optimization.
- **🎨 Vectorized Design System**: High-density dark SRE theme built exclusively with crisp SVG Lucide icons and responsive layout components.
- **📝 Incident Synthesis & Narrator**: Auto-generated executive summaries and natural-language incident analysis.

---

## 🧩 Architecture & Implemented Modules

### Module 1: SVG Vector Design System
- **Lucide Vector Icons**: Replaced all informal emojis and legacy assets with high-precision, scalable inline SVG icons (`frontend/js/components/Icons.js`).
- **Responsive SRE UI**: Fixed sidebar layout transitions, responsive table overflow, mobile drawer state preservation, and glassmorphism styling.

### Module 2: Multi-Currency Conversion Engine
- **Base USD Accounting**: Backend stores all metrics and financial projections strictly in USD (`backend/app/services/cost_service.py`).
- **Client-Side Currency Converter**: Centralized `currency_service.py` and UI currency selector supporting 8 major global currencies (`USD`, `EUR`, `GBP`, `JPY`, `CAD`, `AUD`, `INR`, `CHF`) with live symbol and formatting conversion across all charts, tables, and cost breakdowns.

### Module 3: RBAC & Super Admin Lifecycle
- **Hierarchical Role Model**:
  - `SUPER_ADMIN`: Full system control, Super Admin / Admin role promotions, admin request approval/rejection, and SMTP diagnostic tools.
  - `ADMIN`: Infrastructure rule configurations, incident management, and user provisioning.
  - `OPERATOR`: Alert triage, host telemetry monitoring, and feedback classification.
  - `VIEWER`: Read-only telemetry access.
- **Admin Registration & Approval Workflow**:
  1. Prospective Admin submits request via public portal.
  2. Verification email sent with secure token.
  3. Super Admins receive notification upon email verification.
  4. Super Admin approves or rejects the request.
  5. On approval, an inactive account is created and an activation link with a 24-hour expiration token is sent to the applicant.
- **Single-Use Password Reset**: Secure token hash verification preventing token reuse or leakage.

### Module 4: Production SMTP & Email Notification System
- **Dual-Mode Transport**:
  - **Development Mode (`SMTP_ENABLED=false`)**: Captures all outgoing emails to an in-memory test outbox (`_dev_outbox`) for deterministic, zero-network testing.
  - **Production Mode (`SMTP_ENABLED=true`)**: Dispatches RFC 5322 multipart emails over STARTTLS (port 587) or direct SSL (port 465).
- **Anti-Storm Incident Deduplication**: Rules evaluated by metric with highest severity prioritization; newly created critical alerts dispatch **one** email, while ongoing evaluations update snapshots without duplicate email storms.
- **7 Responsive Templates**:
  - Admin Email Verification
  - Super Admin New-Request Notification
  - Admin Approval & Account Activation
  - Admin Request Rejection
  - Single-Use Password Reset
  - Critical SRE Incident Alert
  - SMTP Relay Diagnostic Test
- **Super Admin SMTP Diagnostic Modal**: UI modal in Admin Management for real-time live connection tests with sanitized error reporting.

---

## 📁 Repository Structure

```text
Cloud-Intelligence-Platform/
│
├── backend/                # FastAPI Core REST API, DB models, services, & lifespan
│   └── app/
│       ├── api/v1/         # REST API route handlers (auth, admin, metrics, alerts, etc.)
│       ├── cli/            # Administrative CLI tools (bootstrap_admin.py)
│       ├── core/           # Config, database, security, and rate-limiting
│       ├── database/       # SQLite / PostgreSQL ORM schemas & init seeders
│       ├── models/         # SQLAlchemy DB models (User, Host, Metric, Alert, Audit, etc.)
│       ├── schemas/        # Pydantic request/response schemas
│       ├── services/       # Core business logic (auth, email, alerts, AI, currency, cost)
│       └── templates/      # Responsive HTML + plaintext email templates
│
├── frontend/               # Single-page SRE / SOC monitoring web dashboard
│   ├── css/                # CSS design system & dark-mode tokens
│   ├── js/                 # Views (Overview, Metrics, AdminManagement, Auth, etc.)
│   │   ├── components/     # Reusable SVG Icons, StatusBadges, and modals
│   │   ├── services/       # Client-side currency conversion & state
│   │   ├── api.js          # Centralized API client
│   │   ├── auth.js         # JWT token management & RBAC route guards
│   │   └── app.js          # Core routing and view lifecycle orchestration
│   └── index.html          # Main web application entry point
│
├── monitoring_agent/       # Telemetry collection & sliding window metric buffers
├── ai_engine/              # Isolation Forest, LSTM Autoencoders & forecasters
├── cost_engine/            # Cloud cost analysis, forecasting & anomaly detection
├── security_engine/        # Security posture, compliance checks & vulnerability scanning
├── narrator/               # Executive summaries & incident reporting engine
│
├── data/                   # Datasets (raw, processed, benchmarks & ground truth)
├── models/                 # Pretrained serialized ML models (.joblib, .pt)
├── tests/                  # 81 comprehensive unit & integration test suites
├── scripts/                # Data generators, fleet simulators & verification scripts
├── docs/                   # Architecture, API specifications & design tokens
│
├── .env.example            # Environment variables template with documentation
├── requirements.txt        # Python dependency manifest
├── README.md               # Project documentation
└── docker-compose.yml      # Multi-container orchestration
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.10+** (Python 3.10 – 3.13 fully supported)
- **Git**

---

### 1. Clone Repository

```bash
git clone https://github.com/Shaikh921/Major-Project-Phase-1.git
cd Major-Project-Phase-1
```

---

### 2. Set Up Virtual Environment

#### On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### On Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

### 4. Environment Variables Configuration

Copy `.env.example` to `.env`:

```bash
# Windows PowerShell:
Copy-Item .env.example .env

# Linux / macOS:
cp .env.example .env
```

---

### 5. Bootstrap Initial Super Admin

Before logging in for the first time, create the initial `SUPER_ADMIN` user via the CLI utility:

```bash
python -m backend.app.cli.bootstrap_admin
```

Follow the prompts or supply environment defaults to create your administrator credentials.

---

### 6. Run the Application

Start the FastAPI backend and frontend server:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 Accessing Services & Dashboard

Once the server is running, open your web browser:

| Interface | URL | Description |
| :--- | :--- | :--- |
| **Web Dashboard** | [http://localhost:8000/](http://localhost:8000/) | SOC / SRE Live Monitoring, Anomaly Center & Admin UI |
| **Interactive API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for exploring and testing API endpoints |
| **ReDoc API Reference** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Alternative structured REST documentation |
| **Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | Liveness probe endpoint (`{"status": "healthy"}`) |

---

## 📧 Email & SMTP Configuration Guide

### 1. Configure `.env`
To enable live email delivery (e.g. Gmail, Outlook, or corporate SMTP relay):

```ini
SMTP_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_TLS=true
SMTP_SSL=false
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME="CloudOps Intel Command Center"
SMTP_TIMEOUT_SECONDS=10

NOTIFY_SUPER_ADMINS_ON_NEW_REQUEST=true
NOTIFY_ON_CRITICAL_ALERTS=true
```

*(For Gmail: Generate a 16-character **App Password** under Google Account -> Security -> 2-Step Verification -> App Passwords).*

### 2. Test SMTP Delivery
- **From Dashboard UI**: Log in as `SUPER_ADMIN` -> Go to **Admin Management** -> Click **"Test Email / SMTP"** -> Enter recipient -> Click **"Dispatch Test Email"**.
- **From CLI**:
  ```bash
  python -c "from backend.app.services.email_service import EmailService; ok, msg = EmailService.send_test_email('your-email@example.com'); print(ok, msg)"
  ```

---

## 🧪 Running Tests & Regression Suite (81 Tests)

Run the complete test suite covering all modules:

```bash
pytest
```

### Test Coverage Highlights:
- **`tests/test_email_service.py`**: SMTP dispatch, STARTTLS, SSL, timeout handling, sanitization, anti-storm alert deduplication, and template rendering.
- **`tests/test_auth_service.py`**: Admin verification, approval, rejection, password reset, and rate limiting.
- **`tests/test_super_admin_service.py`**: Super Admin RBAC, role promotion, demotion protections, and audit logging.
- **`tests/test_currency_service.py`**: Multi-currency conversion accuracy and base USD accounting.
- **`tests/test_alert_engine.py` & `tests/test_ai_anomaly.py`**: Isolation Forest, anomaly thresholds, and alert state management.

```text
============================= 81 passed in 14.86s =============================
```

---

## 🐳 Running with Docker

To spin up the containerized stack:

```bash
docker-compose up -d --build
```

To stop all services:
```bash
docker-compose down
```

---

## 📄 License
This project is developed for educational and enterprise cloud intelligence research.
