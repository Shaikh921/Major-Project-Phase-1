from sqlalchemy import create_engine, event

from backend.app.core.config import settings


DATABASE_URL = settings.database_url

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)


def configure_sqlite_pragmas(target_engine, timeout_ms: int = 5000):
    """
    Configures SQLite-specific pragmas on an engine:
    - PRAGMA journal_mode=WAL (Write-Ahead Logging for concurrent readers/writers)
    - PRAGMA busy_timeout=5000 (Bounded wait for concurrent write transactions)
    - PRAGMA foreign_keys=ON (Enforces referential integrity)
    Strictly executed only on SQLite engines.
    """
    @event.listens_for(target_engine, "connect")
    def set_pragmas(dbapi_connection, connection_record):
        if hasattr(dbapi_connection, "cursor"):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute(f"PRAGMA busy_timeout={timeout_ms};")
                cursor.execute("PRAGMA foreign_keys=ON;")
            finally:
                cursor.close()


if DATABASE_URL.startswith("sqlite"):
    configure_sqlite_pragmas(engine, timeout_ms=5000)