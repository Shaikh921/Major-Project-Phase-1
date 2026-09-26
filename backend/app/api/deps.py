"""
API Dependencies.

Provides shared dependencies like database session lifecycle management.
"""

from typing import Generator
from sqlalchemy.orm import Session

from backend.app.database.session import SessionLocal


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
