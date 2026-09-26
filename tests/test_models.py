from sqlalchemy import inspect

from backend.app.database.connection import engine
from backend.app.database.init_db import init_db


def test_database_tables_created():
    init_db()

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "hosts" in tables
    assert "metrics" in tables