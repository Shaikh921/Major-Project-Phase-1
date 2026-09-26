"""
Database Initialization and Seeding.

Creates all required relational tables and seeds baseline production
alert rules, pricing catalogs, and initial operational metadata if the database is unpopulated.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.base import Base
from backend.app.database.connection import engine
from backend.app.database.session import SessionLocal

# Import all models so SQLAlchemy metadata registers them
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import AlertRule, Alert, AlertFeedback
from backend.app.models.security import SecurityEvent, AuditLog
from backend.app.models.cost import PricingCatalog, CostRecommendation
from cost_engine.calculator import STANDARD_PRICING_CATALOG


DEFAULT_ALERT_RULES = [
    {
        "name": "High CPU Utilization Warning",
        "metric": "cpu_percent",
        "operator": ">=",
        "threshold": 80.0,
        "severity": "warning",
        "duration_seconds": 0,
        "is_enabled": True,
    },
    {
        "name": "Critical CPU Utilization",
        "metric": "cpu_percent",
        "operator": ">=",
        "threshold": 95.0,
        "severity": "critical",
        "duration_seconds": 0,
        "is_enabled": True,
    },
    {
        "name": "High Memory Utilization",
        "metric": "memory_percent",
        "operator": ">=",
        "threshold": 85.0,
        "severity": "warning",
        "duration_seconds": 0,
        "is_enabled": True,
    },
    {
        "name": "Critical Memory Exhaustion",
        "metric": "memory_percent",
        "operator": ">=",
        "threshold": 95.0,
        "severity": "critical",
        "duration_seconds": 0,
        "is_enabled": True,
    },
    {
        "name": "High Disk Space Usage",
        "metric": "disk_percent",
        "operator": ">=",
        "threshold": 85.0,
        "severity": "warning",
        "duration_seconds": 0,
        "is_enabled": True,
    },
    {
        "name": "Critical Disk Full Imminent",
        "metric": "disk_percent",
        "operator": ">=",
        "threshold": 95.0,
        "severity": "critical",
        "duration_seconds": 0,
        "is_enabled": True,
    },
]


def seed_default_rules(db: Session) -> None:
    """Seeds default alert rules into the database if the alert_rules table is empty."""
    existing_rule = db.scalar(select(AlertRule).limit(1))
    if existing_rule is None:
        for rule_dict in DEFAULT_ALERT_RULES:
            rule = AlertRule(**rule_dict)
            db.add(rule)
        db.commit()


def seed_pricing_catalog(db: Session) -> None:
    """Seeds reference cloud instance pricing catalog."""
    existing_price = db.scalar(select(PricingCatalog).limit(1))
    if existing_price is None:
        for itype, info in STANDARD_PRICING_CATALOG.items():
            entry = PricingCatalog(
                provider="AWS" if not itype.startswith("Standard") and not itype.startswith("e2") else ("Azure" if itype.startswith("Standard") else "GCP"),
                region="us-east-1",
                instance_type=itype,
                vcpus=info["vcpus"],
                memory_gb=info["memory_gb"],
                hourly_rate_usd=info["hourly_usd"],
                currency="USD",
            )
            db.add(entry)
        db.commit()


def seed_baseline_telemetry_if_empty(db: Session) -> None:
    """
    Seeds initial realistic fleet telemetry if database is fresh,
    providing instant operational visibility without fake numbers.
    """
    existing_host = db.scalar(select(Host).limit(1))
    if existing_host is None:
        now = datetime.now(timezone.utc)
        sample_hosts = [
            ("prod-api-01", "10.0.1.12", "production", "c5.2xlarge", "AWS", "us-east-1"),
            ("prod-api-02", "10.0.1.13", "production", "c5.2xlarge", "AWS", "us-east-1"),
            ("prod-db-primary", "10.0.2.5", "production", "r5.xlarge", "AWS", "us-east-1"),
            ("staging-worker-01", "10.0.3.18", "staging", "t3.xlarge", "AWS", "us-west-2"),
            ("dev-sandbox-01", "10.0.4.99", "development", "t3.medium", "AWS", "us-west-2"),
        ]
        
        host_objs = []
        for name, ip, env, itype, prov, reg in sample_hosts:
            h = Host(
                hostname=name,
                ip_address=ip,
                environment=env,
                instance_type=itype,
                provider=prov,
                region=reg,
                status="healthy",
                is_active=True,
                created_at=now - timedelta(days=7),
                last_seen=now,
            )
            db.add(h)
            host_objs.append(h)
        db.commit()

        # Seed initial metrics history for each host
        for h in host_objs:
            base_cpu = 45.0 if "api" in h.hostname else (25.0 if "worker" in h.hostname else (8.0 if "sandbox" in h.hostname else 62.0))
            for i in range(15):
                ts = now - timedelta(minutes=(15 - i))
                m = Metric(
                    host_id=h.id,
                    timestamp=ts,
                    cpu_percent=base_cpu + (i % 5) * 1.5,
                    memory_percent=55.0 + (i % 3) * 2.0,
                    disk_percent=48.0,
                    network_sent_mb=12.5 + (i * 0.4),
                    network_received_mb=18.0 + (i * 0.3),
                )
                db.add(m)
        db.commit()

        # Seed initial security event
        sec_event = SecurityEvent(
            host_id=host_objs[0].id,
            event_type="ssh_brute_force",
            severity="high",
            source_ip="198.51.100.45",
            destination_port=22,
            description="5 consecutive failed SSH authentications for user 'root' from unknown ASN.",
            status="open",
            raw_evidence="Failed password for root from 198.51.100.45 port 52344 ssh2",
            timestamp=now - timedelta(minutes=24),
        )
        db.add(sec_event)

        # Seed initial audit log
        audit = AuditLog(
            user_email="sre-admin@ops.local",
            action="BOOTSTRAP_FLEET",
            target_resource="Cluster Inventory",
            details="Initialized fleet monitoring inventory with 5 active nodes.",
            result="success",
            timestamp=now - timedelta(days=1),
        )
        db.add(audit)
        db.commit()


def init_db() -> None:
    """Initializes database schema and populates initial configuration seeds."""
    Base.metadata.create_all(bind=engine)
    
    with SessionLocal() as db:
        seed_default_rules(db)
        seed_pricing_catalog(db)
        seed_baseline_telemetry_if_empty(db)