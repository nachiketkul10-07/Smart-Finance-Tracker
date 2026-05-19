"""
api/routes/imports.py
---------------------
Endpoints for importing transactions from external sources:
  - Bank statement CSV / Excel / PDF
  - UPI screenshot OCR (Phase 2)
  - Gmail email sync (Phase 3)
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.models import ImportResult
from api.deps import get_current_user

router = APIRouter(prefix="/api/import", tags=["Import"])


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — Bank Statement Import
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/bank-statement", response_model=ImportResult)
async def import_bank_statement(
    file: UploadFile = File(...),
    bank: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """
    Upload a bank statement (CSV, XLS, XLSX, or PDF).
    The system auto-detects the bank and parses transactions.
    Optionally specify the bank name to skip auto-detection.
    """
    # Validate file type
    allowed_ext = {".csv", ".xls", ".xlsx", ".pdf"}
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed_ext)}",
        )

    try:
        from bank_parser import parse_statement, import_transactions
        file_bytes = await file.read()
        result = parse_statement(file_bytes, ext, user["id"], bank_hint=bank)
        return ImportResult(**result)
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Bank parser module not yet available.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse statement: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — UPI Screenshot OCR  (stub — will be implemented in Phase 2)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/upi-screenshot", response_model=ImportResult)
async def import_upi_screenshot(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a UPI transaction screenshot for OCR-based import."""
    allowed_ext = {".png", ".jpg", ".jpeg", ".webp"}
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in allowed_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type. Allowed: {', '.join(allowed_ext)}",
        )

    try:
        from ocr_parser import parse_upi_screenshot
        file_bytes = await file.read()
        result = parse_upi_screenshot(file_bytes, user["id"])
        return ImportResult(**result)
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OCR module not yet available. Coming in Phase 2.",
        )


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3 — Gmail Email Sync
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/gmail-sync")
async def import_gmail(
    days_back: int = 30,
    user: dict = Depends(get_current_user),
):
    """Sync bank transaction alert emails from Gmail."""
    try:
        from gmail_parser import sync_gmail_transactions
        result = sync_gmail_transactions(user["id"], days_back)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gmail sync failed: {str(e)}",
        )


@router.get("/gmail-status")
async def gmail_status(user: dict = Depends(get_current_user)):
    """Check Gmail connection status."""
    from gmail_parser import is_credentials_available, is_authenticated, get_connected_email
    has_creds = is_credentials_available()
    authenticated = is_authenticated()
    email = get_connected_email() if authenticated else None
    return {
        "has_credentials": has_creds,
        "authenticated": authenticated,
        "email": email,
    }


@router.post("/gmail-connect")
async def gmail_connect(user: dict = Depends(get_current_user)):
    """Start Gmail OAuth2 connection (opens browser locally)."""
    from gmail_parser import authenticate_local
    result = authenticate_local()
    return result


@router.post("/gmail-disconnect")
async def gmail_disconnect(user: dict = Depends(get_current_user)):
    """Disconnect Gmail account."""
    from gmail_parser import disconnect
    return disconnect()
