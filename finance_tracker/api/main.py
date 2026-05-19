"""
api/main.py
-----------
FastAPI application entry point.
Mounts all route modules, configures CORS, and initialises the database.

Run with:
    uvicorn api.main:app --reload --port 8000
"""

import sys
import os
from pathlib import Path

# Ensure the finance_tracker directory is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.config import CORS_ORIGINS
from api.routes import auth, transactions, budgets, goals, recurring, settings, analytics, imports
from database import init_db

# ── Initialise database ─────────────────────────────────────────────────────
init_db()

# ── Create FastAPI app ───────────────────────────────────────────────────────
app = FastAPI(
    title="Smart Finance Tracker API",
    description=(
        "RESTful API for the Smart Finance Tracker.\n\n"
        "Features: JWT auth, transactions CRUD, budgets, savings goals, "
        "recurring entries, AI insights, bank statement import, and more.\n\n"
        "Built with FastAPI + SQLite — runs 100% locally."
    ),
    version="2.0.0",
    docs_url="/docs",           # Swagger UI
    redoc_url="/redoc",         # ReDoc
    openapi_url="/openapi.json",
)

# ── CORS middleware ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount route modules ──────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(budgets.router)
app.include_router(goals.router)
app.include_router(recurring.router)
app.include_router(settings.router)
app.include_router(analytics.router)
app.include_router(imports.router)

# ── Mobile PWA static files ─────────────────────────────────────────────────
MOBILE_DIR = Path(__file__).resolve().parent.parent / "mobile"
if MOBILE_DIR.exists():
    @app.get("/mobile", include_in_schema=False)
    @app.get("/mobile/", include_in_schema=False)
    async def mobile_index():
        return FileResponse(MOBILE_DIR / "index.html")

    app.mount("/mobile", StaticFiles(directory=str(MOBILE_DIR)), name="mobile")


# ── Root endpoint ────────────────────────────────────────────────────────────
@app.get("/", tags=["Status"])
def root():
    return {
        "app": "Smart Finance Tracker API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "mobile": "/mobile",
        "endpoints": {
            "auth": "/api/auth/",
            "transactions": "/api/transactions/",
            "budgets": "/api/budgets/",
            "goals": "/api/goals/",
            "recurring": "/api/recurring/",
            "settings": "/api/settings/",
            "analytics": "/api/analytics/",
            "import": "/api/import/",
        },
    }


@app.get("/health", tags=["Status"])
def health_check():
    return {"status": "healthy"}

