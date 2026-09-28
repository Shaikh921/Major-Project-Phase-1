"""
API Dependencies and RBAC Enforcement.

Provides:
- Database session lifecycle dependency.
- JWT Bearer token authentication and validation.
- Role-based authorization guards (ADMIN, OPERATOR, VIEWER).
"""

from typing import Generator, List, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.app.database.session import SessionLocal
from backend.app.core.security import decode_access_token
from backend.app.models.user import User, UserRole
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
