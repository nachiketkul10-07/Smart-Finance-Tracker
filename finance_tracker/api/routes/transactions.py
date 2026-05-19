"""
api/routes/transactions.py
--------------------------
CRUD endpoints for income & expense transactions.
Supports filtering, pagination, and bulk operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.models import (
    TransactionCreate, TransactionUpdate, TransactionResponse
)
from api.deps import get_current_user
from database import (
    add_transaction, get_transactions, update_transaction, delete_transaction
)

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.get("/", response_model=list[TransactionResponse])
def list_transactions(
    type: Optional[str] = Query(None, pattern="^(income|expense)$"),
    category: Optional[str] = None,
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """List transactions with optional filters."""
    filters = {}
    if type:     filters["type"] = type
    if category: filters["category"] = category
    if month:    filters["month"] = month
    if search:   filters["search"] = search

    rows = get_transactions(user["id"], filters or None)

    # Manual pagination (DB doesn't support LIMIT/OFFSET in current impl)
    paginated = rows[offset: offset + limit]
    return [TransactionResponse(**r) for r in paginated]


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: TransactionCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new transaction."""
    add_transaction(
        user["id"], data.type, data.amount, data.category,
        data.note, data.payment_mode, str(data.trans_date), data.is_recurring,
    )
    # Fetch the most recent transaction for this user
    rows = get_transactions(user["id"])
    if rows:
        return TransactionResponse(**rows[0])
    raise HTTPException(status_code=500, detail="Failed to create transaction.")


@router.put("/{transaction_id}", response_model=dict)
def edit_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    user: dict = Depends(get_current_user),
):
    """Update an existing transaction."""
    updates = data.model_dump(exclude_unset=True)
    if "trans_date" in updates and updates["trans_date"]:
        updates["trans_date"] = str(updates["trans_date"])
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    update_transaction(transaction_id, user["id"], **updates)
    return {"message": "Transaction updated.", "id": transaction_id}


@router.delete("/{transaction_id}", status_code=status.HTTP_200_OK)
def remove_transaction(
    transaction_id: int,
    user: dict = Depends(get_current_user),
):
    """Delete a transaction."""
    delete_transaction(transaction_id, user["id"])
    return {"message": "Transaction deleted.", "id": transaction_id}
