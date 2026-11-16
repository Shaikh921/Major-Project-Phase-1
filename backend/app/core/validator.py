"""
Target Validator for Predefined Remote Diagnostics (Phase 9A.1).

Enforces strict RFC 1123 hostname formatting rules, IPv4/IPv6 syntax,
and CLI parameter injection defenses.
"""

import re
import json
import ipaddress
from typing import Optional

RFC_1123_HOSTNAME_REGEX = re.compile(
    r'^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*$'
)

SAFE_REASON_REGEX = re.compile(r'^[a-zA-Z0-9_\-\.\,\s\:\(\)\[\]]{1,128}$')


def validate_diagnostic_target(target: str) -> str:
    """
    Validates a network target (hostname or IP) against strict RFC 1123 rules.
    Raises ValueError with descriptive reason if invalid.
    """
    if target is None:
        return ""

    cleaned = target.strip()
    if not cleaned:
        return ""

    if len(cleaned) > 253:
        raise ValueError("Target length exceeds maximum of 253 characters.")

    # 1. Allow valid IPv4 or IPv6 addresses
    try:
        ipaddress.ip_address(cleaned)
        return cleaned
    except ValueError:
        pass

    # 2. Reject CLI parameter injection characters
    if cleaned.startswith("-") or cleaned.startswith("/"):
        raise ValueError("Target cannot start with CLI parameter flags ('-' or '/').")

    # 3. Reject forbidden shell metacharacters
    forbidden_chars = set(';&|><$`"\' \t\r\n\\')
    if any(c in forbidden_chars for c in cleaned):
        raise ValueError("Target contains illegal shell or whitespace characters.")

    # 4. Enforce RFC 1123 hostname regex
    if not RFC_1123_HOSTNAME_REGEX.match(cleaned):
        raise ValueError("Target violates RFC 1123 hostname formatting specifications.")

    # 5. Top-level domain (rightmost label) cannot be all-numeric (RFC 1123 §2.1 & RFC 3696 §2)
    labels = cleaned.split(".")
    if len(labels) > 1 and labels[-1].isdigit():
        raise ValueError("Top-level domain cannot be purely numeric in DNS hostnames.")

    return cleaned


def validate_power_action_target(action: str, target: Optional[str]) -> str:
    """
    Validates parameter inputs for privileged remote power actions (REBOOT_HOST, SHUTDOWN_HOST, ABORT_SHUTDOWN).
    Enforces strict typing on grace_seconds and sanitizes reasons against CLI command injection.
    Returns a canonical JSON string.
    """
    from backend.app.core.config import settings

    default_grace = getattr(settings, "power_operation_default_grace_seconds", 60)
    min_grace = getattr(settings, "power_operation_min_grace_seconds", 10)

    if action == "ABORT_SHUTDOWN":
        reason = "Administrative emergency cancellation"
        if target:
            t = target.strip()
            if t:
                try:
                    data = json.loads(t)
                    if isinstance(data, dict) and "reason" in data:
                        t = str(data["reason"]).strip()
                except Exception:
                    pass
                if not SAFE_REASON_REGEX.match(t):
                    raise ValueError("Abort reason contains forbidden characters. Only alphanumeric, spaces, and basic punctuation are allowed.")
                reason = t[:128]
        return json.dumps({"reason": reason}, ensure_ascii=False)

    grace_seconds = default_grace
    reason = "Administrative power operation"

    if target:
        t = target.strip()
        if t:
            parsed = False
            try:
                data = json.loads(t)
                if isinstance(data, dict):
                    if "grace_seconds" in data:
                        grace_seconds = int(data["grace_seconds"])
                    if "reason" in data and str(data["reason"]).strip():
                        reason = str(data["reason"]).strip()
                    parsed = True
            except Exception:
                pass

            if not parsed:
                # Immediate rejection of forbidden shell and command injection characters in plaintext
                forbidden_chars = set(';&|><$`"\'\r\n\\')
                if any(c in forbidden_chars for c in t):
                    raise ValueError("Power operation parameter contains illegal shell or injection characters.")

                if ":" in t:
                    parts = t.split(":", 1)
                    if not parts[0].strip().isdigit():
                        raise ValueError("Invalid parameter format. Expected integer seconds or 'seconds:reason'.")
                    grace_seconds = int(parts[0].strip())
                    if parts[1].strip():
                        reason = parts[1].strip()
                elif t.isdigit():
                    grace_seconds = int(t)
                else:
                    reason = t

    if grace_seconds < 0 or grace_seconds > 3600:
        raise ValueError("Grace period seconds must be between 0 and 3600.")
    if grace_seconds < min_grace and grace_seconds != 0:
        raise ValueError(f"Grace period seconds must be at least {min_grace} seconds (or 0 for immediate).")

    if not SAFE_REASON_REGEX.match(reason):
        raise ValueError("Power operation reason contains forbidden characters. Only alphanumeric characters, spaces, and basic punctuation are allowed.")

    return json.dumps({"grace_seconds": grace_seconds, "reason": reason[:128]}, ensure_ascii=False)

