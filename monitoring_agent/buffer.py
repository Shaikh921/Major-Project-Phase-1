"""
Resilient Agent Buffer.

Thread-safe local ring buffer designed to store metrics during network partitions
and retry transmission with exponential backoff once connectivity is restored (M1 NFR).
"""

import collections
import os
import threading
import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import requests


class InsecureTransportError(ValueError):
    """Raised when an agent attempts to transmit credentials or telemetry over insecure cleartext HTTP to a remote host."""
    pass


LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "testserver"}


def is_loopback_target(url: str) -> bool:
    """Checks whether the target URL points to a local loopback interface."""
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        return hostname in LOOPBACK_HOSTS
    except Exception:
        return False


def validate_transport_security(url: str, api_key: Optional[str] = None, allow_insecure_http: bool = False) -> None:
    """
    Enforces transport security:
    - Remote (non-loopback) targets must use HTTPS.
    - Cleartext HTTP is rejected before credentials or telemetry are dispatched.
    - Loopback targets (127.0.0.1, localhost) are permitted for local development.
    """
    if not url:
        raise ValueError("ingest_url must not be empty.")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").lower()

    if scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{scheme}'. Target URL must use HTTP or HTTPS.")

    if scheme == "http":
        if not is_loopback_target(url) and not allow_insecure_http:
            if api_key:
                raise InsecureTransportError(
                    f"Insecure transport rejected: Cleartext HTTP transmission of agent credentials "
                    f"to remote target '{hostname}' is forbidden. Target must use HTTPS."
                )
            else:
                raise InsecureTransportError(
                    f"Insecure transport rejected: Remote telemetry target '{hostname}' must use HTTPS."
                )


class MetricBuffer:
    """
    In-memory ring buffer holding metric samples when the backend ingestion API is unreachable.
    
    Attributes:
        max_size: Maximum capacity of unsent metric records.
        ingest_url: Target REST endpoint (e.g. https://localhost:8443/api/v1/metrics).
        api_key: Pre-shared authentication key.
        ca_bundle: Optional custom CA certificate bundle path for TLS verification.
        allow_insecure_http: Explicit flag to allow cleartext HTTP (disabled by default).
    """

    def __init__(
        self,
        ingest_url: str,
        max_size: int = 5000,
        api_key: Optional[str] = None,
        ca_bundle: Optional[str] = None,
        allow_insecure_http: bool = False,
    ):
        self.ingest_url = ingest_url
        self.max_size = max_size
        self.api_key = api_key
        self.ca_bundle = ca_bundle
        self.allow_insecure_http = allow_insecure_http or (
            os.getenv("ALLOW_INSECURE_REMOTE_HTTP", "").lower() in ("true", "1")
        )
        self._buffer = collections.deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._consecutive_failures = 0

        # Validate transport security on initialization
        self.validate_transport()

    def validate_transport(self) -> None:
        """Validates transport security for the configured ingest_url."""
        validate_transport_security(
            url=self.ingest_url,
            api_key=self.api_key,
            allow_insecure_http=self.allow_insecure_http,
        )

    def push(self, sample: Dict[str, Any]) -> None:
        """
        Appends a metric sample to the ring buffer.
        If buffer is full, the oldest uncommitted sample is discarded.
        """
        with self._lock:
            self._buffer.append(sample)

    def size(self) -> int:
        """Returns the current count of buffered samples."""
        with self._lock:
            return len(self._buffer)

    def flush(self, timeout: float = 3.0) -> bool:
        """
        Attempts to transmit queued metric samples to the backend.
        Sends up to 1,000 samples per request to conform to backend batch limits.
        
        Returns:
            True if transmission was successful, False if network/HTTP error occurred.
        """
        # Validate transport security before attempting transmission
        self.validate_transport()

        with self._lock:
            if not self._buffer:
                return True
            # Extract up to 1,000 items from backlog to respect batch ingestion limit
            items_to_send = list(self._buffer)[:1000]

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Agent-Key"] = self.api_key

        # Configure certificate verification: custom bundle, env var, or system CA default (True)
        verify: Any = self.ca_bundle if self.ca_bundle else os.getenv("AGENT_CA_BUNDLE", True)
        if isinstance(verify, str) and not verify.strip():
            verify = True

        try:
            if len(items_to_send) == 1:
                response = requests.post(
                    self.ingest_url,
                    json=items_to_send[0],
                    headers=headers,
                    timeout=timeout,
                    verify=verify,
                )
            else:
                response = requests.post(
                    self.ingest_url,
                    json={"metrics": items_to_send},
                    headers=headers,
                    timeout=timeout,
                    verify=verify,
                )

            if response.status_code in [200, 201]:
                with self._lock:
                    # Remove successfully transmitted items
                    for _ in range(len(items_to_send)):
                        if self._buffer:
                            self._buffer.popleft()
                self._consecutive_failures = 0
                return True
            else:
                self._consecutive_failures += 1
                return False

        except requests.exceptions.SSLError:
            # TLS certificate failure: untrusted CA, invalid cert, hostname mismatch
            # Fail closed immediately; strictly NEVER fallback to cleartext HTTP
            self._consecutive_failures += 1
            return False
        except (requests.RequestException, Exception):
            self._consecutive_failures += 1
            return False

    def get_backoff_delay(self, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
        """
        Calculates exponential backoff delay based on consecutive network failures.
        """
        if self._consecutive_failures == 0:
            return 0.0
        delay = base_delay * (2 ** min(self._consecutive_failures - 1, 5))
        return min(delay, max_delay)

