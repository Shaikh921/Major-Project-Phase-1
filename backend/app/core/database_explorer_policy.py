"""
Database Explorer Centralized Security Policy.
Enforces static table allowlists, security tiers, and column-level projection limits.
"""

from typing import Dict, List, Set, Optional

# --- Security Tier Classification ---
class TableSecurityTier:
    TIER_1_OPERATIONAL = "TIER_1_OPERATIONAL"   # Permitted operational preview with safe allowlists
    TIER_2_SANITIZED = "TIER_2_SANITIZED"       # Permitted preview with credential/secret columns strictly omitted
    TIER_3_ZERO_PREVIEW = "TIER_3_ZERO_PREVIEW" # Strict zero-preview (Schema metadata only; record access forbidden)


TABLE_SECURITY_TIERS: Dict[str, str] = {
    # Tier 1: Restricted Operational Preview (14 tables)
    "hosts": TableSecurityTier.TIER_1_OPERATIONAL,
    "alerts": TableSecurityTier.TIER_1_OPERATIONAL,
    "alert_rules": TableSecurityTier.TIER_1_OPERATIONAL,
    "alert_feedback": TableSecurityTier.TIER_1_OPERATIONAL,
    "audit_logs": TableSecurityTier.TIER_1_OPERATIONAL,
    "security_events": TableSecurityTier.TIER_1_OPERATIONAL,
    "diagnostic_commands": TableSecurityTier.TIER_1_OPERATIONAL,
    "diagnostic_results": TableSecurityTier.TIER_1_OPERATIONAL,
    "ingested_batches": TableSecurityTier.TIER_1_OPERATIONAL,
    "metrics": TableSecurityTier.TIER_1_OPERATIONAL,
    "cost_recommendations": TableSecurityTier.TIER_1_OPERATIONAL,
    "pricing_catalog": TableSecurityTier.TIER_1_OPERATIONAL,
    "user_host_assignments": TableSecurityTier.TIER_1_OPERATIONAL,
    "user_environment_assignments": TableSecurityTier.TIER_1_OPERATIONAL,

    # Tier 2: Sanitized Projections (3 tables)
    "users": TableSecurityTier.TIER_2_SANITIZED,
    "admin_registration_requests": TableSecurityTier.TIER_2_SANITIZED,
    "device_enrollments": TableSecurityTier.TIER_2_SANITIZED,

    # Tier 3: Zero Preview Credential & Session Stores (6 tables)
    "admin_activation_tokens": TableSecurityTier.TIER_3_ZERO_PREVIEW,
    "agent_api_keys": TableSecurityTier.TIER_3_ZERO_PREVIEW,
    "email_verification_tokens": TableSecurityTier.TIER_3_ZERO_PREVIEW,
    "enrollment_codes": TableSecurityTier.TIER_3_ZERO_PREVIEW,
    "password_reset_tokens": TableSecurityTier.TIER_3_ZERO_PREVIEW,
    "user_sessions": TableSecurityTier.TIER_3_ZERO_PREVIEW,
}


TABLE_CATEGORIES: Dict[str, str] = {
    "hosts": "Infrastructure & Fleet",
    "metrics": "Telemetry & Time-Series",
    "ingested_batches": "Telemetry & Ingestion",
    "pricing_catalog": "Cloud Cost & Pricing",
    "alerts": "Alerts & Detection",
    "alert_rules": "Alerts & Detection",
    "alert_feedback": "Alerts & Detection",
    "security_events": "Security & Incident Response",
    "diagnostic_commands": "Remote Operations & Diagnostics",
    "diagnostic_results": "Remote Operations & Diagnostics",
    "users": "Identity & Administration",
    "admin_registration_requests": "Identity & Administration",
    "user_host_assignments": "Hybrid RBAC Access Controls",
    "user_environment_assignments": "Hybrid RBAC Access Controls",
    "audit_logs": "Audit & Compliance",
    "cost_recommendations": "Cost Governance",
    "device_enrollments": "Device Enrollment & Lab PCs",
    "admin_activation_tokens": "Restricted Vault (Tokens)",
    "agent_api_keys": "Restricted Vault (API Keys)",
    "email_verification_tokens": "Restricted Vault (Tokens)",
    "enrollment_codes": "Restricted Vault (Enrollment Secrets)",
    "password_reset_tokens": "Restricted Vault (Tokens)",
    "user_sessions": "Restricted Vault (Active Sessions)",
}


# Explicit SQL Column Projection Allowlists
# Sensitive columns are strictly omitted so they never enter process memory.
TABLE_PROJECTION_ALLOWLISTS: Dict[str, List[str]] = {
    # Tier 1
    "hosts": [
        "id", "hostname", "ip_address", "environment", "instance_type",
        "provider", "region", "is_active", "created_at", "updated_at",
        "source_type", "owner_email"
        # EXCLUDED: tags (arbitrary unvalidated JSON structure)
    ],
    "alerts": [
        "id", "host_id", "rule_id", "metric", "kind", "severity",
        "message", "value", "threshold", "status", "created_at",
        "acknowledged_at", "resolved_at"
    ],
    "alert_rules": [
        "id", "name", "metric", "operator", "threshold", "severity",
        "duration_seconds", "is_enabled", "environment", "created_at", "updated_at"
    ],
    "alert_feedback": [
        "id", "alert_id", "verdict", "created_at"
        # EXCLUDED: operator_notes (arbitrary freeform text)
    ],
    "audit_logs": [
        "id", "user_email", "action", "target_resource", "result",
        "client_ip", "timestamp"
        # EXCLUDED: details (may contain nested parameter JSON or token traces)
    ],
    "cost_recommendations": [
        "id", "host_id", "recommendation_type", "current_instance_type",
        "suggested_instance_type", "current_monthly_spend_usd",
        "estimated_monthly_spend_usd", "estimated_monthly_savings_usd",
        "rationale", "status", "confidence_score", "created_at", "updated_at"
    ],
    "pricing_catalog": [
        "id", "provider", "region", "instance_type", "vcpus", "memory_gb",
        "hourly_rate_usd", "currency"
    ],
    "diagnostic_commands": [
        "id", "host_id", "action", "target", "timeout_seconds", "status",
        "requested_by_user_id", "claimed_at", "claimed_by_agent_id",
        "lease_expires_at", "hard_deadline_at", "completed_at", "failure_reason",
        "created_at", "updated_at"
    ],
    "diagnostic_results": [
        "id", "command_id", "exit_code", "payload_hash", "failure_reason",
        "is_late", "received_at", "created_at"
        # EXCLUDED: stdout, stderr (may contain sensitive environment output)
    ],
    "ingested_batches": [
        "id", "batch_id", "host_id", "payload_hash", "processed_samples",
        "generated_alerts", "created_at"
    ],
    "metrics": [
        "id", "host_id", "timestamp", "cpu_percent", "memory_percent",
        "disk_percent", "network_sent_mb", "network_received_mb"
    ],
    "security_events": [
        "id", "host_id", "event_type", "severity", "source_ip",
        "destination_port", "description", "status", "timestamp", "resolved_at"
    ],
    "user_host_assignments": [
        "id", "user_id", "host_id", "status", "granted_by_id",
        "revoked_by_id", "created_at", "revoked_at", "updated_at"
    ],
    "user_environment_assignments": [
        "id", "user_id", "environment", "status", "granted_by_id",
        "revoked_by_id", "created_at", "revoked_at", "updated_at"
    ],

    # Tier 2: Sanitized Projections
    "users": [
        "id", "email", "role", "is_active", "is_verified", "created_at", "updated_at"
        # EXCLUDED: password_hash
    ],
    "admin_registration_requests": [
        "id", "full_name", "email", "organization", "reason", "status",
        "email_verified", "requested_at", "verified_at", "reviewed_at",
        "reviewed_by_id", "rejection_reason", "created_user_id"
        # EXCLUDED: verification_token_hash, verification_expires_at
    ],
    "device_enrollments": [
        "id", "device_uuid", "reported_hostname", "assigned_name", "lab_name",
        "room_number", "pc_number", "ip_address", "mac_address", "os_version",
        "agent_version", "status", "host_id", "requested_at", "reviewed_at",
        "reviewed_by_user_id", "last_contact_at", "last_collection_at",
        "last_upload_at", "telemetry_health", "queue_backlog",
        "retirement_requested", "retirement_confirmed"
        # EXCLUDED: pending_raw_key, claim_token_hash, claim_token_expires_at,
        # credential_claimed, agent_key_id, enrollment_code_id, rejection_reason
    ],

    # Tier 3: Zero Preview (Empty list - records never queried)
    "admin_activation_tokens": [],
    "agent_api_keys": [],
    "email_verification_tokens": [],
    "enrollment_codes": [],
    "password_reset_tokens": [],
    "user_sessions": [],
}


# Text field clamping limits to prevent UI buffer abuse
FIELD_LENGTH_LIMITS: Dict[str, Dict[str, int]] = {
    "cost_recommendations": {"rationale": 256},
    "admin_registration_requests": {"reason": 150, "rejection_reason": 150},
    "alerts": {"message": 200},
}


# Tables verified for integer keyset pagination
KEYSET_PAGINATION_TABLES: Set[str] = {"metrics", "ingested_batches"}

# Tables strictly restricted to offset pagination (e.g. UUID PK or small metadata)
OFFSET_ONLY_TABLES: Set[str] = {
    "diagnostic_commands",  # UUID primary key
    "hosts", "alerts", "alert_rules", "alert_feedback", "audit_logs",
    "cost_recommendations", "pricing_catalog", "diagnostic_results",
    "security_events", "user_host_assignments", "user_environment_assignments",
    "users", "admin_registration_requests", "device_enrollments",
}
