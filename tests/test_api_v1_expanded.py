"""
Integration Tests for Expanded API v1 Routers (Security, Cost, Narrator, Reports, Audit).
"""

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_api_security_endpoints():
    # 1. Summary
    res = client.get("/api/v1/security/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_events" in data
    assert "open_incidents" in data

    # 2. Create Event
    create_res = client.post(
        "/api/v1/security/events",
        json={
            "event_type": "port_scan",
            "severity": "medium",
            "source_ip": "198.51.100.99",
            "destination_port": 8080,
            "description": "Port scan activity on port 8080",
        },
    )
    assert create_res.status_code == 201
    event_id = create_res.json()["id"]

    # 3. Update Status
    patch_res = client.patch(
        f"/api/v1/security/events/{event_id}",
        json={"status": "mitigated"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "mitigated"


def test_api_cost_endpoints():
    res = client.get("/api/v1/cost/summary")
    assert res.status_code == 200
    data = res.json()
    assert "estimated_monthly_spend_usd" in data
    assert "top_cost_resources" in data


def test_api_narrator_endpoint():
    res = client.post(
        "/api/v1/narrator/query",
        json={
            "query": "Explain active alerts and potential root cause",
            "time_window_minutes": 60,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "structured_explanation" in data
    assert "raw_markdown_narrative" in data


def test_api_reports_and_audit_endpoints():
    # Reports
    rep_res = client.post(
        "/api/v1/reports/generate",
        json={"time_range_hours": 24},
    )
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert "report_id" in rep_data
    assert "sections" in rep_data

    # Audit
    audit_res = client.get("/api/v1/audit/logs")
    assert audit_res.status_code == 200
    assert isinstance(audit_res.json(), list)
