"""
Database Explorer Service.
Provides read-only inspection of SQLite schema metadata and sanitized record previews.
Enforces instruction progress timeout (3,000 ms), deterministic keyset pagination,
and strict column projection allowlists.
"""

import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from backend.app.core.config import settings
from backend.app.core.database_explorer_policy import (
    FIELD_LENGTH_LIMITS,
    KEYSET_PAGINATION_TABLES,
    OFFSET_ONLY_TABLES,
    TABLE_CATEGORIES,
    TABLE_PROJECTION_ALLOWLISTS,
    TABLE_SECURITY_TIERS,
    TableSecurityTier,
)
from backend.app.schemas.database_explorer import (
    ColumnInfo,
    DatabaseOverviewResponse,
    ForeignKeyInfo,
    IndexInfo,
    TableRecordsResponse,
    TableSchemaResponse,
    TableSummaryResponse,
)


def get_canonical_db_path() -> Optional[Path]:
    """
    Resolves the canonical absolute filesystem path of the application's SQLite database.
    Returns None if running under in-memory test mode (:memory:).
    """
    raw_path = settings.database_url
    if ":memory:" in raw_path:
        return None

    if raw_path.startswith("sqlite:///"):
        raw_path = raw_path[len("sqlite:///"):]
    elif raw_path.startswith("sqlite://"):
        raw_path = raw_path[len("sqlite://"):]

    resolved = Path(raw_path).resolve()
    if not resolved.exists():
        # Fallback to local default if relative path
        local_db = Path("cloud_intelligence.db").resolve()
        if local_db.exists():
            return local_db
        raise RuntimeError(f"Database Explorer cannot locate database file at: {resolved}")
    return resolved


@contextmanager
def get_read_only_connection(timeout_seconds: float = 3.0):
    """
    Yields an isolated, read-only SQLite connection.
    In production/staging: uses URI mode=ro with canonical path and instruction progress handler.
    In automated pytest suite: seamlessly binds to test engine's in-memory connection.
    """
    db_path = get_canonical_db_path()

    if db_path is None or ":memory:" in settings.database_url:
        # In-memory test environment isolation
        import backend.app.database.connection as db_conn
        raw_conn = db_conn.engine.raw_connection()
        try:
            if hasattr(raw_conn, "connection"):
                sqlite_conn = raw_conn.connection
            else:
                sqlite_conn = raw_conn
            sqlite_conn.row_factory = sqlite3.Row
            yield sqlite_conn
        finally:
            raw_conn.close()
        return

    # Production / Persistent database URI mode=ro
    uri = f"{db_path.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    start_time = time.monotonic()

    def progress_callback() -> int:
        if time.monotonic() - start_time > timeout_seconds:
            return 1  # Abort query immediately
        return 0

    conn.set_progress_handler(progress_callback, 1000)

    try:
        yield conn
    except sqlite3.OperationalError as err:
        err_msg = str(err).lower()
        if "interrupted" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Database Explorer query timed out after {int(timeout_seconds * 1000)} ms.",
            )
        if "readonly" in err_msg or "attempt to write" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Write operations are strictly prohibited in Database Explorer.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {err}",
        )
    finally:
        try:
            conn.set_progress_handler(None, 0)
        except Exception:
            pass
        conn.close()


class DatabaseExplorerService:

    @classmethod
    def get_database_overview(cls) -> DatabaseOverviewResponse:
        """
        Retrieves high-level database metrics: engine version, size, table counts, row counts.
        """
        db_path = get_canonical_db_path()
        if db_path is not None and db_path.exists():
            file_size_bytes = db_path.stat().st_size
            file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
            db_file_name = db_path.name
        else:
            file_size_bytes = 0
            file_size_mb = 0.0
            db_file_name = ":memory:"

        with get_read_only_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT sqlite_version();")
            version = cursor.fetchone()[0]

            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]

            total_records = 0
            tier_breakdown: Dict[str, int] = {
                TableSecurityTier.TIER_1_OPERATIONAL: 0,
                TableSecurityTier.TIER_2_SANITIZED: 0,
                TableSecurityTier.TIER_3_ZERO_PREVIEW: 0,
            }

            for table_name, tier in TABLE_SECURITY_TIERS.items():
                tier_breakdown[tier] = tier_breakdown.get(tier, 0) + 1
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM [{table_name}];")
                    total_records += cursor.fetchone()[0]
                except Exception:
                    pass

        return DatabaseOverviewResponse(
            status="ONLINE",
            engine="SQLite",
            sqlite_version=version,
            journal_mode=journal_mode,
            database_file=db_file_name,
            database_size_bytes=file_size_bytes,
            database_size_mb=file_size_mb,
            total_tables=len(TABLE_SECURITY_TIERS),
            total_records=total_records,
            tier_breakdown=tier_breakdown,
            refreshed_at=datetime.now(timezone.utc),
        )

    @classmethod
    def get_all_tables(cls) -> List[TableSummaryResponse]:
        """
        Returns summary metadata for all 23 application tables in the catalog.
        """
        summaries: List[TableSummaryResponse] = []

        with get_read_only_connection() as conn:
            cursor = conn.cursor()

            for table_name, tier in TABLE_SECURITY_TIERS.items():
                category = TABLE_CATEGORIES.get(table_name, "General")
                allowlist = TABLE_PROJECTION_ALLOWLISTS.get(table_name, [])
                preview_allowed = tier != TableSecurityTier.TIER_3_ZERO_PREVIEW
                pagination_type = "KEYSET" if table_name in KEYSET_PAGINATION_TABLES else "OFFSET"

                # Row count
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM [{table_name}];")
                    row_count = cursor.fetchone()[0]
                except Exception:
                    row_count = 0

                # Column introspection
                try:
                    cursor.execute(f"PRAGMA table_info([{table_name}]);")
                    columns = cursor.fetchall()
                    total_columns = len(columns)
                    primary_keys = [c["name"] for c in columns if c["pk"] > 0]
                except Exception:
                    total_columns = 0
                    primary_keys = []

                # Foreign keys
                try:
                    cursor.execute(f"PRAGMA foreign_key_list([{table_name}]);")
                    fk_count = len(cursor.fetchall())
                except Exception:
                    fk_count = 0

                # Indexes
                try:
                    cursor.execute(f"PRAGMA index_list([{table_name}]);")
                    idx_count = len(cursor.fetchall())
                except Exception:
                    idx_count = 0

                summaries.append(
                    TableSummaryResponse(
                        name=table_name,
                        category=category,
                        security_tier=tier,
                        preview_allowed=preview_allowed,
                        pagination_type=pagination_type,
                        total_columns=total_columns,
                        projected_columns=len(allowlist),
                        row_count=row_count,
                        primary_keys=primary_keys,
                        foreign_keys_count=fk_count,
                        index_count=idx_count,
                    )
                )

        return summaries

    @classmethod
    def get_table_schema(cls, table_name: str) -> TableSchemaResponse:
        """
        Introspects full schema details (columns, types, indexes, FKs) for a given table.
        """
        if table_name not in TABLE_SECURITY_TIERS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table '{table_name}' does not exist in application schema catalog.",
            )

        tier = TABLE_SECURITY_TIERS[table_name]
        category = TABLE_CATEGORIES.get(table_name, "General")
        allowlist = set(TABLE_PROJECTION_ALLOWLISTS.get(table_name, []))
        preview_allowed = tier != TableSecurityTier.TIER_3_ZERO_PREVIEW
        pagination_type = "KEYSET" if table_name in KEYSET_PAGINATION_TABLES else "OFFSET"

        with get_read_only_connection() as conn:
            cursor = conn.cursor()

            # Row count
            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}];")
            row_count = cursor.fetchone()[0]

            # Columns
            cursor.execute(f"PRAGMA table_info([{table_name}]);")
            raw_cols = cursor.fetchall()
            columns: List[ColumnInfo] = []
            for col in raw_cols:
                col_name = col["name"]
                columns.append(
                    ColumnInfo(
                        cid=col["cid"],
                        name=col_name,
                        type=col["type"],
                        notnull=bool(col["notnull"]),
                        default_value=col["dflt_value"],
                        primary_key=bool(col["pk"] > 0),
                        is_projected=(col_name in allowlist),
                    )
                )

            # Indexes
            cursor.execute(f"PRAGMA index_list([{table_name}]);")
            raw_indexes = cursor.fetchall()
            indexes: List[IndexInfo] = []
            for idx in raw_indexes:
                idx_name = idx["name"]
                is_unique = bool(idx["unique"])
                is_auto = bool(idx_name.startswith("sqlite_autoindex_"))

                cursor.execute(f"PRAGMA index_info([{idx_name}]);")
                idx_cols = [c["name"] for c in cursor.fetchall()]

                indexes.append(
                    IndexInfo(
                        name=idx_name,
                        unique=is_unique,
                        columns=idx_cols,
                        is_autoindex=is_auto,
                    )
                )

            # Foreign Keys
            cursor.execute(f"PRAGMA foreign_key_list([{table_name}]);")
            raw_fks = cursor.fetchall()
            foreign_keys: List[ForeignKeyInfo] = [
                ForeignKeyInfo(
                    id=fk["id"],
                    table=fk["table"],
                    from_column=fk["from"],
                    to_column=fk["to"],
                )
                for fk in raw_fks
            ]

        return TableSchemaResponse(
            table=table_name,
            category=category,
            security_tier=tier,
            preview_allowed=preview_allowed,
            pagination_type=pagination_type,
            row_count=row_count,
            columns=columns,
            indexes=indexes,
            foreign_keys=foreign_keys,
        )

    @classmethod
    def get_table_records(
        cls,
        table_name: str,
        limit: int = 25,
        page: int = 1,
        cursor: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
    ) -> TableRecordsResponse:
        """
        Retrieves paginated records for a permitted table using explicit projection allowlists.
        Enforces Keyset pagination for metrics/batches and bounded offset pagination for others.
        Tier 3 credential tables are strictly blocked.
        """
        if table_name not in TABLE_SECURITY_TIERS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table '{table_name}' does not exist in application schema catalog.",
            )

        tier = TABLE_SECURITY_TIERS[table_name]
        if tier == TableSecurityTier.TIER_3_ZERO_PREVIEW:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Record preview is disabled by security policy for credential and session storage ('{table_name}').",
            )

        allowlist = TABLE_PROJECTION_ALLOWLISTS.get(table_name, [])
        if not allowlist:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No permitted projection allowlist defined for table '{table_name}'.",
            )

        # Validate parameters
        limit = max(1, min(limit, 50))  # Max 50 rows per page
        page = max(1, page)
        sort_order = "asc" if sort_order.lower() == "asc" else "desc"

        # Validate sort_by
        if sort_by:
            if sort_by not in allowlist:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sort column '{sort_by}' is not in the permitted projection allowlist for '{table_name}'.",
                )
        else:
            sort_by = "id" if "id" in allowlist else allowlist[0]

        is_keyset_table = table_name in KEYSET_PAGINATION_TABLES

        # Validate cursor against table capabilities
        if cursor is not None:
            if not is_keyset_table:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Table '{table_name}' does not support keyset pagination. Use page-number offset pagination.",
                )
            if cursor <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cursor must be a positive integer ID.",
                )
            if sort_by != "id" or sort_order != "desc":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Keyset cursor pagination strictly requires ordering by 'id DESC'. Omit cursor to use custom column sorting with offset pagination.",
                )

        # Build SQL with static column allowlist projection
        cols_sql = ", ".join([f"[{col}]" for col in allowlist])

        with get_read_only_connection() as conn:
            db_cursor = conn.cursor()

            # Exact live count
            db_cursor.execute(f"SELECT COUNT(*) FROM [{table_name}];")
            total_records = db_cursor.fetchone()[0]

            has_more = False
            next_cursor: Optional[int] = None
            total_pages: Optional[int] = None
            current_page: Optional[int] = None
            pagination_type: str

            if is_keyset_table and (cursor is not None or (sort_by == "id" and sort_order == "desc")):
                pagination_type = "KEYSET"
                limit_plus_one = limit + 1

                if cursor is not None:
                    query = f"SELECT {cols_sql} FROM [{table_name}] WHERE [id] < ? ORDER BY [id] DESC LIMIT ?;"
                    db_cursor.execute(query, (cursor, limit_plus_one))
                else:
                    query = f"SELECT {cols_sql} FROM [{table_name}] ORDER BY [id] DESC LIMIT ?;"
                    db_cursor.execute(query, (limit_plus_one,))

                raw_rows = db_cursor.fetchall()

                # Mathematical Keyset Evaluation:
                # Fetch limit + 1. If len > limit, extra record proves has_more is True.
                # Client receives rows[:limit]. Next cursor is ID of the LAST RETURNED record.
                has_more = len(raw_rows) > limit
                paged_rows = raw_rows[:limit]

                if has_more and len(paged_rows) > 0:
                    next_cursor = paged_rows[-1]["id"]
            else:
                pagination_type = "OFFSET"
                current_page = page
                total_pages = max(1, (total_records + limit - 1) // limit)
                offset = (page - 1) * limit

                query = f"SELECT {cols_sql} FROM [{table_name}] ORDER BY [{sort_by}] {sort_order.upper()} LIMIT ? OFFSET ?;"
                db_cursor.execute(query, (limit, offset))
                paged_rows = db_cursor.fetchall()
                has_more = (offset + len(paged_rows)) < total_records

            # Serialize and clamp text fields
            clamping_rules = FIELD_LENGTH_LIMITS.get(table_name, {})
            records: List[Dict[str, Any]] = []

            for row in paged_rows:
                item: Dict[str, Any] = {}
                for col in allowlist:
                    val = row[col]
                    # Clamp text if rule applies
                    if col in clamping_rules and isinstance(val, str):
                        max_len = clamping_rules[col]
                        if len(val) > max_len:
                            val = val[:max_len] + "..."
                    item[col] = val
                records.append(item)

        return TableRecordsResponse(
            table=table_name,
            security_tier=tier,
            pagination_type=pagination_type,
            total_records=total_records,
            count_exact=True,
            limit=limit,
            page=current_page,
            total_pages=total_pages,
            next_cursor=next_cursor,
            has_more=has_more,
            columns=allowlist,
            records=records,
        )
