"""
Lab Overview API Router.

Provides room-wise aggregation of lab PCs: online/offline status tracking,
latest CPU/memory/disk metrics, busiest machines triage, and room summaries.
Reads from existing hosts and metrics tables without requiring new database migrations.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_viewer
from backend.app.models.user import User
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.schemas.lab import (
    LabPCEntry,
    LabRoomSummary,
    LabTotalsSummary,
    LabSummaryResponse,
)

router = APIRouter(prefix="/lab", tags=["Lab"])


def _aware(ts: datetime) -> datetime:
    """Ensures datetime timestamps returned from SQLite are timezone-aware (UTC)."""
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def _cpu_level(cpu: Optional[float], online: bool) -> str:
    """
    Classifies CPU severity level aligned with system threshold rules:
    - Offline or no metric -> 'offline'
    - CPU >= 95.0% -> 'high' (critical operational saturation)
    - CPU >= 80.0% -> 'warning' (elevated load)
    - Otherwise -> 'normal' (healthy)
    """
    if not online or cpu is None:
        return "offline"
    if cpu >= 95.0:
        return "high"
    if cpu >= 80.0:
        return "warning"
    return "normal"


@router.get("/summary", response_model=LabSummaryResponse)
def get_lab_summary(
    environment: str = Query(default="lab", description="Target host environment to query"),
    offline_after_seconds: int = Query(
        default=90,
        ge=10,
        le=3600,
        description="Inactivity threshold in seconds before a PC is considered offline",
    ),
    real_agents_only: bool = Query(
        default=True,
        description="When true, excludes simulator hosts and includes only REAL_AGENT telemetry",
    ),
    current_user: User = Depends(get_current_viewer),
    db: Session = Depends(get_db),
) -> LabSummaryResponse:
    """
    Retrieves the aggregated status of lab PCs grouped by room (region).
    Calculates online/offline status using configurable heartbeat threshold,
    ranks busiest machines, and summarizes room resource consumption.
    Requires viewer authentication.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=offline_after_seconds)

    # 1. Scoped subquery: Identify host IDs in the requested environment
    host_filter = [Host.environment == environment, Host.is_active.is_(True)]
    if real_agents_only:
        host_filter.append(Host.source_type == "REAL_AGENT")

    scoped_host_ids = select(Host.id).where(and_(*host_filter))

    # 2. Optimized latest metric subquery: Restricted strictly to relevant hosts
    # Uses composite index ix_metrics_host_id_timestamp ("host_id", "timestamp")
    latest_ts_subquery = (
        select(Metric.host_id, func.max(Metric.timestamp).label("max_ts"))
        .where(Metric.host_id.in_(scoped_host_ids))
        .group_by(Metric.host_id)
        .subquery()
    )

    # 3. Outer join hosts with their latest metric sample
    stmt = (
        select(Host, Metric)
        .where(and_(*host_filter))
        .outerjoin(latest_ts_subquery, latest_ts_subquery.c.host_id == Host.id)
        .outerjoin(
            Metric,
            and_(
                Metric.host_id == latest_ts_subquery.c.host_id,
                Metric.timestamp == latest_ts_subquery.c.max_ts,
            ),
        )
        .order_by(Host.hostname)
    )

    rows = db.execute(stmt).all()

    # 4. Deduplicate rows (in case of duplicate timestamps) and build PC entries
    pcs_by_id: Dict[int, LabPCEntry] = {}
    for host, metric in rows:
        if host.id in pcs_by_id:
            continue

        last_seen = _aware(metric.timestamp) if metric and metric.timestamp else None
        online = bool(last_seen and last_seen >= cutoff)

        cpu_val = round(metric.cpu_percent, 1) if (metric and metric.cpu_percent is not None) else None
        mem_val = round(metric.memory_percent, 1) if (metric and metric.memory_percent is not None) else None
        disk_val = round(metric.disk_percent, 1) if (metric and metric.disk_percent is not None) else None

        pcs_by_id[host.id] = LabPCEntry(
            host_id=host.id,
            hostname=host.hostname,
            room=host.region or "unknown",
            ip_address=host.ip_address,
            online=online,
            last_seen=last_seen,
            cpu_percent=cpu_val,
            memory_percent=mem_val,
            disk_percent=disk_val,
            cpu_level=_cpu_level(cpu_val, online),
        )

    pc_list: List[LabPCEntry] = list(pcs_by_id.values())
    online_pcs = [p for p in pc_list if p.online]

    # 5. Room-wise grouping
    rooms_map: Dict[str, Dict[str, Any]] = {}
    for pc in pc_list:
        if pc.room not in rooms_map:
            rooms_map[pc.room] = {
                "room": pc.room,
                "total": 0,
                "online": 0,
                "offline": 0,
                "pcs": [],
            }
        r = rooms_map[pc.room]
        r["total"] += 1
        if pc.online:
            r["online"] += 1
        else:
            r["offline"] += 1
        r["pcs"].append(pc)

    room_summaries: List[LabRoomSummary] = []
    for room_name in sorted(rooms_map.keys()):
        r_data = rooms_map[room_name]
        online_room_cpus = [
            p.cpu_percent for p in r_data["pcs"] if p.online and p.cpu_percent is not None
        ]
        avg_room_cpu = (
            round(sum(online_room_cpus) / len(online_room_cpus), 1)
            if online_room_cpus
            else None
        )
        r_data["pcs"].sort(key=lambda x: x.hostname)
        room_summaries.append(
            LabRoomSummary(
                room=r_data["room"],
                total=r_data["total"],
                online=r_data["online"],
                offline=r_data["offline"],
                avg_cpu=avg_room_cpu,
                pcs=r_data["pcs"],
            )
        )

    # 6. Overall totals and busiest PCs ranking
    online_all_cpus = [
        p.cpu_percent for p in online_pcs if p.cpu_percent is not None
    ]
    total_avg_cpu = (
        round(sum(online_all_cpus) / len(online_all_cpus), 1)
        if online_all_cpus
        else None
    )

    busiest_candidates = [p for p in online_pcs if p.cpu_percent is not None]
    busiest = sorted(busiest_candidates, key=lambda x: (x.cpu_percent or 0.0), reverse=True)[:5]

    totals = LabTotalsSummary(
        total_pcs=len(pc_list),
        online=len(online_pcs),
        offline=len(pc_list) - len(online_pcs),
        avg_cpu=total_avg_cpu,
    )

    return LabSummaryResponse(
        generated_at=now,
        environment=environment,
        offline_after_seconds=offline_after_seconds,
        totals=totals,
        busiest_pcs=busiest,
        rooms=room_summaries,
    )
