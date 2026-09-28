"""
Reports and Analytics API Router.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_viewer
from backend.app.models.user import User
from backend.app.schemas.report import ReportGenerateRequest, ReportResponse
from backend.app.services.report_service import generate_executive_report

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.post("/generate", response_model=ReportResponse)
def generate_report(
    req: ReportGenerateRequest,
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Generates a consolidated operational and security report across the requested timeframe.
    """
    return generate_executive_report(db, req)
