"""
Acceptance Test Suite for Agent Transport Security & Reverse Proxy (Phase 8B).

Verifies:
1. Cleartext HTTP to remote targets is strictly rejected before credentials are transmitted.
2. HTTPS is required and used for remote agent targets.
3. Local loopback targets (localhost, 127.0.0.1) are permitted for local development.
4. TLS certificate validation failures fail closed and never fall back to plain HTTP.
5. Caddyfile reverse proxy configuration is structured correctly.
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import requests

from monitoring_agent.buffer import (
    MetricBuffer,
    InsecureTransportError,
    validate_transport_security,
    is_loopback_target,
)


def test_remote_http_agent_target_rejected_before_credentials_sent():
    """
    CRITICAL: Verifies that attempts to send agent telemetry over cleartext HTTP
    to a remote target raise InsecureTransportError before any network connection is made.
    """
    remote_http_url = "http://192.168.1.150:8000/api/v1/metrics"
    api_key = "secret-agent-key-should-never-be-leaked"

    # Initialization rejects remote plain HTTP
    with pytest.raises(InsecureTransportError) as exc_info:
        MetricBuffer(ingest_url=remote_http_url, api_key=api_key)

    assert "Cleartext HTTP transmission of agent credentials to remote target" in str(exc_info.value)
    # Ensure raw secret is NOT leaked in the exception message
    assert api_key not in str(exc_info.value)


def test_remote_http_without_key_rejected_by_default():
    """Verifies that remote cleartext HTTP is rejected even without an API key by default."""
    remote_http_url = "http://monitoring.ops.lan:8000/api/v1/metrics"

    with pytest.raises(InsecureTransportError) as exc_info:
        MetricBuffer(ingest_url=remote_http_url)

    assert "Remote telemetry target 'monitoring.ops.lan' must use HTTPS" in str(exc_info.value)


def test_loopback_http_permitted_for_local_development():
    """
    Verifies that loopback HTTP (localhost and 127.0.0.1) is permitted
    to preserve legitimate local development workflows.
    """
    # 127.0.0.1
    buf1 = MetricBuffer(ingest_url="http://127.0.0.1:8000/api/v1/metrics", api_key="dev-key")
    assert buf1.ingest_url == "http://127.0.0.1:8000/api/v1/metrics"

    # localhost
    buf2 = MetricBuffer(ingest_url="http://localhost:8000/api/v1/metrics", api_key="dev-key")
    assert buf2.ingest_url == "http://localhost:8000/api/v1/metrics"


@patch("requests.post")
def test_remote_https_target_permitted_and_transmits_credentials(mock_post):
    """Verifies that remote HTTPS targets are permitted and dispatch credentials securely."""
    mock_post.return_value = MagicMock(status_code=201)

    remote_https_url = "https://collector.cloudops.internal:8443/api/v1/metrics"
    api_key = "secure-production-agent-key-12345"

    buffer = MetricBuffer(ingest_url=remote_https_url, api_key=api_key)
    buffer.push({"hostname": "lab-pc-01", "cpu_percent": 45.0})
    success = buffer.flush()

    assert success is True
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == remote_https_url
    assert kwargs["headers"]["X-Agent-Key"] == api_key
    # Verify certificate validation was enabled by default
    assert kwargs.get("verify") is True or isinstance(kwargs.get("verify"), str)


@patch("requests.post")
def test_tls_certificate_error_fails_closed_no_http_fallback(mock_post):
    """
    CRITICAL: Verifies that an invalid, expired, or untrusted TLS certificate causes
    the request to fail closed (returning False) and strictly NEVER falls back to plain HTTP.
    """
    mock_post.side_effect = requests.exceptions.SSLError("Certificate verification failed: self signed certificate in certificate chain")

    remote_https_url = "https://untrusted-ca-collector:8443/api/v1/metrics"
    buffer = MetricBuffer(ingest_url=remote_https_url, api_key="test-key-tls")
    buffer.push({"hostname": "lab-pc-02", "cpu_percent": 50.0})

    # Flush should return False (failed closed)
    success = buffer.flush()
    assert success is False

    # Backlog must remain intact for retry once CA is trusted
    assert buffer.size() == 1
    assert buffer.get_backoff_delay() > 0.0

    # Ensure only ONE call was made (no second call falling back to plain HTTP)
    assert mock_post.call_count == 1
    called_url = mock_post.call_args[0][0]
    assert called_url.startswith("https://"), "Security violation: Agent attempted insecure fallback!"


def test_custom_ca_bundle_passed_to_requests():
    """Verifies that custom CA certificate bundle is passed to requests.post for internal CAs."""
    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=201)
        custom_bundle = "C:/path/to/caddy/root.crt"

        buffer = MetricBuffer(
            ingest_url="https://caddy-proxy:8443/api/v1/metrics",
            api_key="key-ca",
            ca_bundle=custom_bundle,
        )
        buffer.push({"hostname": "lab-pc-03", "cpu_percent": 25.0})
        buffer.flush()

        _, kwargs = mock_post.call_args
        assert kwargs.get("verify") == custom_bundle


def test_caddyfile_configuration_syntax_and_structure():
    """Verifies that Caddyfile exists and enforces internal TLS and secure reverse proxy."""
    caddyfile_path = Path("Caddyfile")
    assert caddyfile_path.exists(), "Caddyfile must exist in repository root."

    content = caddyfile_path.read_text(encoding="utf-8")
    assert "tls internal" in content, "Caddyfile must configure internal TLS."
    assert "reverse_proxy 127.0.0.1:8000" in content, "Caddyfile must reverse proxy to backend loopback."
    assert "Strict-Transport-Security" in content, "Caddyfile must inject HSTS headers."
    assert "admin off" in content, "Caddyfile must disable remote administrative interface."
