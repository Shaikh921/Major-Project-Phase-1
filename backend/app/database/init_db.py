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
from backend.app.models.user import User, UserSession, EmailVerificationToken, PasswordResetToken, UserRole
from backend.app.core.config import settings
from backend.app.services.auth_service import create_bootstrap_admin
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
            ("prod-api-01", "10.0.1.12", "production", "c5.2xlarge", "simulation", "synthetic", "irafanshaikh505@gmail.com"),
            ("prod-api-02", "10.0.1.13", "production", "c5.2xlarge", "simulation", "synthetic", "irafanshaikh505@gmail.com"),
            ("prod-db-primary", "10.0.2.5", "production", "r5.xlarge", "simulation", "synthetic", "projectinengineering@gmail.com"),
            ("staging-worker-01", "10.0.3.18", "staging", "t3.xlarge", "simulation", "synthetic", "mrirfanshaikh0777@gmail.com"),
            ("dev-sandbox-01", "10.0.4.99", "development", "t3.medium", "simulation", "synthetic", "mrirfanshaikh0777@gmail.com"),
        ]
        
        host_objs = []
        for name, ip, env, itype, prov, reg, owner in sample_hosts:
            h = Host(
                hostname=name,
                ip_address=ip,
                environment=env,
                instance_type=itype,
                provider=prov,
                region=reg,
                source_type="SIMULATED",
                owner_email=owner,
                is_active=True,
                created_at=now - timedelta(days=7),
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


def migrate_schema_if_needed() -> None:
    """
    Safely checks and adds missing columns (such as source_type, owner_email) to existing SQLite tables
    without destructive drops or data loss.
    """
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            # Check existing columns on hosts table
            result = conn.execute(text("PRAGMA table_info(hosts)"))
            columns = [row[1] for row in result.fetchall()]
            if columns and "source_type" not in columns:
                conn.execute(text("ALTER TABLE hosts ADD COLUMN source_type VARCHAR(50) DEFAULT 'UNKNOWN'"))
                conn.commit()

            if columns and "owner_email" not in columns:
                conn.execute(text("ALTER TABLE hosts ADD COLUMN owner_email VARCHAR(255)"))
                conn.commit()

            # Associate host owner emails
            conn.execute(text("UPDATE hosts SET owner_email = 'irafanshaikh505@gmail.com' WHERE (hostname LIKE 'prod-api%' OR hostname LIKE 'DESKTOP%' OR environment = 'local')"))
            conn.execute(text("UPDATE hosts SET owner_email = 'projectinengineering@gmail.com' WHERE (hostname LIKE 'prod-db%' OR hostname LIKE '%db%')"))
            conn.execute(text("UPDATE hosts SET owner_email = 'mrirfanshaikh0777@gmail.com' WHERE (hostname LIKE 'staging%' OR hostname LIKE 'dev-%')"))
            conn.execute(text("UPDATE hosts SET owner_email = 'irafanshaikh505@gmail.com' WHERE owner_email IS NULL"))
            conn.commit()
        except Exception as e:
            # Table might not exist yet before create_all
            pass


def init_db() -> None:
    """Initializes database schema, applies safe schema additions, and populates baseline configuration."""
    Base.metadata.create_all(bind=engine)
    migrate_schema_if_needed()
    
    with SessionLocal() as db:
        seed_default_rules(db)
        seed_pricing_catalog(db)
        seed_baseline_telemetry_if_empty(db)

        # Ensure configured bootstrap super admin account exists with updated credentials
        if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
            from backend.app.core.security import hash_password
            super_user = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.strip().lower()))
            if super_user:
                super_user.role = UserRole.SUPER_ADMIN
                super_user.password_hash = hash_password(settings.bootstrap_admin_password)
                super_user.is_active = True
                super_user.is_verified = True
                db.commit()
            else:
                super_user = User(
                    email=settings.bootstrap_admin_email.strip().lower(),
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=UserRole.SUPER_ADMIN,
                    is_active=True,
                    is_verified=True,
                )
                db.add(super_user)
                db.commit()