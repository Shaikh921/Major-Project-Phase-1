"""
End-to-End Verification Script for Point 3 Manual Scenarios & Regressions.
"""

import sys
import secrets
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from backend.app.main import app
from backend.app.database.session import SessionLocal
from backend.app.models.user import User, UserRole, UserSession, EmailVerificationToken, PasswordResetToken
from backend.app.models.security import AuditLog
from backend.app.core.security import hash_token, hash_password
from backend.app.services.email_service import EmailService
from backend.app.core.rate_limit import auth_rate_limiter

def run_all_checks():
    print("============================================================")
    print("STARTING POINT 3 END-TO-END VERIFICATION & REGRESSION CHECKS")
    print("============================================================\n")

    client = TestClient(app, base_url="http://127.0.0.1:8000")
    auth_rate_limiter._history.clear()

    # 1. First-run Admin Login
    print("[TEST 1 & 2] Testing Admin Login with correct password...")
    auth_rate_limiter._history.clear()
    login_res = client.post("/api/v1/auth/login", json={"email": "admin@ops.local", "password": "AdminSecurePassword2026!"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    login_data = login_res.json()
    admin_token = login_data["access_token"]
    assert login_data["user"]["role"] == "ADMIN"
    refresh_cookie = login_res.cookies.get("cloudops_refresh_token")
    assert refresh_cookie is not None
    print(" -> SUCCESS: Admin logged in, received access token and HttpOnly refresh cookie.\n")

    # 3. Wrong Password
    print("[TEST 3] Testing Login with incorrect password...")
    auth_rate_limiter._history.clear()
    bad_login = client.post("/api/v1/auth/login", json={"email": "admin@ops.local", "password": "WrongPassword123!"})
    assert bad_login.status_code == 401
    assert "Invalid email or password" in bad_login.json()["detail"]
    print(" -> SUCCESS: Returned 401 with generic safe message.\n")

    # 4. Unknown email login (Anti-enumeration)
    print("[TEST 4] Testing Login with unknown email...")
    auth_rate_limiter._history.clear()
    unknown_login = client.post("/api/v1/auth/login", json={"email": "nonexistent@ops.local", "password": "AnyPassword!"})
    assert unknown_login.status_code == 401
    assert "Invalid email or password" in unknown_login.json()["detail"]
    print(" -> SUCCESS: Returned identical 401 error message.\n")

    # 5. Protected Endpoint without Authentication
    print("[TEST 5 & 6] Testing Protected endpoint without auth -> 401...")
    unauth_res = client.get("/api/v1/summary")
    assert unauth_res.status_code == 401
    print(" -> SUCCESS: Unauthenticated access rejected with 401 Unauthorized.\n")

    # 6. Protected Endpoint with Admin Bearer Token
    print("[TEST 7] Testing Protected endpoints with Admin Bearer Token...")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    summary_res = client.get("/api/v1/summary", headers=admin_headers)
    assert summary_res.status_code == 200
    rules_res = client.get("/api/v1/alerts/rules", headers=admin_headers)
    assert rules_res.status_code == 200
    print(" -> SUCCESS: Admin allowed access to Overview and Admin Rules endpoints.\n")

    # 7. Create an OPERATOR user and test RBAC (403 on Admin endpoint)
    print("[TEST 8] Testing Role Authorization (OPERATOR forbidden on Admin endpoint)...")
    auth_rate_limiter._history.clear()
    with SessionLocal() as db:
        op = db.scalar(select(User).where(User.email == "op-test@ops.local"))
        if not op:
            op = User(
                email="op-test@ops.local",
                password_hash=hash_password("OperatorPass123!"),
                role="OPERATOR",
                is_active=True,
                is_verified=True,
            )
            db.add(op)
            db.commit()

    op_login = client.post("/api/v1/auth/login", json={"email": "op-test@ops.local", "password": "OperatorPass123!"})
    assert op_login.status_code == 200
    op_token = op_login.json()["access_token"]
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # Operator accessing Viewer endpoint -> 200
    op_summary = client.get("/api/v1/summary", headers=op_headers)
    assert op_summary.status_code == 200
    # Operator accessing Admin endpoint -> 403
    op_rules = client.get("/api/v1/alerts/rules", headers=op_headers)
    assert op_rules.status_code == 403
    assert "requires one of ['ADMIN']" in op_rules.json()["detail"]
    print(" -> SUCCESS: Operator permitted on telemetry view (200), forbidden on admin rules (403).\n")

    # 8. Refresh and Session Continuity
    print("[TEST 9] Testing Silent Token Refresh with Cookie...")
    refresh_client = TestClient(app, cookies={"cloudops_refresh_token": refresh_cookie})
    ref_res = refresh_client.post("/api/v1/auth/refresh")
    assert ref_res.status_code == 200
    new_access_token = ref_res.json()["access_token"]
    assert new_access_token is not None
    print(" -> SUCCESS: Refresh session returned fresh access token.\n")

    # 9. Logout & Session Revocation
    print("[TEST 10] Testing Logout and Server-Side Session Revocation...")
    logout_res = refresh_client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200

    # Subsequent refresh attempt with revoked cookie must fail 401
    dead_refresh = refresh_client.post("/api/v1/auth/refresh")
    assert dead_refresh.status_code == 401
    print(" -> SUCCESS: Logout revoked session in database; refresh request rejected (401).\n")

    # 10. Email Verification Workflow
    print("[TEST 11] Testing Email Verification Workflow & Replay Protection...")
    auth_rate_limiter._history.clear()
    with SessionLocal() as db:
        unv = db.scalar(select(User).where(User.email == "unv-verify@ops.local"))
        if not unv:
            unv = User(
                email="unv-verify@ops.local",
                password_hash=hash_password("Password123!"),
                role="VIEWER",
                is_active=True,
                is_verified=False,
            )
            db.add(unv)
            db.commit()
            db.refresh(unv)
        else:
            unv.is_verified = False
            unv.password_hash = hash_password("Password123!")
            db.commit()

        raw_v_token = f"verify_token_{secrets.token_hex(16)}"
        v_hash = hash_token(raw_v_token)
        vt = EmailVerificationToken(
            user_id=unv.id,
            token_hash=v_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(vt)
        db.commit()

    # Attempt login before verification -> 403
    unv_login = client.post("/api/v1/auth/login", json={"email": "unv-verify@ops.local", "password": "Password123!"})
    assert unv_login.status_code == 403
    assert "not verified" in unv_login.json()["detail"]

    # Verify email
    v_res = client.post("/api/v1/auth/verify-email", json={"token": raw_v_token})
    assert v_res.status_code == 200
    assert "successfully verified" in v_res.json()["message"]

    # Replay verification token -> 400
    replay_v = client.post("/api/v1/auth/verify-email", json={"token": raw_v_token})
    assert replay_v.status_code == 400

    # Now login succeeds
    auth_rate_limiter._history.clear()
    v_login = client.post("/api/v1/auth/login", json={"email": "unv-verify@ops.local", "password": "Password123!"})
    assert v_login.status_code == 200
    print(" -> SUCCESS: Email verification activated user account; token replay rejected.\n")

    # 11. Forgot Password & Password Reset Workflow
    print("[TEST 12] Testing Forgot Password & Password Reset Lifecycle...")
    auth_rate_limiter._history.clear()
    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": "unv-verify@ops.local"})
    assert forgot_res.status_code == 200
    assert "instructions have been sent" in forgot_res.json()["message"]

    latest_email = EmailService.get_latest_email_for("unv-verify@ops.local")
    assert latest_email is not None
    pw_reset_token = latest_email["raw_token"]

    # Reset password
    reset_res = client.post("/api/v1/auth/reset-password", json={"token": pw_reset_token, "new_password": "NewSecretPassword2026!"})
    assert reset_res.status_code == 200

    # Old password rejected
    auth_rate_limiter._history.clear()
    old_pw_res = client.post("/api/v1/auth/login", json={"email": "unv-verify@ops.local", "password": "Password123!"})
    assert old_pw_res.status_code == 401

    # New password accepted
    auth_rate_limiter._history.clear()
    new_pw_res = client.post("/api/v1/auth/login", json={"email": "unv-verify@ops.local", "password": "NewSecretPassword2026!"})
    assert new_pw_res.status_code == 200

    # Replay reset token -> 400
    replay_reset = client.post("/api/v1/auth/reset-password", json={"token": pw_reset_token, "new_password": "AnotherNewPassword!"})
    assert replay_reset.status_code == 400
    print(" -> SUCCESS: Password reset updated password; old password fails; new password works; token single-use enforced.\n")

    # 12. Rate Limiting Protection Check
    print("[TEST 13] Testing Rate Limiting Protection (429 Too Many Requests)...")
    auth_rate_limiter._history.clear()
    # Login allows max 5 requests per 60s
    for i in range(5):
        r = client.post("/api/v1/auth/login", json={"email": "admin@ops.local", "password": "WrongPassword!"})
        assert r.status_code == 401
    # 6th request must trigger 429
    rate_limited_res = client.post("/api/v1/auth/login", json={"email": "admin@ops.local", "password": "WrongPassword!"})
    assert rate_limited_res.status_code == 429
    assert "Too many requests" in rate_limited_res.json()["detail"]
    print(" -> SUCCESS: Rate limiter triggered 429 Too Many Requests on abusive attempts.\n")

    # 13. Regression Testing: All Core Operational Modules
    print("[TEST 14] Running Full Module Regression Suite with Authenticated Session...")
    auth_headers = {"Authorization": f"Bearer {admin_token}"}

    # Overview Summary
    assert client.get("/api/v1/summary", headers=auth_headers).status_code == 200
    # Hosts / Infrastructure
    assert client.get("/api/v1/hosts", headers=auth_headers).status_code == 200
    # Telemetry Stream
    assert client.get("/api/v1/metrics?host_id=1", headers=auth_headers).status_code == 200
    # Alerts / Anomaly Center / Incidents
    assert client.get("/api/v1/alerts", headers=auth_headers).status_code == 200
    # Security & Threat
    assert client.get("/api/v1/security/summary", headers=auth_headers).status_code == 200
    assert client.get("/api/v1/security/events", headers=auth_headers).status_code == 200
    # Cost Optimization
    assert client.get("/api/v1/cost/summary", headers=auth_headers).status_code == 200
    # Forecast
    assert client.get("/api/v1/forecast?host_id=1&metric=cpu_percent", headers=auth_headers).status_code == 200
    # AI Models
    assert client.get("/api/v1/ai/models", headers=auth_headers).status_code == 200
    # AI Incident Narrator
    assert client.post("/api/v1/narrator/query", json={"query": "test query", "time_window_minutes": 60}, headers=auth_headers).status_code == 200
    # Reports & Export
    assert client.post("/api/v1/reports/generate", json={"time_range_hours": 24}, headers=auth_headers).status_code == 200
    # Audit Trail
    assert client.get("/api/v1/audit/logs", headers=auth_headers).status_code == 200
    # Threshold Rules
    assert client.get("/api/v1/alerts/rules", headers=auth_headers).status_code == 200
    # Currency Rates (Point 2)
    assert client.get("/api/v1/currency/rates?base=USD&quotes=INR,EUR,GBP", headers=auth_headers).status_code == 200
    assert client.get("/api/v1/currency/supported", headers=auth_headers).status_code == 200

    print(" -> SUCCESS: All 11 operational modules, Currency FX, and Alert Rules verified operational!\n")

    # 14. Audit Trail Verification
    with SessionLocal() as db:
        recent_audits = list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(20)).all())
        actions = [a.action for a in recent_audits]
        print(f"Recorded Security Audit Actions: {set(actions)}")
        assert "LOGIN_SUCCESS" in actions
        assert "LOGIN_FAILURE" in actions
        assert "PASSWORD_RESET_SUCCESS" in actions

    print("\n============================================================")
    print("ALL POINT 3 AUTHENTICATION & REGRESSION CHECKS PASSED (100%)!")
    print("============================================================\n")

if __name__ == "__main__":
    run_all_checks()
