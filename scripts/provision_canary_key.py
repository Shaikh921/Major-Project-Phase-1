"""
Provision Canary Agent API Key.

Generates a dedicated, cryptographically secure API key for the Stage 1 Canary PC (PC-Room1-01).
The key has provenance authority restricted strictly to 'REAL_AGENT'.
The raw key is stored in a secured local environment file (.env.canary) and is NEVER committed or logged.
"""

import hashlib
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.app.database.session import SessionLocal
from backend.app.database.connection import engine
from backend.app.database.base import Base
from backend.app.models.agent_key import AgentApiKey


def provision_canary_key(db_session=None, key_name: str = "PC-Room1-01-Canary") -> dict:
    """
    Ensures agent_api_keys table exists, then creates an active AgentApiKey
    with source_type='REAL_AGENT'.
    """
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # Generate cryptographically secure secret
    raw_token = "ak_lab_room1_" + secrets.token_hex(24)
    key_prefix = raw_token[:16]
    hashed_key = hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

    owns_session = False
    if db_session is None:
        db = SessionLocal()
        owns_session = True
    else:
        db = db_session

    try:
        # Check if an active key with this name already exists
        existing = db.query(AgentApiKey).filter(AgentApiKey.name == key_name, AgentApiKey.is_active == True).first()
        if existing:
            print(f"[*] Active key for '{key_name}' already exists (Prefix: {existing.key_prefix}...).")
            return {
                "key_id": existing.id,
                "key_name": existing.name,
                "key_prefix": existing.key_prefix,
                "source_type": existing.source_type,
                "status": "existing",
            }

        key_record = AgentApiKey(
            name=key_name,
            key_prefix=key_prefix,
            hashed_key=hashed_key,
            description="Dedicated Stage 1 Canary Agent key for PC-Room1-01 in Room 1",
            source_type="REAL_AGENT",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(key_record)
        db.commit()
        db.refresh(key_record)

        # Write raw key to secured local file .env.canary (gitignored)
        env_canary_path = _ROOT / ".env.canary"
        with open(env_canary_path, "w", encoding="utf-8") as f:
            f.write(f"# Auto-generated Stage 1 Canary Agent Credentials - DO NOT COMMIT\n")
            f.write(f"AGENT_API_KEY={raw_token}\n")
            f.write(f"APP_ENV=lab\n")
            f.write(f"CLOUD_REGION=Room 1\n")
            f.write(f"POLL_INTERVAL=15\n")

        print(f"[+] Successfully provisioned canary key (ID: {key_record.id}, Prefix: {key_prefix}..., Provenance: REAL_AGENT).")
        print(f"[+] Saved credentials securely to {env_canary_path.name} (permissions: local machine only).")

        return {
            "key_id": key_record.id,
            "key_name": key_record.name,
            "key_prefix": key_prefix,
            "source_type": key_record.source_type,
            "status": "created",
            "raw_token": raw_token,
        }
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    result = provision_canary_key()
    print("[*] Key provisioning complete.")
