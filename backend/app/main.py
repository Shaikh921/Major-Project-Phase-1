"""
FastAPI Application Entry Point.

Initializes application configuration, database schemas, default rule seeds,
CORS middleware, and REST API routing for all platform modules.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from backend.app.core.config import settings
from backend.app.database.init_db import init_db
from backend.app.api.v1 import api_router

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager: initializes database schema and seeds on startup.
    """
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Backend API for cloud resource monitoring, "
        "AI-driven anomaly detection, cost optimization, "
        "security intrusion detection, and incident analysis."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

# Enable CORS for frontend dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/js") or path.startswith("/css") or path == "/" or path.endswith(".html") or path.endswith(".js"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Mount API Routers
app.include_router(api_router)


# Mount Static Frontend Files
if os.path.exists(FRONTEND_DIR):
    app.mount("/dashboard", StaticFiles(directory=FRONTEND_DIR, html=True), name="dashboard")
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


@app.get("/")
def root(request: Request):
    """Application root: returns JSON metadata for API clients or serves HTML if requested."""
    accept = request.headers.get("accept", "")
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if "text/html" in accept and os.path.exists(index_path):
        resp = FileResponse(index_path)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        return resp
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }


@app.get("/health")
def health_check():
    """Liveness probe endpoint."""
    return {
        "status": "healthy",
    }