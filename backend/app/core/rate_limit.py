"""
In-Memory Rate Limiting Infrastructure for Authentication Endpoints.

Provides sliding-window rate limiting per client IP to protect against
brute-force attacks, credential stuffing, and email spamming.

NOTE: This in-memory implementation is designed for single-instance / development
deployments. In distributed production clusters with multiple replicas,
a shared Redis-backed limiter should be utilized.
"""

import time
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException, status


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter per client IP key.
    """

    def __init__(self):
        # key -> list of timestamp floats
        self._history: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, int]:
        """
        Records an attempt for the given key and checks if the rate limit is exceeded.
        Returns (is_allowed, retry_after_seconds).
        """
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
        if key in self._history:
            del self._history[key]


# Global rate limiter instance
auth_rate_limiter = SlidingWindowRateLimiter()


def rate_limit_ip(
    request: Request,
    endpoint_name: str,
    max_requests: int = 5,
    window_seconds: int = 60,
) -> None:
    """
    FastAPI helper function to enforce IP-based rate limiting.
    Raises HTTPException 429 if limit is exceeded.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
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
