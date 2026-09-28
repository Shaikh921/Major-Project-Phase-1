"""
Security Core Utilities: Argon2id Password Hashing & PyJWT Token Handling.

Provides cryptographic functions for:
- Argon2id password hashing and constant-time verification.
- PyJWT HS256 access token creation and payload validation.
- Cryptographically secure high-entropy token generation (32-byte).
- SHA-256 token hashing for database storage.
"""

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash

from backend.app.core.config import settings

# Initialize Argon2id password hasher with high-security parameters
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    if not password or not isinstance(password, str):
        raise ValueError("Password must be a non-empty string.")
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash using constant-time comparison."""
    if not plain_password or not hashed_password:
        return False
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def create_access_token(
    user_id: int,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates a signed PyJWT access token with standard claims.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a signed access token. Returns payload dict or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "email", "role", "exp", "iat"]},
        )
        if payload.get("type") != "access":
            return None
        return payload
    except (jwt.PyJWTError, Exception):
        return None


def generate_secure_token(length_bytes: int = 32) -> str:
    """Generates a high-entropy, URL-safe random cryptographic token string."""
    return secrets.token_urlsafe(length_bytes)


def hash_token(token: str) -> str:
    """
    Returns the SHA-256 hex digest of a token string for safe database indexing/storage.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
