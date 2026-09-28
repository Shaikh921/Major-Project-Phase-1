"""
Monitoring Agent Daemon.

Continuously runs in the background on target hosts, polling system telemetry
at configurable intervals and pushing it to the backend ingestion API.
"""

import argparse
import os
import sys
import time
from typing import Optional

from monitoring_agent.collector import SystemCollector
from monitoring_agent.buffer import MetricBuffer


class MonitoringAgent:
    """
    Host monitoring agent coordinating collection, buffering, and HTTP dispatch.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:8000/api/v1/metrics",
        interval: int = 5,
        environment: str = "local",
        provider: str = "bare-metal",
        region: str = "local",
    ):
        self.collector = SystemCollector()
        self.buffer = MetricBuffer(ingest_url=server_url)
        self.interval = interval
        self.environment = environment
        self.provider = provider
        self.region = region
        self._running = False

    def start(self, max_cycles: Optional[int] = None) -> None:
        """
        Starts the polling loop.
        
        Args:
            max_cycles: Optional integer limit for cycle count (useful for tests/demos).
        """
        self._running = True
        cycle = 0

        print(f"[*] Starting Monitoring Agent -> Target: {self.buffer.ingest_url} | Polling: {self.interval}s")

        try:
            while self._running:
                # 1. Collect telemetry
                sample = self.collector.collect()
                sample["environment"] = self.environment
                sample["provider"] = self.provider
                sample["region"] = self.region
                sample["source_type"] = "REAL_AGENT"

                # 2. Push to local buffer
                self.buffer.push(sample)

                # 3. Attempt flush
                success = self.buffer.flush()
                if success:
                    print(
                        f"[+] [{sample['hostname']}] CPU: {sample['cpu_percent']:.1f}% | "
                        f"MEM: {sample['memory_percent']:.1f}% | DISK: {sample['disk_percent']:.1f}% -> Ingested"
                    )
                else:
                    backoff = self.buffer.get_backoff_delay()
                    print(
                        f"[!] Failed to reach ingestion server. Buffered: {self.buffer.size()} samples. "
                        f"Backoff delay: {backoff:.1f}s"
                    )
                    time.sleep(backoff)

                cycle += 1
                if max_cycles and cycle >= max_cycles:
                    break

                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n[*] Monitoring Agent stopped gracefully.")
            self._running = False

    def stop(self) -> None:
        """Stops the daemon."""
        self._running = False


def main():
    parser = argparse.ArgumentParser(description="Cloud Intelligence Telemetry Collection Agent")
    parser.add_argument("--url", default=os.getenv("INGEST_URL", "http://localhost:8000/api/v1/metrics"), help="Ingestion API endpoint")
    parser.add_argument("--interval", type=int, default=int(os.getenv("POLL_INTERVAL", "5")), help="Polling interval in seconds")
    parser.add_argument("--env", default=os.getenv("APP_ENV", "local"), help="Environment name")
    parser.add_argument("--provider", default=os.getenv("CLOUD_PROVIDER", "bare-metal"), help="Cloud provider")
    parser.add_argument("--region", default=os.getenv("CLOUD_REGION", "local"), help="Cloud region")

    args = parser.parse_args()

    agent = MonitoringAgent(
        server_url=args.url,
        interval=args.interval,
        environment=args.env,
        provider=args.provider,
        region=args.region,
    )
    agent.start()


if __name__ == "__main__":
    main()
