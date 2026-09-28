"""
AI Incident Narrator API Router (Module 5).

Provides conversational and structured incident analysis correlating signals across
Metrics, Alerts, Security Events, and Cost.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_viewer
from backend.app.models.user import User
from backend.app.schemas.narrator import NarratorQueryRequest, NarratorQueryResponse
from backend.app.services.narrator_service import execute_narrator_query

router = APIRouter(prefix="/narrator", tags=["AI Incident Narrator"])


@router.post("/query", response_model=NarratorQueryResponse)
def query_incident_narrator(
    req: NarratorQueryRequest,
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Submits a natural-language or incident inquiry to the AI Narrator engine.
    Returns structured observations, evidence citations, root-cause hypothesis,
    and recommended investigation steps.
    """
    return execute_narrator_query(db, req)
