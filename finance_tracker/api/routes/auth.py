"""
api/routes/auth.py
------------------
Authentication endpoints: register, login.
Returns JWT tokens for authenticated sessions.
"""

from fastapi import APIRouter, HTTPException, status

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.models import UserRegister, UserLogin, TokenResponse, UserResponse
from api.deps import create_access_token
from database import create_user, get_user_by_username
from auth import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister):
    """Register a new user account."""
    # Check duplicate
    existing = get_user_by_username(data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken."
        )

    try:
        hashed = hash_password(data.password)
        user_id = create_user(data.username, data.email, hashed, data.full_name or "")
        user = get_user_by_username(data.username)
        return UserResponse(**user)
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email or username already registered."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {e}"
        )


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin):
    """Authenticate and receive a JWT access token."""
    if not data.username or not data.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required."
        )

    user = get_user_by_username(data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account found with that username."
        )

    if not verify_password(data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password."
        )

    token = create_access_token(user["id"], user["username"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(**user),
    )
