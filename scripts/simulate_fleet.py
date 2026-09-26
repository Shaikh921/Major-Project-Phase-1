"""
Fleet Telemetry & Incident Simulator.

Generates realistic telemetry across multiple simulated cloud virtual machines,
simulating normal operations, CPU starvation spikes, memory leak patterns,
and disk exhaustion to test dashboard rendering and alert deduplication engines.
"""

import argparse
import random
import time
from datetime import datetime, timezone
import requests

DEFAULT_FLEET = [
    {
        "hostname": "prod-web-01",
        "ip_address": "10.0.1.10",
        "environment": "production",
        "provider": "aws",
        "region": "us-east-1",
        "profile": "normal",
    },
    {
        "hostname": "prod-web-02",
        "ip_address": "10.0.1.11",
        "environment": "production",
        "provider": "aws",
        "region": "us-east-1",
        "profile": "cpu_spike",  # Simulates high load / spike
    },
    {
        "hostname": "prod-db-primary",
        "ip_address": "10.0.2.20",
        "environment": "production",
        "provider": "aws",
        "region": "us-east-1",
        "profile": "memory_leak",  # Simulates progressive memory leak
    },
    {
        "hostname": "staging-api-01",
        "ip_address": "10.1.1.15",
        "environment": "staging",
        "provider": "gcp",
        "region": "us-central1",
        "profile": "normal",
    },
    {
        "hostname": "dev-sandbox-01",
        "ip_address": "192.168.1.50",
        "environment": "development",
        "provider": "bare-metal",
        "region": "local",
        "profile": "disk_exhaustion",  # Simulates high disk usage
    },
]


class FleetSimulator:
    """
    Simulates a multi-node infrastructure fleet.
    """

    def __init__(self, target_url: str = "http://localhost:8000/api/v1/metrics", fleet=None):
        self.target_url = target_url
        self.fleet = fleet or DEFAULT_FLEET
        self.states = {
            h["hostname"]: {
                "step": 0,
                "mem_base": random.uniform(40.0, 55.0),
                "disk_base": random.uniform(50.0, 65.0),
            }
            for h in self.fleet
        }

    def generate_sample(self, host_cfg: dict) -> dict:
        """Generates a synthetic metric sample tailored to host behavior profile."""
        hostname = host_cfg["hostname"]
        profile = host_cfg["profile"]
        state = self.states[hostname]
        state["step"] += 1
        step = state["step"]

        cpu = 25.0
        mem = state["mem_base"]
        disk = state["disk_base"]
        net_sent = random.uniform(0.1, 1.5)
        net_recv = random.uniform(0.5, 3.0)

        if profile == "normal":
            cpu = random.uniform(15.0, 45.0)
            mem = min(100.0, state["mem_base"] + random.uniform(-2.0, 2.0))
            disk = min(100.0, state["disk_base"] + 0.01 * step)

        elif profile == "cpu_spike":
            # Oscillates between normal and intense 95%+ CPU spikes
            if step % 6 in [3, 4, 5]:
                cpu = random.uniform(92.0, 98.5)
            else:
                cpu = random.uniform(20.0, 40.0)
            mem = min(100.0, state["mem_base"] + random.uniform(5.0, 15.0))

        elif profile == "memory_leak":
            cpu = random.uniform(25.0, 50.0)
            # Memory steadily increases each interval
            mem = min(98.0, state["mem_base"] + (step * 2.5))
            disk = state["disk_base"]

        elif profile == "disk_exhaustion":
            cpu = random.uniform(10.0, 30.0)
            mem = state["mem_base"]
            # Disk space near capacity
            disk = min(96.0, 88.0 + (step * 0.5))

        return {
            "hostname": hostname,
            "ip_address": host_cfg["ip_address"],
            "environment": host_cfg["environment"],
            "provider": host_cfg["provider"],
            "region": host_cfg["region"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": round(cpu, 2),
            "memory_percent": round(mem, 2),
            "disk_percent": round(disk, 2),
            "network_sent_mb": round(net_sent, 3),
            "network_received_mb": round(net_recv, 3),
        }

    def run(self, interval: int = 5, iterations: int = 0):
        """
        Runs the simulation loop.
        
        Args:
            interval: Delay in seconds between telemetry cycles.
            iterations: Total cycles to execute (0 = infinite).
        """
        print(f"[*] Starting Fleet Simulator for {len(self.fleet)} hosts -> {self.target_url}")
        count = 0
        try:
            while True:
                batch = [self.generate_sample(h) for h in self.fleet]
                try:
                    res = requests.post(
                        self.target_url,
                        json={"metrics": batch},
                        timeout=5.0,
                    )
                    if res.status_code in [200, 201]:
                        data = res.json()
                        print(
                            f"[+] Cycle {count+1}: Dispatched {len(batch)} host samples | "
                            f"Active Alerts Generated/Updated: {data.get('generated_alerts', 0)}"
                        )
                    else:
                        print(f"[!] Server returned HTTP {res.status_code}: {res.text}")
                except Exception as e:
                    print(f"[!] Transmission failed: {e}")

                count += 1
                if iterations and count >= iterations:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[*] Fleet Simulator stopped.")


def main():
    parser = argparse.ArgumentParser(description="Multi-Host Fleet Telemetry Simulator")
    parser.add_argument("--url", default="http://localhost:8000/api/v1/metrics", help="Metrics ingestion URL")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between cycles")
    parser.add_argument("--iterations", type=int, default=0, help="Total iterations (0 = endless)")

    args = parser.parse_args()
    sim = FleetSimulator(target_url=args.url)
    sim.run(interval=args.interval, iterations=args.iterations)


if __name__ == "__main__":
    main()
