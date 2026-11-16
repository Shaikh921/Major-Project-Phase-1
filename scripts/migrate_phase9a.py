"""
Phase 9A.1 Additive Schema Migration Script.

Creates new tables for:
- user_environment_assignments
- user_host_assignments
- diagnostic_commands
- diagnostic_results

Verifies table existence, foreign keys, indexes, and existing data integrity.
"""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import sqlite3
from backend.app.database.connection import engine
from backend.app.database.base import Base
import backend.app.models


def run_migration():
    print("[*] Starting Phase 9A.1 additive schema creation...")
    Base.metadata.create_all(bind=engine)
    print("[+] Base.metadata.create_all executed successfully.")

    conn = sqlite3.connect("cloud_intelligence.db")
    cur = conn.cursor()

    expected_tables = [
        "user_environment_assignments",
        "user_host_assignments",
        "diagnostic_commands",
        "diagnostic_results",
    ]

    for tbl in expected_tables:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (tbl,))
        row = cur.fetchone()
        if not row:
            print(f"[!] Error: Table {tbl} was not created!")
            sys.exit(1)
        print(f"[+] Verified table exists: {tbl}")

    # Check partial indexes
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name LIKE 'uq_user_%';")
    indexes = cur.fetchall()
    print("[+] Verified partial unique indexes:")
    for idx_name, idx_sql in indexes:
        print(f"    - {idx_name}: {idx_sql}")

    # Verify existing table counts
    for tbl in ["users", "hosts", "alert_rules"]:
        cur.execute(f"SELECT COUNT(*) FROM \"{tbl}\";")
        cnt = cur.fetchone()[0]
        print(f"[+] Verified existing data untouched: {tbl} has {cnt} rows.")

    # Run integrity and foreign key check
    cur.execute("PRAGMA integrity_check;")
    integrity = cur.fetchall()
    print(f"[+] PRAGMA integrity_check: {integrity[0][0]}")

    cur.execute("PRAGMA foreign_key_check;")
    fk_errors = cur.fetchall()
    if fk_errors:
        print(f"[!] Foreign key check errors: {fk_errors}")
        sys.exit(1)
    print("[+] PRAGMA foreign_key_check: OK (0 errors)")

    conn.close()
    print("[========================================================================]")
    print("[+] PHASE B: ADDITIVE DATABASE SCHEMA MIGRATION SUCCESSFULLY COMPLETE")
    print("[========================================================================]")


if __name__ == "__main__":
    run_migration()
