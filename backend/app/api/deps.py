"""
API Dependencies and RBAC Enforcement.

Provides:
- Database session lifecycle dependency.
- JWT Bearer token authentication and validation.
- Role-based authorization guards (ADMIN, OPERATOR, VIEWER).
"""

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Generator, List, Optional, Dict, Any
from fastapi import Depends, HTTPException, Security, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.session import SessionLocal
from backend.app.core.config import settings
from backend.app.core.security import decode_access_token
from backend.app.models.user import User, UserRole
from backend.app.models.agent_key import AgentApiKey
from backend.app.services.auth_service import get_user_by_id

security_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding an active SQLAlchemy session,
    guaranteeing proper cleanup and closure upon request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_agent_key(raw_key: str) -> str:
    """Hashes an agent ingestion secret using SHA-256."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def verify_agent_credentials(
    x_agent_key: Optional[str] = Header(None, alias="X-Agent-Key"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    FastAPI security dependency for telemetry ingestion endpoints.
    Verifies agent pre-shared secrets (via X-Agent-Key, X-API-Key, or Bearer auth)
    against configured settings or hashed database records in agent_api_keys.
    
    Rejects missing, invalid, inactive, or revoked credentials BEFORE
    any database mutations occur.
    
    Returns an IngestionContext dict describing the authorized agent.
    """
    raw_key = x_agent_key or x_api_key
    if not raw_key and authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() in ("bearer", "apikey"):
            raw_key = parts[1]
        elif len(parts) == 1:
            raw_key = parts[0]

    if not raw_key or not raw_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing agent ingestion credentials. Provide header 'X-Agent-Key: <key>'.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    raw_key_clean = raw_key.strip()

    # 1. Check against environment-configured AGENT_INGESTION_KEY using constant-time comparison
    if settings.agent_ingestion_key and settings.agent_ingestion_key.strip():
        if hmac.compare_digest(raw_key_clean, settings.agent_ingestion_key.strip()):
            return {
                "source": "environment_config",
                "name": "Configured Ingestion Agent",
                "source_type": "ALL",
                "key_prefix": raw_key_clean[:8],
            }

    # 2. Check against database-managed AgentApiKey records
    raw_hash = hash_agent_key(raw_key_clean)
    query = select(AgentApiKey).where(AgentApiKey.hashed_key == raw_hash)
    key_record = db.scalar(query)

    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid agent ingestion credentials.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not key_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Agent ingestion key is inactive.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if key_record.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Agent ingestion key has been revoked.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Update last_used_at timestamp safely
    key_record.last_used_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()

    return {
        "source": "database",
        "id": key_record.id,
        "name": key_record.name,
        "source_type": key_record.source_type,
        "key_prefix": key_record.key_prefix,
    }


def get_current_user(
    auth_creds: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Extracts and validates the Bearer JWT token from the Authorization header.
    Returns the active authenticated User entity or raises 401 Unauthorized.
    """
    if not auth_creds or not auth_creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth_creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token identity payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


def require_role(allowed_roles: List[str]):
    """
    Factory creating a FastAPI dependency that verifies the authenticated user
    possesses one of the allowed role privileges.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {allowed_roles} role permissions.",
            )
        return current_user

    return role_checker


# Convenient role-tiered dependencies
get_current_super_admin = require_role([UserRole.SUPER_ADMIN])
get_current_admin = require_role([UserRole.ADMIN, UserRole.SUPER_ADMIN])
get_current_operator = require_role([UserRole.OPERATOR, UserRole.ADMIN, UserRole.SUPER_ADMIN])
get_current_viewer = require_role([UserRole.VIEWER, UserRole.OPERATOR, UserRole.ADMIN, UserRole.SUPER_ADMIN])
