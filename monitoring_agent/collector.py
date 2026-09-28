"""
Telemetry Collector.

Uses psutil to sample system metrics (CPU, RAM, Disk, Network I/O deltas)
and system identifiers (hostname, local IP).
"""

import socket
import time
from typing import Dict, Any, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class SystemCollector:
    """
    Samples real hardware and OS resource utilization metrics.
    """

    def __init__(self):
        self._last_net_io = None
        self._last_net_time = None
        if PSUTIL_AVAILABLE:
            # Prime psutil cpu_percent calculation
            psutil.cpu_percent(interval=None)
            self._last_net_io = psutil.net_io_counters()
            self._last_net_time = time.time()

    def get_hostname(self) -> str:
        """Returns the system hostname."""
        return socket.gethostname()

    def get_ip_address(self) -> str:
        """Determines the primary outbound IP address."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Does not actually transmit packets, just determines routing
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def collect(self) -> Dict[str, Any]:
        """
        Samples CPU, memory, disk, and network I/O deltas.
        
        Returns:
            Dictionary containing metric values formatted for MetricCreate schema.
        """
        if not PSUTIL_AVAILABLE:
            raise RuntimeError(
                "psutil package is required for real hardware telemetry collection. "
                "Install psutil to collect live CPU, memory, disk, and network metrics."
            )

        # CPU Utilization %
        cpu = psutil.cpu_percent(interval=None)

        # Memory Utilization %
        mem = psutil.virtual_memory().percent

        # Disk Utilization % (root or system partition)
        try:
            disk = psutil.disk_usage("/").percent
        except Exception:
            try:
                disk = psutil.disk_usage("C:\\").percent
            except Exception:
                disk = 50.0

        # Network I/O MB delta calculation
        current_net = psutil.net_io_counters()
        current_time = time.time()
        sent_mb = 0.0
        recv_mb = 0.0

        if self._last_net_io and self._last_net_time:
            time_delta = max(current_time - self._last_net_time, 0.001)
            bytes_sent_delta = max(current_net.bytes_sent - self._last_net_io.bytes_sent, 0)
            bytes_recv_delta = max(current_net.bytes_recv - self._last_net_io.bytes_recv, 0)
            sent_mb = round(bytes_sent_delta / (1024 * 1024), 3)
            recv_mb = round(bytes_recv_delta / (1024 * 1024), 3)

        self._last_net_io = current_net
        self._last_net_time = current_time

        return {
            "hostname": self.get_hostname(),
            "ip_address": self.get_ip_address(),
            "cpu_percent": float(cpu),
            "memory_percent": float(mem),
            "disk_percent": float(disk),
            "network_sent_mb": float(sent_mb),
            "network_received_mb": float(recv_mb),
        }
