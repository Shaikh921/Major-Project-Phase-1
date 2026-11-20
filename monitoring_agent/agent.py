"""
Monitoring Agent Daemon & Workstation Sensor.

Continuously runs in the background on target hosts, polling system telemetry
at configurable intervals and pushing it to the backend ingestion API.
Supports secure enrollment, one-time credential claim, persistent SQLite spooling,
and graceful retirement notifications.
"""

import argparse
import json
import os
import platform
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
import urllib.request
import urllib.error
import ssl

# Ensure project root is on sys.path for direct execution
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Safe stdout/stderr writer when running headless under Windows Task Scheduler / services
class _SafeWriter:
    def __init__(self, fallback_path: Optional[str] = None):
        self.fallback_path = fallback_path

    def write(self, s: str) -> None:
        if not s:
            return
        if self.fallback_path:
            try:
                with open(self.fallback_path, "a", encoding="utf-8") as f:
                    f.write(s)
            except Exception:
                pass

    def flush(self) -> None:
        pass

_sensor_dir = "C:\\ProgramData\\CloudOpsIntel\\Sensor"
_sensor_log = os.path.join(_sensor_dir, "sensor.log") if os.path.isdir(_sensor_dir) else None
if sys.stdout is None:
    sys.stdout = _SafeWriter(_sensor_log)
if sys.stderr is None:
    sys.stderr = _SafeWriter(_sensor_log)

from monitoring_agent.collector import SystemCollector
from monitoring_agent.buffer import MetricBuffer

AGENT_VERSION = "1.0.0"
DEFAULT_CONFIG_PATH = "sensor_config.json"
DEFAULT_SPOOL_PATH = "sensor_spool.db"


class MonitoringAgent:
    """
    Host monitoring agent coordinating collection, persistent buffering,
    HTTP dispatch, and device lifecycle management.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:8000/api/v1/metrics",
        interval: int = 5,
        environment: str = "local",
        provider: str = "bare-metal",
        region: str = "local",
        api_key: Optional[str] = None,
        ca_bundle: Optional[str] = None,
        allow_insecure_http: bool = False,
        spool_db_path: str = DEFAULT_SPOOL_PATH,
        device_uuid: Optional[str] = None,
        config_path: str = DEFAULT_CONFIG_PATH,
    ):
        self.config_path = config_path
        self.device_uuid = device_uuid or self._load_or_generate_uuid()
        self.collector = SystemCollector()
        self.buffer = MetricBuffer(
            ingest_url=server_url,
            api_key=api_key,
            ca_bundle=ca_bundle,
            allow_insecure_http=allow_insecure_http,
            spool_path=spool_db_path,
            poll_interval=interval,
        )
        self.interval = interval
        self.environment = environment
        self.provider = provider
        self.region = region
        self.api_key = api_key
        self.ca_bundle = ca_bundle
        self.allow_insecure_http = allow_insecure_http
        self.spool_db_path = spool_db_path
        self._running = False

        # Load assigned name and room overrides from sensor config if available
        self.assigned_name = None
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if cfg.get("assigned_name"):
                        self.assigned_name = cfg["assigned_name"]
                    if cfg.get("room_number") and self.region == "local":
                        self.region = cfg["room_number"]
                    if self.environment == "local" and cfg.get("assigned_name"):
                        self.environment = "lab"
            except Exception:
                pass

        # Phase 9A.1 Predefined Diagnostic Worker integration
        try:
            from monitoring_agent.diagnostic_worker import DiagnosticWorker
            self.diagnostic_worker = DiagnosticWorker(config_path=self.config_path)
            raw_url = self.diagnostic_worker.config.get("server_url") or server_url
            base_url = raw_url.replace("/api/v1/metrics", "").rstrip("/")
            self.diagnostic_worker.config["server_url"] = base_url
            if not self.diagnostic_worker.config.get("api_key") and api_key:
                self.diagnostic_worker.config["api_key"] = api_key
            if not self.diagnostic_worker.config.get("device_uuid") and self.device_uuid:
                self.diagnostic_worker.config["device_uuid"] = self.device_uuid
            if not self.diagnostic_worker.config.get("ca_bundle") and ca_bundle:
                self.diagnostic_worker.config["ca_bundle"] = ca_bundle
        except Exception:
            self.diagnostic_worker = None

    def _load_or_generate_uuid(self) -> str:
        """Loads device_uuid from config file if present, else generates a new stable UUID."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("device_uuid"):
                        return data["device_uuid"]
            except Exception:
                pass
        return str(uuid.uuid4())

    def start(self, max_cycles: Optional[int] = None) -> None:
        """
        Starts the polling loop.
        
        Args:
            max_cycles: Optional integer limit for cycle count (useful for tests/demos).
        """
        self._running = True
        cycle = 0

        print(f"[*] Starting Monitoring Agent v{AGENT_VERSION} (UUID: {self.device_uuid})")
        print(f"[*] Target Ingestion URL: {self.buffer.ingest_url} | Polling: {self.interval}s")

        try:
            while self._running:
                # 1. Collect telemetry
                sample = self.collector.collect()
                if self.assigned_name:
                    sample["hostname"] = self.assigned_name
                sample["environment"] = self.environment
                sample["provider"] = self.provider
                sample["region"] = self.region
                sample["source_type"] = "REAL_AGENT"

                # 2. Push to local persistent buffer
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
                        f"[!] Ingestion unreachable or rejected. Buffered: {self.buffer.size()} samples. "
                        f"Backoff delay: {backoff:.1f}s"
                    )
                    time.sleep(backoff)

                cycle += 1
                if max_cycles and cycle >= max_cycles:
                    break

                # 4. Phase 9A.1: Check for pending remote diagnostic commands
                if self.diagnostic_worker:
                    try:
                        self.diagnostic_worker.poll_and_execute_once()
                    except Exception:
                        pass

                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n[*] Monitoring Agent stopped gracefully.")
            self._running = False

    def stop(self) -> None:
        """Stops the daemon."""
        self._running = False


def _build_ssl_context(ca_bundle: Optional[str] = None, allow_insecure_http: bool = False) -> ssl.SSLContext:
    """Constructs a strict SSL context with local CA validation."""
    if ca_bundle and os.path.exists(ca_bundle):
        ctx = ssl.create_default_context(cafile=ca_bundle)
    else:
        ctx = ssl.create_default_context()
    return ctx


def enroll_device(
    server_base_url: str,
    enrollment_code: str,
    ca_bundle: Optional[str] = None,
    config_path: str = DEFAULT_CONFIG_PATH,
    timeout_seconds: int = 300,
    poll_interval: int = 5,
) -> bool:
    """
    Submits enrollment request to server, polls for Super Admin approval,
    and saves provisioned device credential into config_path.
    """
    server_base_url = server_base_url.rstrip("/")
    enroll_url = f"{server_base_url}/api/v1/devices/enroll"
    claim_url = f"{server_base_url}/api/v1/devices/claim-credential"

    collector = SystemCollector()
    reported_hostname = collector.get_hostname()
    ip_addr = collector.get_ip_address()
    os_ver = f"{platform.system()} {platform.release()} ({platform.version()})"
    device_uuid = str(uuid.uuid4())

    payload = {
        "enrollment_code": enrollment_code.strip(),
        "device_uuid": device_uuid,
        "reported_hostname": reported_hostname,
        "ip_address": ip_addr,
        "os_version": os_ver,
        "agent_version": AGENT_VERSION,
    }

    print(f"[*] Submitting enrollment request to {enroll_url}...")
    print(f"    Device UUID: {device_uuid}")
    print(f"    Reported Hostname: {reported_hostname}")
    print(f"    Agent Version: {AGENT_VERSION}")

    ssl_ctx = _build_ssl_context(ca_bundle)
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        enroll_url,
        data=req_data,
        headers={"Content-Type": "application/json", "User-Agent": f"CloudOps-Sensor/{AGENT_VERSION}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, context=ssl_ctx if enroll_url.startswith("https") else None, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"[-] Enrollment failed (HTTP {e.code}): {err_msg}")
        return False
    except Exception as e:
        print(f"[-] Connection failed to enrollment server: {e}")
        return False

    claim_token = data.get("claim_token")
    if not claim_token:
        print("[-] Server did not return a claim token.")
        return False

    print(f"[+] Enrollment request accepted! Status: PENDING_APPROVAL.")
    print(f"[*] Awaiting Super Admin review and physical device mapping in CloudOps Intel dashboard...")

    start_wait = time.time()
    while time.time() - start_wait < timeout_seconds:
        time.sleep(poll_interval)
        claim_payload = {"device_uuid": device_uuid, "claim_token": claim_token}
        c_req = urllib.request.Request(
            claim_url,
            data=json.dumps(claim_payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": f"CloudOps-Sensor/{AGENT_VERSION}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(c_req, context=ssl_ctx if claim_url.startswith("https") else None, timeout=15) as c_resp:
                claim_data = json.loads(c_resp.read().decode("utf-8"))
                status = claim_data.get("status")
                if status == "APPROVED":
                    agent_key = claim_data.get("agent_key")
                    assigned_name = claim_data.get("assigned_name", reported_hostname)
                    lab = claim_data.get("lab_name", "Lab")
                    room = claim_data.get("room_number", "")
                    pc = claim_data.get("pc_number", "")

                    print(f"\n[+] Device APPROVED by Super Admin!")
                    print(f"    Assigned Label: {assigned_name}")
                    print(f"    Location: {lab} / Room: {room} / PC: {pc}")

                    # Persist sensor configuration securely
                    config = {
                        "device_uuid": device_uuid,
                        "server_url": f"{server_base_url}/api/v1/metrics",
                        "api_key": agent_key,
                        "assigned_name": assigned_name,
                        "lab_name": lab,
                        "room_number": room,
                        "pc_number": pc,
                        "ca_bundle": ca_bundle,
                        "agent_version": AGENT_VERSION,
                    }
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(config, f, indent=2)

                    print(f"[+] Sensor configuration persisted to '{config_path}'. Device ready to start.")
                    return True

                elif status == "REJECTED":
                    print(f"\n[-] Device enrollment was REJECTED: {claim_data.get('rejection_reason')}")
                    return False
                else:
                    print(".", end="", flush=True)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"\n[-] Claim token expired or invalid.")
                return False
            time.sleep(poll_interval)
        except Exception:
            time.sleep(poll_interval)

    print(f"\n[!] Enrollment approval timed out after {timeout_seconds}s. Super Admin did not approve in time.")
    return False


def notify_uninstall(
    server_base_url: str,
    device_uuid: str,
    api_key: str,
    ca_bundle: Optional[str] = None,
) -> bool:
    """Notifies the backend that a local uninstaller is retiring this device."""
    server_base_url = server_base_url.rstrip("/")
    notice_url = f"{server_base_url}/api/v1/devices/uninstall-notice"
    payload = {
        "device_uuid": device_uuid,
        "agent_key": api_key,
        "reason": f"Local sensor uninstaller executed on {socket.gethostname()}",
    }
    ssl_ctx = _build_ssl_context(ca_bundle)
    req = urllib.request.Request(
        notice_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Agent-Key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=ssl_ctx if notice_url.startswith("https") else None, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[+] Remote retirement confirmed: {data.get('message')}")
            return True
    except Exception as e:
        print(f"[!] WARNING: Remote server could not be reached to confirm credential revocation: {e}")
        print("    The local files will be removed, but remote revocation remains UNCONFIRMED.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Cloud Intelligence Telemetry Collection Agent & Sensor")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help=f"Path to sensor config file (default: {DEFAULT_CONFIG_PATH})")
    parser.add_argument("--url", default=None, help="Ingestion API endpoint (overrides config)")
    parser.add_argument("--server-url", default=None, help="Server base HTTPS URL (e.g. https://10.227.136.246:8443)")
    parser.add_argument("--interval", type=int, default=None, help="Polling interval in seconds")
    parser.add_argument("--env", default="local", help="Environment name")
    parser.add_argument("--provider", default="bare-metal", help="Cloud provider")
    parser.add_argument("--region", default="local", help="Cloud region")
    parser.add_argument("--api-key", default=None, help="Agent ingestion API key")
    parser.add_argument("--ca-bundle", default=None, help="Path to CA certificate bundle (e.g. root.crt)")
    parser.add_argument("--allow-insecure-http", action="store_true", default=False, help="Allow cleartext HTTP (dev only)")
    parser.add_argument("--spool-db", default=DEFAULT_SPOOL_PATH, help="Path to SQLite spool queue DB")
    parser.add_argument("--max-cycles", type=int, default=None, help="Run for N cycles then exit (testing)")

    # Lifecycle commands
    parser.add_argument("--enroll", action="store_true", help="Execute enrollment handshake using --code")
    parser.add_argument("--code", default=None, help="Single-use enrollment code generated by Super Admin")
    parser.add_argument("--notify-uninstall", action="store_true", help="Notify backend before local uninstallation")

    args = parser.parse_args()

    # Handle enrollment flow
    if args.enroll:
        if not args.code:
            print("[-] Error: --code <ENROLLMENT_CODE> is required for --enroll mode.")
            sys.exit(1)
        target_server = args.server_url or "https://localhost:8443"
        ca = args.ca_bundle or ("root.crt" if os.path.exists("root.crt") else None)
        success = enroll_device(
            server_base_url=target_server,
            enrollment_code=args.code,
            ca_bundle=ca,
            config_path=args.config,
        )
        sys.exit(0 if success else 1)

    # Handle uninstall notice
    if args.notify_uninstall:
        target_server = args.server_url or "https://localhost:8443"
        ca = args.ca_bundle or ("root.crt" if os.path.exists("root.crt") else None)
        # Load credentials from config
        device_uuid = "unknown"
        api_key = args.api_key or ""
        if os.path.exists(args.config):
            try:
                with open(args.config, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    device_uuid = cfg.get("device_uuid", device_uuid)
                    if not api_key:
                        api_key = cfg.get("api_key", "")
            except Exception:
                pass
        confirmed = notify_uninstall(target_server, device_uuid, api_key, ca)
        sys.exit(0 if confirmed else 2)

    # Normal daemon run: load config if present
    cfg_data: Dict[str, Any] = {}
    if os.path.exists(args.config):
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
        except Exception as e:
            print(f"[!] Warning: failed to parse '{args.config}': {e}")

    server_url = args.url or cfg_data.get("server_url") or os.getenv("INGEST_URL", "http://localhost:8000/api/v1/metrics")
    api_key = args.api_key or cfg_data.get("api_key") or os.getenv("AGENT_API_KEY", os.getenv("AGENT_INGESTION_KEY", ""))
    ca_bundle = args.ca_bundle or cfg_data.get("ca_bundle") or os.getenv("AGENT_CA_BUNDLE", "")
    interval = args.interval or cfg_data.get("poll_interval") or int(os.getenv("POLL_INTERVAL", "5"))
    device_uuid = cfg_data.get("device_uuid")

    agent = MonitoringAgent(
        server_url=server_url,
        interval=interval,
        environment=args.env,
        provider=args.provider,
        region=args.region,
        api_key=api_key or None,
        ca_bundle=ca_bundle or None,
        allow_insecure_http=args.allow_insecure_http,
        spool_db_path=args.spool_db,
        device_uuid=device_uuid,
        config_path=args.config,
    )
    agent.start(max_cycles=args.max_cycles)


if __name__ == "__main__":
    main()

