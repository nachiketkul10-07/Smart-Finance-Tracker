"""
api/routes/settings.py
----------------------
Endpoints for user settings and data management.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.models import SettingsUpdate, SettingsResponse
from api.deps import get_current_user
from database import get_settings, update_settings, reset_user_data

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/", response_model=SettingsResponse)
def get_user_settings(user: dict = Depends(get_current_user)):
    """Get current user settings."""
    cfg = get_settings(user["id"])
    return SettingsResponse(user_id=user["id"], **cfg)


@router.put("/")
def save_settings(
    data: SettingsUpdate,
    user: dict = Depends(get_current_user),
):
    """Update user settings (currency, theme)."""
    update_settings(user["id"], data.currency, data.theme)
    return {"message": "Settings saved."}


@router.post("/reset-data", status_code=status.HTTP_200_OK)
def reset_data(
    user: dict = Depends(get_current_user),
):
    """Delete ALL financial data for the user (transactions, budgets, goals, recurring). Account remains."""
    reset_user_data(user["id"])
    return {"message": "All financial data has been reset."}


@router.get("/backup")
def download_backup(user: dict = Depends(get_current_user)):
    """Download the SQLite database file as a backup."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "finance.db")
    if not os.path.exists(db_path):
        return {"error": "Database file not found."}
    return FileResponse(
        db_path,
        media_type="application/octet-stream",
        filename="finance_backup.db",
    )
