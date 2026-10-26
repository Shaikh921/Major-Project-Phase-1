"""
Device Enrollment & Workstation Management API Router.

Endpoints for:
- Client sensor registration requests using single-use cryptographically hashed enrollment codes.
- One-time credential claiming upon Super Admin physical verification.
- Super Admin device lifecycle management (Approve, Reject, Disable, Re-enable, Retire).
- Live fleet status overview and downloadable client agent bundle.
"""

import io
import os
import zipfile
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.core.rate_limit import rate_limit_ip
from backend.app.api.deps import get_db, get_current_super_admin
from backend.app.models.user import User
from backend.app.schemas.device import (
    EnrollmentCodeCreate,
    EnrollmentCodeGenerated,
    EnrollmentCodeRead,
    DeviceEnrollRequest,
    DeviceEnrollResponse,
    DeviceClaimCredentialRequest,
    DeviceClaimCredentialResponse,
    DeviceApproveRequest,
    DeviceRejectRequest,
    DeviceUninstallNoticeRequest,
    DeviceRead,
    DeviceSummaryStats,
)
from backend.app.services.device_service import (
    generate_enrollment_code,
    list_enrollment_codes,
    revoke_enrollment_code,
    request_enrollment,
    claim_credential,
    approve_device,
    reject_device,
    disable_device,
    enable_device,
    retire_device,
    record_uninstall_request,
    get_devices,
    get_device_by_id,
    get_device_summary_stats,
)

router = APIRouter(prefix="/devices", tags=["Device Enrollment & Management"])


# ==============================================================================
# Public / Sensor Workstation Endpoints (Rate-limited, verification protected)
# ==============================================================================

@router.post("/enroll", response_model=DeviceEnrollResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_device_enrollment(
    req: DeviceEnrollRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Called by client sensor installer with single-use enrollment code.
    Validates code, creates PENDING record, and returns a polling claim token.
    Pending devices cannot submit accepted telemetry.
    Protected by IP rate limiting (SEC-02).
    """
    rate_limit_ip(request, "device_enroll", max_requests=10, window_seconds=60)
    return request_enrollment(db, req)


@router.post("/claim-credential", response_model=DeviceClaimCredentialResponse)
def poll_claim_credential(
    req: DeviceClaimCredentialRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Polled by sensor agent. Once approved by Super Admin, returns the provisioned
    AgentApiKey exactly once.
    Protected by IP rate limiting (SEC-02).
    """
    rate_limit_ip(request, "device_claim", max_requests=30, window_seconds=60)
    return claim_credential(db, req)


@router.post("/uninstall-notice", status_code=status.HTTP_200_OK)
def notify_uninstall(
    req: DeviceUninstallNoticeRequest,
    db: Session = Depends(get_db),
):
    """
    Notifies server of a local client uninstallation when network connectivity is available.
    """
    success = record_uninstall_request(db, req)
    return {"status": "recorded" if success else "unrecognized_device"}


# ==============================================================================
# Super Administrator Endpoints (Strictly RBAC Enforced)
# ==============================================================================

@router.post("/enrollment-codes", response_model=EnrollmentCodeGenerated, status_code=status.HTTP_201_CREATED)
def create_enrollment_code(
    payload: EnrollmentCodeCreate,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Super Admin generates a single-use enrollment code expiring in N minutes (default 15m).
    Raw code is returned only in this response and is NEVER persisted in plaintext.
    """
    return generate_enrollment_code(
        db=db,
        super_admin=super_admin,
        expires_in_minutes=payload.expires_in_minutes,
        notes=payload.notes,
    )


@router.get("/enrollment-codes", response_model=List[EnrollmentCodeRead])
def get_enrollment_codes(
    limit: int = Query(default=50, ge=1, le=100),
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Lists recent enrollment codes omitting raw secrets."""
    return list_enrollment_codes(db, limit=limit)


@router.delete("/enrollment-codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enrollment_code(
    code_id: int,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Revokes an unused enrollment code prior to expiration."""
    revoke_enrollment_code(db, code_id, super_admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=List[DeviceRead])
def list_enrolled_devices(
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status: PENDING, APPROVED, DISABLED, RETIRED"),
    room_filter: Optional[str] = Query(default=None, alias="room", description="Filter by room number"),
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Lists enrolled workstations with computed online/offline and telemetry health states."""
    return get_devices(db, status_filter=status_filter, room_filter=room_filter)


@router.get("/summary", response_model=DeviceSummaryStats)
@router.get("/stats", response_model=DeviceSummaryStats, include_in_schema=False)
def get_summary_stats(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Retrieves fleet overview statistics for the Device Management tab."""
    return get_device_summary_stats(db)


@router.get("/download-package")
def download_sensor_package(
    super_admin: User = Depends(get_current_super_admin),
):
    """
    Generates a clean client sensor distribution bundle (.zip) containing:
    - monitoring_agent/ (collector, durable buffer, agent daemon)
    - root.crt (Public Certificate Authority bundle for TLS verification)
    - install_sensor.ps1 (Configurable client installer script)
    NEVER includes root.key, .env, or master server secrets.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    agent_dir = os.path.join(project_root, "monitoring_agent")
    root_crt = os.path.join(project_root, "data", "caddy", "pki", "authorities", "local", "root.crt")

    if not os.path.exists(agent_dir):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="monitoring_agent directory not found on server.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Package monitoring_agent/ files
        for root, _, files in os.walk(agent_dir):
            for file in files:
                if file.endswith((".py", ".txt", ".md")) and not file.endswith(".pyc") and "__pycache__" not in root:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, project_root)
                    zf.write(file_path, arcname=rel_path)

        # 2. Package public root.crt if present
        if os.path.exists(root_crt):
            zf.write(root_crt, arcname="root.crt")

        # 3. Add client installer template
        installer_ps1 = os.path.join(project_root, "scripts", "install_sensor_client.ps1")
        if os.path.exists(installer_ps1):
            zf.write(installer_ps1, arcname="install_sensor_client.ps1")

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=cloudops-sensor-package.zip"},
    )


@router.get("/{device_id}", response_model=DeviceRead)
def get_device_details(
    device_id: int,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Retrieves full details for a specific device enrollment."""
    device = get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    from backend.app.services.device_service import _to_device_read
    return _to_device_read(device)


@router.post("/{device_id}/approve", response_model=DeviceRead)
def approve_pending_device(
    device_id: int,
    req: DeviceApproveRequest,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """
    Super Admin explicitly approves a pending device, assigns label, lab, room,
    and provisions a unique, revocable AgentApiKey.
    """
    return approve_device(db, device_id, req, super_admin)


@router.post("/{device_id}/reject", response_model=DeviceRead)
def reject_pending_device(
    device_id: int,
    req: DeviceRejectRequest,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Super Admin rejects a pending enrollment request."""
    return reject_device(db, device_id, req, super_admin)


@router.post("/{device_id}/disable", response_model=DeviceRead)
def disable_enrolled_device(
    device_id: int,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Temporarily blocks telemetry ingestion for an enrolled device."""
    return disable_device(db, device_id, super_admin)


@router.post("/{device_id}/enable", response_model=DeviceRead)
def enable_enrolled_device(
    device_id: int,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Re-enables telemetry ingestion for a disabled device."""
    return enable_device(db, device_id, super_admin)


@router.post("/{device_id}/retire", response_model=DeviceRead)
def retire_enrolled_device(
    device_id: int,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Permanently revokes device credentials and marks device as RETIRED."""
    return retire_device(db, device_id, super_admin)
