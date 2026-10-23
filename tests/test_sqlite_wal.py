"""
Acceptance Test Suite for SQLite WAL Mode & Bounded Busy Timeout (Phase 8B).

Verifies on an ISOLATED temporary SQLite database:
1. PRAGMA journal_mode returns 'wal'.
2. PRAGMA busy_timeout is set to 5000 milliseconds on newly established connections.
3. Concurrent readers and writers execute representative telemetry inserts without
   unhandled 'database is locked' errors or transaction failures.
4. Data integrity: zero records lost, zero duplicate primary keys, PRAGMA integrity_check passes.
"""

import concurrent.futures
import os
import sqlite3
import tempfile
import time
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from backend.app.database.base import Base
from backend.app.database.connection import configure_sqlite_pragmas
from backend.app.models.host import Host
from backend.app.models.metric import Metric


@pytest.fixture
def temp_disk_db():
    """Provides a dedicated temporary on-disk SQLite database file for WAL testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_wal_isolated.db"
        db_url = f"sqlite:///{db_path.as_posix()}"
        
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        configure_sqlite_pragmas(engine, timeout_ms=5000)

        # Create tables
        Base.metadata.create_all(bind=engine)

        yield {
            "path": db_path,
            "url": db_url,
            "engine": engine,
        }

        engine.dispose()


def test_sqlite_wal_mode_and_busy_timeout_applied(temp_disk_db):
    """
    CRITICAL: Verifies that newly created connections on disk databases
    inherit journal_mode=WAL and busy_timeout=5000ms.
    """
    engine = temp_disk_db["engine"]

    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode;")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        foreign_keys = conn.execute(text("PRAGMA foreign_keys;")).scalar()

    assert journal_mode.lower() == "wal", f"Expected WAL journal mode, got: {journal_mode}"
    assert busy_timeout == 5000, f"Expected 5000ms busy timeout, got: {busy_timeout}"
    assert foreign_keys == 1, "Expected foreign keys to be ON"


def test_concurrent_readers_and_writers_under_wal(temp_disk_db):
    """
    Stress-tests concurrent reads and writes on the isolated temporary database.
    Spawns concurrent worker threads executing telemetry insertions and parallel reader threads
    executing aggregations, verifying zero 'database is locked' errors and complete data consistency.
    """
    engine = temp_disk_db["engine"]
    Session = sessionmaker(bind=engine)

    # 1. Seed initial host
    with Session() as s:
        host = Host(
            hostname="stress-wal-node-01",
            ip_address="10.200.1.1",
            environment="test",
            provider="simulation",
            region="test-region",
            source_type="REAL_AGENT",
            is_active=True,
        )
        s.add(host)
        s.commit()
        host_id = host.id

    num_writers = 4
    inserts_per_writer = 25
    num_readers = 4
    reads_per_reader = 30
    total_expected_metrics = num_writers * inserts_per_writer

    errors = []

    def writer_task(writer_id: int):
        try:
            with Session() as session:
                for i in range(inserts_per_writer):
                    m = Metric(
                        host_id=host_id,
                        cpu_percent=10.0 + (writer_id * 5) + (i % 10),
                        memory_percent=40.0 + (i % 20),
                        disk_percent=50.0,
                        network_sent_mb=1.0 * i,
                        network_received_mb=2.0 * i,
                    )
                    session.add(m)
                    session.commit()
                    time.sleep(0.005)
        except Exception as e:
            errors.append(f"Writer-{writer_id} failed: {e}")

    def reader_task(reader_id: int):
        try:
            with Session() as session:
                for _ in range(reads_per_reader):
                    count = session.scalar(select(Metric).where(Metric.host_id == host_id))
                    time.sleep(0.003)
        except Exception as e:
            errors.append(f"Reader-{reader_id} failed: {e}")

    # Run writers and readers concurrently in a thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_writers + num_readers) as executor:
        futures = []
        for w in range(num_writers):
            futures.append(executor.submit(writer_task, w))
        for r in range(num_readers):
            futures.append(executor.submit(reader_task, r))

        concurrent.futures.wait(futures)

    # Verify zero concurrency errors occurred
    assert len(errors) == 0, f"Concurrency errors occurred under WAL mode: {errors}"

    # Verify all metrics were persisted without duplication or omission
    with Session() as session:
        final_count = session.query(Metric).filter(Metric.host_id == host_id).count()
        assert final_count == total_expected_metrics, (
            f"Data loss or duplication detected! Expected {total_expected_metrics}, got {final_count}"
        )

    # Verify physical SQLite database integrity check passes
    with engine.connect() as conn:
        integrity = conn.execute(text("PRAGMA integrity_check;")).scalar()
        assert integrity.lower() == "ok", f"Database integrity check failed: {integrity}"
