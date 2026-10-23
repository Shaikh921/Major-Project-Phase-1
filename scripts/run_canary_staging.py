"""
Staging Canary Agent Runner.

Runs a real MonitoringAgent process on the current host configured as PC-Room1-01 in Room 1.
Loads dedicated REAL_AGENT credentials from .env.canary and pushes live system telemetry
to the running CloudOps Intel backend.
"""

import argparse
import os
import random
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from monitoring_agent.agent import MonitoringAgent


def load_canary_env() -> dict:
    env_file = _ROOT / ".env.canary"
    config = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip()
    return config


def main():
    parser = argparse.ArgumentParser(description="Staging Canary Agent (PC-Room1-01)")
    parser.add_argument("--url", default="http://localhost:8000/api/v1/metrics", help="Metrics ingestion URL")
    parser.add_argument("--interval", type=int, default=15, help="Telemetry reporting interval in seconds")
    parser.add_argument("--cycles", type=int, default=None, help="Maximum telemetry cycles to run (None = continuous)")
    parser.add_argument("--hostname", default="PC-Room1-01", help="Target hostname to report as")
    parser.add_argument("--jitter", action="store_true", default=True, help="Apply 1-10s startup jitter")
    parser.add_argument("--ca-bundle", default=os.getenv("AGENT_CA_BUNDLE", ""), help="Path to CA certificate bundle")
    parser.add_argument("--allow-insecure-http", action="store_true", default=False, help="Permit plain HTTP (test only)")
    args = parser.parse_args()

    env_config = load_canary_env()
    api_key = env_config.get("AGENT_API_KEY", os.getenv("AGENT_API_KEY", ""))

    if not api_key:
        print("[!] Error: No AGENT_API_KEY found in .env.canary or environment.")
        print("    Run 'python scripts/provision_canary_key.py' first.")
        sys.exit(1)

    print("=" * 60)
    print(f"[*] Starting Canary Monitoring Agent -> Hostname: {args.hostname}")
    print(f"[*] Region: Room 1 | Environment: lab | Interval: {args.interval}s")
    print(f"[*] Target Ingestion: {args.url}")
    print("=" * 60)

    # Apply randomized startup jitter (1 to 10 seconds)
    if args.jitter:
        jitter = random.randint(1, 10)
        print(f"[*] Applying randomized startup jitter: waiting {jitter}s before initial collection...")
        time.sleep(jitter)

    agent = MonitoringAgent(
        server_url=args.url,
        interval=args.interval,
        environment="lab",
        provider="bare-metal",
        region="Room 1",
        api_key=api_key,
        ca_bundle=args.ca_bundle or None,
        allow_insecure_http=args.allow_insecure_http,
    )

    # Configure hostname override for canary staging
    agent.collector.get_hostname = lambda: args.hostname

    # Start collection
    agent.start(max_cycles=args.cycles)


if __name__ == "__main__":
    main()
