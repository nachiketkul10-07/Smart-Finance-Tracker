"""
api/config.py
-------------
Centralised configuration for the FastAPI backend.
JWT secret, token expiry, CORS settings, etc.
"""

import os
import secrets

# ── JWT Settings ─────────────────────────────────────────────────────────────
# In production, set FINANCE_JWT_SECRET as an environment variable.
JWT_SECRET = os.environ.get("FINANCE_JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 60 * 24  # 24 hours

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS = [
    "http://localhost:3000",      # React / Next.js dev
    "http://localhost:8501",      # Streamlit
    "http://localhost:8080",      # Generic dev
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8501",
    "*",                          # Allow all in dev (restrict in prod)
]

# ── Database ─────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "finance.db")
