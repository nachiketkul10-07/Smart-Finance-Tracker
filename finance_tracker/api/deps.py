"""
api/deps.py
-----------
Shared dependencies for FastAPI routes.
JWT token creation / verification and the get_current_user dependency.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from api.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_MINUTES

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_user_by_id


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Token helpers ────────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Current user dependency ──────────────────────────────────────────────────

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    """
    FastAPI dependency — extracts the user from the JWT token.
    Use as: user = Depends(get_current_user)
    """
    payload = verify_token(token)
    user_id = int(payload["sub"])
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    return user
