"""
Comprehensive Automated Tests for Point 3 Extension:
Super Admin + Admin Management Panel + Admin Registration Workflow.
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
from backend.app.models.user import (
    User,
    UserRole,
    AdminRegistrationRequest,
    AdminRequestStatus,
    AdminActivationToken,
)
from backend.app.models.security import AuditLog
from backend.app.core.config import settings
from backend.app.core.rate_limit import auth_rate_limiter
from backend.app.services.auth_service import (
    authenticate_user,
    create_bootstrap_admin,
    create_admin_registration_request,
    verify_admin_request_email,
    approve_admin_request,
    reject_admin_request,
    activate_admin_account,
    disable_admin_user,
    enable_admin_user,
    revoke_admin_user_sessions,
    force_admin_password_reset,
    soft_delete_admin_user,
)
from backend.app.services.email_service import EmailService
from backend.app.schemas.auth import (
    AdminRegistrationRequestCreate,
    AdminActivateAccountRequest,
)


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


# --- 1. Super Admin Bootstrap & Role Tests ---

def test_super_admin_bootstrap(db):
    EmailService.clear_outbox()
    super_admin = create_bootstrap_admin(
        db,
        email="superadmin@ops.local",
        password="SuperAdminSecret2026!"
    )
    assert super_admin.id is not None
    assert super_admin.role == UserRole.SUPER_ADMIN
    assert super_admin.is_active is True
    assert super_admin.is_verified is True


# --- 2. Public Admin Registration Request & Email Verification ---

def test_admin_registration_request_lifecycle(db):
    EmailService.clear_outbox()
    auth_rate_limiter.reset_for_key("admin_request:127.0.0.1")

    # 1. Submit Request
    req_data = AdminRegistrationRequestCreate(
        full_name="Jane Doe",
        email="jane.doe@enterprise.com",
        organization="Enterprise SRE Team",
        reason="Need access to triage infrastructure anomalies.",
    )
    req = create_admin_registration_request(db, req_data, client_ip="127.0.0.1")

    assert req.id is not None
    assert req.status == AdminRequestStatus.EMAIL_UNVERIFIED
    assert req.email_verified is False

    # Check outbox email
    outbox = EmailService.get_outbox()
    assert len(outbox) == 1
    assert "Verify" in outbox[0]["subject"]
    raw_token = outbox[0]["raw_token"]
    assert raw_token is not None

    # Verify no User account was created yet
    user = db.scalar(select(User).where(User.email == "jane.doe@enterprise.com"))
    assert user is None

    # 2. Verify Email with Token
    verified_req = verify_admin_request_email(db, raw_token, client_ip="127.0.0.1")
    assert verified_req.email_verified is True
    assert verified_req.status == AdminRequestStatus.PENDING_SUPER_ADMIN_APPROVAL
    assert verified_req.verified_at is not None

    # 3. Token Reuse Attempt must fail
    with pytest.raises(HTTPException) as exc:
        verify_admin_request_email(db, raw_token, client_ip="127.0.0.1")
    assert exc.value.status_code == 400


# --- 3. Super Admin Approval, Activation & Login ---

def test_super_admin_approval_and_activation_flow(db):
    EmailService.clear_outbox()
    super_admin = db.scalar(select(User).where(User.role == UserRole.SUPER_ADMIN))
    assert super_admin is not None

    req = db.scalar(select(AdminRegistrationRequest).where(AdminRegistrationRequest.email == "jane.doe@enterprise.com"))
    assert req.status == AdminRequestStatus.PENDING_SUPER_ADMIN_APPROVAL

    # 1. Super Admin approves request
    approved_req, user, raw_activation_token = approve_admin_request(db, req.id, super_admin, client_ip="127.0.0.1")
    assert user is not None
    assert user.role == UserRole.ADMIN
    assert user.is_active is False  # Inactive until activation
    assert user.is_verified is True
    assert raw_activation_token is not None

    # Verify activation email in outbox
    outbox = EmailService.get_outbox()
    assert any("Activation" in m["subject"] or "Approved" in m["subject"] for m in outbox)

    # Inactive/unactivated admin cannot login yet
    with pytest.raises(HTTPException) as exc:
        authenticate_user(db, email="jane.doe@enterprise.com", password="AnyPassword123!")
    assert exc.value.status_code in (401, 403)

    # 2. Admin Activates Account & Sets Password
    activated_user = activate_admin_account(
        db,
        raw_token=raw_activation_token,
        new_password="JaneSecureAdmin2026!",
        client_ip="127.0.0.1",
    )
    assert activated_user.id == user.id
    assert activated_user.is_active is True

    # 3. Activation token reuse must be rejected
    with pytest.raises(HTTPException) as exc:
        activate_admin_account(
            db,
            raw_token=raw_activation_token,
            new_password="AnotherPassword123!",
            client_ip="127.0.0.1",
        )
    assert exc.value.status_code == 400

    # 4. Activated Admin can now log in
    auth_user = authenticate_user(db, email="jane.doe@enterprise.com", password="JaneSecureAdmin2026!")
    assert auth_user.id == activated_user.id
    assert auth_user.role == UserRole.ADMIN


# --- 4. Admin Request Rejection Flow ---

def test_admin_request_rejection_flow(db):
    EmailService.clear_outbox()
    auth_rate_limiter.reset_for_key("admin_request:127.0.0.1")
    super_admin = db.scalar(select(User).where(User.role == UserRole.SUPER_ADMIN))

    req_data = AdminRegistrationRequestCreate(
        full_name="Bob Reject",
        email="bob.reject@fakecorp.com",
        organization="Fake Corp",
        reason="Testing rejection workflow.",
    )
    req = create_admin_registration_request(db, req_data, client_ip="127.0.0.1")
    outbox = EmailService.get_outbox()
    raw_token = outbox[-1]["raw_token"]
    verify_admin_request_email(db, raw_token, client_ip="127.0.0.1")

    # Reject
    rejected_req = reject_admin_request(
        db,
        req.id,
        current_super_admin=super_admin,
        reason="Invalid organizational credentials.",
        client_ip="127.0.0.1"
    )
    assert rejected_req.status == AdminRequestStatus.REJECTED
    assert rejected_req.rejection_reason == "Invalid organizational credentials."

    # Cannot approve a rejected request
    with pytest.raises(HTTPException) as exc:
        approve_admin_request(db, req.id, super_admin, client_ip="127.0.0.1")
    assert exc.value.status_code == 400


# --- 5. Administrator Directory & Administrative Lifecycle Actions ---

def test_admin_directory_and_account_actions(db):
    super_admin = db.scalar(select(User).where(User.role == UserRole.SUPER_ADMIN))
    admin_user = db.scalar(select(User).where(User.email == "jane.doe@enterprise.com"))
    assert admin_user is not None

    # 1. Disable Admin
    disabled_user = disable_admin_user(db, admin_user.id, super_admin, client_ip="127.0.0.1")
    assert disabled_user.is_active is False

    # Disabled Admin cannot login
    with pytest.raises(HTTPException) as exc:
        authenticate_user(db, email="jane.doe@enterprise.com", password="JaneSecureAdmin2026!")
    assert exc.value.status_code == 403

    # 2. Enable Admin
    enabled_user = enable_admin_user(db, admin_user.id, super_admin, client_ip="127.0.0.1")
    assert enabled_user.is_active is True

    # 3. Revoke Sessions
    revoked_count = revoke_admin_user_sessions(db, admin_user.id, super_admin, client_ip="127.0.0.1")
    assert isinstance(revoked_count, int)

    # 4. Force Password Reset
    EmailService.clear_outbox()
    force_admin_password_reset(db, admin_user.id, super_admin, client_ip="127.0.0.1")
    outbox = EmailService.get_outbox()
    assert any("Password Reset" in m["subject"] for m in outbox)

    # 5. Soft Delete / Deactivate
    soft_deleted = soft_delete_admin_user(db, admin_user.id, super_admin, client_ip="127.0.0.1")
    assert soft_deleted.is_active is False

    # Check database row is still physically present
    persisted = db.scalar(select(User).where(User.id == admin_user.id))
    assert persisted is not None
    assert persisted.is_active is False


# --- 6. Last Super Admin Protection Rule ---

def test_last_super_admin_protection(db):
    super_admin = db.scalar(select(User).where(User.role == UserRole.SUPER_ADMIN))

    # Attempt to disable the only active Super Admin -> 400
    with pytest.raises(HTTPException) as exc:
        disable_admin_user(db, super_admin.id, super_admin, client_ip="127.0.0.1")
    assert exc.value.status_code == 400
    assert "At least one active Super Administrator must remain" in exc.value.detail

    # Attempt to soft delete the only active Super Admin -> 400
    with pytest.raises(HTTPException) as exc:
        soft_delete_admin_user(db, super_admin.id, super_admin, client_ip="127.0.0.1")
    assert exc.value.status_code == 400
    assert "At least one active Super Administrator must remain" in exc.value.detail


# --- 7. RBAC API Endpoints Guarding (Super Admin vs Admin vs Operator vs Viewer) ---

def test_api_endpoint_super_admin_rbac(client, db):
    auth_rate_limiter.reset_for_key("login:testclient")

    # 1. Unauthenticated -> 401
    res = client.get("/api/v1/admin/stats")
    assert res.status_code == 401

    # 2. Login as Normal Admin (re-enable Jane who was soft-deleted in test 5)
    admin_user = db.scalar(select(User).where(User.email == "jane.doe@enterprise.com"))
    if admin_user:
        admin_user.is_active = True
        db.commit()

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "jane.doe@enterprise.com", "password": "JaneSecureAdmin2026!"},
    )
    assert res.status_code == 200
    admin_token = res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Normal Admin attempting Super Admin API -> 403 Forbidden
    res = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert res.status_code == 403
    assert "SUPER_ADMIN" in res.json()["detail"]

    res = client.get("/api/v1/admin/requests", headers=admin_headers)
    assert res.status_code == 403

    res = client.get("/api/v1/admin/users", headers=admin_headers)
    assert res.status_code == 403

    # 3. Login as Super Admin
    auth_rate_limiter.reset_for_key("login:testclient")
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@ops.local", "password": "SuperAdminSecret2026!"},
    )
    assert res.status_code == 200
    super_token = res.json()["access_token"]
    super_headers = {"Authorization": f"Bearer {super_token}"}

    # Super Admin accessing Super Admin API -> 200 OK
    res = client.get("/api/v1/admin/stats", headers=super_headers)
    assert res.status_code == 200
    stats = res.json()
    assert "total_admins" in stats
    assert "active_admins" in stats
    assert "pending_requests" in stats

    res = client.get("/api/v1/admin/requests", headers=super_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.get("/api/v1/admin/users", headers=super_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)
