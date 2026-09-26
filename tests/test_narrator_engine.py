"""
Unit Tests for AI Incident Narrator Engine (Module 5).
"""

from narrator.engine import IncidentNarratorEngine
from backend.app.schemas.narrator import NarratorQueryRequest
from backend.app.services.narrator_service import execute_narrator_query
from tests.test_alert_engine import create_test_db


def test_narrator_cross_module_analysis():
    db = create_test_db()
    
    req = NarratorQueryRequest(query="What is the current operational health of the fleet?", time_window_minutes=60)
    res = execute_narrator_query(db, req)
    
    assert res.query == req.query
    assert res.structured_explanation is not None
    assert len(res.structured_explanation.evidence_points) > 0
    assert len(res.structured_explanation.cited_data_sources) > 0
    assert "Observed" in res.raw_markdown_narrative or "Observation" in res.raw_markdown_narrative
    assert res.disclaimer is not None

    db.close()
