"""
utils.py
--------
Shared constants, category definitions, keyword-to-category mapping,
currency formatters, and the sample demo data loader.
"""

import random
from datetime import date, timedelta
from database import add_transaction, add_goal, set_budget

# ── Categories ───────────────────────────────────────────────────────────────

INCOME_CATEGORIES = ["Salary", "Freelance", "Business", "Investment", "Other Income"]

EXPENSE_CATEGORIES = [
    "Food", "Travel", "Rent", "Shopping", "Bills",
    "Health", "Education", "Entertainment", "Subscription", "Other"
]

PAYMENT_MODES = ["Cash", "UPI", "Credit Card", "Debit Card", "Net Banking", "Auto-Debit", "Wallet"]

CURRENCIES = {
    "INR (₹)": "₹",
    "USD ($)": "$",
    "EUR (€)": "€",
    "GBP (£)": "£",
    "JPY (¥)": "¥",
}

# ── Category colour map (for charts) ─────────────────────────────────────────

CATEGORY_COLORS = {
    "Food":          "#FF6B6B",
    "Travel":        "#4ECDC4",
    "Rent":          "#45B7D1",
    "Shopping":      "#FFA07A",
    "Bills":         "#98D8C8",
    "Health":        "#FF8E53",
    "Education":     "#6C5CE7",
    "Entertainment": "#A29BFE",
    "Subscription":  "#00CEC9",
    "Other":         "#B2BEC3",
    "Salary":        "#00B894",
    "Freelance":     "#55EFC4",
    "Business":      "#0984E3",
    "Investment":    "#FDCB6E",
    "Other Income":  "#81ECEC",
}

# ── Keyword → Category mapper ─────────────────────────────────────────────────

KEYWORD_MAP = {
    # Travel
    "uber": "Travel", "ola": "Travel", "cab": "Travel", "taxi": "Travel",
    "fuel": "Travel", "petrol": "Travel", "diesel": "Travel", "bus": "Travel",
    "metro": "Travel", "train": "Travel", "flight": "Travel", "airline": "Travel",
    "airport": "Travel", "rapido": "Travel",
    # Food
    "pizza": "Food", "restaurant": "Food", "cafe": "Food", "coffee": "Food",
    "swiggy": "Food", "zomato": "Food", "lunch": "Food", "dinner": "Food",
    "breakfast": "Food", "burger": "Food", "biryani": "Food", "hotel": "Food",
    "canteen": "Food", "food": "Food", "snack": "Food", "tea": "Food",
    # Subscription
    "netflix": "Subscription", "spotify": "Subscription", "prime": "Subscription",
    "hotstar": "Subscription", "youtube": "Subscription", "subscription": "Subscription",
    "membership": "Subscription", "apple": "Subscription",
    # Health
    "doctor": "Health", "medicine": "Health", "pharmacy": "Health",
    "hospital": "Health", "clinic": "Health", "dentist": "Health",
    "gym": "Health", "medic": "Health", "chemist": "Health",
    # Shopping
    "amazon": "Shopping", "flipkart": "Shopping", "myntra": "Shopping",
    "shopping": "Shopping", "clothes": "Shopping", "shoes": "Shopping",
    "mall": "Shopping", "store": "Shopping",
    # Bills
    "electricity": "Bills", "water": "Bills", "internet": "Bills",
    "wifi": "Bills", "broadband": "Bills", "phone": "Bills",
    "mobile": "Bills", "recharge": "Bills", "bill": "Bills",
    # Education
    "course": "Education", "book": "Education", "udemy": "Education",
    "college": "Education", "tuition": "Education", "school": "Education",
    "exam": "Education", "coaching": "Education",
    # Entertainment
    "movie": "Entertainment", "cinema": "Entertainment", "game": "Entertainment",
    "gaming": "Entertainment", "concert": "Entertainment", "party": "Entertainment",
    "outing": "Entertainment",
    # Rent
    "rent": "Rent", "pg": "Rent", "hostel": "Rent", "flat": "Rent",
    # Income
    "salary": "Salary", "freelance": "Freelance", "dividend": "Investment",
    "interest": "Investment", "bonus": "Salary",
}


def auto_detect_category(note: str, trans_type: str = "expense") -> str:
    """Return the best-matching category for a note string."""
    if not note:
        return "Other" if trans_type == "expense" else "Other Income"
    note_lower = note.lower()
    for keyword, category in KEYWORD_MAP.items():
        if keyword in note_lower:
            return category
    return "Other" if trans_type == "expense" else "Other Income"


# ── Formatters ────────────────────────────────────────────────────────────────

def fmt_currency(amount: float, symbol: str = "₹") -> str:
    """Format a number as a currency string with Indian-style grouping."""
    if symbol == "₹":
        # Indian numbering: 1,00,000
        s = f"{abs(amount):.2f}"
        integer_part, decimal_part = s.split(".")
        if len(integer_part) > 3:
            last3 = integer_part[-3:]
            rest   = integer_part[:-3]
            groups = []
            while len(rest) > 2:
                groups.insert(0, rest[-2:])
                rest = rest[:-2]
            if rest:
                groups.insert(0, rest)
            integer_part = ",".join(groups) + "," + last3
        sign = "-" if amount < 0 else ""
        return f"{sign}{symbol}{integer_part}.{decimal_part}"
    else:
        return f"{symbol}{abs(amount):,.2f}"


def month_options(n: int = 12) -> list[str]:
    """Return a list of the last n months as 'YYYY-MM' strings."""
    today = date.today()
    months = []
    for i in range(n):
        m = today.replace(day=1) - timedelta(days=i * 28)
        months.append(m.strftime("%Y-%m"))
    return months


def current_month() -> str:
    return date.today().strftime("%Y-%m")


# ── Sample data loader ────────────────────────────────────────────────────────

def load_sample_data(user_id: int):
    """Insert realistic demo transactions, budgets, and goals for a new user."""
    today = date.today()

    # Helper to get a date within the last 90 days
    def rand_date(days_back=90):
        return (today - timedelta(days=random.randint(0, days_back))).isoformat()

    income_samples = [
        (55000,  "Salary",     "Monthly salary",           "Net Banking"),
        (12000,  "Freelance",  "Website project payment",  "UPI"),
        (3500,   "Investment", "Dividend received",        "Net Banking"),
        (55000,  "Salary",     "Monthly salary",           "Net Banking"),
        (8000,   "Freelance",  "Logo design",              "UPI"),
    ]

    expense_samples = [
        (450,  "Food",         "Swiggy order",         "UPI"),
        (1200, "Shopping",     "Amazon purchase",      "Credit Card"),
        (350,  "Travel",       "Uber cab",             "UPI"),
        (199,  "Subscription", "Netflix subscription", "Credit Card"),
        (149,  "Subscription", "Spotify premium",      "Credit Card"),
        (3500, "Rent",         "Room rent",            "Net Banking"),
        (800,  "Food",         "Zomato biryani",       "UPI"),
        (2200, "Health",       "Doctor consultation",  "Cash"),
        (600,  "Bills",        "Electricity bill",     "Net Banking"),
        (500,  "Entertainment","Movie tickets",         "UPI"),
        (1800, "Education",    "Udemy course",         "Credit Card"),
        (700,  "Food",         "Restaurant dinner",    "Credit Card"),
        (250,  "Travel",       "Metro recharge",       "UPI"),
        (1500, "Shopping",     "Myntra clothes",       "Credit Card"),
        (400,  "Food",         "Cafe coffee",          "Cash"),
        (999,  "Bills",        "Internet bill",        "Auto-Debit"),
        (3500, "Rent",         "Room rent",            "Net Banking"),
        (600,  "Food",         "Pizza party",          "UPI"),
        (200,  "Travel",       "Rapido ride",          "UPI"),
        (850,  "Health",       "Medicine pharmacy",    "Cash"),
        (300,  "Entertainment","Gaming subscription",  "Credit Card"),
        (450,  "Food",         "Lunch at canteen",     "Cash"),
        (1100, "Shopping",     "Flipkart gadget",      "Debit Card"),
        (650,  "Bills",        "Mobile recharge",      "UPI"),
        (500,  "Travel",       "Petrol fill",          "Cash"),
    ]

    for amount, category, note, mode in income_samples:
        add_transaction(user_id, "income", amount + random.randint(-500, 500),
                        category, note, mode, rand_date(60))

    for amount, category, note, mode in expense_samples:
        add_transaction(user_id, "expense", amount + random.randint(-50, 50),
                        category, note, mode, rand_date(90))

    # Budgets for current month
    budgets = {
        "Food": 6000, "Travel": 3000, "Shopping": 5000,
        "Bills": 2500, "Health": 3000, "Entertainment": 2000,
        "Subscription": 1000, "Education": 2000,
    }
    for cat, amt in budgets.items():
        set_budget(user_id, cat, current_month(), amt)

    # Goals
    from database import add_goal
    add_goal(user_id, "Emergency Fund",  100000, 35000, (today + timedelta(days=365)).isoformat())
    add_goal(user_id, "New Laptop",       80000, 20000, (today + timedelta(days=180)).isoformat())
    add_goal(user_id, "Goa Trip",         25000,  8000, (today + timedelta(days=90)).isoformat())
    add_goal(user_id, "iPhone Upgrade",  100000,  5000, (today + timedelta(days=300)).isoformat())
