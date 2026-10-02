"""
Live Anomaly Trigger Script for Email Verification.

Injects an anomalous telemetry sample (breaching Resource Threshold, Isolation Forest, and LSTM)
into the live monitoring engine for a specified host to trigger dual email dispatch:
1. Super Admin: s23_shaikh_irafan@mgmcen.ac.in
2. Host Contact Email: (e.g. irafanshaikh505@gmail.com, projectinengineering@gmail.com, mrirfanshaikh0777@gmail.com)
"""

import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database.session import SessionLocal
from backend.app.services.metric_service import ingest_metric
from backend.app.schemas.metric import MetricCreate
from backend.app.models.host import Host
from sqlalchemy import select


def trigger_live_correlated_anomaly(target_host: str = "prod-api-01"):
    print("=" * 70)
    print(f" TRIGGERING LIVE CORRELATED INCIDENT FOR HOST: {target_host} ")
    print("=" * 70)

    db = SessionLocal()
    try:
        host = db.scalar(select(Host).where(Host.hostname == target_host))
        if not host:
            print(f"[-] Host '{target_host}' not found in database. Creating it...")
            from backend.app.services.host_service import get_or_create_host
            host = get_or_create_host(db, hostname=target_host, owner_email="irafanshaikh505@gmail.com")

        print(f"[+] Target Host: {host.hostname} (ID: {host.id})")
        print(f"[+] Associated Owner Email: {host.owner_email}")

        # Ingest extreme anomalous sample
        sample = MetricCreate(
            hostname=host.hostname,
            ip_address=host.ip_address or "10.0.1.12",
            environment=host.environment or "production",
            owner_email=host.owner_email,
            cpu_percent=98.5,
            memory_percent=96.0,
            disk_percent=89.0,
            network_sent_mb=85.0,
            network_received_mb=95.0,
        )

        print("[+] Ingesting anomalous telemetry sample...")
        metric, alerts = ingest_metric(db, sample)
        
        print(f"[+] Successfully ingested Metric ID: {metric.id}")
        print(f"[+] Generated/Updated Alerts ({len(alerts)}):")
        for a in alerts:
            print(f"    - ID: #{a.id} | Kind: {a.kind} | Severity: {a.severity.upper()} | Metric: {a.metric} | Message: {a.message}")

        print("\n[+] Email Dispatch Status:")
        print(f"    -> Super Admin: s23_shaikh_irafan@mgmcen.ac.in")
        print(f"    -> Host Owner:  {host.owner_email}")
        print("\n[✓] Correlated Anomaly Email queued for SMTP delivery via Gmail relay.")
    finally:
        db.close()


if __name__ == "__main__":
    hostname = sys.argv[1] if len(sys.argv) > 1 else "prod-api-01"
    trigger_live_correlated_anomaly(hostname)
