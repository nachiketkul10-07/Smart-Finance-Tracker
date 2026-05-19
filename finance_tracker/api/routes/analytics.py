"""
api/routes/analytics.py
-----------------------
Endpoints for financial summaries, insights, and export.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.models import SummaryResponse, InsightResponse
from api.deps import get_current_user
from analytics import get_summary
from ai_insights import get_insights
from export_utils import export_excel, export_pdf
from utils import CURRENCIES

router = APIRouter(prefix="/api/analytics", tags=["Analytics & Reports"])


@router.get("/summary", response_model=SummaryResponse)
def financial_summary(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    user: dict = Depends(get_current_user),
):
    """Get financial summary (totals, monthly breakdown)."""
    summary = get_summary(user["id"], month)
    return SummaryResponse(**summary)


@router.get("/insights", response_model=list[InsightResponse])
def ai_insights(user: dict = Depends(get_current_user)):
    """Get AI-powered spending insights."""
    from database import get_settings
    cfg = get_settings(user["id"])
    sym = CURRENCIES.get(cfg.get("currency", "INR (₹)"), "₹")
    insights = get_insights(user["id"], sym)
    return [InsightResponse(**i) for i in insights]


@router.get("/export/excel")
def download_excel(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    user: dict = Depends(get_current_user),
):
    """Download an Excel (.xlsx) report."""
    from database import get_settings
    cfg = get_settings(user["id"])
    sym = CURRENCIES.get(cfg.get("currency", "INR (₹)"), "₹")
    xlsx_bytes = export_excel(user["id"], month, sym)
    filename = f"finance_{month or 'all'}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/pdf")
def download_pdf(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    user: dict = Depends(get_current_user),
):
    """Download a PDF summary report."""
    from database import get_settings
    cfg = get_settings(user["id"])
    sym = CURRENCIES.get(cfg.get("currency", "INR (₹)"), "₹")
    pdf_bytes = export_pdf(user["id"], month, sym)
    filename = f"finance_report_{month or 'all'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
