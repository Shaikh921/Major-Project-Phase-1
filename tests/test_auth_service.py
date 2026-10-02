"""
Comprehensive Automated Tests for Authentication, RBAC, Password Reset, and Verification.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.init_db import seed_default_rules
from backend.app.api.deps import get_db
from backend.app.main import app
from backend.app.models.user import User, UserRole, UserSession, EmailVerificationToken, PasswordResetToken
from backend.app.models.security import AuditLog
from backend.app.core.config import settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    hash_token,
)
from backend.app.services.auth_service import (
    authenticate_user,
    create_user_session,
    refresh_user_session,
    revoke_user_session,
    create_bootstrap_admin,
    create_internal_user,
    create_email_verification,
    verify_email_token,
    request_password_reset,
    reset_password_with_token,
)
from backend.app.services.email_service import EmailService
from backend.app.schemas.auth import UserCreateInternal
from backend.app.core.rate_limit import auth_rate_limiter


@pytest.fixture(scope="module")
def db_engine():
    orig_smtp = settings.smtp_enabled
    settings.smtp_enabled = False
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestingSessionLocal() as db:
        seed_default_rules(db)
    yield engine
    Base.metadata.drop_all(bind=engine)
    settings.smtp_enabled = orig_smtp


@pytest.fixture
def db(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    with TestingSessionLocal() as session:
        yield session


@pytest.fixture
def client(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.pop(get_db, None)


# --- 1. Password Hashing Security Tests ---

def test_argon2id_hashing_and_verification():
    raw_pwd = "SuperSecretPassword123!"
    hashed = hash_password(raw_pwd)

    assert hashed.startswith("$argon2id$")
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


# --- 2. Admin Bootstrap Tests ---

def test_admin_bootstrap_lifecycle(db):
    admin = create_bootstrap_admin(db, email="root-admin@ops.local", password="RootPassword2026!")
    assert admin.id is not None
    assert admin.role == UserRole.SUPER_ADMIN
    assert admin.is_active is True
    assert admin.is_verified is True

    # Second bootstrap attempt must be rejected
    with pytest.raises(HTTPException) as exc:
        create_bootstrap_admin(db, email="second-admin@ops.local", password="AnotherPassword!")
    assert exc.value.status_code == 409


# --- 3. Authentication & Login Tests ---

def test_authenticate_user_success_and_failures(db):
    # Success
    user = authenticate_user(db, email="root-admin@ops.local", password="RootPassword2026!")
    assert user.email == "root-admin@ops.local"

    # Wrong password
    with pytest.raises(HTTPException) as exc:
        authenticate_user(db, email="root-admin@ops.local", password="BadPassword")
    assert exc.value.status_code == 401
    assert "Invalid email or password" in exc.value.detail

    # Unknown email (identical safe response)
    with pytest.raises(HTTPException) as exc:
        authenticate_user(db, email="unknown@ops.local", password="AnyPassword")
    assert exc.value.status_code == 401
    assert "Invalid email or password" in exc.value.detail


def test_inactive_and_unverified_login_denial(db):
    # Create unverified user
    unverified_user, _ = create_internal_user(
        db,
        UserCreateInternal(
            email="unverified@ops.local",
            password="UserPassword123!",
            role=UserRole.VIEWER,
            is_active=True,
            is_verified=False,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        authenticate_user(db, email="unverified@ops.local", password="UserPassword123!")
    assert exc.value.status_code == 403
    assert "not verified" in exc.value.detail

    # Create deactivated user
    deactivated_user, _ = create_internal_user(
        db,
        UserCreateInternal(
            email="locked@ops.local",
            password="UserPassword123!",
            role=UserRole.VIEWER,
            is_active=False,
            is_verified=True,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        authenticate_user(db, email="locked@ops.local", password="UserPassword123!")
    assert exc.value.status_code == 403
    assert "deactivated" in exc.value.detail


# --- 4. Session & Refresh Token Lifecycle Tests ---

def test_session_creation_refresh_and_logout(db):
    admin = db.scalar(select(User).where(User.email == "root-admin@ops.local"))
    access_token, refresh_token, expires_in = create_user_session(db, admin)

    assert access_token is not None
    assert refresh_token is not None
    assert expires_in == 900  # 15 minutes

    # Refresh session
    new_access, new_refresh, _, user = refresh_user_session(db, refresh_token)
    assert user.id == admin.id
    assert new_access is not None

    # Revoke session on logout
    revoke_user_session(db, refresh_token, user)

    # Subsequent refresh attempt must fail
    with pytest.raises(HTTPException) as exc:
        refresh_user_session(db, refresh_token)
    assert exc.value.status_code == 401


# --- 5. Email Verification Workflow Tests ---

def test_email_verification_flow(db):
    EmailService.clear_outbox()
    user, raw_token = create_internal_user(
        db,
        UserCreateInternal(
            email="developer@ops.local",
            password="DevPassword123!",
            role=UserRole.VIEWER,
            is_active=True,
            is_verified=False,
        ),
    )
    assert raw_token != ""
    assert user.is_verified is False

    # Valid token verification
    verified_user = verify_email_token(db, raw_token)
    assert verified_user.is_verified is True

    # Replay attack / reuse of token must fail
    with pytest.raises(HTTPException) as exc:
        verify_email_token(db, raw_token)
    assert exc.value.status_code == 400


# --- 6. Forgot & Reset Password Workflow Tests ---

def test_password_reset_workflow(db):
    EmailService.clear_outbox()
    user, _ = create_internal_user(
        db,
        UserCreateInternal(
            email="reset-test@ops.local",
            password="OldPassword123!",
            role=UserRole.OPERATOR,
            is_active=True,
            is_verified=True,
        ),
    )

    # 1. Forgot password request (generic message)
    msg = request_password_reset(db, "reset-test@ops.local")
    assert "instructions have been sent" in msg

    # Retrieve dispatched token from EmailService
    latest_email = EmailService.get_latest_email_for("reset-test@ops.local")
    assert latest_email is not None
    reset_token = latest_email["raw_token"]

    # 2. Reset password
    updated_user = reset_password_with_token(db, reset_token, "BrandNewPassword2026!")
    assert updated_user.email == "reset-test@ops.local"

    # 3. Old password must fail
    with pytest.raises(HTTPException) as exc:
        authenticate_user(db, email="reset-test@ops.local", password="OldPassword123!")
    assert exc.value.status_code == 401

    # 4. New password must succeed
    auth_user = authenticate_user(db, email="reset-test@ops.local", password="BrandNewPassword2026!")
    assert auth_user.id == user.id

    # 5. Reset token reuse must be rejected
    with pytest.raises(HTTPException) as exc:
        reset_password_with_token(db, reset_token, "AnotherPassword!")
    assert exc.value.status_code == 400


# --- 7. RBAC & Protected API Endpoints Integration Tests ---

def test_api_endpoint_rbac_enforcement(client, db):
    # Reset rate limiter
    auth_rate_limiter.reset_for_key("login:testclient")

    # 1. Unauthenticated request to protected endpoint -> 401
    res = client.get("/api/v1/summary")
    assert res.status_code == 401

    # 2. Login as Admin
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "root-admin@ops.local", "password": "RootPassword2026!"},
    )
    assert res.status_code == 200
    admin_token = res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Admin accesses Admin endpoint (Rules CRUD) -> Success
    res = client.get("/api/v1/alerts/rules", headers=admin_headers)
    assert res.status_code == 200

    # 4. Create an OPERATOR user and login
    op_user, _ = create_internal_user(
        db,
        UserCreateInternal(
            email="operator@ops.local",
            password="OperatorPassword123!",
            role=UserRole.OPERATOR,
            is_active=True,
            is_verified=True,
        ),
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "operator@ops.local", "password": "OperatorPassword123!"},
    )
    op_token = res.json()["access_token"]
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # 5. Operator accesses Viewer endpoint -> Success
    res = client.get("/api/v1/summary", headers=op_headers)
    assert res.status_code == 200

    # 6. Operator accesses Admin endpoint -> 403 Forbidden
    res = client.get("/api/v1/alerts/rules", headers=op_headers)
    assert res.status_code == 403
    assert "requires one of" in res.json()["detail"]


# --- 8. Audit Trail Verification ---

def test_audit_trail_records_auth_events(db):
    logs = list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(20)).all())
    actions = [l.action for l in logs]

    assert "ADMIN_BOOTSTRAP" in actions or "LOGIN_SUCCESS" in actions
    # Confirm no passwords or secrets are in details
    for l in logs:
        assert "password=" not in l.details.lower()
        assert "secret" not in l.details.lower()
