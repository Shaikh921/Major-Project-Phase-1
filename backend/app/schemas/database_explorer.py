"""
Pydantic schemas for the Database & Storage Explorer.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatabaseExplorerStatusResponse(BaseModel):
    enabled: bool = Field(..., description="Whether Database Explorer is enabled by deployment policy")
    engine: str = Field(default="SQLite", description="Database engine type")
    version: str = Field(..., description="Engine version string")
    read_only: bool = Field(default=True, description="Whether explorer sessions are strictly read-only")


class DatabaseOverviewResponse(BaseModel):
    status: str = Field(default="ONLINE", description="Operational connection state")
    engine: str = Field(default="SQLite", description="Database engine type")
    sqlite_version: str = Field(..., description="SQLite engine release version")
    journal_mode: str = Field(..., description="Active SQLite journal mode (e.g. wal)")
    database_file: str = Field(..., description="Canonical database file name")
    database_size_bytes: int = Field(..., description="Physical file size in bytes")
    database_size_mb: float = Field(..., description="Physical file size in megabytes")
    total_tables: int = Field(..., description="Total application tables available")
    total_records: int = Field(..., description="Total records across all application tables")
    tier_breakdown: Dict[str, int] = Field(..., description="Table counts per security tier")
    refreshed_at: datetime = Field(..., description="Timestamp of metadata inspection")


class ColumnInfo(BaseModel):
    cid: int
    name: str
    type: str
    notnull: bool
    default_value: Optional[str] = None
    primary_key: bool
    is_projected: bool = Field(..., description="Whether column is included in preview queries")


class IndexInfo(BaseModel):
    name: str
    unique: bool
    columns: List[str]
    is_autoindex: bool


class ForeignKeyInfo(BaseModel):
    id: int
    table: str
    from_column: str
    to_column: str


class TableSummaryResponse(BaseModel):
    name: str
    category: str
    security_tier: str
    preview_allowed: bool
    pagination_type: str
    total_columns: int
    projected_columns: int
    row_count: int
    primary_keys: List[str]
    foreign_keys_count: int
    index_count: int


class TableSchemaResponse(BaseModel):
    table: str
    category: str
    security_tier: str
    preview_allowed: bool
    pagination_type: str
    row_count: int
    columns: List[ColumnInfo]
    indexes: List[IndexInfo]
    foreign_keys: List[ForeignKeyInfo]


class TableRecordsResponse(BaseModel):
    table: str
    security_tier: str
    pagination_type: str
    total_records: int
    count_exact: bool = True
    limit: int
    page: Optional[int] = None
    total_pages: Optional[int] = None
    next_cursor: Optional[int] = None
    has_more: bool
    columns: List[str]
    records: List[Dict[str, Any]]
