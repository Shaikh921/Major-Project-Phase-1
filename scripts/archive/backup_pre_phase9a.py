"""
SQLite Consistent Online Backup Script for CloudOps Intel — Pre-Phase 9A.1.

Implements all Phase A defensive backup and verification requirements:
1. Online page-level backup via sqlite3.Connection.backup() while active writers proceed.
2. Windows-safe atomic staging via .tmp file with strict connection cleanup in finally blocks.
3. Physical B-tree integrity check (PRAGMA integrity_check).
4. Referential integrity check (PRAGMA foreign_key_check).
5. Schema parity comparison (sqlite_master SHA-256).
6. Deterministic content checksums on critical tables (users, hosts, alert_rules).
7. Atomic rename to final .db and manifest generation with SHA-256 file digest.
"""

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def compute_file_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_table_checksum(cursor: sqlite3.Cursor, table_name: str, primary_key: str = "id") -> str:
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
    if not cursor.fetchone():
        return "TABLE_NOT_FOUND"
    cursor.execute(f"SELECT * FROM \"{table_name}\" ORDER BY \"{primary_key}\";")
    rows = cursor.fetchall()
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()


def perform_phase_a_backup():
    project_root = Path(__file__).resolve().parent.parent
    src_db_path = project_root / "cloud_intelligence.db"
    backup_dir = project_root / "backups" / "pre_phase9a"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    tmp_dest_path = backup_dir / f"cloud_intelligence_pre_phase9a_{timestamp}.db.tmp"
    final_dest_path = backup_dir / f"cloud_intelligence_pre_phase9a_{timestamp}.db"

    print(f"[*] CloudOps Intel — Phase A Database Backup & Parity Verification")
    print(f"[*] Source Database: {src_db_path}")
    print(f"[*] Staging Backup:  {tmp_dest_path}")

    if not src_db_path.exists():
        print(f"[!] Source database does not exist: {src_db_path}")
        sys.exit(1)

    src_conn = None
    dest_conn = None
    verify_conn = None
    src_verify_conn = None

    try:
        # 1. Connect to source read-only and destination
        src_conn = sqlite3.connect(f"file:{src_db_path.as_posix()}?mode=ro", uri=True)
        dest_conn = sqlite3.connect(tmp_dest_path.as_posix())

        # 2. Perform online streaming backup
        print("[*] Executing sqlite3.Connection.backup(pages=100)...")
        with dest_conn:
            src_conn.backup(dest_conn, pages=100, sleep=0.01)

        print("[+] Online streaming backup complete.")

    finally:
        # Guarantee connection handles are closed before verification/file operations
        if dest_conn:
            dest_conn.close()
        if src_conn:
            src_conn.close()

    try:
        # 3. Open temporary backup in read-only mode for comprehensive verification
        verify_conn = sqlite3.connect(f"file:{tmp_dest_path.as_posix()}?mode=ro", uri=True)
        verify_cur = verify_conn.cursor()

        # 3A. Physical B-tree Integrity Check
        verify_cur.execute("PRAGMA integrity_check;")
        integrity_res = verify_cur.fetchall()
        integrity_ok = len(integrity_res) == 1 and integrity_res[0][0] == "ok"
        if not integrity_ok:
            raise RuntimeError(f"Integrity check failed: {integrity_res}")
        print("[+] PRAGMA integrity_check: OK")

        # 3B. Foreign Key Referential Integrity Check
        verify_cur.execute("PRAGMA foreign_key_check;")
        fk_violations = verify_cur.fetchall()
        if fk_violations:
            raise RuntimeError(f"Foreign key violations found: {fk_violations}")
        print("[+] PRAGMA foreign_key_check: OK (0 violations)")

        # 3C. Schema Parity Verification
        verify_cur.execute(
            "SELECT sql FROM sqlite_master WHERE type IN ('table', 'index') AND sql IS NOT NULL ORDER BY name;"
        )
        dest_schema_rows = verify_cur.fetchall()
        dest_schema_str = "".join([r[0] for r in dest_schema_rows])
        dest_schema_hash = hashlib.sha256(dest_schema_str.encode("utf-8")).hexdigest()

        # Connect to source to compare schema and content
        src_verify_conn = sqlite3.connect(f"file:{src_db_path.as_posix()}?mode=ro", uri=True)
        src_verify_cur = src_verify_conn.cursor()

        src_verify_cur.execute(
            "SELECT sql FROM sqlite_master WHERE type IN ('table', 'index') AND sql IS NOT NULL ORDER BY name;"
        )
        src_schema_rows = src_verify_cur.fetchall()
        src_schema_str = "".join([r[0] for r in src_schema_rows])
        src_schema_hash = hashlib.sha256(src_schema_str.encode("utf-8")).hexdigest()

        if src_schema_hash != dest_schema_hash:
            raise RuntimeError(f"Schema mismatch! Source: {src_schema_hash}, Dest: {dest_schema_hash}")
        print(f"[+] Schema Parity Verified (SHA-256: {dest_schema_hash[:16]}...)")

        # 3D. Deterministic Table Content Checksums & Row Counts
        critical_tables = ["users", "hosts", "alert_rules"]
        content_parity = {}
        for tbl in critical_tables:
            src_chk = compute_table_checksum(src_verify_cur, tbl)
            dest_chk = compute_table_checksum(verify_cur, tbl)
            if src_chk != dest_chk:
                raise RuntimeError(f"Content hash mismatch on table '{tbl}'! Src: {src_chk}, Dest: {dest_chk}")
            content_parity[tbl] = {
                "status": "MATCH",
                "sha256": dest_chk,
            }
            print(f"[+] Content Parity on '{tbl}': MATCH ({dest_chk[:16]}...)")

        # Count all tables and row counts
        verify_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
        all_tables = [r[0] for r in verify_cur.fetchall()]
        table_row_counts = {}
        for tbl in all_tables:
            verify_cur.execute(f"SELECT COUNT(*) FROM \"{tbl}\";")
            table_row_counts[tbl] = verify_cur.fetchone()[0]

    finally:
        if verify_conn:
            verify_conn.close()
        if src_verify_conn:
            src_verify_conn.close()

    # 4. Atomic rename from .tmp to final .db
    os.replace(tmp_dest_path, final_dest_path)
    print(f"[+] Atomically renamed backup to: {final_dest_path}")

    # 5. Compute final backup file SHA-256 and size
    file_size = final_dest_path.stat().st_size
    backup_file_sha256 = compute_file_sha256(final_dest_path)

    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(src_db_path),
        "backup_path": str(final_dest_path),
        "file_size_bytes": file_size,
        "backup_file_sha256": backup_file_sha256,
        "schema_sha256": dest_schema_hash,
        "integrity_check": "ok",
        "foreign_key_violations": 0,
        "content_parity": content_parity,
        "table_count": len(all_tables),
        "table_row_counts": table_row_counts,
    }

    manifest_path = backup_dir / f"backup_manifest_{timestamp}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[+] Backup Manifest written to: {manifest_path}")
    print(f"[+] Final Backup SHA-256: {backup_file_sha256}")
    print("[========================================================================]")
    print("[+] PHASE A: DATABASE BACKUP & PARITY VERIFICATION SUCCESSFULLY COMPLETE")
    print("[========================================================================]")
    return manifest


if __name__ == "__main__":
    perform_phase_a_backup()

