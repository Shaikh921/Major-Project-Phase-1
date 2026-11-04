"""
Reports and Analytics API Router.

Provides endpoints for:
1. Overall Infrastructure Monitoring Report (JSON preview + Downloadable PDF)
2. Individual Sensor / PC Performance Report (JSON preview + Downloadable PDF)
"""

from fastapi import APIRouter, Depends, Response, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_viewer
from backend.app.models.user import User
from backend.app.schemas.report import (
    ReportGenerateRequest,
    ReportResponse,
    HostReportRequest,
    HostReportResponse,
)
from backend.app.services.report_service import (
    generate_executive_report,
    generate_overall_report_pdf,
    generate_host_report_data,
    generate_host_report_pdf,
)

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.post("/generate", response_model=ReportResponse)
def generate_report(
    req: ReportGenerateRequest,
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Generates a consolidated operational and security report JSON preview
    across the requested timeframe and authorized infrastructure scope.
    """
    return generate_executive_report(db, req, user=current_user)


@router.post("/generate-pdf")
def generate_overall_pdf_report(
    req: ReportGenerateRequest,
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Generates and downloads a multi-page publication-grade PDF report
    covering the entire authorized infrastructure fleet.
    """
    pdf_bytes = generate_overall_report_pdf(db, req, user=current_user)
    filename = f"cloudops-overall-report-{req.environment or 'all'}-{req.time_range_hours}h.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.post("/host/{host_id}/generate", response_model=HostReportResponse)
def generate_individual_host_report(
    host_id: int,
    req: HostReportRequest,
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Generates a detailed operational and telemetry report JSON preview
    strictly scoped to one authorized sensor node.
    """
    return generate_host_report_data(db, host_id=host_id, req=req, user=current_user)


@router.post("/host/{host_id}/generate-pdf")
def generate_individual_host_pdf_report(
    host_id: int,
    req: HostReportRequest,
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
):
    """
    Generates and downloads a dedicated publication-grade PDF report
    containing strictly the selected workstation's diagnostics and telemetry.
    """
    pdf_bytes = generate_host_report_pdf(db, host_id=host_id, req=req, user=current_user)
    filename = f"cloudops-sensor-report-host-{host_id}-{req.time_range_hours}h.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )
