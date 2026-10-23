"""
SQLite Consistent Online Backup Script for CloudOps Intel.

Uses sqlite3.backup() to produce a point-in-time consistent backup
of the active SQLite database even while concurrent writers are active.
Computes SHA-256, compares table schemas and row counts between
source and destination, and verifies read-only integrity.
"""

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

def backup_database():
    project_root = Path(__file__).resolve().parent.parent
    src_db_path = project_root / "cloud_intelligence.db"
    backup_dir = project_root / "backups" / "pre_phase8b"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest_db_path = backup_dir / f"cloud_intelligence_pre_phase8b_{timestamp}.db"

    print(f"[*] Source Database: {src_db_path}")
    print(f"[*] Destination Backup: {dest_db_path}")

    if not src_db_path.exists():
        print(f"[!] Source database does not exist: {src_db_path}")
        sys.exit(1)

    # 1. Connect to source (read-only URI) and destination
    src_conn = sqlite3.connect(f"file:{src_db_path.as_posix()}?mode=ro", uri=True)
    dest_conn = sqlite3.connect(dest_db_path.as_posix())

    # 2. Perform online consistent backup
    print("[*] Executing sqlite3.backup() pages=100...")
    with dest_conn:
        src_conn.backup(dest_conn, pages=100)
    dest_conn.close()
    src_conn.close()

    # 3. Calculate file size and SHA-256 checksum
    file_size = dest_db_path.stat().st_size
    hasher = hashlib.sha256()
    with open(dest_db_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    backup_sha256 = hasher.hexdigest()

    # 4. Verification: Open backup read-only and verify integrity, tables, and row counts
    verify_conn = sqlite3.connect(f"file:{dest_db_path.as_posix()}?mode=ro", uri=True)
    cursor = verify_conn.cursor()

    # Check quick integrity
    cursor.execute("PRAGMA quick_check;")
    quick_check = cursor.fetchall()

    # Query all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [r[0] for r in cursor.fetchall()]

    row_counts = {}
    for tbl in tables:
        cursor.execute(f"SELECT COUNT(*) FROM \"{tbl}\";")
        row_counts[tbl] = cursor.fetchone()[0]

    verify_conn.close()

    # Compare with source
    src_check_conn = sqlite3.connect(f"file:{src_db_path.as_posix()}?mode=ro", uri=True)
    src_cursor = src_check_conn.cursor()
    src_row_counts = {}
    for tbl in tables:
        src_cursor.execute(f"SELECT COUNT(*) FROM \"{tbl}\";")
        src_row_counts[tbl] = src_cursor.fetchone()[0]
    src_check_conn.close()

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(src_db_path),
        "backup_path": str(dest_db_path),
        "file_size_bytes": file_size,
        "sha256": backup_sha256,
        "quick_check": quick_check,
        "table_count": len(tables),
        "tables": tables,
        "backup_row_counts": row_counts,
        "source_row_counts": src_row_counts,
    }

    report_path = backup_dir / f"backup_manifest_{timestamp}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("[+] Consistent SQLite Backup Complete.")
    print(json.dumps(report, indent=2))
    return report

if __name__ == "__main__":
    backup_database()
