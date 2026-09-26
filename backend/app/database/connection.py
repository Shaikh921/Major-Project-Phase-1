from sqlalchemy import create_engine

from backend.app.core.config import settings


DATABASE_URL = settings.database_url

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)