"""
api/routes/goals.py
-------------------
Endpoints for savings goal tracking.
"""

from fastapi import APIRouter, Depends, status

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.models import GoalCreate, GoalUpdate, GoalResponse
from api.deps import get_current_user
from database import add_goal, get_goals, update_goal, delete_goal

router = APIRouter(prefix="/api/goals", tags=["Savings Goals"])


@router.get("/", response_model=list[GoalResponse])
def list_goals(user: dict = Depends(get_current_user)):
    """List all savings goals."""
    rows = get_goals(user["id"])
    return [GoalResponse(**r) for r in rows]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_goal(
    data: GoalCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new savings goal."""
    add_goal(user["id"], data.name, data.target_amount, data.saved_amount, data.deadline)
    return {"message": f"Goal '{data.name}' created."}


@router.put("/{goal_id}")
def edit_goal(
    goal_id: int,
    data: GoalUpdate,
    user: dict = Depends(get_current_user),
):
    """Update saved amount for a goal."""
    update_goal(goal_id, user["id"], data.saved_amount)
    return {"message": "Goal updated.", "id": goal_id}


@router.delete("/{goal_id}", status_code=status.HTTP_200_OK)
def remove_goal(
    goal_id: int,
    user: dict = Depends(get_current_user),
):
    """Delete a savings goal."""
    delete_goal(goal_id, user["id"])
    return {"message": "Goal deleted.", "id": goal_id}
