"""
Device Enrollment & Workstation Lifecycle Service.

Implements single-use cryptographic enrollment codes, pending workstation queues,
manual physical location assignment, unique AgentApiKey issuance, revocation,
retirement, and multi-dimensional connectivity health calculations (180s threshold).
"""

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.host import Host
from backend.app.models.agent_key import AgentApiKey
from backend.app.models.device import (
    DeviceEnrollment,
    EnrollmentCode,
    DeviceStatus,
    TelemetryHealthStatus,
)
from backend.app.schemas.device import (
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
from backend.app.services.audit_service import record_audit_action


OFFLINE_THRESHOLD_SECONDS = 180
STALE_THRESHOLD_SECONDS = 60


def _hash_token(raw_token: str) -> str:
    """Cryptographic SHA-256 hash of secrets/tokens for safe DB storage."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def generate_enrollment_code(
    db: Session,
    super_admin: User,
    expires_in_minutes: int = 15,
    notes: Optional[str] = None,
) -> EnrollmentCodeGenerated:
    """
    Generates a cryptographically secure single-use enrollment code.
    Only the SHA-256 hash is persisted in the database; raw code is returned once.
    """
    raw_code = "ec_" + secrets.token_hex(16)
    code_hash = _hash_token(raw_code)
    code_prefix = raw_code[:11] + "..."
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_in_minutes)

    enrollment_code = EnrollmentCode(
        code_hash=code_hash,
        code_prefix=code_prefix,
        created_by_user_id=super_admin.id,
        expires_at=expires_at,
        is_used=False,
        created_at=now,
    )
    db.add(enrollment_code)
    db.commit()
    db.refresh(enrollment_code)

    record_audit_action(
        db=db,
        action="ENROLLMENT_CODE_GENERATED",
        target_resource=f"EnrollmentCode:{enrollment_code.id}",
        details=f"Generated enrollment code prefix {code_prefix} expiring in {expires_in_minutes}m. Notes: {notes or 'None'}",
        user_email=super_admin.email,
        result="success",
    )

    return EnrollmentCodeGenerated(
        id=enrollment_code.id,
        raw_code=raw_code,
        code_prefix=code_prefix,
        expires_at=expires_at,
        created_at=now,
    )


def list_enrollment_codes(db: Session, limit: int = 50) -> List[EnrollmentCodeRead]:
    """Lists recent enrollment codes omitting raw secret."""
    stmt = select(EnrollmentCode).order_by(desc(EnrollmentCode.created_at)).limit(limit)
    return [EnrollmentCodeRead.model_validate(c) for c in db.scalars(stmt).all()]


def revoke_enrollment_code(db: Session, code_id: int, super_admin: User) -> bool:
    """Revokes an unused enrollment code prior to expiration."""
    code = db.get(EnrollmentCode, code_id)
    if not code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment code not found.")
    if code.is_used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot revoke an already used enrollment code.")
    if code.revoked_at is not None:
        return True

    now = datetime.now(timezone.utc)
    code.revoked_at = now
    db.commit()

    record_audit_action(
        db=db,
        action="ENROLLMENT_CODE_REVOKED",
        target_resource=f"EnrollmentCode:{code.id}",
        details=f"Super Admin revoked enrollment code prefix {code.code_prefix}",
        user_email=super_admin.email,
        result="success",
    )
    return True


def request_enrollment(db: Session, req: DeviceEnrollRequest) -> DeviceEnrollResponse:
    """
    Submits a device enrollment request from a sensor installer.
    Validates single-use enrollment code, registers device in PENDING state,
    and returns a one-time polling claim token.
    """
    now = datetime.now(timezone.utc)
    code_hash = _hash_token(req.enrollment_code)

    # 1. Validate enrollment code
    stmt = select(EnrollmentCode).where(EnrollmentCode.code_hash == code_hash)
    code = db.scalar(stmt)
    if not code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid enrollment code.")
    if code.is_used:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Enrollment code has already been redeemed.")
    if code.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Enrollment code has been revoked.")
    if now > code.expires_at.replace(tzinfo=timezone.utc if code.expires_at.tzinfo is None else code.expires_at.tzinfo):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Enrollment code has expired.")

    # 2. Consume enrollment code (Atomic Single-Use)
    code.is_used = True
    code.used_at = now

    # 3. Generate claim token for sensor to poll approval status
    raw_claim_token = "claim_" + secrets.token_hex(24)
    claim_token_hash = _hash_token(raw_claim_token)
    claim_expires_at = now + timedelta(hours=24)

    # 4. Check if device_uuid already exists in system
    stmt_dev = select(DeviceEnrollment).where(DeviceEnrollment.device_uuid == req.device_uuid)
    existing_device = db.scalar(stmt_dev)

    if existing_device:
        if existing_device.status in (DeviceStatus.APPROVED.value, DeviceStatus.DISABLED.value):
            # If approved or disabled, do not silently overwrite identity
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Device UUID '{req.device_uuid}' is already enrolled in state '{existing_device.status}'. Retire device first if replacing.",
            )
        # If PENDING or RETIRED, re-initialize request
        existing_device.reported_hostname = req.reported_hostname
        existing_device.ip_address = req.ip_address
        existing_device.mac_address = req.mac_address
        existing_device.os_version = req.os_version
        existing_device.agent_version = req.agent_version
        existing_device.status = DeviceStatus.PENDING.value
        existing_device.enrollment_code_id = code.id
        existing_device.claim_token_hash = claim_token_hash
        existing_device.claim_token_expires_at = claim_expires_at
        existing_device.pending_raw_key = None
        existing_device.credential_claimed = False
        existing_device.requested_at = now
        existing_device.rejection_reason = None
        db.commit()
        db.refresh(existing_device)
        device = existing_device
    else:
        device = DeviceEnrollment(
            device_uuid=req.device_uuid,
            reported_hostname=req.reported_hostname,
            ip_address=req.ip_address,
            mac_address=req.mac_address,
            os_version=req.os_version,
            agent_version=req.agent_version,
            status=DeviceStatus.PENDING.value,
            enrollment_code_id=code.id,
            claim_token_hash=claim_token_hash,
            claim_token_expires_at=claim_expires_at,
            requested_at=now,
            telemetry_health=TelemetryHealthStatus.HEALTHY.value,
            queue_backlog=0,
            credential_claimed=False,
        )
        db.add(device)
        db.commit()
        db.refresh(device)

    record_audit_action(
        db=db,
        action="DEVICE_ENROLLMENT_REQUESTED",
        target_resource=f"DeviceEnrollment:{device.id}",
        details=f"Device {device.reported_hostname} (UUID: {device.device_uuid[:12]}...) submitted enrollment request via code prefix {code.code_prefix}",
        user_email="system@ops.local",
        result="success",
        client_ip=req.ip_address,
    )

    return DeviceEnrollResponse(
        status=DeviceStatus.PENDING.value,
        request_id=device.id,
        device_uuid=device.device_uuid,
        claim_token=raw_claim_token,
        poll_interval_seconds=5,
        message="Enrollment request registered. Awaiting Super Administrator physical verification and approval.",
    )


def claim_credential(db: Session, req: DeviceClaimCredentialRequest) -> DeviceClaimCredentialResponse:
    """
    Polled by sensor agent. Once Super Admin approves, returns unique AgentApiKey exactly once.
    """
    now = datetime.now(timezone.utc)
    stmt = select(DeviceEnrollment).where(DeviceEnrollment.device_uuid == req.device_uuid)
    device = db.scalar(stmt)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")

    claim_hash = _hash_token(req.claim_token)
    if device.claim_token_hash != claim_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid claim token.")

    if device.claim_token_expires_at:
        exp = device.claim_token_expires_at.replace(tzinfo=timezone.utc if device.claim_token_expires_at.tzinfo is None else device.claim_token_expires_at.tzinfo)
        if now > exp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Claim token has expired. Re-enrollment required.")

    if device.status == DeviceStatus.PENDING.value:
        return DeviceClaimCredentialResponse(
            status=DeviceStatus.PENDING.value,
            server_time=now,
        )

    if device.status == DeviceStatus.REJECTED.value:
        return DeviceClaimCredentialResponse(
            status=DeviceStatus.REJECTED.value,
            rejection_reason=device.rejection_reason,
            server_time=now,
        )

    if device.status == DeviceStatus.APPROVED.value:
        if device.credential_claimed or not device.pending_raw_key:
            # Already delivered
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Credential has already been claimed. Contact Super Admin to rotate or reissue credentials.",
            )

        # Single-use delivery of raw API key
        raw_key = device.pending_raw_key
        device.pending_raw_key = None
        device.credential_claimed = True
        device.claim_token_hash = None
        db.commit()

        record_audit_action(
            db=db,
            action="DEVICE_CREDENTIAL_CLAIMED",
            target_resource=f"DeviceEnrollment:{device.id}",
            details=f"Device {device.assigned_name or device.reported_hostname} claimed issued AgentApiKey successfully.",
            user_email="system@ops.local",
            result="success",
        )

        return DeviceClaimCredentialResponse(
            status=DeviceStatus.APPROVED.value,
            agent_key=raw_key,
            assigned_name=device.assigned_name,
            lab_name=device.lab_name,
            room_number=device.room_number,
            pc_number=device.pc_number,
            server_time=now,
        )

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Device in unclaimable state: '{device.status}'")


def approve_device(
    db: Session,
    device_id: int,
    req: DeviceApproveRequest,
    super_admin: User,
) -> DeviceRead:
    """
    Super Admin approves pending device, assigns physical room/PC label,
    and provisions a unique, revocable AgentApiKey.
    """
    device = db.get(DeviceEnrollment, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    if device.status != DeviceStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Device is not in PENDING state (current: {device.status}).")

    now = datetime.now(timezone.utc)

    # 1. Generate unique AgentApiKey for this device
    raw_key = "ak_lab_" + secrets.token_hex(24)
    key_prefix = raw_key[:16]
    key_hash = _hash_token(raw_key)

    api_key_record = AgentApiKey(
        name=f"LabPC: {req.assigned_name} ({device.device_uuid[:8]})",
        key_prefix=key_prefix,
        hashed_key=key_hash,
        description=f"Assigned to {req.assigned_name} in {req.lab_name or 'Lab'} {req.room_number or ''}",
        source_type="REAL_AGENT",
        device_uuid=device.device_uuid,
        is_active=True,
        is_disabled=False,
        created_at=now,
    )
    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)

    # 2. Auto-bind or create Host record
    stmt_host = select(Host).where(Host.hostname == req.assigned_name)
    host = db.scalar(stmt_host)
    if not host:
        host = Host(
            hostname=req.assigned_name,
            ip_address=device.ip_address,
            environment="lab",
            provider="bare-metal",
            region=req.room_number or "lab-room",
            source_type="REAL_AGENT",
            is_active=True,
            tags={"device_uuid": device.device_uuid, "pc_number": req.pc_number or ""},
            created_at=now,
        )
        db.add(host)
        db.commit()
        db.refresh(host)
    else:
        host.environment = "lab"
        host.region = req.room_number or host.region
        host.source_type = "REAL_AGENT"
        host.is_active = True
        db.commit()

    # 3. Update device enrollment record
    device.assigned_name = req.assigned_name
    device.lab_name = req.lab_name
    device.room_number = req.room_number
    device.pc_number = req.pc_number
    device.status = DeviceStatus.APPROVED.value
    device.agent_key_id = api_key_record.id
    device.host_id = host.id
    device.reviewed_at = now
    device.reviewed_by_user_id = super_admin.id
    device.pending_raw_key = raw_key
    device.credential_claimed = False
    db.commit()
    db.refresh(device)

    record_audit_action(
        db=db,
        action="DEVICE_APPROVED",
        target_resource=f"DeviceEnrollment:{device.id}",
        details=f"Approved device {device.reported_hostname} as '{req.assigned_name}' in {req.room_number}. Issued key prefix {key_prefix}...",
        user_email=super_admin.email,
        result="success",
    )

    return _to_device_read(device)


def reject_device(
    db: Session,
    device_id: int,
    req: DeviceRejectRequest,
    super_admin: User,
) -> DeviceRead:
    """Super Admin rejects a pending device enrollment request."""
    device = db.get(DeviceEnrollment, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    if device.status != DeviceStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Device is not in PENDING state (current: {device.status}).")

    now = datetime.now(timezone.utc)
    device.status = DeviceStatus.REJECTED.value
    device.rejection_reason = req.reason or "Rejected by administrator"
    device.reviewed_at = now
    device.reviewed_by_user_id = super_admin.id
    device.pending_raw_key = None
    db.commit()
    db.refresh(device)

    record_audit_action(
        db=db,
        action="DEVICE_REJECTED",
        target_resource=f"DeviceEnrollment:{device.id}",
        details=f"Rejected enrollment request for {device.reported_hostname} (UUID: {device.device_uuid[:12]}). Reason: {device.rejection_reason}",
        user_email=super_admin.email,
        result="success",
    )

    return _to_device_read(device)


def disable_device(db: Session, device_id: int, super_admin: User) -> DeviceRead:
    """Temporarily disables telemetry ingestion for an enrolled device."""
    device = db.get(DeviceEnrollment, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    if device.status == DeviceStatus.RETIRED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot disable a retired device.")

    device.status = DeviceStatus.DISABLED.value
    if device.agent_key_id:
        key = db.get(AgentApiKey, device.agent_key_id)
        if key:
            key.is_disabled = True
            key.is_active = False

    db.commit()
    db.refresh(device)

    record_audit_action(
        db=db,
        action="DEVICE_DISABLED",
        target_resource=f"DeviceEnrollment:{device.id}",
        details=f"Disabled telemetry ingestion for {device.assigned_name or device.reported_hostname}.",
        user_email=super_admin.email,
        result="success",
    )
    return _to_device_read(device)


def enable_device(db: Session, device_id: int, super_admin: User) -> DeviceRead:
    """Re-enables telemetry ingestion for a disabled device."""
    device = db.get(DeviceEnrollment, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    if device.status != DeviceStatus.DISABLED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Device is not in DISABLED state.")

    # Check key revocation
    if device.agent_key_id:
        key = db.get(AgentApiKey, device.agent_key_id)
        if key and key.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot re-enable device because its credential was permanently revoked. Rotate key first.")
        if key:
            key.is_disabled = False
            key.is_active = True

    device.status = DeviceStatus.APPROVED.value
    db.commit()
    db.refresh(device)

    record_audit_action(
        db=db,
        action="DEVICE_ENABLED",
        target_resource=f"DeviceEnrollment:{device.id}",
        details=f"Re-enabled telemetry ingestion for {device.assigned_name or device.reported_hostname}.",
        user_email=super_admin.email,
        result="success",
    )
    return _to_device_read(device)


def retire_device(db: Session, device_id: int, super_admin: User) -> DeviceRead:
    """Permanently revokes device credentials and marks device as RETIRED."""
    device = db.get(DeviceEnrollment, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")

    now = datetime.now(timezone.utc)
    device.status = DeviceStatus.RETIRED.value
    device.retirement_confirmed = True

    if device.agent_key_id:
        key = db.get(AgentApiKey, device.agent_key_id)
        if key:
            key.is_active = False
            key.is_disabled = True
            key.revoked_at = now

    db.commit()
    db.refresh(device)

    record_audit_action(
        db=db,
        action="DEVICE_RETIRED",
        target_resource=f"DeviceEnrollment:{device.id}",
        details=f"Retired workstation {device.assigned_name or device.reported_hostname} and revoked credentials permanently.",
        user_email=super_admin.email,
        result="success",
    )
    return _to_device_read(device)


def record_uninstall_request(db: Session, req: DeviceUninstallNoticeRequest) -> bool:
    """
    Called by client uninstaller when network connectivity is available.
    Marks device as retirement requested.
    """
    stmt = select(DeviceEnrollment).where(DeviceEnrollment.device_uuid == req.device_uuid)
    device = db.scalar(stmt)
    if not device:
        return False

    device.retirement_requested = True
    db.commit()

    record_audit_action(
        db=db,
        action="DEVICE_UNINSTALL_REQUESTED",
        target_resource=f"DeviceEnrollment:{device.id}",
        details=f"Client uninstaller notified server of local uninstallation on {device.reported_hostname}. Reason: {req.reason}",
        user_email="system@ops.local",
        result="success",
    )
    return True


def get_devices(
    db: Session,
    status_filter: Optional[str] = None,
    room_filter: Optional[str] = None,
) -> List[DeviceRead]:
    """Queries all devices with calculated online/offline status."""
    stmt = select(DeviceEnrollment).order_by(desc(DeviceEnrollment.requested_at))
    if status_filter:
        stmt = stmt.where(DeviceEnrollment.status == status_filter.upper())
    if room_filter:
        stmt = stmt.where(DeviceEnrollment.room_number == room_filter)

    devices = db.scalars(stmt).all()
    return [_to_device_read(d) for d in devices]


def get_device_by_id(db: Session, device_id: int) -> Optional[DeviceEnrollment]:
    """Retrieves device entity by primary ID."""
    return db.get(DeviceEnrollment, device_id)


def get_device_summary_stats(db: Session) -> DeviceSummaryStats:
    """Computes fleet overview counts for Device Management tab."""
    devices = db.scalars(select(DeviceEnrollment)).all()
    now = datetime.now(timezone.utc)

    total = len(devices)
    pending = sum(1 for d in devices if d.status == DeviceStatus.PENDING.value)
    approved = sum(1 for d in devices if d.status == DeviceStatus.APPROVED.value)
    disabled = sum(1 for d in devices if d.status == DeviceStatus.DISABLED.value)
    retired = sum(1 for d in devices if d.status == DeviceStatus.RETIRED.value)

    online_count = 0
    offline_count = 0
    healthy_telemetry = 0
    stale_telemetry = 0

    for d in devices:
        if d.status == DeviceStatus.APPROVED.value:
            is_on = False
            if d.last_contact_at:
                ts = d.last_contact_at.replace(tzinfo=timezone.utc if d.last_contact_at.tzinfo is None else d.last_contact_at.tzinfo)
                if (now - ts).total_seconds() <= OFFLINE_THRESHOLD_SECONDS:
                    is_on = True

            if is_on:
                online_count += 1
                if d.telemetry_health == TelemetryHealthStatus.STALE.value:
                    stale_telemetry += 1
                else:
                    healthy_telemetry += 1
            else:
                offline_count += 1

    return DeviceSummaryStats(
        total_devices=total,
        pending_approval=pending,
        approved_active=approved,
        disabled=disabled,
        retired=retired,
        online_count=online_count,
        offline_count=offline_count,
        healthy_telemetry=healthy_telemetry,
        stale_telemetry=stale_telemetry,
    )


def update_device_telemetry_heartbeat(
    db: Session,
    device_uuid: str,
    collection_ts: Optional[datetime] = None,
    upload_ts: Optional[datetime] = None,
    queue_backlog: int = 0,
) -> None:
    """Updates device contact timestamps and evaluates telemetry freshness."""
    now = datetime.now(timezone.utc)
    stmt = select(DeviceEnrollment).where(DeviceEnrollment.device_uuid == device_uuid)
    device = db.scalar(stmt)
    if not device:
        return

    device.last_contact_at = now
    if upload_ts:
        device.last_upload_at = upload_ts
    else:
        device.last_upload_at = now

    if collection_ts:
        device.last_collection_at = collection_ts
        c_ts = collection_ts.replace(tzinfo=timezone.utc if collection_ts.tzinfo is None else collection_ts.tzinfo)
        # Check staleness: if metric collection is older than 60s
        if (now - c_ts).total_seconds() > STALE_THRESHOLD_SECONDS:
            device.telemetry_health = TelemetryHealthStatus.STALE.value
        else:
            device.telemetry_health = TelemetryHealthStatus.HEALTHY.value

    device.queue_backlog = queue_backlog
    try:
        db.commit()
    except Exception:
        db.rollback()


def _to_device_read(d: DeviceEnrollment) -> DeviceRead:
    """Converts DeviceEnrollment entity to DeviceRead with computed is_online."""
    now = datetime.now(timezone.utc)
    is_online = False
    if d.last_contact_at:
        ts = d.last_contact_at.replace(tzinfo=timezone.utc if d.last_contact_at.tzinfo is None else d.last_contact_at.tzinfo)
        if (now - ts).total_seconds() <= OFFLINE_THRESHOLD_SECONDS:
            is_online = True

    return DeviceRead(
        id=d.id,
        device_uuid=d.device_uuid,
        reported_hostname=d.reported_hostname,
        assigned_name=d.assigned_name,
        lab_name=d.lab_name,
        room_number=d.room_number,
        pc_number=d.pc_number,
        ip_address=d.ip_address,
        mac_address=d.mac_address,
        os_version=d.os_version,
        agent_version=d.agent_version,
        status=d.status,
        telemetry_health=d.telemetry_health,
        queue_backlog=d.queue_backlog,
        is_online=is_online,
        requested_at=d.requested_at,
        reviewed_at=d.reviewed_at,
        last_contact_at=d.last_contact_at,
        last_collection_at=d.last_collection_at,
        last_upload_at=d.last_upload_at,
        rejection_reason=d.rejection_reason,
        retirement_requested=d.retirement_requested,
        retirement_confirmed=d.retirement_confirmed,
    )
