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
from datetime import date, datetime, timedelta
import streamlit as st
import numpy as np
from database import get_transactions
from utils import CATEGORY_COLORS


# ── Database trigger key helper for caching ───────────────────────────────────

def get_db_trigger_key(user_id: int) -> str:
    """Fetch a fast database summary key to automatically invalidate cached queries."""
    from database import get_connection
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*), MAX(id), SUM(amount) FROM transactions WHERE user_id=?",
            (user_id,)
        ).fetchone()
        return f"{row[0]}_{row[1] or 0}_{row[2] or 0.0}"
    except Exception:
        return "empty"
    finally:
        conn.close()


# ── DataFrame builder ────────────────────────────────────────────────────────

def get_df(user_id: int, filters: dict = None) -> pd.DataFrame:
    """Fetch transactions and return as a clean DataFrame (with caching)."""
    trigger_key = get_db_trigger_key(user_id)
    filters_tuple = tuple(sorted((k, v) for k, v in filters.items())) if filters else ()
    return _get_df_cached(user_id, trigger_key, filters_tuple)


@st.cache_data
def _get_df_cached(user_id: int, trigger_key: str, filters_tuple: tuple) -> pd.DataFrame:
    filters = dict(filters_tuple)
    rows = get_transactions(user_id, filters)
    if not rows:
        return pd.DataFrame(columns=[
            "id", "user_id", "type", "amount", "category",
            "note", "payment_mode", "trans_date", "created_at"
        ])
    df = pd.DataFrame(rows)
    # Robust date parsing: handle multiple formats, coerce errors to NaT
    df["trans_date"] = pd.to_datetime(df["trans_date"], errors="coerce", dayfirst=True)
    # Drop rows with unparseable dates
    df = df.dropna(subset=["trans_date"])
    if df.empty:
        return pd.DataFrame(columns=[
            "id", "user_id", "type", "amount", "category",
            "note", "payment_mode", "trans_date", "created_at"
        ])
    df["month"]      = df["trans_date"].dt.strftime("%Y-%m")
    df["month_name"] = df["trans_date"].dt.strftime("%b %Y")
    df["day_name"]   = df["trans_date"].dt.strftime("%A")
    df["amount"]     = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
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


# ── Smart Portfolio Metrics & Forecasts ───────────────────────────────────────

def get_dashboard_metrics(user_id: int) -> dict:
    """Calculate advanced growth, indicators, health score, and comparison metrics."""
    df = get_df(user_id)
    today = date.today()
    curr_m = today.strftime("%Y-%m")
    
    # Calculate previous month
    prev_month_date = today.replace(day=1) - timedelta(days=1)
    prev_m = prev_month_date.strftime("%Y-%m")

    metrics = {
        "monthly_income_growth_pct": 0.0,
        "monthly_expense_growth_pct": 0.0,
        "monthly_savings_growth_pct": 0.0,
        "expense_trend_indicator": "Stable",
        "savings_trend_indicator": "Stable",
        "best_month": "N/A",
        "worst_month": "N/A",
        "top_spending_category": "N/A",
        "financial_health_score": 100,
        "income_vs_expense_ratio": 0.0,
    }

    if df.empty:
        return metrics

    df_inc = df[df["type"] == "income"]
    df_exp = df[df["type"] == "expense"]

    inc_curr = df_inc[df_inc["month"] == curr_m]["amount"].sum()
    inc_prev = df_inc[df_inc["month"] == prev_m]["amount"].sum()
    
    exp_curr = df_exp[df_exp["month"] == curr_m]["amount"].sum()
    exp_prev = df_exp[df_exp["month"] == prev_m]["amount"].sum()

    sav_curr = inc_curr - exp_curr
    sav_prev = inc_prev - exp_prev

    # Growth %
    metrics["monthly_income_growth_pct"] = ((inc_curr - inc_prev) / inc_prev * 100) if inc_prev > 0 else 0.0
    metrics["monthly_expense_growth_pct"] = ((exp_curr - exp_prev) / exp_prev * 100) if exp_prev > 0 else 0.0
    metrics["monthly_savings_growth_pct"] = ((sav_curr - sav_prev) / abs(sav_prev) * 100) if sav_prev != 0 else 0.0

    # Trend indicators
    if exp_curr > exp_prev * 1.05:
        metrics["expense_trend_indicator"] = "Rising"
    elif exp_curr < exp_prev * 0.95:
        metrics["expense_trend_indicator"] = "Falling"
    else:
        metrics["expense_trend_indicator"] = "Stable"

    if sav_curr > sav_prev * 1.05:
        metrics["savings_trend_indicator"] = "Rising"
    elif sav_curr < sav_prev * 0.95:
        metrics["savings_trend_indicator"] = "Falling"
    else:
        metrics["savings_trend_indicator"] = "Stable"

    # Best and worst months
    monthly_summary = []
    all_months = df["month"].unique()
    for m in all_months:
        m_inc = df_inc[df_inc["month"] == m]["amount"].sum()
        m_exp = df_exp[df_exp["month"] == m]["amount"].sum()
        m_sav = m_inc - m_exp
        try:
            m_date = datetime.strptime(m, "%Y-%m")
            m_name = m_date.strftime("%b %Y")
        except Exception:
            m_name = m
        monthly_summary.append({"month": m, "name": m_name, "savings": m_sav})
    
    if monthly_summary:
        best = max(monthly_summary, key=lambda x: x["savings"])
        worst = min(monthly_summary, key=lambda x: x["savings"])
        metrics["best_month"] = best["name"]
        metrics["worst_month"] = worst["name"]

    # Top spending category
    if not df_exp.empty:
        cat_sums = df_exp.groupby("category")["amount"].sum()
        if not cat_sums.empty:
            metrics["top_spending_category"] = cat_sums.idxmax()

    # Financial Health Score (0-100)
    score = 100
    
    # 1. Savings rate component (45 points)
    total_inc = df_inc["amount"].sum()
    total_exp = df_exp["amount"].sum()
    if total_inc > 0:
        overall_sav_rate = (total_inc - total_exp) / total_inc
        if overall_sav_rate >= 0.30:
            sav_points = 45
        elif overall_sav_rate > 0:
            sav_points = int(overall_sav_rate * (45 / 0.3))
        else:
            sav_points = 0
        score -= (45 - sav_points)
    else:
        score -= 45

    # 2. Budget utilization component (35 points)
    from database import get_budgets
    budgets = get_budgets(user_id, curr_m)
    exceeded_count = 0
    for b in budgets:
        limit = b["amount"]
        spent = df_exp[(df_exp["month"] == curr_m) & (df_exp["category"] == b["category"])]["amount"].sum()
        if spent > limit:
            exceeded_count += 1
    if budgets:
        pct_exceeded = exceeded_count / len(budgets)
        score -= int(pct_exceeded * 35)

    # 3. Savings goals component (20 points)
    from database import get_goals
    goals = get_goals(user_id)
    if goals:
        total_target = sum(g["target_amount"] for g in goals)
        total_saved = sum(g["saved_amount"] for g in goals)
        if total_target > 0:
            progress = total_saved / total_target
            score -= int((1.0 - min(progress, 1.0)) * 20)
    else:
        score -= 10

    metrics["financial_health_score"] = max(0, min(100, score))

    if total_inc > 0:
        metrics["income_vs_expense_ratio"] = round((total_exp / total_inc) * 100, 1)
    else:
        metrics["income_vs_expense_ratio"] = 0.0

    return metrics


def chart_spending_prediction(user_id: int) -> go.Figure:
    """Cumulative spending prediction chart with line regression extrapolation."""
    df = get_df(user_id)
    df_exp = df[df["type"] == "expense"]
    if df_exp.empty:
        return _empty_fig("No expense data yet for prediction")
    
    today = date.today()
    curr_m = today.strftime("%Y-%m")
    df_curr = df_exp[df_exp["month"] == curr_m].copy()
    
    if len(df_curr) < 2:
        return _empty_fig("Need at least 2 transactions this month to forecast")
        
    df_curr["day"] = df_curr["trans_date"].dt.day
    daily = df_curr.groupby("day")["amount"].sum().reset_index().sort_values("day")
    daily["cum"] = daily["amount"].cumsum()
    
    try:
        from sklearn.linear_model import LinearRegression
        import calendar
        
        X = daily["day"].values.reshape(-1, 1)
        y = daily["cum"].values
        model = LinearRegression().fit(X, y)
        
        _, days_in_month = calendar.monthrange(today.year, today.month)
        
        days_seq = np.arange(1, days_in_month + 1).reshape(-1, 1)
        pred_cum = model.predict(days_seq)
        
        pred_df = pd.DataFrame({
            "day": np.arange(1, days_in_month + 1),
            "predicted": pred_cum
        })
        
        fig = go.Figure()
        # Actual cumulative
        fig.add_trace(go.Scatter(
            x=daily["day"], y=daily["cum"],
            mode="lines+markers",
            name="Actual Spend",
            line=dict(color="#FF6B6B", width=3),
            marker=dict(size=6)
        ))
        # Forecasted cumulative
        fig.add_trace(go.Scatter(
            x=pred_df["day"], y=pred_df["predicted"],
            mode="lines",
            name="Forecasted Spend",
            line=dict(color="#6C5CE7", width=2, dash="dash")
        ))
        
        fig.update_layout(
            **CHART_LAYOUT,
            title="Spending Forecast (Cumulative)",
            xaxis=dict(title="Day of Month", showgrid=False, tickmode="linear", tick0=1, dtick=5),
            yaxis=dict(title="Cumulative Amount (₹)", showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
        )
        return fig
    except Exception as e:
        return _empty_fig(f"Prediction forecast: {e}")


def chart_monthly_comparison(user_id: int) -> go.Figure:
    """Current Month vs Last Month comparison bar chart."""
    df = get_df(user_id)
    if df.empty:
        return _empty_fig("No data available")
    
    monthly = df.groupby(["month", "month_name", "type"])["amount"].sum().reset_index()
    unique_months = sorted(df["month"].unique())[-2:]
    if len(unique_months) < 2:
        return _empty_fig("Need at least 2 months of data to compare")
        
    monthly = monthly[monthly["month"].isin(unique_months)]
    
    fig = px.bar(
        monthly, x="type", y="amount", color="month_name",
        barmode="group",
        color_discrete_sequence=["#6C5CE7", "#00B894"],
        labels={"amount": "Amount (₹)", "type": "Transaction Type", "month_name": "Month"},
        title="Current Month vs Last Month"
    )
    fig.update_layout(**CHART_LAYOUT)
    return fig


def get_category_comparison(user_id: int) -> pd.DataFrame:
    """Calculate Category spending change between current and previous month."""
    df = get_df(user_id)
    df_exp = df[df["type"] == "expense"]
    if df_exp.empty:
        return pd.DataFrame()
        
    today = date.today()
    curr_m = today.strftime("%Y-%m")
    prev_month_date = today.replace(day=1) - timedelta(days=1)
    prev_m = prev_month_date.strftime("%Y-%m")
    
    curr_sums = df_exp[df_exp["month"] == curr_m].groupby("category")["amount"].sum()
    prev_sums = df_exp[df_exp["month"] == prev_m].groupby("category")["amount"].sum()
    
    all_cats = list(set(curr_sums.index) | set(prev_sums.index))
    rows = []
    for cat in all_cats:
        curr_amt = curr_sums.get(cat, 0.0)
        prev_amt = prev_sums.get(cat, 0.0)
        diff = curr_amt - prev_amt
        pct = ((curr_amt - prev_amt) / prev_amt * 100) if prev_amt > 0 else 0.0
        rows.append({
            "category": cat,
            "previous_amount": prev_amt,
            "current_amount": curr_amt,
            "difference": diff,
            "change_pct": round(pct, 1)
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("difference", ascending=False)


def chart_yearly_summary(user_id: int) -> go.Figure:
    """Yearly summary stacked bar chart."""
    df = get_df(user_id)
    if df.empty:
        return _empty_fig("No data available")
    
    df = df.copy()
    df["year"] = df["trans_date"].dt.strftime("%Y")
    yearly = df.groupby(["year", "type"])["amount"].sum().reset_index()
    
    fig = px.bar(
        yearly, x="year", y="amount", color="type",
        barmode="group",
        color_discrete_map={"income": "#00B894", "expense": "#FF6B6B"},
        labels={"amount": "Amount (₹)", "year": "Year", "type": "Type"},
        title="Yearly Summary"
    )
    fig.update_layout(**CHART_LAYOUT)
    return fig

