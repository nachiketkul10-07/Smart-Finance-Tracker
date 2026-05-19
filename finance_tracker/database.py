"""
database.py
-----------
Handles all database operations using SQLite + sqlite3.
Creates tables on first run, provides CRUD helpers for every entity.
"""

import sqlite3
import os
from datetime import datetime, date

# ── Path to the SQLite file ──────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "finance.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


# ── Connection helper ────────────────────────────────────────────────────────
def get_connection():
    """Return a sqlite3 connection with row_factory set to dict-like Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Schema creation (idempotent) ─────────────────────────────────────────────
def init_db():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    c = conn.cursor()

    # users
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    UNIQUE NOT NULL,
            email       TEXT    UNIQUE NOT NULL,
            password    TEXT    NOT NULL,
            full_name   TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # settings  (one row per user)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER UNIQUE NOT NULL REFERENCES users(id),
            currency    TEXT    DEFAULT 'INR',
            theme       TEXT    DEFAULT 'dark',
            updated_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # transactions
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            type            TEXT    NOT NULL CHECK(type IN ('income','expense')),
            amount          REAL    NOT NULL,
            category        TEXT    NOT NULL,
            note            TEXT,
            payment_mode    TEXT    DEFAULT 'Cash',
            trans_date      TEXT    NOT NULL,
            is_recurring    INTEGER DEFAULT 0,
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    # budgets  (per category, per month)
    c.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            category    TEXT    NOT NULL,
            month       TEXT    NOT NULL,   -- 'YYYY-MM'
            amount      REAL    NOT NULL,
            UNIQUE(user_id, category, month)
        )
    """)

    # goals
    c.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            name            TEXT    NOT NULL,
            target_amount   REAL    NOT NULL,
            saved_amount    REAL    DEFAULT 0,
            deadline        TEXT,
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    # recurring_transactions  (template rows)
    c.execute("""
        CREATE TABLE IF NOT EXISTS recurring_transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            type            TEXT    NOT NULL,
            amount          REAL    NOT NULL,
            category        TEXT    NOT NULL,
            note            TEXT,
            payment_mode    TEXT    DEFAULT 'Auto-Debit',
            frequency       TEXT    DEFAULT 'monthly',  -- monthly / weekly
            next_date       TEXT,
            active          INTEGER DEFAULT 1,
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# USER helpers
# ══════════════════════════════════════════════════════════════════════════════

def create_user(username: str, email: str, hashed_pw: str, full_name: str = "") -> int:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (username, email, password, full_name) VALUES (?,?,?,?)",
            (username.strip(), email.strip().lower(), hashed_pw, full_name.strip())
        )
        user_id = c.lastrowid
        # Create default settings row
        c.execute("INSERT INTO settings (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return user_id
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS helpers
# ══════════════════════════════════════════════════════════════════════════════

def get_settings(user_id: int) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else {"currency": "INR", "theme": "dark"}
    finally:
        conn.close()


def update_settings(user_id: int, currency: str, theme: str):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO settings (user_id, currency, theme)
               VALUES (?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET currency=excluded.currency,
               theme=excluded.theme, updated_at=datetime('now')""",
            (user_id, currency, theme)
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTION helpers
# ══════════════════════════════════════════════════════════════════════════════

def add_transaction(user_id, type_, amount, category, note, payment_mode, trans_date, is_recurring=0):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO transactions
               (user_id,type,amount,category,note,payment_mode,trans_date,is_recurring)
               VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, type_, float(amount), category, note, payment_mode,
             str(trans_date), is_recurring)
        )
        conn.commit()
    finally:
        conn.close()


def get_transactions(user_id: int, filters: dict = None):
    """
    Return all transactions for a user, optionally filtered.
    filters keys: type, category, month (YYYY-MM), search (note contains)
    """
    conn = get_connection()
    try:
        query = "SELECT * FROM transactions WHERE user_id = ?"
        params = [user_id]
        if filters:
            if filters.get("type"):
                query += " AND type = ?"
                params.append(filters["type"])
            if filters.get("category"):
                query += " AND category = ?"
                params.append(filters["category"])
            if filters.get("month"):
                query += " AND strftime('%Y-%m', trans_date) = ?"
                params.append(filters["month"])
            if filters.get("search"):
                query += " AND note LIKE ?"
                params.append(f"%{filters['search']}%")
        query += " ORDER BY trans_date DESC, id DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_transaction(trans_id: int, user_id: int, **kwargs):
    """Update allowed fields on a transaction row."""
    allowed = {"type", "amount", "category", "note", "payment_mode", "trans_date"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    params = list(updates.values()) + [trans_id, user_id]
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE transactions SET {set_clause} WHERE id=? AND user_id=?", params
        )
        conn.commit()
    finally:
        conn.close()


def delete_transaction(trans_id: int, user_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM transactions WHERE id=? AND user_id=?", (trans_id, user_id)
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# BUDGET helpers
# ══════════════════════════════════════════════════════════════════════════════

def set_budget(user_id: int, category: str, month: str, amount: float):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO budgets (user_id, category, month, amount) VALUES (?,?,?,?)
               ON CONFLICT(user_id,category,month) DO UPDATE SET amount=excluded.amount""",
            (user_id, category, month, amount)
        )
        conn.commit()
    finally:
        conn.close()


def get_budgets(user_id: int, month: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM budgets WHERE user_id=? AND month=?", (user_id, month)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_budget(budget_id: int, user_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM budgets WHERE id=? AND user_id=?", (budget_id, user_id)
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# GOALS helpers
# ══════════════════════════════════════════════════════════════════════════════

def add_goal(user_id, name, target_amount, saved_amount=0, deadline=None):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO goals (user_id,name,target_amount,saved_amount,deadline) VALUES (?,?,?,?,?)",
            (user_id, name, target_amount, saved_amount, deadline)
        )
        conn.commit()
    finally:
        conn.close()


def get_goals(user_id: int) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM goals WHERE user_id=? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_goal(goal_id: int, user_id: int, saved_amount: float):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE goals SET saved_amount=? WHERE id=? AND user_id=?",
            (saved_amount, goal_id, user_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_goal(goal_id: int, user_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM goals WHERE id=? AND user_id=?", (goal_id, user_id)
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# RECURRING helpers
# ══════════════════════════════════════════════════════════════════════════════

def add_recurring(user_id, type_, amount, category, note, payment_mode, frequency, next_date):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO recurring_transactions
               (user_id,type,amount,category,note,payment_mode,frequency,next_date)
               VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, type_, amount, category, note, payment_mode, frequency, str(next_date))
        )
        conn.commit()
    finally:
        conn.close()


def get_recurring(user_id: int) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM recurring_transactions WHERE user_id=? AND active=1", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_recurring(rec_id: int, user_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE recurring_transactions SET active=0 WHERE id=? AND user_id=?",
            (rec_id, user_id)
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# RESET / WIPE
# ══════════════════════════════════════════════════════════════════════════════

def reset_user_data(user_id: int):
    """Delete all financial data for a user (keep account)."""
    conn = get_connection()
    try:
        for table in ("transactions", "budgets", "goals", "recurring_transactions"):
            conn.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()
