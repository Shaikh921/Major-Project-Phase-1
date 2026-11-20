"""
API v1 Router aggregation.
"""

from fastapi import APIRouter
from backend.app.api.v1.hosts import router as hosts_router
from backend.app.api.v1.metrics import router as metrics_router
from backend.app.api.v1.alerts import router as alerts_router
from backend.app.api.v1.summary import router as summary_router
from backend.app.api.v1.forecast import router as forecast_router
from backend.app.api.v1.ai import router as ai_router
from backend.app.api.v1.security import router as security_router
from backend.app.api.v1.cost import router as cost_router
from backend.app.api.v1.narrator import router as narrator_router
from backend.app.api.v1.reports import router as reports_router
from backend.app.api.v1.audit import router as audit_router
from backend.app.api.v1.currency import router as currency_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.lab import router as lab_router
from backend.app.api.v1.devices import router as devices_router
from backend.app.api.v1.assignments import router as assignments_router
from backend.app.api.v1.diagnostics import router as diagnostics_router
from backend.app.api.v1.database_explorer import router as database_explorer_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(database_explorer_router)
api_router.include_router(assignments_router)
api_router.include_router(diagnostics_router)
# Backward-compatibility alias for sensor agents that append to server_url ending in /api/v1/metrics
api_router.include_router(diagnostics_router, prefix="/metrics/api/v1")
api_router.include_router(devices_router)
api_router.include_router(hosts_router)
api_router.include_router(metrics_router)
api_router.include_router(alerts_router)
api_router.include_router(summary_router)
api_router.include_router(forecast_router)
api_router.include_router(ai_router)
api_router.include_router(security_router)
api_router.include_router(cost_router)
api_router.include_router(narrator_router)
api_router.include_router(reports_router)
api_router.include_router(audit_router)
api_router.include_router(currency_router)
api_router.include_router(lab_router)


