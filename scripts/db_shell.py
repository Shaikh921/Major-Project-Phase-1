"""
CloudOps Intel — Interactive Database Terminal Shell
Provides a direct, zero-dependency CLI interface to query and manage cloud_intelligence.db.
Usage:
    Interactive REPL:   python scripts/db_shell.py
    Single Query:       python scripts/db_shell.py "SELECT id, email, role, is_active FROM users"
"""

import sys
import os
import sqlite3
from pathlib import Path

def get_db_path():
    root = Path(__file__).resolve().parent.parent
    db = root / "cloud_intelligence.db"
    if not db.exists():
        print(f"[!] Warning: Database not found at {db}. Initializing new or checking current directory...")
        db = Path("cloud_intelligence.db").resolve()
    return db

def connect_db(db_path, read_only=False):
    if read_only:
        uri = f"file:{db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    else:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def print_table(cursor, headers=None):
    rows = cursor.fetchall()
    if not rows:
        print("Empty set (0 rows).")
        return

    if headers is None and cursor.description:
        headers = [desc[0] for desc in cursor.description]

    # Calculate column widths
    str_rows = [[str(item) if item is not None else "NULL" for item in row] for row in rows]
    widths = [len(h) for h in headers] if headers else [0] * len(rows[0])
    for row in str_rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    # Format header
    sep_line = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    print(sep_line)
    if headers:
        header_line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
        print(header_line)
        print(sep_line)

    # Format data rows
    for row in str_rows:
        print("| " + " | ".join(val.ljust(widths[i]) for i, val in enumerate(row)) + " |")
    print(sep_line)
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})\n")

def execute_query(conn, query):
    query = query.strip()
    if not query:
        return
    try:
        cur = conn.cursor()
        cur.execute(query)
        if query.upper().startswith(("SELECT", "PRAGMA", "EXPLAIN")):
            print_table(cur)
        else:
            conn.commit()
            print(f"Query executed successfully. Rows affected: {cur.rowcount}\n")
    except Exception as e:
        print(f"SQL Error: {e}\n")

def repl(conn, db_path):
    print("=" * 70)
    print(" CloudOps Intel — SQLite Database Interactive Terminal Shell")
    print(f" Database: {db_path}")
    print(" Commands: .tables, .schema [table], exit/quit, or any standard SQL query")
    print("=" * 70)

    while True:
        try:
            line = input("cloudops-db> ").strip()
            if not line:
                continue
            if line.lower() in ("exit", "quit", "\\q"):
                print("Exiting database shell. Goodbye.")
                break
            elif line.lower() == ".tables":
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
                tables = [r[0] for r in cur.fetchall()]
                print("\nDatabase Tables:")
                for i in range(0, len(tables), 3):
                    print("  " + "  ".join(t.ljust(26) for t in tables[i:i+3]))
                print()
            elif line.lower().startswith(".schema"):
                parts = line.split()
                cur = conn.cursor()
                if len(parts) > 1:
                    tbl = parts[1]
                    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (tbl,))
                    res = cur.fetchone()
                    if res:
                        print(f"\n{res[0]};\n")
                    else:
                        print(f"[!] Table '{tbl}' not found.\n")
                else:
                    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name;")
                    for r in cur.fetchall():
                        if r[0]:
                            print(f"{r[0]};\n")
            else:
                execute_query(conn, line)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting database shell.")
            break

def main():
    db_path = get_db_path()
    conn = connect_db(db_path)
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        execute_query(conn, query)
    else:
        repl(conn, db_path)
    conn.close()

if __name__ == "__main__":
    main()
