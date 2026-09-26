"""
Cloud-based Intrusion Detection and Security Analysis Engine (Module 4).

Performs signature-based pattern detection and behavioral anomaly correlation
on authentication streams, network egress flows, and system configurations.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


class SecurityDetector:
    """
    Security analyzer evaluating infrastructure telemetry and security events.
    """

    KNOWN_ATTACK_SIGNATURES = {
        "ssh_brute_force": {
            "threshold_failures": 5,
            "severity": "high",
            "description": "Repeated failed SSH authentications detected within 60s window.",
        },
        "port_scan": {
            "threshold_ports": 15,
            "severity": "medium",
            "description": "Sequential rapid port probing detected across closed endpoints.",
        },
        "suspicious_egress": {
            "egress_spike_mb": 150.0,
            "severity": "critical",
            "description": "Anomalous outbound bandwidth spike indicative of potential data exfiltration.",
        },
        "unauthorized_sudo": {
            "severity": "high",
            "description": "Privilege escalation attempt by unauthorized service account.",
        },
    }

    def analyze_network_sample(
        self,
        hostname: str,
        network_sent_mb: float,
        network_received_mb: float,
        source_ip: Optional[str] = None,
        destination_port: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates network traffic for exfiltration or DoS signatures.
        Dynamically receives source_ip and destination_port from ingested telemetry.
        """
        if network_sent_mb >= self.KNOWN_ATTACK_SIGNATURES["suspicious_egress"]["egress_spike_mb"]:
            return {
                "event_type": "suspicious_egress",
                "severity": "critical",
                "description": f"Abnormal outbound egress of {network_sent_mb:.1f} MB on host {hostname}.",
                "raw_evidence": f"network_sent_mb={network_sent_mb:.2f}, baseline_expected=<20.0MB",
                "source_ip": source_ip if source_ip else "unknown",
                "destination_port": destination_port if destination_port is not None else 443,
            }
        return None

    def analyze_auth_event(
        self,
        hostname: str,
        failed_attempts: int,
        source_ip: Optional[str] = None,
        username: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates authentication failures for brute-force attacks.
        """
        threshold = self.KNOWN_ATTACK_SIGNATURES["ssh_brute_force"]["threshold_failures"]
        if failed_attempts >= threshold:
            resolved_ip = source_ip or "unknown"
            return {
                "event_type": "ssh_brute_force",
                "severity": self.KNOWN_ATTACK_SIGNATURES["ssh_brute_force"]["severity"],
                "description": f"Repeated failed SSH logins ({failed_attempts} attempts) on {hostname} from {resolved_ip}.",
                "raw_evidence": f"failed_attempts={failed_attempts}, threshold={threshold}, user={username or 'unknown'}",
                "source_ip": resolved_ip,
                "destination_port": 22,
            }
        return None
