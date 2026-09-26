# 🌐 Cloud Intelligence Platform

An intelligent, multi-cloud observability, AI-driven anomaly detection, cost optimization, security assessment, and narrative synthesis platform.

---

## 📋 Table of Contents
- [✨ Key Features](#-key-features)
- [📁 Repository Structure](#-repository-structure)
- [🚀 Quick Start Guide](#-quick-start-guide)
  - [1. Clone Repository](#1-clone-repository)
  - [2. Set Up Virtual Environment](#2-set-up-virtual-environment)
  - [3. Install Dependencies](#3-install-dependencies)
  - [4. Environment Variables](#4-environment-variables)
  - [5. Run the Application](#5-run-the-application)
- [🌐 Accessing Services](#-accessing-services)
- [🧪 Running Tests & Diagnostics](#-running-tests--diagnostics)
- [🐳 Running with Docker](#-running-with-docker)
- [🧩 Architecture & Modules](#-architecture--modules)

---

## ✨ Key Features

- **⚡ Real-Time Telemetry & Health Monitoring**: Multi-cloud resource metric collection (CPU, Memory, Disk, Network) with automatic anomaly ingestion.
- **🤖 AI & Deep Learning Anomaly Detection**: Multivariate Isolation Forest and LSTM Autoencoder for predictive incident detection.
- **📈 Predictive Forecasting**: Time-series regression forecasting with time-to-threshold countdowns and confidence intervals.
- **🛡️ Security Posture & Vulnerability Scanning**: CIS compliance evaluation, IAM policy checks, and network egress spike anomaly detection.
- **💰 Cloud Cost Intelligence**: Automated spend tracking, idle resource detection, and cost-reduction recommendations.
- **📝 Incident Synthesis & Narrator**: Auto-generated executive summaries and natural-language incident analysis.
- **🖥️ High-Density Dark SRE Dashboard**: Built-in responsive web user interface served directly alongside the API.

---

## 📁 Repository Structure

```text
Cloud-Intelligence-Platform/
│
├── backend/                # FastAPI Core REST API, DB models, services, & lifespan
│   └── app/
│       ├── api/v1/         # REST API route handlers
│       ├── core/           # Config & environment settings
│       ├── database/       # SQLite / PostgreSQL ORM schemas & init seeders
│       ├── models/         # SQLAlchemy DB models
│       ├── schemas/        # Pydantic request/response schemas
│       └── services/       # Core business logic (AI, alerts, security, cost)
│
├── frontend/               # Single-page SRE / SOC monitoring web dashboard
│   ├── css/                # CSS design system & tokens
│   ├── js/                 # Dashboard logic, charting & live polling
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
├── tests/                  # 45+ unit & integration test suites
├── scripts/                # Data generators, fleet simulators & verification scripts
├── docs/                   # Architecture, API specifications & design tokens
│
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependency manifest
├── README.md               # Project documentation
└── docker-compose.yml      # Multi-container orchestration
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.10+** (Python 3.10 – 3.13 supported)
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
*(If PowerShell restricts script execution, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

#### On Windows (CMD):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
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

### 4. Environment Variables

Create your local `.env` configuration file from `.env.example`:

#### On Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

#### On Linux / macOS:
```bash
cp .env.example .env
```

*(Default settings run out-of-the-box with local SQLite `cloud_intelligence.db`. API keys for OpenAI / Gemini / AWS are optional for local development).*

---

### 5. Run the Application

Start the application with a single terminal command:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### ⚡ Direct execution (without activating virtualenv):
- **Windows**: `.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload`
- **Linux/macOS**: `./.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload`

> **Note**: On first startup, the database schema and default fleet host records are automatically initialized and seeded.

---

## 🌐 Accessing Services

Once the server is running, open your web browser:

| Interface | URL | Description |
| :--- | :--- | :--- |
| **Web Dashboard** | [http://localhost:8000/](http://localhost:8000/) | SOC / SRE Live Monitoring & Analytics UI |
| **Interactive API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for exploring and testing API endpoints |
| **ReDoc API Reference** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Alternative structured REST documentation |
| **Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | Liveness probe endpoint (`{"status": "healthy"}`) |

---

## 🧪 Running Tests & Diagnostics

### Run Automated Test Suites
Run all 45+ unit and integration tests across all modules:
```bash
pytest tests/ -v
```

### Run Live Fleet Telemetry Simulation
To simulate live metrics, CPU/memory spikes, and anomaly alerts across 5 cloud hosts:
```bash
python scripts/simulate_fleet.py
```

### Run Live API Verification
To perform an automated end-to-end audit of all endpoints (Fleet Summary, AI Anomaly, Forecasting, Security & Costs):
```bash
python scripts/verify_live_api.py
```

---

## 🐳 Running with Docker

To spin up the complete containerized environment (PostgreSQL, Redis, Backend API, Monitoring Agent, and Frontend):

```bash
docker-compose up -d --build
```

To stop all services:
```bash
docker-compose down
```

---

## 🧩 Architecture & Modules

| Module | Core Logic Location | Description |
| :--- | :--- | :--- |
| **Backend Core** | `backend/app/` | RESTful API, database schemas, alert engine, CORS & static file mounting. |
| **AI Anomaly Detector** | `ai_engine/anomaly_detector.py` | Multivariate anomaly scoring & per-metric Z-score attribution. |
| **Time-Series Forecaster** | `ai_engine/forecaster.py` | Trend regression, confidence interval modeling & threshold ETA calculations. |
| **Monitoring Agent** | `monitoring_agent/` | Ring buffer metric collector for system & container telemetry. |
| **Security Posture** | `security_engine/` | CIS benchmark scans, open-port vulnerability detection & network spike alarms. |
| **Cost Optimizer** | `cost_engine/` | Idle instance detection, rightsizing recommendations & cost forecasting. |
| **Narrative Synthesis** | `narrator/` | Multi-agent reasoning for plain-language incident synthesis. |

---

## 📄 License
This project is developed for educational and enterprise cloud intelligence research.
