"""
Resilient Agent Buffer.

Thread-safe local ring buffer designed to store metrics during network partitions
and retry transmission with exponential backoff once connectivity is restored (M1 NFR).
"""

import collections
import threading
import time
from typing import List, Dict, Any, Optional
import requests


class MetricBuffer:
    """
    In-memory ring buffer holding metric samples when the backend ingestion API is unreachable.
    
    Attributes:
        max_size: Maximum capacity of unsent metric records.
        ingest_url: Target REST endpoint (e.g. http://localhost:8000/api/v1/metrics).
    """

    def __init__(self, ingest_url: str, max_size: int = 5000):
        self.ingest_url = ingest_url
        self.max_size = max_size
        self._buffer = collections.deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._consecutive_failures = 0

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
        Attempts to transmit all queued metric samples to the backend.
        Uses batch ingestion if multiple samples are queued.
        
        Returns:
            True if transmission was successful, False if network/HTTP error occurred.
        """
        with self._lock:
            if not self._buffer:
                return True
            # Extract current backlog
            items_to_send = list(self._buffer)

        try:
            if len(items_to_send) == 1:
                response = requests.post(self.ingest_url, json=items_to_send[0], timeout=timeout)
            else:
                response = requests.post(
                    self.ingest_url,
                    json={"metrics": items_to_send},
                    timeout=timeout,
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
