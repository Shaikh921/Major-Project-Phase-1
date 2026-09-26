# Cloud Intelligence Platform

An intelligent, multi-cloud observability, cost optimization, security assessment, and narrative synthesis platform powered by AI agents.

---

## 📁 Repository Structure

```
Cloud-Intelligence-Platform/
│
├── backend/                # FastAPI Core REST / WebSocket API & services
├── monitoring_agent/       # Telemetry collection, metrics & health monitoring agents
├── ai_engine/              # LLM reasoning, multi-agent orchestration & anomaly detection
├── cost_engine/            # Cloud cost analysis, forecasting & anomaly detection
├── security_engine/        # Security posture, compliance checks & vulnerability scanning
├── narrator/               # Executive summaries, incident narrative & incident reporting
├── frontend/               # Web UI dashboard
│
├── data/
│   ├── raw/                # Unprocessed metrics, logs, and telemetry data
│   ├── processed/          # Cleaned, normalized datasets for modeling
│   └── synthetic/          # Synthetic benchmarks and test scenarios
│
├── models/                 # Pretrained weights, serialized ML models & embeddings
├── tests/                  # Unit, integration, and end-to-end test suites
├── scripts/                # Utility scripts, data seeders, and migration helpers
├── docs/                   # Architecture, API specifications, and design documents
│
├── .env                    # Local environment variables
├── .env.example            # Template for environment configuration
├── .gitignore              # Git ignore rules
├── requirements.txt        # Python dependency manifest
├── README.md               # Project documentation
└── docker-compose.yml      # Multi-container local orchestration
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend)
- Docker & Docker Compose (optional, for containerized execution)

### 1. Environment Configuration
Copy the sample environment file and populate the relevant keys:
```bash
cp .env.example .env
```

### 2. Install Python Dependencies
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Run with Docker Compose
To launch all services (PostgreSQL, Redis, Backend, Monitoring Agent, Frontend):
```bash
docker-compose up -d --build
```

---

## 🧩 Components Overview

| Module | Description |
| :--- | :--- |
| **`backend/`** | API endpoints, business logic, DB models, and real-time event streaming. |
| **`monitoring_agent/`** | Real-time agents polling cloud metrics (AWS CloudWatch, GCP Cloud Monitoring, Azure Monitor). |
| **`ai_engine/`** | LLM orchestration and intelligent multi-agent synthesis. |
| **`cost_engine/`** | Analyzes cloud spend, identifies idle resources, and suggests savings plans. |
| **`security_engine/`** | Evaluates IAM policies, security groups, CVEs, and compliance drift. |
| **`narrator/`** | Converts complex metrics and security alerts into plain-language executive reports. |
| **`frontend/`** | Interactive dashboard for viewing insights, topology, and alerts. |

---

## 🧪 Testing

Run test suites using `pytest`:
```bash
pytest tests/ -v
```
