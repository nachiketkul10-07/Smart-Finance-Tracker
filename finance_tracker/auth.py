"""
auth.py
-------
Handles user authentication: registration, login, logout.
Uses bcrypt for secure password hashing.
Manages Streamlit session state for login persistence.
"""

import bcrypt
import streamlit as st
from database import create_user, get_user_by_username


# ── Password helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches hashed."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── Session state helpers ────────────────────────────────────────────────────

def is_logged_in() -> bool:
    return st.session_state.get("user_id") is not None


def get_current_user() -> dict | None:
    return st.session_state.get("user_info")


def login_user(user: dict):
    """Store user info in session state."""
    st.session_state["user_id"]   = user["id"]
    st.session_state["user_info"] = user


def logout_user():
    """Clear session state."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# ── Registration ─────────────────────────────────────────────────────────────

def register(username: str, email: str, password: str, full_name: str = "") -> tuple[bool, str]:
    """
    Attempt to register a new user.
    Returns (success: bool, message: str).
    """
    # --- validation ---
    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters."
    if not email or "@" not in email:
        return False, "Please enter a valid email address."
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters."

    # --- check duplicate ---
    existing = get_user_by_username(username)
    if existing:
        return False, "Username already taken. Please choose another."

    # --- create user ---
    try:
        hashed = hash_password(password)
        create_user(username, email, hashed, full_name)
        return True, "Account created successfully! Please log in."
    except Exception as e:
        if "UNIQUE" in str(e):
            return False, "Email or username already registered."
        return False, f"Registration failed: {e}"


# ── Login ────────────────────────────────────────────────────────────────────

def login(username: str, password: str) -> tuple[bool, str]:
    """
    Attempt to log in.
    Returns (success: bool, message: str).
    On success, populates session state.
    """
    if not username or not password:
        return False, "Please enter both username and password."

    user = get_user_by_username(username)
    if not user:
        return False, "No account found with that username."

    if not verify_password(password, user["password"]):
        return False, "Incorrect password. Please try again."

    login_user(user)
    return True, f"Welcome back, {user.get('full_name') or user['username']}! 👋"
