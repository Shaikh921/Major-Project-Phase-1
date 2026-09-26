"""
AI Incident Narrator API Router (Module 5).

Provides conversational and structured incident analysis correlating signals across
Metrics, Alerts, Security Events, and Cost.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.narrator import NarratorQueryRequest, NarratorQueryResponse
from backend.app.services.narrator_service import execute_narrator_query

router = APIRouter(prefix="/narrator", tags=["AI Incident Narrator"])


@router.post("/query", response_model=NarratorQueryResponse)
def query_incident_narrator(
    req: NarratorQueryRequest,
    db: Session = Depends(get_db),
):
    """
    Submits a natural-language or incident inquiry to the AI Narrator engine.
    Returns structured observations, evidence citations, root-cause hypothesis,
    and recommended investigation steps.
    """
    return execute_narrator_query(db, req)
