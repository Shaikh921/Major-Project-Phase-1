"""
Database Explorer API Endpoints.
Restricted strictly to SUPER_ADMIN role with server-side feature flag enforcement.
Provides read-only inspection of schema metadata and sanitized record previews.
"""

import sqlite3
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db, require_role
from backend.app.core.config import settings
from backend.app.models.user import User, UserRole
from backend.app.schemas.database_explorer import (
    DatabaseExplorerStatusResponse,
    DatabaseOverviewResponse,
    TableRecordsResponse,
    TableSchemaResponse,
    TableSummaryResponse,
)
from backend.app.services.audit_service import record_audit_action
from backend.app.services.database_explorer_service import (
    DatabaseExplorerService,
    get_canonical_db_path,
)

router = APIRouter(prefix="/database-explorer", tags=["Database Explorer"])


def require_explorer_access(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Enforces the strict 6-state security gate:
    1. Authentication: Validates JWT token via get_current_user (raises 401).
    2. Feature Flag: Verifies enable_database_explorer is True (raises 403 'globally disabled').
    3. Authorization: Verifies current_user.role is SUPER_ADMIN (raises 403 'requires SUPER_ADMIN').
    """
    if not getattr(settings, "enable_database_explorer", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Database Explorer is globally disabled by deployment policy.",
        )

    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: requires ['SUPER_ADMIN'] role permissions.",
        )

    return current_user


@router.get("/status", response_model=DatabaseExplorerStatusResponse)
def get_explorer_status(
    current_user: User = Depends(get_current_user),
):
    """
    Returns feature flag status and engine availability.
    Accessible to authenticated Super Admins to dynamically negotiate tab visibility.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: requires ['SUPER_ADMIN'] role permissions.",
        )

    is_enabled = getattr(settings, "enable_database_explorer", False)
    return DatabaseExplorerStatusResponse(
        enabled=is_enabled,
        engine="SQLite",
        version=sqlite3.sqlite_version,
        read_only=True,
    )


@router.get("/overview", response_model=DatabaseOverviewResponse)
def get_database_overview(
    request: Request,
    current_user: User = Depends(require_explorer_access),
    db: Session = Depends(get_db),
):
    """
    Retrieves high-level database metrics: engine version, size, table count, row count.
    """
    overview = DatabaseExplorerService.get_database_overview()

    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        record_audit_action(
            db=db,
            action="DATABASE_EXPLORER_OVERVIEW",
            target_resource=f"Database:{overview.database_file}",
            details="Inspected high-level database storage and table statistics.",
            user_email=current_user.email,
            result="success",
            client_ip=client_ip,
        )
    except Exception:
        pass

    return overview


@router.get("/tables", response_model=List[TableSummaryResponse])
def get_tables_summary(
    request: Request,
    current_user: User = Depends(require_explorer_access),
    db: Session = Depends(get_db),
):
    """
    Lists all application tables in the catalog with security classifications and row counts.
    """
    tables = DatabaseExplorerService.get_all_tables()

    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        record_audit_action(
            db=db,
            action="DATABASE_EXPLORER_LIST_TABLES",
            target_resource="Database:Catalog",
            details=f"Listed all {len(tables)} tables with security classifications.",
            user_email=current_user.email,
            result="success",
            client_ip=client_ip,
        )
    except Exception:
        pass

    return tables


@router.get("/tables/{table_name}/schema", response_model=TableSchemaResponse)
def get_table_schema(
    table_name: str,
    request: Request,
    current_user: User = Depends(require_explorer_access),
    db: Session = Depends(get_db),
):
    """
    Introspects full schema details (columns, data types, indexes, and foreign keys) for a table.
    """
    schema = DatabaseExplorerService.get_table_schema(table_name)

    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        record_audit_action(
            db=db,
            action="DATABASE_EXPLORER_VIEW_SCHEMA",
            target_resource=f"Table:{table_name}",
            details=f"Introspected schema metadata for table '{table_name}' (Tier: {schema.security_tier}).",
            user_email=current_user.email,
            result="success",
            client_ip=client_ip,
        )
    except Exception:
        pass

    return schema


@router.get("/tables/{table_name}/records", response_model=TableRecordsResponse)
def get_table_records(
    table_name: str,
    request: Request,
    limit: int = Query(default=25, ge=1, le=50, description="Records per page (max 50)"),
    page: int = Query(default=1, ge=1, description="Page number for offset pagination"),
    cursor: Optional[int] = Query(default=None, description="Cursor integer for keyset pagination"),
    sort_by: Optional[str] = Query(default=None, description="Permitted column to sort by"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort direction"),
    current_user: User = Depends(require_explorer_access),
    db: Session = Depends(get_db),
):
    """
    Retrieves paginated, sanitized records for a permitted table.
    Tier 3 tables (credential/session stores) raise 403 Forbidden.
    High-volume tables (metrics, ingested_batches) support keyset pagination.
    """
    # Normalize Query object defaults for direct invocations
    actual_limit = getattr(limit, "default", limit) if not isinstance(limit, int) else limit
    actual_page = getattr(page, "default", page) if not isinstance(page, int) else page
    actual_cursor = getattr(cursor, "default", cursor) if not (isinstance(cursor, int) or cursor is None) else cursor
    actual_sort_by = getattr(sort_by, "default", sort_by) if not (isinstance(sort_by, str) or sort_by is None) else sort_by
    actual_sort_order = getattr(sort_order, "default", sort_order) if not isinstance(sort_order, str) else sort_order

    records_resp = DatabaseExplorerService.get_table_records(
        table_name=table_name,
        limit=actual_limit,
        page=actual_page,
        cursor=actual_cursor,
        sort_by=actual_sort_by,
        sort_order=actual_sort_order,
    )

    # Avoid recursive audit log expansion when querying audit_logs table itself
    if table_name != "audit_logs":
        client_ip = request.client.host if request.client else "127.0.0.1"
        try:
            record_audit_action(
                db=db,
                action="DATABASE_EXPLORER_QUERY_RECORDS",
                target_resource=f"Table:{table_name}",
                details=(
                    f"Queried records from '{table_name}' [method: {records_resp.pagination_type}, "
                    f"returned: {len(records_resp.records)}, total: {records_resp.total_records}]. "
                    "Zero row contents logged."
                ),
                user_email=current_user.email,
                result="success",
                client_ip=client_ip,
            )
        except Exception:
            pass

    return records_resp
