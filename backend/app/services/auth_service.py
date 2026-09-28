"""
Authentication and Identity Business Logic Service.

Implements secure credential validation, session/refresh token lifecycle,
Argon2id password updates, audit journal logging, and anti-enumeration safeguards.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy import select, update, func, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.core.config import settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_secure_token,
    hash_token,
)
from backend.app.models.user import (
    User,
    UserRole,
    UserSession,
    EmailVerificationToken,
    PasswordResetToken,
    AdminRegistrationRequest,
    AdminActivationToken,
    AdminRequestStatus,
)
from backend.app.services.audit_service import record_audit_action
from backend.app.services.email_service import EmailService
from backend.app.schemas.auth import (
    UserCreateInternal,
    AdminRegistrationRequestCreate,
    AdminSummaryStats,
    AdminUserRead,
)


def _ensure_utc(dt: datetime) -> datetime:
    """Ensures datetime object is UTC timezone-aware for cross-DB compatibility."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Fetches user by primary key ID."""
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Fetches user by normalized email address."""
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def authenticate_user(
    db: Session,
    email: str,
    password: str,
    client_ip: Optional[str] = None,
) -> User:
    """
    Authenticates user credentials. Enforces Argon2id check, active state, and verification.
    Appends audit log on success/failure without logging credentials.
    """
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        record_audit_action(
            db=db,
            action="LOGIN_FAILURE",
            target_resource="Authentication Portal",
            details=f"Invalid credentials submitted for identifier: {email.strip().lower()}",
            user_email=email.strip().lower(),
            result="failure",
            client_ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        record_audit_action(
            db=db,
            action="LOGIN_FAILURE",
            target_resource="Authentication Portal",
            details="Login denied: account is deactivated or locked.",
            user_email=user.email,
            result="denied",
            client_ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact an administrator.",
        )

    if not user.is_verified:
        record_audit_action(
            db=db,
            action="LOGIN_FAILURE",
            target_resource="Authentication Portal",
            details="Login denied: email verification pending.",
            user_email=user.email,
            result="denied",
            client_ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account email is not verified. Please verify your email before logging in.",
        )

    record_audit_action(
        db=db,
        action="LOGIN_SUCCESS",
        target_resource="Authentication Portal",
        details=f"User authenticated successfully with role '{user.role}'.",
        user_email=user.email,
        result="success",
        client_ip=client_ip,
    )
    return user


def create_user_session(
    db: Session,
    user: User,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[str, str, int]:
    """
    Generates a short-lived access token and a long-lived trackable refresh token session.
    Returns (access_token, raw_refresh_token, access_token_expires_in_seconds).
    """
    now = datetime.now(timezone.utc)
    access_token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    expires_in_seconds = settings.access_token_expire_minutes * 60

    raw_refresh_token = generate_secure_token(32)
    refresh_hash = hash_token(raw_refresh_token)
    refresh_expires_at = now + timedelta(days=settings.refresh_token_expire_days)

    session = UserSession(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_expires_at,
        client_ip=client_ip,
        user_agent=user_agent[:255] if user_agent else None,
        created_at=now,
    )
    db.add(session)
    db.commit()

    return access_token, raw_refresh_token, expires_in_seconds


def refresh_user_session(
    db: Session,
    raw_refresh_token: str,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[str, str, int, User]:
    """
    Validates a refresh token against active database sessions and issues a new access token.
    """
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token.",
        )

    refresh_hash = hash_token(raw_refresh_token)
    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == refresh_hash,
            UserSession.revoked_at.is_(None),
        )
    )

    now = datetime.now(timezone.utc)
    if not session or _ensure_utc(session.expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is expired or revoked. Please log in again.",
        )

    user = get_user_by_id(db, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Associated user account is invalid or deactivated.",
        )

    # Issue fresh access token
    access_token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    expires_in_seconds = settings.access_token_expire_minutes * 60

    return access_token, raw_refresh_token, expires_in_seconds, user


def revoke_user_session(
    db: Session,
    raw_refresh_token: Optional[str],
    user: Optional[User] = None,
    client_ip: Optional[str] = None,
) -> bool:
    """
    Revokes the refresh token session in the database upon logout.
    """
    if raw_refresh_token:
        refresh_hash = hash_token(raw_refresh_token)
        session = db.scalar(
            select(UserSession).where(UserSession.token_hash == refresh_hash)
        )
        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()

    record_audit_action(
        db=db,
        action="LOGOUT",
        target_resource="Authentication Portal",
        details="User logged out and refresh session was revoked.",
        user_email=user.email if user else "anonymous",
        result="success",
        client_ip=client_ip,
    )
    return True


def create_bootstrap_admin(
    db: Session,
    email: str,
    password: str,
) -> User:
    """
    Secure first-run administrator provisioning.
    Ensures that only 1 initial bootstrap occurs and marks the root administrator as SUPER_ADMIN.
    """
    existing_super_admin = db.scalar(
        select(User).where(User.role == UserRole.SUPER_ADMIN).limit(1)
    )
    if existing_super_admin is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Super Administrator account already exists. Bootstrap is disabled.",
        )

    norm_email = email.strip().lower()
    
    # Check if this email already exists as a normal ADMIN (e.g. from previous Point 3) and promote it
    existing_user = db.scalar(select(User).where(User.email == norm_email))
    if existing_user:
        existing_user.role = UserRole.SUPER_ADMIN
        existing_user.is_active = True
        existing_user.is_verified = True
        existing_user.password_hash = hash_password(password)
        db.commit()
        db.refresh(existing_user)
        record_audit_action(
            db=db,
            action="ADMIN_BOOTSTRAP",
            target_resource="System Identity",
            details=f"Existing administrator promoted to Super Administrator: {norm_email}",
            user_email=norm_email,
            result="success",
        )
        return existing_user

    hashed_pwd = hash_password(password)
    admin = User(
        email=norm_email,
        password_hash=hashed_pwd,
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_verified=True,  # Root bootstrap super admin is pre-verified
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    record_audit_action(
        db=db,
        action="ADMIN_BOOTSTRAP",
        target_resource="System Identity",
        details=f"Initial platform Super Administrator provisioned: {norm_email}",
        user_email=norm_email,
        result="success",
    )
    return admin


def create_internal_user(
    db: Session,
    user_in: UserCreateInternal,
    creator_email: str = "system",
    client_ip: Optional[str] = None,
) -> Tuple[User, str]:
    """
    Internal user provisioning by an authenticated administrator.
    Creates user with is_verified=False and issues email verification token.
    """
    norm_email = user_in.email.strip().lower()
    existing = get_user_by_email(db, norm_email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{norm_email}' already exists.",
        )

    hashed_pwd = hash_password(user_in.password)
    user = User(
        email=norm_email,
        password_hash=hashed_pwd,
        role=user_in.role if user_in.role in UserRole.ALL_ROLES else UserRole.VIEWER,
        is_active=user_in.is_active,
        is_verified=user_in.is_verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    record_audit_action(
        db=db,
        action="USER_CREATED",
        target_resource="User Management",
        details=f"User created with role '{user.role}' by {creator_email}.",
        user_email=creator_email,
        result="success",
        client_ip=client_ip,
    )

    # Generate verification token if unverified
    raw_token = ""
    if not user.is_verified:
        raw_token = create_email_verification(db, user)

    return user, raw_token


def create_email_verification(db: Session, user: User) -> str:
    """Generates a secure verification token and dispatches email via EmailService."""
    raw_token = generate_secure_token(32)
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.verification_token_expire_hours)

    vt = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(vt)
    db.commit()

    EmailService.send_verification_email(email=user.email, raw_token=raw_token, user_id=user.id)
    record_audit_action(
        db=db,
        action="EMAIL_VERIFICATION_SENT",
        target_resource="Identity Verification",
        details=f"Verification dispatch sent to {user.email}",
        user_email=user.email,
        result="success",
    )
    return raw_token


def verify_email_token(db: Session, raw_token: str, client_ip: Optional[str] = None) -> User:
    """Validates an email verification token, marks user verified, and updates token state."""
    token_hash = hash_token(raw_token.strip())
    vt = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
        )
    )

    now = datetime.now(timezone.utc)
    if not vt or vt.used_at is not None or _ensure_utc(vt.expires_at) <= now:
        record_audit_action(
            db=db,
            action="EMAIL_VERIFY_FAILURE",
            target_resource="Identity Verification",
            details="Invalid, expired, or already-used verification token provided.",
            user_email="anonymous",
            result="failure",
            client_ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link is invalid, already used, or has expired.",
        )

    user = get_user_by_id(db, vt.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Associated user account not found.",
        )

    vt.used_at = now
    user.is_verified = True
    db.commit()

    record_audit_action(
        db=db,
        action="EMAIL_VERIFIED",
        target_resource="Identity Verification",
        details=f"Email address verified successfully for {user.email}",
        user_email=user.email,
        result="success",
        client_ip=client_ip,
    )
    return user


def request_password_reset(
    db: Session,
    email: str,
    client_ip: Optional[str] = None,
) -> str:
    """
    Generates a password reset token if account exists and dispatches reset instructions.
    Anti-enumeration: Caller always receives a generic confirmation string.
    """
    norm_email = email.strip().lower()
    user = get_user_by_email(db, norm_email)

    if user and user.is_active:
        raw_token = generate_secure_token(32)
        token_hash = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expire_minutes)

        prt = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(prt)
        db.commit()

        EmailService.send_password_reset_email(email=user.email, raw_token=raw_token, user_id=user.id)
        record_audit_action(
            db=db,
            action="PASSWORD_RESET_REQUESTED",
            target_resource="Password Recovery",
            details=f"Password reset requested for {user.email}",
            user_email=user.email,
            result="success",
            client_ip=client_ip,
        )

    return "If the account exists, password reset instructions have been sent."


def reset_password_with_token(
    db: Session,
    raw_token: str,
    new_password: str,
    client_ip: Optional[str] = None,
) -> User:
    """
    Validates reset token, updates password hash using Argon2id, revokes all existing sessions,
    and invalidates the reset token.
    """
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters long.",
        )

    token_hash = hash_token(raw_token.strip())
    prt = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
        )
    )

    now = datetime.now(timezone.utc)
    if not prt or prt.used_at is not None or _ensure_utc(prt.expires_at) <= now:
        record_audit_action(
            db=db,
            action="PASSWORD_RESET_FAILURE",
            target_resource="Password Recovery",
            details="Invalid, expired, or previously used password reset token attempted.",
            user_email="anonymous",
            result="failure",
            client_ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset link is invalid, already used, or has expired.",
        )

    user = get_user_by_id(db, prt.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Associated user account not found.",
        )

    # Update password hash
    user.password_hash = hash_password(new_password)
    user.updated_at = now
    prt.used_at = now

    # Invalidate all existing sessions for this user
    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()

    record_audit_action(
        db=db,
        action="PASSWORD_RESET_SUCCESS",
        target_resource="Password Recovery",
        details=f"Password reset completed successfully. Existing sessions revoked for {user.email}.",
        user_email=user.email,
        result="success",
        client_ip=client_ip,
    )
    return user


# =========================================================================
# POINT 3 EXTENSION: ADMIN REQUEST & SUPER ADMIN LIFECYCLE MANAGEMENT
# =========================================================================

def create_admin_registration_request(
    db: Session,
    req_in: AdminRegistrationRequestCreate,
    client_ip: Optional[str] = None,
) -> AdminRegistrationRequest:
    """
    Step 1: Public submission of an administrator access request.
    Creates an AdminRegistrationRequest in EMAIL_UNVERIFIED state and dispatches verification link.
    Does NOT create a User account.
    """
    norm_email = req_in.email.strip().lower()

    # Check if an active user already exists with this email
    existing_user = get_user_by_email(db, norm_email)
    if existing_user and existing_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active account with this email address already exists.",
        )

    # Check existing registration requests
    existing_req = db.scalar(
        select(AdminRegistrationRequest).where(
            AdminRegistrationRequest.email == norm_email
        )
    )

    if existing_req:
        if existing_req.status == AdminRequestStatus.PENDING_SUPER_ADMIN_APPROVAL:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An access request for this email is already awaiting Super Admin review.",
            )
        if existing_req.status in (AdminRequestStatus.APPROVED, AdminRequestStatus.ACTIVATION_PENDING):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An access request for this email has already been approved and is awaiting activation.",
            )
        if existing_req.status == AdminRequestStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active administrator account already exists for this email.",
            )

    now = datetime.now(timezone.utc)
    raw_token = generate_secure_token(32)
    token_hash = hash_token(raw_token)
    expires_at = now + timedelta(hours=settings.verification_token_expire_hours)

    if existing_req:
        # Re-use existing request row to prevent duplicates
        existing_req.full_name = req_in.full_name.strip()
        existing_req.organization = req_in.organization.strip() if req_in.organization else None
        existing_req.reason = req_in.reason.strip() if req_in.reason else None
        existing_req.status = AdminRequestStatus.EMAIL_UNVERIFIED
        existing_req.email_verified = False
        existing_req.verification_token_hash = token_hash
        existing_req.verification_expires_at = expires_at
        existing_req.requested_at = now
        existing_req.rejection_reason = None
        req = existing_req
    else:
        req = AdminRegistrationRequest(
            full_name=req_in.full_name.strip(),
            email=norm_email,
            organization=req_in.organization.strip() if req_in.organization else None,
            reason=req_in.reason.strip() if req_in.reason else None,
            status=AdminRequestStatus.EMAIL_UNVERIFIED,
            email_verified=False,
            verification_token_hash=token_hash,
            verification_expires_at=expires_at,
            requested_at=now,
        )
        db.add(req)

    db.commit()
    db.refresh(req)

    EmailService.send_admin_request_verification_email(
        email=req.email,
        full_name=req.full_name,
        raw_token=raw_token,
    )

    record_audit_action(
        db=db,
        action="ADMIN_REQUEST_CREATED",
        target_resource="Admin Access Request",
        details=f"Admin registration request submitted by {req.full_name} ({req.email})",
        user_email=req.email,
        result="success",
        client_ip=client_ip,
    )
    return req


def verify_admin_request_email(
    db: Session,
    raw_token: str,
    client_ip: Optional[str] = None,
) -> AdminRegistrationRequest:
    """
    Step 2: Requester validates their email address.
    Transitions request from EMAIL_UNVERIFIED -> PENDING_SUPER_ADMIN_APPROVAL.
    """
    token_hash = hash_token(raw_token.strip())
    req = db.scalar(
        select(AdminRegistrationRequest).where(
            AdminRegistrationRequest.verification_token_hash == token_hash
        )
    )

    now = datetime.now(timezone.utc)
    if not req or not req.verification_expires_at or _ensure_utc(req.verification_expires_at) <= now:
        record_audit_action(
            db=db,
            action="ADMIN_EMAIL_VERIFY_FAILURE",
            target_resource="Admin Access Request",
            details="Invalid or expired admin request verification token submitted.",
            user_email="anonymous",
            result="failure",
            client_ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is invalid or has expired.",
        )

    if req.status != AdminRequestStatus.EMAIL_UNVERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This request has already completed email verification.",
        )

    req.email_verified = True
    req.verified_at = now
    req.status = AdminRequestStatus.PENDING_SUPER_ADMIN_APPROVAL
    # Invalidate token
    req.verification_token_hash = None
    db.commit()
    db.refresh(req)

    # Notify active Super Administrators of pending request if enabled
    if settings.notify_super_admins_on_new_request:
        active_supers = db.scalars(
            select(User).where(
                User.role == UserRole.SUPER_ADMIN,
                User.is_active == True,
            )
        ).all()
        for sa in active_supers:
            EmailService.send_super_admin_new_request_notification(
                super_admin_email=sa.email,
                applicant_email=req.email,
                applicant_name=req.full_name,
                organization=req.organization,
                reason=req.reason,
            )

    record_audit_action(
        db=db,
        action="ADMIN_EMAIL_VERIFIED",
        target_resource="Admin Access Request",
        details=f"Email verified for admin request: {req.email}. Now pending Super Admin approval.",
        user_email=req.email,
        result="success",
        client_ip=client_ip,
    )
    return req


def approve_admin_request(
    db: Session,
    request_id: int,
    current_super_admin: User,
    client_ip: Optional[str] = None,
) -> Tuple[AdminRegistrationRequest, User, str]:
    """
    Step 3: Super Admin approves the request.
    Creates inactive Admin User account and issues single-use activation token.
    Transitions request -> ACTIVATION_PENDING.
    """
    req = db.get(AdminRegistrationRequest, request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin request #{request_id} not found.",
        )

    if not req.email_verified or req.status != AdminRequestStatus.PENDING_SUPER_ADMIN_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve request in status '{req.status}'. Email must be verified and pending approval.",
        )

    now = datetime.now(timezone.utc)

    # Check if a user already exists with this email
    user = get_user_by_email(db, req.email)
    if user and user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active user account for '{req.email}' already exists.",
        )

    if not user:
        # Create unactivated ADMIN user with temporary secure hash
        temp_pwd = generate_secure_token(32)
        user = User(
            email=req.email,
            password_hash=hash_password(temp_pwd),
            role=UserRole.ADMIN,
            is_active=False,      # Must set password via activation
            is_verified=True,     # Email already verified
            created_at=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.role = UserRole.ADMIN
        user.is_active = False
        user.is_verified = True
        db.commit()

    # Generate single-use activation token (24h expiration)
    raw_activation_token = generate_secure_token(32)
    activation_hash = hash_token(raw_activation_token)
    expires_at = now + timedelta(hours=24)

    act_token = AdminActivationToken(
        request_id=req.id,
        user_id=user.id,
        token_hash=activation_hash,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(act_token)

    req.status = AdminRequestStatus.ACTIVATION_PENDING
    req.reviewed_at = now
    req.reviewed_by_id = current_super_admin.id
    req.created_user_id = user.id
    req.rejection_reason = None
    db.commit()
    db.refresh(req)

    EmailService.send_admin_approval_activation_email(
        email=req.email,
        full_name=req.full_name,
        raw_token=raw_activation_token,
    )

    record_audit_action(
        db=db,
        action="ADMIN_REQUEST_APPROVED",
        target_resource="Admin Access Request",
        details=f"Admin request #{req.id} for '{req.email}' approved by Super Admin '{current_super_admin.email}'.",
        user_email=current_super_admin.email,
        result="success",
        client_ip=client_ip,
    )
    return req, user, raw_activation_token


def reject_admin_request(
    db: Session,
    request_id: int,
    current_super_admin: User,
    reason: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> AdminRegistrationRequest:
    """
    Step 4: Super Admin rejects the request.
    Transitions request -> REJECTED.
    """
    req = db.get(AdminRegistrationRequest, request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin request #{request_id} not found.",
        )

    if req.status != AdminRequestStatus.PENDING_SUPER_ADMIN_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject request in status '{req.status}'.",
        )

    now = datetime.now(timezone.utc)
    req.status = AdminRequestStatus.REJECTED
    req.rejection_reason = reason.strip() if reason else None
    req.reviewed_at = now
    req.reviewed_by_id = current_super_admin.id
    db.commit()
    db.refresh(req)

    EmailService.send_admin_rejection_email(
        email=req.email,
        full_name=req.full_name,
        reason=req.rejection_reason,
    )

    record_audit_action(
        db=db,
        action="ADMIN_REQUEST_REJECTED",
        target_resource="Admin Access Request",
        details=f"Admin request #{req.id} for '{req.email}' rejected by Super Admin '{current_super_admin.email}'. Reason: {req.rejection_reason or 'None provided'}",
        user_email=current_super_admin.email,
        result="success",
        client_ip=client_ip,
    )
    return req


def activate_admin_account(
    db: Session,
    raw_token: str,
    new_password: str,
    client_ip: Optional[str] = None,
) -> User:
    """
    Step 5: Approved prospective admin sets initial password using activation token.
    Transitions account -> ACTIVE.
    """
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters long.",
        )

    token_hash = hash_token(raw_token.strip())
    act_token = db.scalar(
        select(AdminActivationToken).where(
            AdminActivationToken.token_hash == token_hash
        )
    )

    now = datetime.now(timezone.utc)
    if not act_token or act_token.used_at is not None or _ensure_utc(act_token.expires_at) <= now:
        record_audit_action(
            db=db,
            action="ADMIN_ACTIVATION_FAILURE",
            target_resource="Account Activation",
            details="Invalid, expired, or already-used activation token provided.",
            user_email="anonymous",
            result="failure",
            client_ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activation link is invalid, already used, or has expired.",
        )

    req = db.get(AdminRegistrationRequest, act_token.request_id)
    user = db.get(User, act_token.user_id)

    if not req or not user or req.status != AdminRequestStatus.ACTIVATION_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Associated admin request or user record is not eligible for activation.",
        )

    # Set new password, activate account, mark token used
    user.password_hash = hash_password(new_password)
    user.is_active = True
    user.is_verified = True
    user.updated_at = now

    act_token.used_at = now
    req.status = AdminRequestStatus.ACTIVE

    db.commit()
    db.refresh(user)

    record_audit_action(
        db=db,
        action="ADMIN_ACCOUNT_ACTIVATED",
        target_resource="Account Activation",
        details=f"Admin account activated and password set for '{user.email}'.",
        user_email=user.email,
        result="success",
        client_ip=client_ip,
    )
    return user


# =========================================================================
# SUPER ADMIN DASHBOARD & DIRECTORY MANAGEMENT
# =========================================================================

def get_admin_summary_stats(db: Session) -> AdminSummaryStats:
    """Computes summary counts for the Super Admin Management Dashboard."""
    total_admins = db.scalar(
        select(func.count(User.id)).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
    ) or 0

    active_admins = db.scalar(
        select(func.count(User.id)).where(
            User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]),
            User.is_active.is_(True),
        )
    ) or 0

    disabled_admins = db.scalar(
        select(func.count(User.id)).where(
            User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]),
            User.is_active.is_(False),
        )
    ) or 0

    pending_requests = db.scalar(
        select(func.count(AdminRegistrationRequest.id)).where(
            AdminRegistrationRequest.status == AdminRequestStatus.PENDING_SUPER_ADMIN_APPROVAL
        )
    ) or 0

    return AdminSummaryStats(
        total_admins=total_admins,
        active_admins=active_admins,
        disabled_admins=disabled_admins,
        pending_requests=pending_requests,
    )


def get_admin_requests(
    db: Session,
    status_filter: Optional[str] = None,
) -> List[AdminRegistrationRequest]:
    """Retrieves all or filtered admin registration requests."""
    stmt = select(AdminRegistrationRequest).order_by(AdminRegistrationRequest.requested_at.desc())
    if status_filter and status_filter in AdminRequestStatus.ALL_STATUSES:
        stmt = stmt.where(AdminRegistrationRequest.status == status_filter)
    return list(db.scalars(stmt).all())


def get_admin_request_by_id(db: Session, request_id: int) -> Optional[AdminRegistrationRequest]:
    """Retrieves a single admin registration request by ID."""
    return db.get(AdminRegistrationRequest, request_id)


def get_all_admin_users(db: Session) -> List[Dict[str, Any]]:
    """Retrieves all administrator accounts with active session counts."""
    users = list(
        db.scalars(
            select(User)
            .where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
            .order_by(User.id.asc())
        ).all()
    )

    now = datetime.now(timezone.utc)
    res = []
    for u in users:
        active_sessions = db.scalar(
            select(func.count(UserSession.id)).where(
                UserSession.user_id == u.id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
        ) or 0

        res.append({
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at,
            "updated_at": u.updated_at,
            "active_sessions_count": active_sessions,
        })
    return res


def get_admin_user_details(db: Session, user_id: int) -> Dict[str, Any]:
    """Retrieves detailed profile for an administrator including active session count."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Administrator #{user_id} not found.",
        )

    now = datetime.now(timezone.utc)
    active_sessions = db.scalar(
        select(func.count(UserSession.id)).where(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    ) or 0

    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "active_sessions_count": active_sessions,
    }


def _verify_not_last_super_admin(db: Session, target_user: User):
    """Enforces the invariant: at least 1 active SUPER_ADMIN must remain."""
    if target_user.role == UserRole.SUPER_ADMIN:
        active_super_count = db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.SUPER_ADMIN,
                User.is_active.is_(True),
            )
        ) or 0
        if active_super_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Operation rejected: At least one active Super Administrator must remain.",
            )


def disable_admin_user(
    db: Session,
    target_user_id: int,
    current_super_admin: User,
    client_ip: Optional[str] = None,
) -> User:
    """Disables an administrator account and revokes all active sessions."""
    target = get_user_by_id(db, target_user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Administrator #{target_user_id} not found.",
        )

    _verify_not_last_super_admin(db, target)

    now = datetime.now(timezone.utc)
    target.is_active = False
    target.updated_at = now

    # Revoke all active sessions
    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == target.id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()
    db.refresh(target)

    record_audit_action(
        db=db,
        action="ADMIN_ACCOUNT_DISABLED",
        target_resource="Administrator Directory",
        details=f"Administrator '{target.email}' disabled by Super Admin '{current_super_admin.email}'. Active sessions revoked.",
        user_email=current_super_admin.email,
        result="success",
        client_ip=client_ip,
    )
    return target


def enable_admin_user(
    db: Session,
    target_user_id: int,
    current_super_admin: User,
    client_ip: Optional[str] = None,
) -> User:
    """Reactivates an eligible disabled administrator account."""
    target = get_user_by_id(db, target_user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Administrator #{target_user_id} not found.",
        )

    now = datetime.now(timezone.utc)
    target.is_active = True
    target.updated_at = now
    db.commit()
    db.refresh(target)

    record_audit_action(
        db=db,
        action="ADMIN_ACCOUNT_ENABLED",
        target_resource="Administrator Directory",
        details=f"Administrator '{target.email}' enabled by Super Admin '{current_super_admin.email}'.",
        user_email=current_super_admin.email,
        result="success",
        client_ip=client_ip,
    )
    return target


def revoke_admin_user_sessions(
    db: Session,
    target_user_id: int,
    current_super_admin: User,
    client_ip: Optional[str] = None,
) -> int:
    """Revokes all active refresh sessions for an administrator."""
    target = get_user_by_id(db, target_user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Administrator #{target_user_id} not found.",
        )

    now = datetime.now(timezone.utc)
    result = db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == target.id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()

    record_audit_action(
        db=db,
        action="ADMIN_SESSION_REVOKED",
        target_resource="Administrator Sessions",
        details=f"All active refresh sessions revoked for '{target.email}' by Super Admin '{current_super_admin.email}'.",
        user_email=current_super_admin.email,
        result="success",
        client_ip=client_ip,
    )
    return result.rowcount


def force_admin_password_reset(
    db: Session,
    target_user_id: int,
    current_super_admin: User,
    client_ip: Optional[str] = None,
) -> str:
    """Triggers a secure password reset flow for an administrator."""
    target = get_user_by_id(db, target_user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Administrator #{target_user_id} not found.",
        )

    # Trigger reset flow
    msg = request_password_reset(db=db, email=target.email, client_ip=client_ip)

    record_audit_action(
        db=db,
        action="ADMIN_PASSWORD_RESET_FORCED",
        target_resource="Administrator Directory",
        details=f"Password reset forced for '{target.email}' by Super Admin '{current_super_admin.email}'.",
        user_email=current_super_admin.email,
        result="success",
        client_ip=client_ip,
    )
    return msg


def soft_delete_admin_user(
    db: Session,
    target_user_id: int,
    current_super_admin: User,
    client_ip: Optional[str] = None,
) -> User:
    """
    Performs safe soft-delete / deactivation of an administrator account.
    Preserves audit trail history while instantly cutting off system access.
    """
    target = get_user_by_id(db, target_user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Administrator #{target_user_id} not found.",
        )

    _verify_not_last_super_admin(db, target)

    now = datetime.now(timezone.utc)
    target.is_active = False
    target.updated_at = now

    # Revoke all sessions
    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == target.id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()
    db.refresh(target)

    record_audit_action(
        db=db,
        action="ADMIN_ACCOUNT_SOFT_DELETED",
        target_resource="Administrator Directory",
        details=f"Administrator '{target.email}' deactivated/soft-deleted by Super Admin '{current_super_admin.email}'. Audit history preserved.",
        user_email=current_super_admin.email,
        result="success",
        client_ip=client_ip,
    )
    return target

