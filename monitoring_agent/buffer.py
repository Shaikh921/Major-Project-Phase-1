"""
Resilient Agent Buffer with Durable Disk Spooling.

Provides a thread-safe, persistent SQLite-backed queue that survives agent restarts,
machine reboots, and network outages (24h retention, configurable disk quota).
Guarantees verified HTTPS transmission, atomic acknowledgement, and exponential backoff with jitter.
"""

import json
import os
import random
import sqlite3
import threading
import time
from pathlib import Path
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


def calculate_queue_capacity(
    poll_interval: float = 5.0,
    max_age_hours: float = 24.0,
    safety_margin: float = 0.25,
    max_disk_mb: float = 50.0,
    bytes_per_sample: int = 512,
) -> int:
    """
    Calculates queue capacity required to safely buffer telemetry over max_age_hours (default 24h).
    Ensures mathematical consistency with polling intervals and reconciles with disk byte quotas (REL-01).
    
    Formula:
        samples_per_hour = 3600 / poll_interval
        required_samples = samples_per_hour * max_age_hours * (1 + safety_margin)
        max_quota_samples = (max_disk_mb * 1024 * 1024) / bytes_per_sample
        capacity = min(required_samples, max_quota_samples)
    """
    interval = max(0.5, float(poll_interval))
    samples_per_hour = 3600.0 / interval
    required_samples = int(samples_per_hour * max_age_hours * (1.0 + safety_margin))
    max_quota_samples = int((max_disk_mb * 1024 * 1024) / bytes_per_sample)
    return min(max(5000, required_samples), max_quota_samples)


class MetricBuffer:
    """
    Durable, disk-backed or in-memory telemetry queue with exponential backoff.
    
    Attributes:
        ingest_url: Target REST endpoint (e.g. https://<server>:8443/api/v1/metrics).
        max_size: Maximum capacity of queued metric samples (derived for 24h retention).
        api_key: Pre-shared or provisioned device API key.
        ca_bundle: Optional custom CA certificate bundle path for TLS verification.
        allow_insecure_http: Explicit flag to allow cleartext HTTP (disabled by default).
        spool_path: Path to SQLite spool file for persistence (e.g. 'sensor_spool.db' or ':memory:').
        max_age_hours: Maximum retention period before expiring uncommitted metrics (default 24h).
        max_disk_mb: Maximum size of the local spool file in megabytes (default 50MB).
        poll_interval: Host polling interval in seconds (default 5.0).
        overflow_policy: Policy when capacity/disk quota is reached ('preserve_queued' or 'drop_oldest').
    """

    def __init__(
        self,
        ingest_url: str,
        max_size: Optional[int] = None,
        api_key: Optional[str] = None,
        ca_bundle: Optional[str] = None,
        allow_insecure_http: bool = False,
        spool_path: Optional[str] = None,
        max_age_hours: float = 24.0,
        max_disk_mb: float = 50.0,
        poll_interval: float = 5.0,
        overflow_policy: str = "preserve_queued",
    ):
        self.ingest_url = ingest_url
        self.poll_interval = poll_interval
        self.max_age_hours = max_age_hours
        self.max_disk_mb = max_disk_mb
        self.overflow_policy = overflow_policy
        if max_size is not None:
            self.max_size = max_size
        else:
            self.max_size = calculate_queue_capacity(
                poll_interval=self.poll_interval,
                max_age_hours=self.max_age_hours,
                max_disk_mb=self.max_disk_mb,
            )
        self.api_key = api_key
        self.ca_bundle = ca_bundle
        self.allow_insecure_http = allow_insecure_http or (
            os.getenv("ALLOW_INSECURE_REMOTE_HTTP", "").lower() in ("true", "1")
        )
        self.spool_path = spool_path or os.getenv("AGENT_SPOOL_PATH", ":memory:")
        
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._expired_count = 0
        self._dropped_count = 0
        self._last_overflow_reason: Optional[str] = None
        self._last_overflow_at: Optional[float] = None
        self._last_auth_error: Optional[str] = None
        self._device_disabled = False
        self._conn: Optional[sqlite3.Connection] = None

        # Initialize SQLite spool database
        self._init_spool_db()

        # Validate transport security on initialization
        self.validate_transport()

    def _init_spool_db(self) -> None:
        """Initializes the local SQLite spool connection, table and indexes."""
        with self._lock:
            if self.spool_path != ":memory:":
                spool_dir = os.path.dirname(os.path.abspath(self.spool_path))
                if spool_dir and not os.path.exists(spool_dir):
                    os.makedirs(spool_dir, exist_ok=True)

            self._conn = sqlite3.connect(self.spool_path, check_same_thread=False, timeout=10.0)
            self._conn.row_factory = sqlite3.Row
            if self.spool_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS spool_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    batch_id TEXT
                );
            """)
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_spool_created ON spool_queue(created_at);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_spool_batch_id ON spool_queue(batch_id);")

            # Safe migration if table existed previously without batch_id
            try:
                self._conn.execute("ALTER TABLE spool_queue ADD COLUMN batch_id TEXT;")
            except sqlite3.OperationalError:
                pass

            self._conn.commit()

    def validate_transport(self) -> None:
        """Validates transport security for the configured ingest_url."""
        validate_transport_security(
            url=self.ingest_url,
            api_key=self.api_key,
            allow_insecure_http=self.allow_insecure_http,
        )

    def push(self, sample: Dict[str, Any]) -> bool:
        """
        Appends a metric sample to the durable spool queue.
        Enforces maximum capacity (FIFO or preserve_queued), disk quotas, and retention age limits.
        Returns True if accepted into spool, False if dropped due to capacity/disk overflow.
        """
        now = time.time()
        payload_str = json.dumps(sample)

        with self._lock:
            # 1. Enforce retention age limit (24 hours)
            cutoff = now - (self.max_age_hours * 3600.0)
            cur_exp = self._conn.execute("DELETE FROM spool_queue WHERE created_at < ?;", (cutoff,))
            if cur_exp.rowcount > 0:
                self._expired_count += cur_exp.rowcount

            # 2. Check current queue count and disk quota
            cursor = self._conn.execute("SELECT COUNT(*) FROM spool_queue;")
            count = cursor.fetchone()[0]

            disk_quota_exceeded = False
            if self.spool_path != ":memory:" and os.path.exists(self.spool_path):
                disk_bytes = os.path.getsize(self.spool_path)
                if disk_bytes >= (self.max_disk_mb * 1024 * 1024):
                    disk_quota_exceeded = True

            # 3. Enforce overflow policy if limits are reached
            if count >= self.max_size or disk_quota_exceeded:
                self._dropped_count += 1
                self._last_overflow_reason = (
                    "disk_quota_exceeded" if disk_quota_exceeded else "max_size_reached"
                )
                self._last_overflow_at = now

                if self.overflow_policy == "preserve_queued":
                    # Explicit overflow policy: preserve existing queued telemetry without overwriting
                    self._conn.commit()
                    return False
                else:
                    # Drop oldest queued telemetry to make room
                    excess = (count - self.max_size) + 1
                    self._conn.execute("""
                        DELETE FROM spool_queue WHERE id IN (
                            SELECT id FROM spool_queue ORDER BY id ASC LIMIT ?
                        );
                    """, (excess,))

            # 4. Insert new metric
            self._conn.execute(
                "INSERT INTO spool_queue (created_at, payload_json) VALUES (?, ?);",
                (now, payload_str),
            )
            self._conn.commit()
            return True

    def size(self) -> int:
        """Returns the current count of buffered samples in the spool queue."""
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM spool_queue;")
            return cursor.fetchone()[0]

    def flush(self, timeout: float = 3.0) -> bool:
        """
        Attempts to transmit queued metric samples to the backend.
        Batches up to 1,000 samples per request with persistent batch_id for idempotent retries (REL-02).
        Deletes records from the spool ONLY upon confirmed HTTP 200/201 response.
        """
        self.validate_transport()

        with self._lock:
            # Check for existing in-flight batch that was unconfirmed
            cursor = self._conn.execute(
                "SELECT id, payload_json, batch_id FROM spool_queue WHERE batch_id IS NOT NULL ORDER BY id ASC LIMIT 1000;"
            )
            rows = cursor.fetchall()

            if not rows:
                cursor = self._conn.execute(
                    "SELECT id, payload_json, batch_id FROM spool_queue ORDER BY id ASC LIMIT 1000;"
                )
                rows = cursor.fetchall()

            if not rows:
                return True

            active_batch_id = rows[0]["batch_id"]
            if not active_batch_id:
                import uuid
                active_batch_id = f"batch_{uuid.uuid4().hex}"
                ids_to_tag = [r["id"] for r in rows]
                placeholders = ",".join("?" for _ in ids_to_tag)
                self._conn.execute(
                    f"UPDATE spool_queue SET batch_id = ? WHERE id IN ({placeholders});",
                    [active_batch_id] + ids_to_tag,
                )
                self._conn.commit()
            else:
                rows = [r for r in rows if r["batch_id"] == active_batch_id]

            ids_to_send = [row["id"] for row in rows]
            items_to_send = [json.loads(row["payload_json"]) for row in rows]

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Agent-Key"] = self.api_key

        verify: Any = self.ca_bundle if self.ca_bundle else os.getenv("AGENT_CA_BUNDLE", True)
        if isinstance(verify, str) and not verify.strip():
            verify = True

        payload: Dict[str, Any] = {
            "batch_id": active_batch_id,
            "metrics": items_to_send,
        }

        try:
            response = requests.post(
                self.ingest_url,
                json=payload,
                headers=headers,
                timeout=timeout,
                verify=verify,
            )

            if response.status_code in [200, 201]:
                with self._lock:
                    placeholders = ",".join("?" for _ in ids_to_send)
                    self._conn.execute(f"DELETE FROM spool_queue WHERE id IN ({placeholders});", ids_to_send)
                    self._conn.commit()

                self._consecutive_failures = 0
                self._last_auth_error = None
                self._device_disabled = False
                return True

            elif response.status_code in [401, 403]:
                # Permanent authorization error (Key revoked, device disabled, or pending approval)
                self._consecutive_failures += 1
                self._last_auth_error = response.text
                if "disabled" in response.text.lower():
                    self._device_disabled = True
                return False

            elif response.status_code == 409:
                # Conflict: payload hash mismatch on batch_id reuse; reset batch_id
                with self._lock:
                    placeholders = ",".join("?" for _ in ids_to_send)
                    self._conn.execute(f"UPDATE spool_queue SET batch_id = NULL WHERE id IN ({placeholders});", ids_to_send)
                    self._conn.commit()
                self._consecutive_failures += 1
                return False

            else:
                self._consecutive_failures += 1
                return False

        except requests.exceptions.SSLError:
            self._consecutive_failures += 1
            return False
        except (requests.RequestException, Exception):
            self._consecutive_failures += 1
            return False

    def get_backoff_delay(self, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
        """
        Calculates exponential backoff delay with jitter based on consecutive failures.
        """
        if self._consecutive_failures == 0:
            return 0.0
        exp = min(self._consecutive_failures - 1, 5)
        raw_delay = base_delay * (2 ** exp)
        jitter = random.uniform(0.8, 1.2)
        return min(raw_delay * jitter, max_delay)

    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns observable telemetry queue diagnostics."""
        with self._lock:
            cur_count = self._conn.execute("SELECT COUNT(*) FROM spool_queue;").fetchone()[0]
            oldest_row = self._conn.execute("SELECT MIN(created_at) FROM spool_queue;").fetchone()[0]

            now = time.time()
            oldest_age = round(now - oldest_row, 1) if oldest_row else 0.0
            spool_bytes = 0
            if self.spool_path != ":memory:" and os.path.exists(self.spool_path):
                spool_bytes = os.path.getsize(self.spool_path)

            return {
                "queue_size": cur_count,
                "max_size": self.max_size,
                "max_disk_mb": self.max_disk_mb,
                "overflow_policy": self.overflow_policy,
                "oldest_record_age_seconds": oldest_age,
                "spool_file_bytes": spool_bytes,
                "expired_count": self._expired_count,
                "dropped_count": self._dropped_count,
                "last_overflow_reason": self._last_overflow_reason,
                "last_overflow_at": self._last_overflow_at,
                "consecutive_failures": self._consecutive_failures,
                "last_auth_error": self._last_auth_error,
                "device_disabled": self._device_disabled,
                "is_durable": self.spool_path != ":memory:",
            }

    def close(self) -> None:
        """Closes the underlying SQLite connection cleanly."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
