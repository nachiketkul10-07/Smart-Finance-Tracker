"""
api/routes/budgets.py
---------------------
Endpoints for monthly budget management.
"""

from fastapi import APIRouter, Depends, status

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.models import BudgetCreate, BudgetResponse, BudgetComparison
from api.deps import get_current_user
from database import set_budget, get_budgets, delete_budget
from analytics import get_budget_comparison

router = APIRouter(prefix="/api/budgets", tags=["Budgets"])


@router.get("/{month}", response_model=list[BudgetResponse])
def list_budgets(
    month: str,
    user: dict = Depends(get_current_user),
):
    """List all budgets for a given month (YYYY-MM)."""
    rows = get_budgets(user["id"], month)
    return [BudgetResponse(user_id=user["id"], **r) for r in rows]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_or_update_budget(
    data: BudgetCreate,
    user: dict = Depends(get_current_user),
):
    """Set or update a budget for a category/month."""
    set_budget(user["id"], data.category, data.month, data.amount)
    return {"message": f"Budget for {data.category} in {data.month} set to {data.amount}."}


@router.delete("/{budget_id}", status_code=status.HTTP_200_OK)
def remove_budget(
    budget_id: int,
    user: dict = Depends(get_current_user),
):
    """Delete a budget."""
    delete_budget(budget_id, user["id"])
    return {"message": "Budget deleted.", "id": budget_id}


@router.get("/{month}/comparison", response_model=list[BudgetComparison])
def budget_comparison(
    month: str,
    user: dict = Depends(get_current_user),
):
    """Get budget vs actual spending comparison for a month."""
    df = get_budget_comparison(user["id"], month)
    if df.empty:
        return []
    return [BudgetComparison(**row) for row in df.to_dict("records")]
