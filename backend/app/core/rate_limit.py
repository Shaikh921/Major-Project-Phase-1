"""
In-Memory Rate Limiting Infrastructure for Authentication Endpoints (AUD-02, AUD-04).

Provides thread-safe sliding-window rate limiting per client IP to protect against
brute-force attacks, credential stuffing, and public endpoint flooding.

Trusted Reverse Proxy Identity Contract (AUD-02):
- Forwarded client-IP information (X-Real-IP, X-Forwarded-For) is trusted ONLY when
  the immediate connection peer is an explicitly verified reverse proxy (e.g. Caddy on 127.0.0.1).
- Direct connections from untrusted peers strictly ignore client-supplied forwarding headers,
  preventing header spoofing attacks.

Concurrency & Deployment Model (AUD-04):
- Thread-safe for multi-threaded asyncio / Starlette threadpools within a single process.
- Synchronized via threading.Lock() ensuring check-and-record state transitions are atomic.
- Deployment constraint: Bounded to single-process deployments (uvicorn without multi-worker clustering).
  In multi-process or clustered environments, a centralized store (e.g., Redis) is required.
"""

import ipaddress
import threading
import time
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional
from fastapi import Request, HTTPException, status


# Explicit trusted reverse proxy peers permitted to forward client identities
TRUSTED_PROXIES: Set[str] = {
    "127.0.0.1",
    "::1",
    "localhost",
    "testclient",
}


def get_client_ip(
    request: Request,
    trusted_proxies: Optional[Set[str]] = None,
) -> str:
    """
    Safely resolves the client IP address considering reverse proxy topologies (AUD-02).

    Security Contract:
    1. If immediate peer (request.client.host) is NOT in trusted_proxies:
       - The request arrived directly or from an untrusted peer.
       - NEVER inspect X-Real-IP, X-Forwarded-For, or client headers (prevents header spoofing).
       - Return request.client.host directly.
    2. If immediate peer IS in trusted_proxies:
       - The request arrived via a verified reverse proxy (e.g. Caddy on 127.0.0.1).
       - Caddy actively sets 'header_up X-Real-IP {remote_host}'.
       - Inspect 'X-Real-IP'. Validate that it is a syntactically valid IPv4 or IPv6 address.
       - If valid, return the validated forwarded IP.
       - If missing, invalid, or malformed, fall back safely to the trusted proxy's host.
    """
    if not request.client or not request.client.host:
        return "127.0.0.1"

    peer_host = request.client.host.strip()
    active_trusted = trusted_proxies if trusted_proxies is not None else TRUSTED_PROXIES

    if peer_host not in active_trusted:
        # Untrusted direct client -> strictly ignore forwarded headers
        return peer_host

    # Immediate peer is trusted proxy: check X-Real-IP
    forwarded_ip = request.headers.get("x-real-ip")
    if not forwarded_ip:
        # Check first hop of X-Forwarded-For if X-Real-IP is absent
        xff = request.headers.get("x-forwarded-for")
        if xff:
            forwarded_ip = xff.split(",")[0].strip()

    if forwarded_ip:
        forwarded_ip_clean = forwarded_ip.strip()
        try:
            # Validate IP address format (handles both IPv4 and IPv6)
            parsed_ip = ipaddress.ip_address(forwarded_ip_clean)
            return str(parsed_ip)
        except ValueError:
            # Malformed address -> fallback safely to peer_host
            pass

    return peer_host


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter per client IP key (AUD-04).
    """

    def __init__(self):
        # key -> list of timestamp floats
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, int]:
        """
        Atomically records an attempt for the given key and checks if the rate limit is exceeded.
        Returns (is_allowed, retry_after_seconds).
        """
        with self._lock:
            now = time.time()
            cutoff = now - window_seconds
            timestamps = self._history[key]

            # Purge timestamps outside sliding window
            valid_timestamps = [ts for ts in timestamps if ts > cutoff]
            self._history[key] = valid_timestamps

            if len(valid_timestamps) >= max_requests:
                oldest = valid_timestamps[0]
                retry_after = max(1, int(oldest + window_seconds - now))
                return False, retry_after

            # Record this request
            self._history[key].append(now)
            return True, 0

    def reset_for_key(self, key: str) -> None:
        """Clears request history for a specific key upon successful action."""
        with self._lock:
            if key in self._history:
                del self._history[key]


# Global rate limiter instance
auth_rate_limiter = SlidingWindowRateLimiter()


def rate_limit_ip(
    request: Request,
    endpoint_name: str,
    max_requests: int = 5,
    window_seconds: int = 60,
    trusted_proxies: Optional[Set[str]] = None,
) -> None:
    """
    FastAPI helper function to enforce IP-based rate limiting (AUD-02, AUD-04).
    Raises HTTPException 429 if limit is exceeded.
    """
    client_ip = get_client_ip(request, trusted_proxies=trusted_proxies)
    key = f"{endpoint_name}:{client_ip}"
    allowed, retry_after = auth_rate_limiter.check_rate_limit(
        key=key,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

