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
    Return a list of insight dicts: {icon, title, detail, level}
    level: 'info' | 'warning' | 'success' | 'tip'
    """
    df = get_df(user_id)
    if df.empty:
        return [{"icon": "📊", "title": "No data yet",
                 "detail": "Add some transactions to start seeing smart insights.",
                 "level": "info"}]

    insights = []
    today    = date.today()
    curr_m   = today.strftime("%Y-%m")
    prev_m   = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    df_exp  = df[df["type"] == "expense"]
    df_curr = df_exp[df_exp["month"] == curr_m]
    df_prev = df_exp[df_exp["month"] == prev_m]

    # 1. Category spending change vs last month
    for cat in df_curr["category"].unique():
        curr_amt = df_curr[df_curr["category"] == cat]["amount"].sum()
        prev_amt = df_prev[df_prev["category"] == cat]["amount"].sum()
        if prev_amt > 0:
            change_pct = ((curr_amt - prev_amt) / prev_amt) * 100
            if change_pct > 25:
                insights.append({
                    "icon": "📈",
                    "title": f"{cat} spending up {change_pct:.0f}%",
                    "detail": f"You spent {fmt_currency(curr_amt, currency_symbol)} on {cat} this month vs "
                              f"{fmt_currency(prev_amt, currency_symbol)} last month.",
                    "level": "warning",
                })
            elif change_pct < -20:
                insights.append({
                    "icon": "📉",
                    "title": f"Great! {cat} spending down {abs(change_pct):.0f}%",
                    "detail": f"You reduced {cat} expenses by {fmt_currency(prev_amt - curr_amt, currency_symbol)} vs last month.",
                    "level": "success",
                })

    # 2. Highest spending category this month
    if not df_curr.empty:
        top_cat = df_curr.groupby("category")["amount"].sum().idxmax()
        top_amt = df_curr.groupby("category")["amount"].sum().max()
        insights.append({
            "icon": "🏆",
            "title": f"Top spend: {top_cat}",
            "detail": f"You spent the most on {top_cat} this month — {fmt_currency(top_amt, currency_symbol)}.",
            "level": "info",
        })

    # 3. Unusual high single expense detection (> 2x avg)
    if not df_curr.empty:
        avg_exp = df_curr["amount"].mean()
        big_txns = df_curr[df_curr["amount"] > avg_exp * 2.5]
        for _, row in big_txns.iterrows():
            insights.append({
                "icon": "⚠️",
                "title": f"Unusual expense detected",
                "detail": f"A {row['category']} transaction of {fmt_currency(row['amount'], currency_symbol)} "
                          f"on {row['trans_date'].strftime('%d %b')} is {row['amount']/avg_exp:.1f}x your average.",
                "level": "warning",
            })

    # 4. Budget exceeded check
    from database import get_budgets
    budgets = get_budgets(user_id, curr_m)
    for b in budgets:
        cat   = b["category"]
        limit = b["amount"]
        spent = df_curr[df_curr["category"] == cat]["amount"].sum()
        if spent > limit:
            over = spent - limit
            insights.append({
                "icon": "🚨",
                "title": f"Budget exceeded: {cat}",
                "detail": f"You've overspent by {fmt_currency(over, currency_symbol)} in {cat} this month.",
                "level": "warning",
            })
        elif limit > 0 and spent / limit > 0.80:
            insights.append({
                "icon": "🔔",
                "title": f"Budget almost full: {cat}",
                "detail": f"You've used {spent/limit*100:.0f}% of your {cat} budget.",
                "level": "warning",
            })

    # 5. Predicted month-end expense (linear regression on daily cumulative)
    prediction = _predict_month_expense(df_exp, curr_m, today)
    if prediction:
        insights.append({
            "icon": "🔮",
            "title": "Predicted month-end expense",
            "detail": f"Based on your spending pattern, you'll spend about {fmt_currency(prediction, currency_symbol)} by end of this month.",
            "level": "tip",
        })

    # 6. Best day of week (lowest avg spend)
    if not df_exp.empty:
        day_avg = df_exp.groupby("day_name")["amount"].mean()
        best_day = day_avg.idxmin()
        insights.append({
            "icon": "✨",
            "title": f"Your cheapest day: {best_day}",
            "detail": f"On average you spend the least on {best_day}s — a great day to relax without spending!",
            "level": "tip",
        })

    # 7. Savings tracking
    df_inc_curr = df[(df["type"] == "income") & (df["month"] == curr_m)]
    total_inc   = df_inc_curr["amount"].sum()
    total_exp_curr = df_curr["amount"].sum()
    if total_inc > 0:
        savings_rate = (total_inc - total_exp_curr) / total_inc * 100
        if savings_rate >= 20:
            insights.append({
                "icon": "🎉",
                "title": f"Excellent savings rate: {savings_rate:.0f}%",
                "detail": f"You're saving {savings_rate:.0f}% of your income this month. Well done!",
                "level": "success",
            })
        elif savings_rate < 5:
            insights.append({
                "icon": "💸",
                "title": f"Low savings rate: {savings_rate:.0f}%",
                "detail": "Try to reduce discretionary expenses. Aim for at least 20% savings.",
                "level": "warning",
            })

    # 8. No income this month
    if total_inc == 0 and not df_curr.empty:
        insights.append({
            "icon": "💡",
            "title": "No income recorded this month",
            "detail": "Don't forget to log your income for accurate savings tracking.",
            "level": "info",
        })

    # 9. Recurring subscription check
    sub_total = df_curr[df_curr["category"] == "Subscription"]["amount"].sum()
    if sub_total > 1000:
        insights.append({
            "icon": "📺",
            "title": f"High subscription cost: {fmt_currency(sub_total, currency_symbol)}",
            "detail": "Consider reviewing your active subscriptions and cancelling unused ones.",
            "level": "tip",
        })

    # 10. Weekend vs weekday spending
    if not df_exp.empty:
        df_exp2 = df_exp.copy()
        df_exp2["is_weekend"] = df_exp2["trans_date"].dt.dayofweek >= 5
        wknd = df_exp2[df_exp2["is_weekend"]]["amount"].mean()
        wkdy = df_exp2[~df_exp2["is_weekend"]]["amount"].mean()
        if wknd > wkdy * 1.4:
            insights.append({
                "icon": "🎭",
                "title": "Weekend spending is higher",
                "detail": f"You spend {fmt_currency(wknd, currency_symbol)} on average on weekends vs "
                          f"{fmt_currency(wkdy, currency_symbol)} on weekdays.",
                "level": "tip",
            })

    return insights if insights else [{
        "icon": "✅",
        "title": "All looks good!",
        "detail": "Your finances appear to be on track. Keep it up!",
        "level": "success",
    }]


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
