"""
api/models.py
-------------
Pydantic models (schemas) for request / response validation.
Covers every entity: User, Transaction, Budget, Goal, Recurring, Settings.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import date


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = ""


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = ""
    created_at: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTIONS
# ══════════════════════════════════════════════════════════════════════════════

class TransactionCreate(BaseModel):
    type: str = Field(..., pattern="^(income|expense)$")
    amount: float = Field(..., gt=0)
    category: str
    note: Optional[str] = ""
    payment_mode: str = "Cash"
    trans_date: date
    is_recurring: int = 0


class TransactionUpdate(BaseModel):
    type: Optional[str] = Field(None, pattern="^(income|expense)$")
    amount: Optional[float] = Field(None, gt=0)
    category: Optional[str] = None
    note: Optional[str] = None
    payment_mode: Optional[str] = None
    trans_date: Optional[date] = None


class TransactionResponse(BaseModel):
    id: int
    user_id: int
    type: str
    amount: float
    category: str
    note: Optional[str] = ""
    payment_mode: str
    trans_date: str
    is_recurring: int = 0
    created_at: Optional[str] = None


class TransactionFilters(BaseModel):
    type: Optional[str] = None
    category: Optional[str] = None
    month: Optional[str] = None       # YYYY-MM
    search: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = 100
    offset: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# BUDGETS
# ══════════════════════════════════════════════════════════════════════════════

class BudgetCreate(BaseModel):
    category: str
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")  # YYYY-MM
    amount: float = Field(..., gt=0)


class BudgetResponse(BaseModel):
    id: int
    user_id: int
    category: str
    month: str
    amount: float


class BudgetComparison(BaseModel):
    id: int
    category: str
    budget: float
    spent: float
    remaining: float
    pct_used: float


# ══════════════════════════════════════════════════════════════════════════════
# GOALS
# ══════════════════════════════════════════════════════════════════════════════

class GoalCreate(BaseModel):
    name: str = Field(..., min_length=1)
    target_amount: float = Field(..., gt=0)
    saved_amount: float = Field(0, ge=0)
    deadline: Optional[str] = None


class GoalUpdate(BaseModel):
    saved_amount: float = Field(..., ge=0)


class GoalResponse(BaseModel):
    id: int
    user_id: int
    name: str
    target_amount: float
    saved_amount: float
    deadline: Optional[str] = None
    created_at: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# RECURRING
# ══════════════════════════════════════════════════════════════════════════════

class RecurringCreate(BaseModel):
    type: str = Field(..., pattern="^(income|expense)$")
    amount: float = Field(..., gt=0)
    category: str
    note: Optional[str] = ""
    payment_mode: str = "Auto-Debit"
    frequency: str = Field("monthly", pattern="^(monthly|weekly)$")
    next_date: date


class RecurringResponse(BaseModel):
    id: int
    user_id: int
    type: str
    amount: float
    category: str
    note: Optional[str] = ""
    payment_mode: str
    frequency: str
    next_date: Optional[str] = None
    active: int = 1
    created_at: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

class SettingsUpdate(BaseModel):
    currency: str = "INR (₹)"
    theme: str = "dark"


class SettingsResponse(BaseModel):
    id: Optional[int] = None
    user_id: int
    currency: str = "INR (₹)"
    theme: str = "dark"
    updated_at: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS / SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

class SummaryResponse(BaseModel):
    total_income: float
    total_expense: float
    net_savings: float
    month_income: float
    month_expense: float
    month_savings: float


# ══════════════════════════════════════════════════════════════════════════════
# IMPORT
# ══════════════════════════════════════════════════════════════════════════════

class ImportPreview(BaseModel):
    """Returned after parsing a file, before user confirms import."""
    bank_detected: str
    total_transactions: int
    new_transactions: int
    duplicate_transactions: int
    transactions: list[TransactionResponse]


class ImportResult(BaseModel):
    imported: int
    duplicates_skipped: int
    errors: int
    message: str


class InsightResponse(BaseModel):
    icon: str
    title: str
    detail: str
    level: str  # info, warning, success, tip
