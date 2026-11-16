"""
Verification and Security Test Suite for Remote Power Operations (Reboot / Shutdown / Abort).

Tests:
1. Parameter validation & CLI command injection prevention.
2. Code-level killswitch / feature flag toggle.
3. Strict RBAC privilege enforcement (Super Admin / Admin vs Operator / Viewer).
4. Full audit trail generation for power operations.
5. DiagnosticWorker client-side execution safety.
"""

import sys
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Setup sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import HTTPException
from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models.user import User, UserRole
from backend.app.models.host import Host
from backend.app.models.diagnostic import DiagnosticAction, DiagnosticCommand
from backend.app.models.security import AuditLog
from backend.app.core.validator import validate_power_action_target
from backend.app.schemas.diagnostic import DiagnosticDispatchCreate
from backend.app.services.diagnostic_service import dispatch_diagnostic_command
from monitoring_agent.diagnostic_worker import DiagnosticWorker


def test_suite_1_parameter_validation():
    print("[*] TEST SUITE 1: Parameter Validation & CLI Injection Defenses")

    # 1. Valid parameters
    res1 = validate_power_action_target("REBOOT_HOST", "60")
    data1 = json.loads(res1)
    assert data1["grace_seconds"] == 60
    print("    [+] Successfully validated integer grace seconds: 60s")

    res2 = validate_power_action_target(
        "SHUTDOWN_HOST",
        json.dumps({"grace_seconds": 120, "reason": "Emergency kernel maintenance"}),
    )
    data2 = json.loads(res2)
    assert data2["grace_seconds"] == 120
    assert data2["reason"] == "Emergency kernel maintenance"
    print("    [+] Successfully validated JSON parameters with reason")

    # 2. Defenses against CLI command injection
    malicious_inputs = [
        "60; calc.exe",
        "60 & dir C:\\",
        "60 | powershell -enc ...",
        "60 `whoami`",
        "60 > output.txt",
        json.dumps({"grace_seconds": 30, "reason": 'Reboot"; shutdown /s /t 0; #'}),
    ]

    for bad in malicious_inputs:
        try:
            validate_power_action_target("REBOOT_HOST", bad)
            assert False, f"Failed to reject malicious injection: {bad}"
        except ValueError:
            pass
    print("    [+] Successfully blocked 6/6 CLI injection attack vectors")

    # 3. Grace bounds check (0-3600s, min grace)
    try:
        validate_power_action_target("REBOOT_HOST", "5")  # Below min 10
        assert False, "Failed to reject grace period below minimum"
    except ValueError:
        print("    [+] Enforced minimum countdown bounds (10s)")

    try:
        validate_power_action_target("REBOOT_HOST", "50000")  # Above 3600
        assert False, "Failed to reject excessive grace period"
    except ValueError:
        print("    [+] Enforced maximum countdown bounds (3600s)")


def test_suite_2_feature_flag_killswitch():
    print("[*] TEST SUITE 2: Code-Level Feature Flag / Killswitch")
    db = SessionLocal()
    try:
        host = db.query(Host).filter(Host.is_active == True).first()
        if not host:
            host = Host(hostname="test-power-host", ip_address="10.0.0.99", environment="lab", is_active=True)
            db.add(host)
            db.commit()

        admin_user = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        assert admin_user is not None

        dispatch_in = DiagnosticDispatchCreate(
            host_id=host.id,
            action=DiagnosticAction.REBOOT_HOST,
            target=json.dumps({"grace_seconds": 60, "reason": "Test reboot"}),
            timeout_seconds=30,
        )

        # Test: When feature flag is disabled
        orig_setting = settings.enable_remote_power_operations
        try:
            settings.enable_remote_power_operations = False
            try:
                dispatch_diagnostic_command(db=db, dispatch_in=dispatch_in, requesting_user=admin_user)
                assert False, "Should have been forbidden when enable_remote_power_operations is False"
            except HTTPException as ex:
                assert ex.status_code == 403
                assert "globally disabled" in ex.detail
                print("    [+] Code killswitch (enable_remote_power_operations=False) completely blocks dispatch with 403")

            # Test: When feature flag is enabled
            settings.enable_remote_power_operations = True
            cmd = dispatch_diagnostic_command(db=db, dispatch_in=dispatch_in, requesting_user=admin_user)
            assert cmd.id is not None
            assert cmd.action == DiagnosticAction.REBOOT_HOST
            print("    [+] Dispatched successfully when feature flag is enabled")
        finally:
            settings.enable_remote_power_operations = orig_setting

    finally:
        db.close()


def test_suite_3_rbac_privilege_enforcement():
    print("[*] TEST SUITE 3: RBAC Privilege Enforcement (Super Admin / Admin vs Operator / Viewer)")
    db = SessionLocal()
    try:
        host = db.query(Host).filter(Host.is_active == True).first()
        dispatch_in = DiagnosticDispatchCreate(
            host_id=host.id,
            action=DiagnosticAction.SHUTDOWN_HOST,
            target=json.dumps({"grace_seconds": 60, "reason": "Role gate test"}),
            timeout_seconds=30,
        )

        # 1. Viewer Role
        viewer_user = db.query(User).filter(User.role == UserRole.VIEWER).first()
        if not viewer_user:
            viewer_user = User(id=9992, email="v@ops.local", role=UserRole.VIEWER, is_active=True, is_verified=True, hashed_password="...")
        try:
            dispatch_diagnostic_command(db=db, dispatch_in=dispatch_in, requesting_user=viewer_user)
            assert False, "Viewer should have been rejected"
        except HTTPException as ex:
            assert ex.status_code == 403
            print("    [+] Blocked VIEWER role with 403 Forbidden")

        # 2. Operator Role
        operator_user = db.query(User).filter(User.role == UserRole.OPERATOR).first()
        if not operator_user:
            operator_user = User(id=9993, email="o@ops.local", role=UserRole.OPERATOR, is_active=True, is_verified=True, hashed_password="...")
        try:
            dispatch_diagnostic_command(db=db, dispatch_in=dispatch_in, requesting_user=operator_user)
            assert False, "Operator should have been rejected from power actions"
        except HTTPException as ex:
            assert ex.status_code == 403
            assert "strictly restricted to Administrators" in ex.detail
            print("    [+] Blocked OPERATOR role with 403 Forbidden")

        # 3. Admin Role (with assignment)
        admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
        assert admin_user is not None
        from backend.app.services.assignment_service import grant_environment_assignment
        try:
            grant_environment_assignment(db, admin_user.id, host.environment, admin_user.id)
        except Exception:
            pass
        cmd = dispatch_diagnostic_command(db=db, dispatch_in=dispatch_in, requesting_user=admin_user)
        assert cmd.id is not None
        assert cmd.action == DiagnosticAction.SHUTDOWN_HOST
        print("    [+] Authorized ADMIN role with active environment assignment successfully")

    finally:
        db.close()


def test_suite_4_audit_trail():
    print("[*] TEST SUITE 4: Authoritative Audit Trail for Power Operations")
    db = SessionLocal()
    try:
        latest_audit = (
            db.query(AuditLog)
            .filter(AuditLog.action.like("REMOTE_POWER_OPERATION%"))
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert latest_audit is not None
        assert "REMOTE_POWER_OPERATION_SHUTDOWN_HOST" in latest_audit.action
        print(f"    [+] Audit log verified: {latest_audit.action} by {latest_audit.user_email}")
    finally:
        db.close()


def test_suite_5_worker_execution_safety():
    print("[*] TEST SUITE 5: Diagnostic Worker Execution Handling")
    from unittest.mock import patch

    worker = DiagnosticWorker(config_path="nonexistent_config.json")
    worker.config = {"allow_remote_power_ops": True}

    with patch("monitoring_agent.diagnostic_worker.run_process_in_job_object", return_value=(0, "Success", "")):
        code, out, err, payload = worker.execute_predefined_action("ABORT_SHUTDOWN", None, 10)
        assert code == 0
        assert payload["action"] == "ABORT_SHUTDOWN"
        print("    [+] DiagnosticWorker cleanly handled ABORT_SHUTDOWN")

        code, out, err, payload = worker.execute_predefined_action(
            "REBOOT_HOST",
            json.dumps({"grace_seconds": 30, "reason": "Test"}),
            10,
        )
        assert code == 0
        assert payload["grace_seconds"] == 30
        print("    [+] DiagnosticWorker cleanly handled REBOOT_HOST with 30s grace")

    # Test local policy disable
    worker.config = {"allow_remote_power_ops": False}
    code, out, err, payload = worker.execute_predefined_action("REBOOT_HOST", None, 10)
    assert code == 1
    assert "disabled by policy" in err
    print("    [+] DiagnosticWorker respected local sensor_config.json killswitch")


def run_all_tests():
    print("=" * 70)
    print(" CloudOps Intel — Remote Power Operations Verification Suite")
    print("=" * 70)
    test_suite_1_parameter_validation()
    test_suite_2_feature_flag_killswitch()
    test_suite_3_rbac_privilege_enforcement()
    test_suite_4_audit_trail()
    test_suite_5_worker_execution_safety()
    print("=" * 70)
    print("[+] ALL 5 TEST SUITES PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
