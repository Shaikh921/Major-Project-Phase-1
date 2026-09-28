"""
Authentication & Identity API Router.

Endpoints for:
- Secure Administrator/User Login with in-memory access token & HttpOnly refresh cookie.
- Silent session refresh.
- Server-side session revocation & logout.
- Current user profile identity.
- Email verification validation.
- Anti-enumeration forgot-password request.
- Password reset token verification & Argon2id hash update.
- Admin-controlled internal user provisioning.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user, get_current_admin
from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limit_ip
from backend.app.models.user import User
from backend.app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserRead,
    UserCreateInternal,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    MessageResponse,
    AdminRegistrationRequestCreate,
    AdminRegistrationRequestRead,
    AdminActivateAccountRequest,
)
from backend.app.services.auth_service import (
    authenticate_user,
    create_user_session,
    refresh_user_session,
    revoke_user_session,
    create_internal_user,
    verify_email_token,
    request_password_reset,
    reset_password_with_token,
    create_admin_registration_request,
    verify_admin_request_email,
    activate_admin_account,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticates credentials, issues a short-lived access token,
    and sets a secure HttpOnly refresh cookie for session tracking.
    """
    rate_limit_ip(request, "login", max_requests=5, window_seconds=60)

    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "")

    user = authenticate_user(
        db=db,
        email=req.email,
        password=req.password,
        client_ip=client_ip,
    )

    access_token, raw_refresh_token, expires_in = create_user_session(
        db=db,
        user=user,
        client_ip=client_ip,
        user_agent=user_agent,
    )

    # Set secure HttpOnly refresh cookie
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_refresh_token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=expires_in,
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Exchanges a valid HttpOnly refresh cookie for a fresh access token.
    """
    raw_refresh_token = request.cookies.get(settings.session_cookie_name)
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh session active.",
        )

    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "")

    access_token, new_refresh_token, expires_in, user = refresh_user_session(
        db=db,
        raw_refresh_token=raw_refresh_token,
        client_ip=client_ip,
        user_agent=user_agent,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=expires_in,
        user=UserRead.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Revokes the active refresh token session in the database and clears the session cookie.
    """
    raw_refresh_token = request.cookies.get(settings.session_cookie_name)
    client_ip = request.client.host if request.client else "127.0.0.1"

    revoke_user_session(
        db=db,
        raw_refresh_token=raw_refresh_token,
        client_ip=client_ip,
    )

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/api/v1/auth",
    )

    return MessageResponse(message="Session successfully terminated and revoked.")


@router.get("/me", response_model=UserRead)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves the identity profile and role claims of the currently authenticated user.
    """
    return UserRead.model_validate(current_user)


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(
    req: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Validates single-use email verification token and activates the user account.
    """
    rate_limit_ip(request, "verify_email", max_requests=10, window_seconds=60)
    client_ip = request.client.host if request.client else "127.0.0.1"

    verify_email_token(db=db, raw_token=req.token, client_ip=client_ip)
    return MessageResponse(message="Email address successfully verified. You may now sign in.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Initiates password reset workflow.
    Always returns generic confirmation to prevent account enumeration.
    """
    rate_limit_ip(request, "forgot_password", max_requests=3, window_seconds=300)
    client_ip = request.client.host if request.client else "127.0.0.1"

    msg = request_password_reset(db=db, email=req.email, client_ip=client_ip)
    return MessageResponse(message=msg)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    req: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Validates single-use reset token, updates password to new Argon2id hash,
    and invalidates all previous sessions.
    """
    rate_limit_ip(request, "reset_password", max_requests=5, window_seconds=300)
    client_ip = request.client.host if request.client else "127.0.0.1"

    reset_password_with_token(
        db=db,
        raw_token=req.token,
        new_password=req.new_password,
        client_ip=client_ip,
    )
    return MessageResponse(message="Password reset successfully. Please sign in with your new password.")


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    user_in: UserCreateInternal,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Administrative endpoint for provisioning operational/viewer users.
    Only accessible by authenticated ADMIN.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    user, _ = create_internal_user(
        db=db,
        user_in=user_in,
        creator_email=current_admin.email,
        client_ip=client_ip,
    )
    return UserRead.model_validate(user)


@router.post("/admin-request", response_model=AdminRegistrationRequestRead, status_code=status.HTTP_201_CREATED)
def request_admin_access(
    req: AdminRegistrationRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Public endpoint for prospective administrators to submit an access request.
    Does NOT create a user account. Dispatches email verification link.
    """
    rate_limit_ip(request, "admin_request", max_requests=3, window_seconds=300)
    client_ip = request.client.host if request.client else "127.0.0.1"

    registration_req = create_admin_registration_request(
        db=db,
        req_in=req,
        client_ip=client_ip,
    )
    return AdminRegistrationRequestRead.model_validate(registration_req)


@router.post("/admin-request/verify", response_model=MessageResponse)
def verify_admin_request(
    req: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Validates single-use email verification token for an admin access request.
    Moves request into PENDING_SUPER_ADMIN_APPROVAL state.
    """
    rate_limit_ip(request, "admin_request_verify", max_requests=5, window_seconds=300)
    client_ip = request.client.host if request.client else "127.0.0.1"

    verify_admin_request_email(db=db, raw_token=req.token, client_ip=client_ip)
    return MessageResponse(
        message="Email address verified successfully. Your request has been queued for Super Administrator approval."
    )


@router.post("/admin-request/activate", response_model=MessageResponse)
def activate_admin_account_endpoint(
    req: AdminActivateAccountRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Validates single-use activation token for an approved administrator request,
    sets initial Argon2id password, and activates the account.
    """
    rate_limit_ip(request, "admin_request_activate", max_requests=5, window_seconds=300)
    client_ip = request.client.host if request.client else "127.0.0.1"

    activate_admin_account(
        db=db,
        raw_token=req.token,
        new_password=req.new_password,
        client_ip=client_ip,
    )
    return MessageResponse(
        message="Administrator account activated successfully. You may now sign in to the Command Center."
    )

