"""
api/routes/recurring.py
-----------------------
Endpoints for recurring transaction templates.
"""

from fastapi import APIRouter, Depends, status

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.models import RecurringCreate, RecurringResponse
from api.deps import get_current_user
from database import add_recurring, get_recurring, delete_recurring

router = APIRouter(prefix="/api/recurring", tags=["Recurring Transactions"])


@router.get("/", response_model=list[RecurringResponse])
def list_recurring(user: dict = Depends(get_current_user)):
    """List all active recurring transaction templates."""
    rows = get_recurring(user["id"])
    return [RecurringResponse(**r) for r in rows]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_recurring(
    data: RecurringCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new recurring transaction template."""
    add_recurring(
        user["id"], data.type, data.amount, data.category,
        data.note, data.payment_mode, data.frequency, str(data.next_date),
    )
    return {"message": "Recurring transaction saved."}


@router.delete("/{recurring_id}", status_code=status.HTTP_200_OK)
def remove_recurring(
    recurring_id: int,
    user: dict = Depends(get_current_user),
):
    """Deactivate a recurring transaction template."""
    delete_recurring(recurring_id, user["id"])
    return {"message": "Recurring transaction removed.", "id": recurring_id}
