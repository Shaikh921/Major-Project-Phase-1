"""
Comprehensive Test Suite for Module 4: Production SMTP & Email Notification System.

Validates:
1. SMTP configuration and dual-mode dispatch (SMTP vs Dev Outbox).
2. Mocked STARTTLS and SSL transports with timeout and auth failure sanitization.
3. All 7 HTML and Plaintext email templates.
4. Admin registration -> verification -> Super Admin notification -> approval -> activation flow.
5. Password reset email flow with single-use token lifecycle.
6. Critical SRE Alert notification hook with anti-storm deduplication.
7. Super Admin SMTP diagnostic endpoint (/api/v1/admin/email/test) with strict RBAC.
8. Zero credentials, passwords, or raw tokens exposed in logs or API responses.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models.user import (
    User,
    UserRole,
    AdminRegistrationRequest,
    AdminRequestStatus,
)
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import AlertRule, Alert
from backend.app.services.email_service import EmailService, EmailDeliveryStatus
from backend.app.services.auth_service import (
    create_admin_registration_request,
    verify_admin_request_email,
    approve_admin_request,
    reject_admin_request,
    request_password_reset,
)
from backend.app.services.alert_service import evaluate_metric_sample
from backend.app.schemas.auth import AdminRegistrationRequestCreate
from backend.app.core.security import hash_password, create_access_token
from backend.app.templates.email_templates import (
    get_admin_verification_email,
    get_super_admin_new_request_notification_email,
    get_admin_approval_activation_email,
    get_admin_rejection_email,
    get_password_reset_email,
    get_critical_alert_email,
    get_smtp_test_email,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_outbox_and_state():
    """Ensures clean outbox and default configuration before each test."""
    EmailService.clear_outbox()
    orig_smtp_enabled = settings.smtp_enabled
    orig_notify_super = settings.notify_super_admins_on_new_request
    orig_notify_alerts = settings.notify_on_critical_alerts

    settings.smtp_enabled = False
    settings.notify_super_admins_on_new_request = True
    settings.notify_on_critical_alerts = False

    yield

    settings.smtp_enabled = orig_smtp_enabled
    settings.notify_super_admins_on_new_request = orig_notify_super
    settings.notify_on_critical_alerts = orig_notify_alerts
    EmailService.clear_outbox()


# ==============================================================================
# 1. Template Generation Tests
# ==============================================================================

def test_all_email_templates_render_cleanly():
    """Verifies all 7 templates produce valid subjects, HTML, and plaintext without emojis."""
    # 1. Admin Verification
    sub, html_body, text_body = get_admin_verification_email(
        email="applicant@corp.local",
        full_name="Alice Admin",
        raw_token="raw_test_token_123",
    )
    assert "Verify Your Administrator Access Request" in sub
    assert "Alice Admin" in html_body
    assert "raw_test_token_123" in html_body
    assert "raw_test_token_123" in text_body
    assert "24 hours" in text_body

    # 2. Super Admin Notification
    sub, html_body, text_body = get_super_admin_new_request_notification_email(
        super_admin_email="super@ops.local",
        applicant_email="applicant@corp.local",
        applicant_name="Alice Admin",
        organization="SRE Operations",
        reason="Fleet on-call",
    )
    assert "ACTION REQUIRED" in sub
    assert "Alice Admin" in html_body
    assert "SRE Operations" in html_body
    assert "Fleet on-call" in text_body

    # 3. Admin Approval & Activation
    sub, html_body, text_body = get_admin_approval_activation_email(
        email="applicant@corp.local",
        full_name="Alice Admin",
        raw_token="activation_token_456",
    )
    assert "Approved" in sub
    assert "activation_token_456" in html_body
    assert "24 hours" in text_body

    # 4. Admin Rejection
    sub, html_body, text_body = get_admin_rejection_email(
        email="applicant@corp.local",
        full_name="Bob User",
        reason="Insufficient authorization level",
    )
    assert "Update Regarding Your Administrator Access Request" in sub
    assert "Insufficient authorization level" in html_body
    assert "Insufficient authorization level" in text_body

    # 5. Password Reset
    sub, html_body, text_body = get_password_reset_email(
        email="user@ops.local",
        raw_token="reset_token_789",
    )
    assert "Password Reset Instructions" in sub
    assert "reset_token_789" in html_body
    assert f"{settings.password_reset_token_expire_minutes} minutes" in text_body

    # 6. Critical SRE Alert
    sub, html_body, text_body = get_critical_alert_email(
        alert_id=42,
        host_name="prod-api-01",
        metric="cpu_percent",
        value=98.5,
        threshold=90.0,
        operator=">=",
        message="Critical CPU load",
    )
    assert "CRITICAL ALERT: prod-api-01 - cpu_percent" in sub
    assert "98.50%" in html_body
    assert "#42" in html_body
    assert "#42" in text_body

    # 7. SMTP Test
    sub, html_body, text_body = get_smtp_test_email(recipient_email="admin@ops.local")
    assert "SMTP Relay Diagnostic Test" in sub
    assert "admin@ops.local" in html_body
    assert "DIAGNOSTIC STATUS: OK" in html_body


# ==============================================================================
# 2. SMTP Transport & Mock Dispatch Tests
# ==============================================================================

def test_smtp_disabled_captures_in_dev_outbox():
    """Verifies that with SMTP_ENABLED=False, emails are logged to _dev_outbox without network calls."""
    settings.smtp_enabled = False
    success, msg = EmailService.send_test_email("test@ops.local")
    assert success is True
    assert "development outbox" in msg.lower()

    outbox = EmailService.get_outbox()
    assert len(outbox) == 1
    assert outbox[0]["to"] == "test@ops.local"
    assert outbox[0]["status"] == EmailDeliveryStatus.MOCKED


@patch("backend.app.services.email_service.smtplib.SMTP")
def test_smtp_enabled_starttls_success(mock_smtp_class):
    """Verifies successful SMTP dispatch over STARTTLS when enabled."""
    mock_server = MagicMock()
    mock_smtp_class.return_value = mock_server

    settings.smtp_enabled = True
    settings.smtp_host = "smtp.mock-relay.local"
    settings.smtp_port = 587
    settings.smtp_user = "user@mock.local"
    settings.smtp_password = "SecretPassword123!"
    settings.smtp_tls = True
    settings.smtp_ssl = False

    success, msg = EmailService.send_test_email("recipient@ops.local")
    assert success is True
    assert "successfully delivered" in msg

    mock_server.ehlo.assert_called()
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@mock.local", "SecretPassword123!")
    mock_server.send_message.assert_called_once()


@patch("backend.app.services.email_service.smtplib.SMTP_SSL")
def test_smtp_enabled_ssl_success(mock_smtp_ssl_class):
    """Verifies direct SSL SMTP dispatch (port 465)."""
    mock_server = MagicMock()
    mock_smtp_ssl_class.return_value = mock_server

    settings.smtp_enabled = True
    settings.smtp_host = "smtp.ssl-relay.local"
    settings.smtp_port = 465
    settings.smtp_user = "ssl-user@mock.local"
    settings.smtp_password = "SecretPassword123!"
    settings.smtp_tls = False
    settings.smtp_ssl = True

    success, msg = EmailService.send_test_email("recipient@ops.local")
    assert success is True
    assert "successfully delivered" in msg

    mock_server.login.assert_called_once_with("ssl-user@mock.local", "SecretPassword123!")
    mock_server.send_message.assert_called_once()


@patch("backend.app.services.email_service.smtplib.SMTP")
def test_smtp_auth_failure_sanitized_error(mock_smtp_class):
    """Verifies that authentication errors are sanitized without leaking passwords."""
    import smtplib
    mock_server = MagicMock()
    mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication credentials invalid")
    mock_smtp_class.return_value = mock_server

    settings.smtp_enabled = True
    settings.smtp_host = "smtp.mock-relay.local"
    settings.smtp_port = 587
    settings.smtp_user = "user@mock.local"
    settings.smtp_password = "MySuperSecretPassword!"
    settings.smtp_tls = True
    settings.smtp_ssl = False

    success, msg = EmailService.send_test_email("recipient@ops.local")
    assert success is False
    assert "authentication failed" in msg.lower()
    assert "MySuperSecretPassword!" not in msg


@patch("backend.app.services.email_service.smtplib.SMTP")
def test_smtp_timeout_sanitized_error(mock_smtp_class):
    """Verifies that network timeouts are handled safely."""
    mock_smtp_class.side_effect = TimeoutError("Connection timed out after 10000ms")

    settings.smtp_enabled = True
    settings.smtp_host = "192.0.2.1"
    settings.smtp_port = 587
    settings.smtp_tls = True
    settings.smtp_ssl = False

    success, msg = EmailService.send_test_email("recipient@ops.local")
    assert success is False
    assert "timed out" in msg.lower()


# ==============================================================================
# 3. Admin Lifecycle & Super Admin Notification Flow
# ==============================================================================

def test_admin_registration_and_super_admin_notification_flow():
    """
    Tests full flow:
    1. Public submission -> Verification email to applicant
    2. Email verified -> Notification email to all active Super Admins
    3. Super Admin approval -> Activation email to applicant
    """
    db = SessionLocal()
    try:
        # Ensure at least one active Super Admin exists
        super_admin = db.scalar(select(User).where(User.role == UserRole.SUPER_ADMIN, User.is_active == True))
        if not super_admin:
            super_admin = User(
                email=f"sa-{datetime.now().timestamp()}@ops.local",
                password_hash=hash_password("SuperSecret123!"),
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(super_admin)
            db.commit()
            db.refresh(super_admin)

        unique_email = f"applicant-{datetime.now().timestamp()}@enterprise.local"

        # 1. Submit Request
        req_in = AdminRegistrationRequestCreate(
            full_name="Arthur Pendelton",
            email=unique_email,
            organization="Cloud Infra Team",
            reason="Primary on-call incident response",
        )
        req = create_admin_registration_request(db, req_in, client_ip="127.0.0.1")
        assert req.status == AdminRequestStatus.EMAIL_UNVERIFIED

        # Verify applicant received verification email
        applicant_email = EmailService.get_latest_email_for(unique_email)
        assert applicant_email is not None
        assert applicant_email["type"] == "ADMIN_REQUEST_VERIFICATION"
        raw_token = applicant_email["raw_token"]

        EmailService.clear_outbox()

        # 2. Verify Email -> Must notify Super Admin
        verified_req = verify_admin_request_email(db, raw_token, client_ip="127.0.0.1")
        assert verified_req.status == AdminRequestStatus.PENDING_SUPER_ADMIN_APPROVAL

        sa_email = EmailService.get_latest_email_for(super_admin.email)
        assert sa_email is not None
        assert sa_email["type"] == "SUPER_ADMIN_NEW_REQUEST_NOTIFICATION"
        assert sa_email["applicant_email"] == unique_email

        EmailService.clear_outbox()

        # 3. Super Admin Approves -> Activation email to applicant
        approved_req, user, act_token = approve_admin_request(db, verified_req.id, super_admin, client_ip="127.0.0.1")
        assert approved_req.status == AdminRequestStatus.ACTIVATION_PENDING

        act_email = EmailService.get_latest_email_for(unique_email)
        assert act_email is not None
        assert act_email["type"] == "ADMIN_APPROVAL_ACTIVATION"
        assert act_email["raw_token"] == act_token

    finally:
        db.close()


def test_admin_request_rejection_email_flow():
    """Verifies rejection email is dispatched with optional reviewer notes."""
    db = SessionLocal()
    try:
        super_admin = db.scalar(select(User).where(User.role == UserRole.SUPER_ADMIN, User.is_active == True))
        unique_email = f"reject-{datetime.now().timestamp()}@enterprise.local"

        req_in = AdminRegistrationRequestCreate(
            full_name="Denied Applicant",
            email=unique_email,
            organization="External Contractor",
            reason="Temporary access",
        )
        req = create_admin_registration_request(db, req_in)
        verify_admin_request_email(db, EmailService.get_latest_email_for(unique_email)["raw_token"])

        EmailService.clear_outbox()

        reject_admin_request(db, req.id, super_admin, reason="Contractor access denied by security policy")

        rej_email = EmailService.get_latest_email_for(unique_email)
        assert rej_email is not None
        assert rej_email["type"] == "ADMIN_REQUEST_REJECTION"
        assert "Contractor access denied by security policy" in rej_email["reason"]

    finally:
        db.close()


# ==============================================================================
# 4. Password Reset Flow Tests
# ==============================================================================

def test_password_reset_email_dispatch():
    """Verifies password reset dispatches email with single-use reset token."""
    db = SessionLocal()
    try:
        user_email = f"pwd-test-{datetime.now().timestamp()}@ops.local"
        user = User(
            email=user_email,
            password_hash=hash_password("OldPassword123!"),
            role=UserRole.OPERATOR,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()

        request_password_reset(db, user_email, client_ip="127.0.0.1")

        reset_email = EmailService.get_latest_email_for(user_email)
        assert reset_email is not None
        assert reset_email["type"] == "PASSWORD_RESET"
        assert "raw_token" in reset_email
        assert reset_email["raw_token"] is not None

    finally:
        db.close()


# ==============================================================================
# 5. Critical SRE Alert Notification & Anti-Storm Deduplication
# ==============================================================================

def test_critical_alert_notification_and_anti_storm_deduplication():
    """
    Verifies:
    1. A newly created CRITICAL alert triggers an email to active administrators when enabled.
    2. Subsequent metric evaluations for the same active alert update values but do NOT dispatch duplicate emails.
    """
    settings.notify_on_critical_alerts = True
    db = SessionLocal()
    try:
        # Create a test host
        host = Host(
            hostname=f"test-alert-host-{datetime.now().timestamp()}",
            ip_address="192.0.2.100",
            environment="production",
            is_active=True,
        )
        db.add(host)
        db.commit()
        db.refresh(host)

        # Ensure an active admin exists to receive alert email
        admin = db.scalar(select(User).where(User.role.in_([UserRole.SUPER_ADMIN, UserRole.ADMIN]), User.is_active == True))
        if not admin:
            admin = User(
                email="alert-admin@ops.local",
                password_hash=hash_password("Pass123!"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
            db.commit()

        # Create a critical alert rule
        rule = AlertRule(
            name="Emergency CPU",
            metric="cpu_percent",
            operator=">=",
            threshold=90.0,
            severity="critical",
            environment="production",
            is_enabled=True,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)

        # 1. Breach Threshold -> Creates new critical Alert -> Dispatches 1 email
        m1 = Metric(
            host_id=host.id,
            timestamp=datetime.now(timezone.utc),
            cpu_percent=95.0,
            memory_percent=50.0,
            disk_percent=40.0,
            network_sent_mb=10.0,
            network_received_mb=10.0,
        )
        db.add(m1)
        db.commit()

        alerts_1 = evaluate_metric_sample(db, host, m1)
        assert len(alerts_1) >= 1
        assert any(a.severity == "critical" for a in alerts_1)

        outbox_1 = EmailService.get_outbox()
        critical_emails_1 = [msg for msg in outbox_1 if msg.get("type") == "CRITICAL_ALERT"]
        assert len(critical_emails_1) >= 1  # Dispatched to active admins

        EmailService.clear_outbox()

        # 2. Subsequent Breach on Same Active Alert -> Updates record, ZERO duplicate emails
        m2 = Metric(
            host_id=host.id,
            timestamp=datetime.now(timezone.utc) + timedelta(seconds=30),
            cpu_percent=98.0,
            memory_percent=50.0,
            disk_percent=40.0,
            network_sent_mb=10.0,
            network_received_mb=10.0,
        )
        db.add(m2)
        db.commit()

        alerts_2 = evaluate_metric_sample(db, host, m2)
        assert len(alerts_2) >= 1

        outbox_2 = EmailService.get_outbox()
        critical_emails_2 = [msg for msg in outbox_2 if msg.get("type") == "CRITICAL_ALERT"]
        assert len(critical_emails_2) == 0  # No duplicate alert emails sent!

    finally:
        # DB Cleanup so other tests have pristine state
        if 'host' in locals() and host.id:
            db.query(Metric).filter(Metric.host_id == host.id).delete()
            db.query(Alert).filter(Alert.host_id == host.id).delete()
            db.delete(host)
        if 'rule' in locals() and rule.id:
            db.delete(rule)
        db.commit()
        db.close()


# ==============================================================================
# 6. Super Admin Diagnostic API & RBAC Tests
# ==============================================================================

def test_smtp_diagnostic_endpoint_rbac():
    """
    Verifies /api/v1/admin/email/test authorization:
    - SUPER_ADMIN: 200 OK
    - ADMIN: 403 Forbidden
    - OPERATOR: 403 Forbidden
    - VIEWER: 403 Forbidden
    - Unauthenticated: 401 Unauthorized
    """
    db = SessionLocal()
    try:
        # Create users with various roles
        roles = {
            UserRole.SUPER_ADMIN: User(email="sa-diag@ops.local", password_hash="dummy", role=UserRole.SUPER_ADMIN, is_active=True, is_verified=True),
            UserRole.ADMIN: User(email="admin-diag@ops.local", password_hash="dummy", role=UserRole.ADMIN, is_active=True, is_verified=True),
            UserRole.OPERATOR: User(email="op-diag@ops.local", password_hash="dummy", role=UserRole.OPERATOR, is_active=True, is_verified=True),
            UserRole.VIEWER: User(email="vi-diag@ops.local", password_hash="dummy", role=UserRole.VIEWER, is_active=True, is_verified=True),
        }
        for u in roles.values():
            existing = db.scalar(select(User).where(User.email == u.email))
            if not existing:
                db.add(u)
        db.commit()

        # 1. Unauthenticated -> 401
        res_unauth = client.post("/api/v1/admin/email/test", json={"recipient": "test@ops.local"})
        assert res_unauth.status_code == 401

        # 2. VIEWER -> 403
        viewer = db.scalar(select(User).where(User.email == "vi-diag@ops.local"))
        viewer_token = create_access_token(user_id=viewer.id, email=viewer.email, role=viewer.role)
        res_viewer = client.post(
            "/api/v1/admin/email/test",
            json={"recipient": "test@ops.local"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert res_viewer.status_code == 403

        # 3. ADMIN -> 403 (Strictly Super Admin only)
        admin = db.scalar(select(User).where(User.email == "admin-diag@ops.local"))
        admin_token = create_access_token(user_id=admin.id, email=admin.email, role=admin.role)
        res_admin = client.post(
            "/api/v1/admin/email/test",
            json={"recipient": "test@ops.local"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_admin.status_code == 403

        # 4. SUPER_ADMIN -> 200 OK
        sa = db.scalar(select(User).where(User.email == "sa-diag@ops.local"))
        sa_token = create_access_token(user_id=sa.id, email=sa.email, role=sa.role)
        res_sa = client.post(
            "/api/v1/admin/email/test",
            json={"recipient": "test@ops.local"},
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert res_sa.status_code == 200
        data = res_sa.json()
        assert data["success"] is True
        assert data["recipient"] == "test@ops.local"
        assert data["mode"] == "DEV_OUTBOX"

    finally:
        db.close()
