"""
ai_insights.py
--------------
Smart AI-like insights generated entirely locally using:
  - pandas-based rule engine
  - simple statistical comparisons
  - scikit-learn LinearRegression for expense prediction
No external APIs or keys required.
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from analytics import get_df
from utils import fmt_currency


# ── Main insight dispatcher ───────────────────────────────────────────────────

def get_insights(user_id: int, currency_symbol: str = "₹") -> list[dict]:
    """
    Generate local, rule-based financial advice and reports based on user transaction history.
    No API keys or internet calls required.
    """
    df = get_df(user_id)
    if df.empty:
        return [{
            "icon": "📊", 
            "title": "Welcome to AI Insights!",
            "detail": "Add some transactions or load sample data to see personalized financial reports and alerts.",
            "level": "info"
        }]

    insights = []
    today = date.today()
    curr_m = today.strftime("%Y-%m")
    prev_m = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    # Filter dataframes
    df_exp = df[df["type"] == "expense"]
    df_inc = df[df["type"] == "income"]
    df_curr_exp = df_exp[df_exp["month"] == curr_m]
    df_prev_exp = df_exp[df_exp["month"] == prev_m]

    total_curr_inc = df_inc[df_inc["month"] == curr_m]["amount"].sum()
    total_curr_exp = df_curr_exp["amount"].sum()

    # ── 1. MONTHLY FINANCIAL REPORT (Summary info card) ───────────────────────
    savings = total_curr_inc - total_curr_exp
    savings_rate = (savings / total_curr_inc * 100) if total_curr_inc > 0 else 0.0
    
    report_title = f"Financial Summary for {today.strftime('%B %Y')}"
    if total_curr_inc > 0:
        report_detail = (
            f"Income: {fmt_currency(total_curr_inc, currency_symbol)} | "
            f"Expenses: {fmt_currency(total_curr_exp, currency_symbol)} | "
            f"Net Savings: {fmt_currency(savings, currency_symbol)} ({savings_rate:.1f}% savings rate)."
        )
    else:
        report_detail = (
            f"Expenses: {fmt_currency(total_curr_exp, currency_symbol)}. "
            f"No income recorded yet for this month. Log your income to track savings rate."
        )
    insights.append({
        "icon": "📝",
        "title": report_title,
        "detail": report_detail,
        "level": "info"
    })

    # ── 2. RISK ALERTS ────────────────────────────────────────────────────────
    # Risk: Overspending income
    if total_curr_inc > 0 and total_curr_exp > total_curr_inc:
        insights.append({
            "icon": "🚨",
            "title": "Overspending Risk: Expenses Exceed Income",
            "detail": f"You have spent {fmt_currency(total_curr_exp - total_curr_inc, currency_symbol)} more than your income this month. Consider freezing discretionary expenses.",
            "level": "warning"
        })
    
    # Risk: Budget overflow
    from database import get_budgets
    budgets = get_budgets(user_id, curr_m)
    for b in budgets:
        cat = b["category"]
        limit = b["amount"]
        spent = df_curr_exp[df_curr_exp["category"] == cat]["amount"].sum()
        if spent > limit:
            over = spent - limit
            insights.append({
                "icon": "🔴",
                "title": f"Budget Exceeded: {cat}",
                "detail": f"You exceeded your budget for {cat} by {fmt_currency(over, currency_symbol)} ({spent/limit*100:.0f}% utilized).",
                "level": "warning"
            })
        elif limit > 0 and spent / limit >= 0.85:
            insights.append({
                "icon": "⚠️",
                "title": f"Budget Warning: {cat}",
                "detail": f"You have used {spent/limit*100:.0f}% of your budget for {cat}. Remaining: {fmt_currency(limit - spent, currency_symbol)}.",
                "level": "warning"
            })

    # ── 3. SPENDING HABIT ANALYSIS ────────────────────────────────────────────
    # Category spending MoM change
    for cat in df_curr_exp["category"].unique():
        curr_amt = df_curr_exp[df_curr_exp["category"] == cat]["amount"].sum()
        prev_amt = df_prev_exp[df_prev_exp["category"] == cat]["amount"].sum()
        if prev_amt > 0:
            change = ((curr_amt - prev_amt) / prev_amt) * 100
            if change > 25:
                insights.append({
                    "icon": "📈",
                    "title": f"Increased Spending: {cat}",
                    "detail": f"Your spending in {cat} rose by {change:.0f}% MoM (from {fmt_currency(prev_amt, currency_symbol)} to {fmt_currency(curr_amt, currency_symbol)}).",
                    "level": "warning"
                })
            elif change < -20:
                insights.append({
                    "icon": "📉",
                    "title": f"Saved in {cat}!",
                    "detail": f"Awesome! Spending on {cat} is down by {abs(change):.0f}% MoM. You saved {fmt_currency(prev_amt - curr_amt, currency_symbol)}.",
                    "level": "success"
                })

    # Payment Mode over-reliance (e.g., Credit Card debt risk)
    if not df_curr_exp.empty:
        mode_sums = df_curr_exp.groupby("payment_mode")["amount"].sum()
        cc_amt = mode_sums.get("Credit Card", 0.0)
        upi_amt = mode_sums.get("UPI", 0.0)
        if cc_amt > total_curr_exp * 0.5:
            insights.append({
                "icon": "💳",
                "title": "High Credit Card Reliance",
                "detail": f"More than {cc_amt/total_curr_exp*100:.0f}% of your current monthly expenses are put on credit. Ensure you pay off the balance in full to avoid debt traps.",
                "level": "warning"
            })
        elif upi_amt > total_curr_exp * 0.6:
            insights.append({
                "icon": "📱",
                "title": "High UPI Usage",
                "detail": f"You spend mostly via UPI ({upi_amt/total_curr_exp*100:.0f}%). Since UPI requires minimal friction, it is easy to overspend. Consider tracking small payments.",
                "level": "tip"
            })

    # ── 4. BUDGET RECOMMENDATIONS ─────────────────────────────────────────────
    # Suggest budgets for high spending categories
    if not df_curr_exp.empty:
        cat_sums = df_curr_exp.groupby("category")["amount"].sum()
        active_budget_cats = {b["category"] for b in budgets}
        for cat, amt in cat_sums.items():
            if cat not in active_budget_cats and amt > 2000:
                insights.append({
                    "icon": "📋",
                    "title": f"Set a Budget for {cat}",
                    "detail": f"You spent {fmt_currency(amt, currency_symbol)} on {cat} this month, but have no budget set. Adding a budget helps regulate your flow.",
                    "level": "tip"
                })

    # ── 5. SAVINGS RECOMMENDATIONS ────────────────────────────────────────────
    # Emergency Fund analysis
    from database import get_goals
    goals = get_goals(user_id)
    emergency_goals = [g for g in goals if "emergency" in g["name"].lower()]
    avg_monthly_exp = df_exp.groupby("month")["amount"].sum().mean() if not df_exp.empty else 0.0
    
    if not emergency_goals and avg_monthly_exp > 0:
        recommended_target = avg_monthly_exp * 6
        insights.append({
            "icon": "🎯",
            "title": "Set up an Emergency Fund Goal",
            "detail": f"Based on your average monthly expenses, we recommend setting a savings goal of at least {fmt_currency(recommended_target, currency_symbol)} (6 months of runway).",
            "level": "tip"
        })
    elif emergency_goals:
        eg = emergency_goals[0]
        if avg_monthly_exp > 0 and eg["target_amount"] < avg_monthly_exp * 3:
            insights.append({
                "icon": "🛡️",
                "title": "Increase Emergency Fund Target",
                "detail": f"Your current emergency fund target ({fmt_currency(eg['target_amount'], currency_symbol)}) covers less than 3 months of expenses. Target at least {fmt_currency(avg_monthly_exp*6, currency_symbol)}.",
                "level": "warning"
            })

    # ── 6. PERSONALIZED TIPS ──────────────────────────────────────────────────
    # Top expense categories tips
    if not df_curr_exp.empty:
        top_cat = df_curr_exp.groupby("category")["amount"].sum().idxmax()
        top_amt = df_curr_exp.groupby("category")["amount"].sum().max()
        if top_cat == "Food":
            insights.append({
                "icon": "🍕",
                "title": "Reduce Dining and Takeout Costs",
                "detail": "Food is your top spending category this month. Try batch cooking or limiting ordering out to weekends to save up to 15% easily.",
                "level": "tip"
            })
        elif top_cat == "Entertainment":
            insights.append({
                "icon": "🎬",
                "title": "Look for Free Entertainment Options",
                "detail": "Entertainment costs are taking up a large portion of your money. Consider free public parks, community events, or board game nights with friends.",
                "level": "tip"
            })
        elif top_cat == "Shopping":
            insights.append({
                "icon": "🛍️",
                "title": "Implement the 48-Hour Buy Rule",
                "detail": "Before buying non-essential items, wait 48 hours. This simple check reduces impulse shopping by up to 60%.",
                "level": "tip"
            })

    # ── 7. FUTURE MONTH EXPENDITURE FORECAST ──────────────────────────────────
    prediction = _predict_month_expense(df_exp, curr_m, today)
    if prediction:
        insights.append({
            "icon": "🔮",
            "title": f"Forecasted Month-end Total: {fmt_currency(prediction, currency_symbol)}",
            "detail": f"At your current spending pace, we estimate you will end this month with a total expense of approximately {fmt_currency(prediction, currency_symbol)}.",
            "level": "tip"
        })

    # Fallback if no specific insights were triggered
    if len(insights) <= 1:
        insights.append({
            "icon": "✨",
            "title": "All Clean!",
            "detail": "Your financial logs show solid habits. Continue tracking consistently to build a richer savings profile.",
            "level": "success"
        })

    return insights


# ── Linear regression predictor ───────────────────────────────────────────────

def _predict_month_expense(df_exp: pd.DataFrame, curr_m: str, today: date) -> float | None:
    """
    Use a simple linear regression on cumulative daily spending of the current
    month to extrapolate end-of-month total.
    Returns predicted total or None if insufficient data.
    """
    try:
        from sklearn.linear_model import LinearRegression

        df_m = df_exp[df_exp["month"] == curr_m].copy()
        if len(df_m) < 4:
            return None

        df_m["day"] = df_m["trans_date"].dt.day
        daily = df_m.groupby("day")["amount"].sum().reset_index()
        daily = daily.sort_values("day")
        daily["cum"] = daily["amount"].cumsum()

        X = daily["day"].values.reshape(-1, 1)
        y = daily["cum"].values

        model = LinearRegression().fit(X, y)
        days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
        predicted = model.predict([[days_in_month]])[0]
        return max(0, predicted)
    except Exception:
        return None
