"""
Narrator Service.

Coordinates incident analysis queries and returns grounded explanations (M5).
"""

from sqlalchemy.orm import Session
from backend.app.schemas.narrator import NarratorQueryRequest, NarratorQueryResponse
from narrator.engine import IncidentNarratorEngine

_engine = IncidentNarratorEngine()


def execute_narrator_query(
    db: Session,
    req: NarratorQueryRequest,
) -> NarratorQueryResponse:
    """Executes a cross-module query and returns a structured response."""
    result_dict = _engine.analyze_incident(
        db=db,
        query=req.query,
        host_id=req.host_id,
        environment=req.environment,
        time_window_minutes=req.time_window_minutes,
    )
    return NarratorQueryResponse.model_validate(result_dict)
