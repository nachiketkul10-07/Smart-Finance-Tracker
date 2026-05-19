"""
analytics.py
------------
All data aggregation and chart-building logic.
Uses pandas for computation and Plotly for visualisation.
No external API calls — everything runs locally.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, datetime
from database import get_transactions
from utils import CATEGORY_COLORS


# ── DataFrame builder ────────────────────────────────────────────────────────

def get_df(user_id: int, filters: dict = None) -> pd.DataFrame:
    """Fetch transactions and return as a clean DataFrame."""
    rows = get_transactions(user_id, filters)
    if not rows:
        return pd.DataFrame(columns=[
            "id", "user_id", "type", "amount", "category",
            "note", "payment_mode", "trans_date", "created_at"
        ])
    df = pd.DataFrame(rows)
    df["trans_date"] = pd.to_datetime(df["trans_date"])
    df["month"]      = df["trans_date"].dt.strftime("%Y-%m")
    df["month_name"] = df["trans_date"].dt.strftime("%b %Y")
    df["day_name"]   = df["trans_date"].dt.strftime("%A")
    df["amount"]     = df["amount"].astype(float)
    return df


# ── KPI summary ───────────────────────────────────────────────────────────────

def get_summary(user_id: int, month: str = None) -> dict:
    """
    Return dict with:
      total_income, total_expense, net_savings,
      month_income, month_expense, month_savings
    """
    df_all = get_df(user_id)
    today  = date.today().strftime("%Y-%m")
    month  = month or today

    if df_all.empty:
        zero = dict(total_income=0, total_expense=0, net_savings=0,
                    month_income=0, month_expense=0, month_savings=0)
        return zero

    inc_all  = df_all[df_all["type"] == "income"]["amount"].sum()
    exp_all  = df_all[df_all["type"] == "expense"]["amount"].sum()
    net_all  = inc_all - exp_all

    df_m     = df_all[df_all["month"] == month]
    inc_m    = df_m[df_m["type"] == "income"]["amount"].sum()
    exp_m    = df_m[df_m["type"] == "expense"]["amount"].sum()
    net_m    = inc_m - exp_m

    return dict(
        total_income   = inc_all,
        total_expense  = exp_all,
        net_savings    = net_all,
        month_income   = inc_m,
        month_expense  = exp_m,
        month_savings  = net_m,
    )


# ── Charts ─────────────────────────────────────────────────────────────────────

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Sora, sans-serif", color="#e0e0e0"),
    margin=dict(t=40, b=20, l=20, r=20),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)


def chart_income_vs_expense(user_id: int) -> go.Figure:
    """Grouped bar chart: income vs expense per month."""
    df = get_df(user_id)
    if df.empty:
        return _empty_fig("No data yet")

    monthly = (
        df.groupby(["month", "month_name", "type"])["amount"]
        .sum().reset_index()
        .sort_values("month")
    )
    last6 = sorted(monthly["month"].unique())[-6:]
    monthly = monthly[monthly["month"].isin(last6)]

    colors = {"income": "#00B894", "expense": "#FF6B6B"}
    fig = px.bar(
        monthly, x="month_name", y="amount", color="type",
        barmode="group",
        color_discrete_map=colors,
        labels={"amount": "Amount (₹)", "month_name": "Month", "type": "Type"},
        title="Income vs Expense (Last 6 Months)",
    )
    fig.update_layout(**CHART_LAYOUT, title_font_size=15)
    fig.update_traces(marker_line_width=0, opacity=0.9)
    return fig


def chart_expense_trend(user_id: int) -> go.Figure:
    """Line chart showing monthly expense trend."""
    df = get_df(user_id)
    df = df[df["type"] == "expense"]
    if df.empty:
        return _empty_fig("No expense data yet")

    monthly = df.groupby(["month", "month_name"])["amount"].sum().reset_index().sort_values("month")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["month_name"], y=monthly["amount"],
        mode="lines+markers",
        line=dict(color="#FF6B6B", width=3),
        marker=dict(size=8, color="#FF6B6B"),
        fill="tozeroy",
        fillcolor="rgba(255,107,107,0.15)",
        name="Expense",
    ))
    fig.update_layout(**CHART_LAYOUT, title="Monthly Expense Trend", title_font_size=15,
                      xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"))
    return fig


def chart_category_pie(user_id: int, month: str = None) -> go.Figure:
    """Pie / donut chart for expense categories."""
    filters = {"type": "expense"}
    if month:
        filters["month"] = month
    df = get_df(user_id, filters)
    if df.empty:
        return _empty_fig("No expense data")

    by_cat = df.groupby("category")["amount"].sum().reset_index()
    by_cat = by_cat[by_cat["amount"] > 0]
    colors = [CATEGORY_COLORS.get(c, "#888") for c in by_cat["category"]]

    fig = go.Figure(go.Pie(
        labels=by_cat["category"],
        values=by_cat["amount"],
        hole=0.55,
        marker=dict(colors=colors, line=dict(color="#1e1e2e", width=2)),
        textinfo="label+percent",
        textfont=dict(size=12),
    ))
    fig.update_layout(**CHART_LAYOUT, title="Expense by Category", title_font_size=15)
    return fig


def chart_savings_trend(user_id: int) -> go.Figure:
    """Cumulative savings over time."""
    df = get_df(user_id)
    if df.empty:
        return _empty_fig("No data yet")

    monthly_inc = df[df["type"] == "income"].groupby("month")["amount"].sum()
    monthly_exp = df[df["type"] == "expense"].groupby("month")["amount"].sum()
    months = sorted(set(monthly_inc.index) | set(monthly_exp.index))

    savings = []
    cumulative = 0
    for m in months:
        inc = monthly_inc.get(m, 0)
        exp = monthly_exp.get(m, 0)
        cumulative += (inc - exp)
        savings.append({"month": m, "savings": cumulative})

    df_s = pd.DataFrame(savings)
    colors = ["#00B894" if v >= 0 else "#FF6B6B" for v in df_s["savings"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_s["month"], y=df_s["savings"],
        marker_color=colors,
        name="Cumulative Savings",
    ))
    fig.add_trace(go.Scatter(
        x=df_s["month"], y=df_s["savings"],
        mode="lines",
        line=dict(color="#FDCB6E", width=2),
        name="Trend",
    ))
    fig.update_layout(**CHART_LAYOUT, title="Savings Trend (Cumulative)", title_font_size=15,
                      xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"))
    return fig


def chart_top_categories(user_id: int, month: str = None) -> go.Figure:
    """Horizontal bar chart of top spending categories."""
    filters = {"type": "expense"}
    if month:
        filters["month"] = month
    df = get_df(user_id, filters)
    if df.empty:
        return _empty_fig("No expense data")

    by_cat = df.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=True)
    colors = [CATEGORY_COLORS.get(c, "#888") for c in by_cat["category"]]

    fig = go.Figure(go.Bar(
        x=by_cat["amount"], y=by_cat["category"],
        orientation="h",
        marker_color=colors,
        text=by_cat["amount"].apply(lambda x: f"₹{x:,.0f}"),
        textposition="outside",
    ))
    fig.update_layout(**CHART_LAYOUT, title="Top Spending Categories", title_font_size=15,
                      xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))
    return fig


def chart_daily_spending(user_id: int, month: str = None) -> go.Figure:
    """Bar chart of daily spending within a month."""
    filters = {"type": "expense"}
    if month:
        filters["month"] = month
    df = get_df(user_id, filters)
    if df.empty:
        return _empty_fig("No expense data")

    daily = df.groupby(df["trans_date"].dt.date)["amount"].sum().reset_index()
    daily.columns = ["date", "amount"]

    fig = go.Figure(go.Bar(
        x=daily["date"], y=daily["amount"],
        marker_color="#6C5CE7",
        opacity=0.85,
    ))
    fig.update_layout(**CHART_LAYOUT, title="Daily Spending", title_font_size=15,
                      xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"))
    return fig


def chart_payment_mode(user_id: int) -> go.Figure:
    """Donut chart for payment mode distribution."""
    df = get_df(user_id, {"type": "expense"})
    if df.empty:
        return _empty_fig("No data")

    by_mode = df.groupby("payment_mode")["amount"].sum().reset_index()

    fig = go.Figure(go.Pie(
        labels=by_mode["payment_mode"],
        values=by_mode["amount"],
        hole=0.5,
        textinfo="label+percent",
    ))
    fig.update_layout(**CHART_LAYOUT, title="Payment Mode Breakdown", title_font_size=15)
    return fig


# ── Budget comparison ─────────────────────────────────────────────────────────

def get_budget_comparison(user_id: int, month: str) -> pd.DataFrame:
    """
    Returns a DataFrame with columns:
    category, budget, spent, remaining, pct_used
    """
    from database import get_budgets
    budgets = get_budgets(user_id, month)
    filters = {"type": "expense", "month": month}
    df = get_df(user_id, filters)

    rows = []
    for b in budgets:
        cat   = b["category"]
        bamt  = b["amount"]
        spent = df[df["category"] == cat]["amount"].sum() if not df.empty else 0
        remaining = bamt - spent
        pct = (spent / bamt * 100) if bamt > 0 else 0
        rows.append(dict(
            id=b["id"],
            category=cat,
            budget=bamt,
            spent=spent,
            remaining=remaining,
            pct_used=round(pct, 1),
        ))
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["id", "category", "budget", "spent", "remaining", "pct_used"]
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _empty_fig(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message, x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color="#888"),
        xref="paper", yref="paper",
    )
    fig.update_layout(**CHART_LAYOUT)
    return fig
