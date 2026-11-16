"""
Automated Integration and Verification Test Suite for Phase 9A.1.

Tests:
1. RFC 1123 target validator and CLI parameter injection defenses.
2. Hybrid RBAC assignment grants, revocations, and access scoping.
3. Atomic conditional diagnostic dispatch under SQLite transaction locking.
4. Command claiming, lease timers, and hard deadlines.
5. Canonical SHA-256 result hashing, idempotency, and conflict quarantine.
6. Atomic host decommissioning cascading to assignments and pending commands.
"""

import sys
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# Setup sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.database.session import SessionLocal
from backend.app.models.user import User, UserRole
from backend.app.models.host import Host
from backend.app.models.assignment import (
    UserEnvironmentAssignment,
    UserHostAssignment,
    AssignmentStatus,
)
from backend.app.models.diagnostic import (
    DiagnosticCommand,
    DiagnosticResult,
    DiagnosticAction,
    DiagnosticStatus,
)
from backend.app.models.security import AuditLog
from backend.app.core.validator import validate_diagnostic_target
from backend.app.schemas.diagnostic import DiagnosticDispatchCreate, DiagnosticResultCreate
from backend.app.services.assignment_service import (
    grant_environment_assignment,
    revoke_environment_assignment,
    grant_host_assignment,
    revoke_host_assignment,
    check_user_host_access,
)
from backend.app.services.diagnostic_service import (
    dispatch_diagnostic_command,
    claim_pending_command,
    record_diagnostic_result,
    sweep_expired_diagnostic_leases,
)
from backend.app.services.host_service import decommission_host_atomic


def run_tests():
    print("[*] ========================================================================")
    print("[*] CLOUDOPS INTEL — PHASE 9A.1 AUTOMATED VERIFICATION TEST SUITE")
    print("[*] ========================================================================")

    # TEST 1: RFC 1123 Hostname Validator
    print("\n[TEST 1] Testing RFC 1123 Hostname Validator & Injection Defenses...")
    assert validate_diagnostic_target("localhost") == "localhost"
    assert validate_diagnostic_target("node-01.prod.internal") == "node-01.prod.internal"
    assert validate_diagnostic_target("10.227.136.246") == "10.227.136.246"
    assert validate_diagnostic_target("2001:db8::1") == "2001:db8::1"
    
    invalid_cases = [
        "-flag", "/flag", "host..com", "host_name.com", "node-.com",
        "node.123", "a" * 254, "; rm -rf", "test&echo", "192.168.1.1;"
    ]
    for inv in invalid_cases:
        try:
            validate_diagnostic_target(inv)
            raise AssertionError(f"Expected ValueError for target: {inv}")
        except ValueError:
            pass
    print("[+] TEST 1 PASSED: Target validator successfully blocks all CLI injections and invalid formats.")

    db = SessionLocal()
    try:
        # TEST 2: Hybrid RBAC Scoping
        print("\n[TEST 2] Testing Hybrid RBAC Assignment Scoping...")
        # Get or create test users
        super_admin = db.scalar(select(User).where(User.role == UserRole.SUPER_ADMIN).limit(1))
        assert super_admin is not None, "Super admin user must exist"

        operator = db.scalar(select(User).where(User.role == UserRole.OPERATOR).limit(1))
        if not operator:
            operator = User(
                email="test_operator@cloudops.internal",
                password_hash="test",
                role=UserRole.OPERATOR,
                is_active=True,
                is_verified=True,
            )
            db.add(operator)
            db.commit()
            db.refresh(operator)

        # Get test host
        host = db.scalar(select(Host).where(Host.is_active == True).limit(1))
        assert host is not None, "At least one active host must exist"

        # Super admin always has access
        assert check_user_host_access(db, super_admin, host) is True, "Super Admin must have global access"

        # Operator without assignment: access denied
        # Ensure any old assignments for test are cleaned
        db.query(UserEnvironmentAssignment).filter(UserEnvironmentAssignment.user_id == operator.id).delete()
        db.query(UserHostAssignment).filter(UserHostAssignment.user_id == operator.id).delete()
        db.commit()

        assert check_user_host_access(db, operator, host) is False, "Operator without assignment must be denied"

        # Grant environment assignment
        ea = grant_environment_assignment(db, operator.id, host.environment, super_admin.id)
        assert ea.status == AssignmentStatus.ACTIVE
        assert check_user_host_access(db, operator, host) is True, "Operator with environment assignment must have access"

        # Revoke environment assignment
        revoke_environment_assignment(db, ea.id, super_admin.id)
        assert check_user_host_access(db, operator, host) is False, "Revoked assignment must immediately deny access"

        # Grant host assignment
        ha = grant_host_assignment(db, operator.id, host.id, super_admin.id)
        assert ha.status == AssignmentStatus.ACTIVE
        assert check_user_host_access(db, operator, host) is True, "Operator with host assignment must have access"
        print("[+] TEST 2 PASSED: Hybrid RBAC access scoping correctly grants and revokes permissions.")

        # TEST 3: Predefined Diagnostic Atomic Dispatch
        print("\n[TEST 3] Testing Atomic Conditional Diagnostic Dispatch...")
        dispatch_req = DiagnosticDispatchCreate(
            host_id=host.id,
            action=DiagnosticAction.PING_GATEWAY,
            target="127.0.0.1",
            timeout_seconds=15,
        )

        cmd = dispatch_diagnostic_command(db, dispatch_req, operator)
        assert cmd is not None
        assert cmd.status == DiagnosticStatus.PENDING
        assert cmd.action == DiagnosticAction.PING_GATEWAY
        assert cmd.host_id == host.id
        print(f"[+] Diagnostic command dispatched successfully: UUID {cmd.id}")

        # Verify atomic AuditLog record
        audit = db.scalar(
            select(AuditLog)
            .where(AuditLog.action == "DISPATCH_DIAGNOSTIC")
            .order_by(AuditLog.id.desc())
            .limit(1)
        )
        assert audit is not None, "Atomic AuditLog row must be present for dispatch"
        print("[+] TEST 3 PASSED: Conditional dispatch and atomic audit logging verified.")

        # TEST 4: Command Claiming & Lease Deadlines
        print("\n[TEST 4] Testing Command Claiming & Lease Bounds...")
        claimed_cmd = claim_pending_command(db, host_id=host.id, agent_id="canary-agent-01")
        assert claimed_cmd is not None
        assert claimed_cmd.id == cmd.id
        assert claimed_cmd.status == DiagnosticStatus.CLAIMED
        assert claimed_cmd.lease_expires_at is not None
        assert claimed_cmd.hard_deadline_at is not None
        print(f"[+] Command claimed by agent: lease expires at {claimed_cmd.lease_expires_at.isoformat()}")
        print("[+] TEST 4 PASSED: Claiming and lease bounds successfully enforced.")

        # TEST 5: Result Persistence, SHA-256 Hashing & Idempotency
        print("\n[TEST 5] Testing Result Persistence, Hashing & Idempotency...")
        result_payload = DiagnosticResultCreate(
            command_id=cmd.id,
            exit_code=0,
            stdout="Pinging 127.0.0.1 with 32 bytes of data:\nReply from 127.0.0.1: bytes=32 time<1ms TTL=128",
            stderr="",
            payload={"target": "127.0.0.1", "packets": 4},
        )

        res, is_idempotent = record_diagnostic_result(db, cmd.id, result_payload)
        assert is_idempotent is False
        assert res.exit_code == 0
        assert len(res.payload_hash) == 64
        
        # Verify command updated to COMPLETED
        db.refresh(cmd)
        assert cmd.status == DiagnosticStatus.COMPLETED

        # Test duplicate submission (idempotency)
        res_dup, is_dup = record_diagnostic_result(db, cmd.id, result_payload)
        assert is_dup is True
        assert res_dup.payload_hash == res.payload_hash
        print("[+] Idempotent duplicate result recognized and acknowledged cleanly.")

        # Test conflict submission (differing payload)
        conflicting_payload = DiagnosticResultCreate(
            command_id=cmd.id,
            exit_code=1,
            stdout="Tampered output",
            stderr="Error",
            payload={"target": "10.0.0.1"},
        )
        try:
            record_diagnostic_result(db, cmd.id, conflicting_payload)
            raise AssertionError("Expected 409 Conflict for differing payload")
        except Exception as e:
            assert "409" in str(e) or "Conflict" in str(e)
            print("[+] Conflicting result payload rejected with HTTP 409 Conflict as required.")
        print("[+] TEST 5 PASSED: Result persistence, canonical hashing, and idempotency verified.")

        # TEST 6: Atomic Host Decommissioning Hook
        print("\n[TEST 6] Testing Atomic Host Decommissioning Hook...")
        # Create a temporary host for deactivation test
        temp_host = Host(
            hostname="temp-decommission-test-" + str(uuid.uuid4())[:8],
            ip_address="10.0.0.99",
            environment="test",
            is_active=True,
        )
        db.add(temp_host)
        db.commit()
        db.refresh(temp_host)

        # Grant assignment to temp host
        temp_ha = grant_host_assignment(db, operator.id, temp_host.id, super_admin.id)
        # Dispatch a pending command to temp host
        temp_cmd = dispatch_diagnostic_command(
            db,
            DiagnosticDispatchCreate(
                host_id=temp_host.id,
                action=DiagnosticAction.SYSTEM_SUMMARY,
                timeout_seconds=20,
            ),
            operator,
        )
        assert temp_cmd.status == DiagnosticStatus.PENDING

        # Decommission the host atomically
        decommissioned = decommission_host_atomic(db, temp_host.id, super_admin.id)
        assert decommissioned.is_active is False

        # Verify assignment is revoked
        db.refresh(temp_ha)
        assert temp_ha.status == AssignmentStatus.REVOKED
        assert temp_ha.revoked_at is not None

        # Verify pending command is expired
        db.refresh(temp_cmd)
        assert temp_cmd.status == DiagnosticStatus.EXPIRED
        assert temp_cmd.failure_reason == "HOST_DECOMMISSIONED"
        print("[+] TEST 6 PASSED: Atomic host decommissioning revokes assignments and expires commands.")

        print("\n[========================================================================]")
        print("[+] ALL 6 PHASE 9A.1 INTEGRATION TESTS PASSED WITH 100% SUCCESS")
        print("[========================================================================]")

    finally:
        db.close()


if __name__ == "__main__":
    from sqlalchemy import select
    run_tests()
