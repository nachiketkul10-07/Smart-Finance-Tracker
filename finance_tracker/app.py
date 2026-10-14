"""
app.py
------
Main Streamlit entry point.
Handles routing between pages via sidebar navigation.
All pages are defined as functions in this file for simplicity,
with helper rendering components kept modular.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import sys
import os
import json
import math

# Add current directory to path for local module imports in deployed environments
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Project imports ───────────────────────────────────────────────────────────
from database import (
    init_db, get_transactions, add_transaction, update_transaction,
    delete_transaction, set_budget, get_budgets, delete_budget,
    add_goal, get_goals, update_goal, delete_goal,
    add_recurring, get_recurring, delete_recurring,
    reset_user_data, update_settings, get_settings,
    backup_user_data, restore_user_data
)
from auth     import is_logged_in, login, register, logout_user, get_current_user
from analytics import (
    get_df, get_summary, chart_income_vs_expense, chart_expense_trend,
    chart_category_pie, chart_savings_trend, chart_top_categories,
    chart_daily_spending, chart_payment_mode, get_budget_comparison,
    get_dashboard_metrics, chart_spending_prediction, chart_monthly_comparison,
    get_category_comparison, chart_yearly_summary
)
from ai_insights import get_insights
from export_utils import export_excel, export_pdf
# Heavy imports (bank_parser, ocr_parser, gmail_parser) are loaded lazily
# inside page_import() to avoid crashing on startup if deps are missing
from utils import (
    INCOME_CATEGORIES, EXPENSE_CATEGORIES, PAYMENT_MODES, CURRENCIES,
    auto_detect_category, fmt_currency, month_options, current_month,
    load_sample_data, CATEGORY_COLORS, validate_amount, validate_note
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title  = "Smart Finance Tracker",
    page_icon   = "💰",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

# ── Init DB ───────────────────────────────────────────────────────────────────
init_db()

# ── Load CSS ──────────────────────────────────────────────────────────────────
css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
with open(css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Mobile viewport ───────────────────────────────────────────────────────────
st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">',
    unsafe_allow_html=True
)


# ══════════════════════════════════════════════════════════════════════════════
# HELPER COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

def kpi_card(label: str, value: str, color: str = "accent",
             icon: str = "💰", delta: str = ""):
    st.markdown(f"""
    <div class="kpi-card {color}">
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-delta">{delta}</div>
    </div>
    """, unsafe_allow_html=True)


def section_title(icon: str, title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="page-title">{icon} {title}</div>
    <div class="page-sub">{subtitle}</div>
    """, unsafe_allow_html=True)


def divider():
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


def badge(text: str, kind: str = "income"):
    return f'<span class="badge badge-{kind}">{text}</span>'


def empty_state(icon: str, title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-icon">{icon}</div>
        <div class="empty-title">{title}</div>
        <div class="empty-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def insight_card(icon: str, title: str, detail: str, level: str = "info"):
    st.markdown(f"""
    <div class="insight-card {level}">
        <div class="insight-icon">{icon}</div>
        <div>
            <div class="insight-title">{title}</div>
            <div class="insight-detail">{detail}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def get_sym() -> str:
    """Return currency symbol for current user."""
    uid = st.session_state.get("user_id")
    if not uid:
        return "₹"
    cfg = get_settings(uid)
    return CURRENCIES.get(cfg.get("currency", "INR (₹)"), "₹")


# ══════════════════════════════════════════════════════════════════════════════
# AUTH PAGES
# ══════════════════════════════════════════════════════════════════════════════

def page_auth():
    col_l, col_c, col_r = st.columns([1, 1.4, 1])
    with col_c:
        st.markdown("""
        <div style="text-align:center;padding:2rem 0 1.5rem 0;">
            <span style="font-size:3rem;">💰</span>
            <div style="font-family:'Sora',sans-serif;font-size:1.8rem;font-weight:800;
                        color:#f0f0ff;letter-spacing:-0.02em;margin-top:0.3rem;">
                Smart Finance Tracker
            </div>
            <div style="color:#a0a0c0;font-size:0.9rem;margin-top:0.3rem;">
                Your intelligent personal finance companion
            </div>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_reg = st.tabs(["🔑 Login", "📝 Register"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="your_username")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    ok, msg = login(username, password)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        with tab_reg:
            with st.form("reg_form"):
                full_name = st.text_input("Full Name", placeholder="Your Name")
                username  = st.text_input("Username",  placeholder="choose_username")
                email     = st.text_input("Email",     placeholder="you@email.com")
                password  = st.text_input("Password",  type="password", placeholder="min 6 chars")
                submitted = st.form_submit_button("Create Account", use_container_width=True)
                if submitted:
                    ok, msg = register(username, email, password, full_name)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

PAGES = [
    ("🏠", "Dashboard"),
    ("💸", "Transactions"),
    ("📥", "Import"),
    ("📊", "Analytics"),
    ("📋", "Budget Planner"),
    ("🎯", "Savings Goals"),
    ("🤖", "AI Insights"),
    ("🔄", "Recurring"),
    ("📤", "Export"),
    ("⚙️", "Settings"),
]

def sidebar_nav() -> str:
    user = get_current_user()
    with st.sidebar:
        # Brand
        st.markdown(f"""
        <div class="brand">
            <div class="brand-icon">💰</div>
            <div>
                <div class="brand-name">FinanceTracker</div>
                <div class="brand-sub">Smart • Local • Secure</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # User info
        st.markdown(f"""
        <div style="padding:0.6rem 0.5rem;margin-bottom:0.8rem;
                    background:rgba(108,92,231,0.1);border-radius:10px;
                    border:1px solid rgba(108,92,231,0.2);">
            <div style="font-weight:700;font-size:0.9rem;color:#f0f0ff;">
                👤 {user.get('full_name') or user.get('username', 'User')}
            </div>
            <div style="font-size:0.75rem;color:#a0a0c0;">@{user.get('username','')}</div>
        </div>
        """, unsafe_allow_html=True)

        # Navigation
        if "current_page" not in st.session_state:
            st.session_state["current_page"] = "Dashboard"

        for icon, name in PAGES:
            active_cls = "active" if st.session_state["current_page"] == name else ""
            if st.button(f"{icon}  {name}", key=f"nav_{name}",
                         use_container_width=True,
                         type="secondary" if active_cls else "secondary"):
                st.session_state["current_page"] = name
                st.rerun()

        divider()

        # Quick stats
        uid = st.session_state["user_id"]
        sym = get_sym()
        summary = get_summary(uid)
        st.markdown(f"""
        <div style="padding:0.6rem 0.3rem;">
            <div style="font-size:0.72rem;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.07em;color:#6060a0;margin-bottom:0.5rem;">
                Quick Stats
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;">
                <span style="font-size:0.8rem;color:#a0a0c0;">Net Balance</span>
                <span style="font-size:0.8rem;font-weight:700;
                             color:{'#00B894' if summary['net_savings']>=0 else '#FF6B6B'};">
                    {fmt_currency(summary['net_savings'], sym)}
                </span>
            </div>
            <div style="display:flex;justify-content:space-between;">
                <span style="font-size:0.8rem;color:#a0a0c0;">This Month</span>
                <span style="font-size:0.8rem;font-weight:700;
                             color:{'#00B894' if summary['month_savings']>=0 else '#FF6B6B'};">
                    {fmt_currency(summary['month_savings'], sym)}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        divider()

        if st.button("🚪  Logout", use_container_width=True):
            logout_user()
            st.rerun()

    return st.session_state.get("current_page", "Dashboard")


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    uid     = st.session_state["user_id"]
    sym     = get_sym()
    summary = get_summary(uid)
    today   = date.today()
    db_metrics = get_dashboard_metrics(uid)

    section_title("🏠", "Dashboard",
                  f"Welcome back! Here's your financial overview — {today.strftime('%d %B %Y')}")

    # ── KPI row ───────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Total Income", fmt_currency(summary["total_income"], sym),
                 "green", "💰", "All time")
    with c2:
        kpi_card("Total Expenses", fmt_currency(summary["total_expense"], sym),
                 "red", "💸", "All time")
    with c3:
        kpi_card("Net Savings", fmt_currency(summary["net_savings"], sym),
                 "green" if summary["net_savings"] >= 0 else "red", "🏦", "All time")
    with c4:
        kpi_card("This Month Net", fmt_currency(summary["month_savings"], sym),
                 "accent" if summary["month_savings"] >= 0 else "red", "📅", 
                 f"{db_metrics['monthly_savings_growth_pct']:+.1f}% vs last month")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Month summary row ─────────────────────────────────────────────────────
    cm1, cm2, cm3 = st.columns(3)
    with cm1:
        kpi_card("Month Income", fmt_currency(summary["month_income"], sym),
                 "green", "📈", f"{db_metrics['monthly_income_growth_pct']:+.1f}% MoM")
    with cm2:
        kpi_card("Month Expense", fmt_currency(summary["month_expense"], sym),
                 "red", "📉", f"{db_metrics['monthly_expense_growth_pct']:+.1f}% MoM")
    with cm3:
        rate = (summary["month_savings"] / summary["month_income"] * 100
                if summary["month_income"] > 0 else 0)
        kpi_card("Savings Rate", f"{rate:.1f}%",
                 "accent", "% ", "This month")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Advanced Portfolio Stats row ──────────────────────────────────────────
    ca1, ca2, ca3, ca4 = st.columns(4)
    with ca1:
        health_color = "green" if db_metrics['financial_health_score'] >= 80 else ("yellow" if db_metrics['financial_health_score'] >= 50 else "red")
        kpi_card("Financial Health", f"{db_metrics['financial_health_score']}/100",
                 health_color, "⚡", "Score based on habits")
    with ca2:
        kpi_card("Top Category", db_metrics['top_spending_category'],
                 "red", "🏷️", "Highest spend")
    with ca3:
        kpi_card("Best Month", db_metrics['best_month'],
                 "green", "🏆", f"Worst: {db_metrics['worst_month']}")
    with ca4:
        kpi_card("Expense/Savings Trend", f"{db_metrics['expense_trend_indicator']} / {db_metrics['savings_trend_indicator']}",
                 "blue", "📈", "MoM comparison direction")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts row ────────────────────────────────────────────────────────────
    ch1, ch2 = st.columns(2)
    with ch1:
        st.plotly_chart(chart_income_vs_expense(uid), use_container_width=True)
    with ch2:
        st.plotly_chart(chart_category_pie(uid, current_month()), use_container_width=True)

    # ── Recent transactions ───────────────────────────────────────────────────
    st.markdown('<div class="card-title">🕐 Recent Transactions</div>', unsafe_allow_html=True)
    df = get_df(uid)
    if df.empty:
        empty_state("📭", "No transactions yet",
                    "Add your first transaction to get started.")
        # Offer sample data
        if st.button("🎲  Load Sample Demo Data", use_container_width=False):
            load_sample_data(uid)
            st.success("✅ Sample data loaded! Refresh to see the dashboard.")
            st.rerun()
    else:
        recent = df.head(8)
        for _, row in recent.iterrows():
            color    = "#00B894" if row["type"] == "income" else "#FF6B6B"
            sign     = "+" if row["type"] == "income" else "-"
            cat_dot  = CATEGORY_COLORS.get(row["category"], "#888")
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
                        padding:0.7rem 1rem;border-radius:10px;margin-bottom:0.4rem;
                        background:#1a1a2e;border:1px solid rgba(255,255,255,0.05);">
                <div style="display:flex;align-items:center;gap:0.8rem;">
                    <div style="width:9px;height:9px;border-radius:50%;
                                background:{cat_dot};flex-shrink:0;"></div>
                    <div>
                        <div style="font-weight:600;font-size:0.88rem;color:#f0f0ff;">
                            {row.get('note') or row['category']}
                        </div>
                        <div style="font-size:0.75rem;color:#a0a0c0;">
                            {row['category']} • {row['trans_date'].strftime('%d %b %Y')} • {row.get('payment_mode','')}
                        </div>
                    </div>
                </div>
                <div style="font-family:'Sora',sans-serif;font-weight:700;
                            font-size:0.95rem;color:{color};">
                    {sign}{fmt_currency(row['amount'], sym)}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Sample data button (when data exists) ─────────────────────────────────
    if not df.empty:
        with st.expander("⚙️ Demo Options"):
            if st.button("🎲 Reload Sample Data"):
                load_sample_data(uid)
                st.success("Sample data added!")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTIONS
# ══════════════════════════════════════════════════════════════════════════════

def page_transactions():
    uid = st.session_state["user_id"]
    sym = get_sym()

    section_title("💸", "Transactions", "Add, view, edit and delete your income & expenses")

    tab_view, tab_add = st.tabs(["📋 View Transactions", "➕ Add Transaction"])

    # ── ADD TAB ───────────────────────────────────────────────────────────────
    with tab_add:
        col_f, col_s = st.columns([1.5, 1])
        with col_f:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            with st.form("add_txn"):
                st.markdown('<div class="card-title">➕ New Transaction</div>',
                            unsafe_allow_html=True)

                t_type = st.radio("Type", ["expense", "income"],
                                  horizontal=True, format_func=str.capitalize)
                categories = EXPENSE_CATEGORIES if t_type == "expense" else INCOME_CATEGORIES

                c1, c2 = st.columns(2)
                with c1:
                    amount   = st.number_input("Amount", min_value=0.01, step=0.01, format="%.2f")
                    category = st.selectbox("Category", category_list := list(categories))
                with c2:
                    trans_date   = st.date_input("Date", value=date.today())
                    payment_mode = st.selectbox("Payment Mode", list(PAYMENT_MODES))

                note = st.text_input("Note / Description",
                                     placeholder="e.g. Swiggy biryani order")
                tags = st.text_input("Tags (comma separated)", placeholder="food, weekend, vacation")

                # Auto detect category from note
                auto_cat = auto_detect_category(note, t_type) if note else None
                if auto_cat and auto_cat != category:
                    st.info(f"💡 Suggested category: **{auto_cat}**")

                submitted = st.form_submit_button("💾 Save Transaction",
                                                   use_container_width=True)
                if submitted:
                    ok_amt, err_amt = validate_amount(amount)
                    ok_note, err_note = validate_note(note)
                    if not ok_amt:
                        st.error(err_amt)
                    elif not ok_note:
                        st.error(err_note)
                    else:
                        add_transaction(uid, t_type, amount, category,
                                        note, payment_mode, trans_date, tags=tags)
                        st.success(f"✅ {t_type.capitalize()} of {fmt_currency(amount, sym)} saved!")
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        with col_s:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">⚡ Quick Add</div>', unsafe_allow_html=True)
            quick = [
                ("🍕 Food",           500,  "Food",         "expense"),
                ("🚕 Cab Ride",       300,  "Travel",       "expense"),
                ("☕ Coffee",          150,  "Food",         "expense"),
                ("🎬 Movie",          400,  "Entertainment","expense"),
                ("💊 Medicine",       200,  "Health",       "expense"),
                ("📺 Netflix",        199,  "Subscription", "expense"),
            ]
            for label, amt, cat, typ in quick:
                if st.button(label, use_container_width=True, key=f"qa_{label}"):
                    add_transaction(uid, typ, amt, cat, label.split(" ", 1)[1],
                                    "UPI", date.today(), tags="quick-add")
                    st.success(f"Added: {label} — {fmt_currency(amt, sym)}")
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # ── VIEW TAB ──────────────────────────────────────────────────────────────
    with tab_view:
        # Filters
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            f_month = st.selectbox("📅 Month", ["All"] + month_options(12), key="txn_month")
        with fc2:
            all_cats = ["All"] + EXPENSE_CATEGORIES + INCOME_CATEGORIES
            f_cat = st.selectbox("🏷️ Category", all_cats, key="txn_cat")
        with fc3:
            f_type = st.selectbox("🔄 Type", ["All", "income", "expense"], key="txn_type")
        with fc4:
            f_search = st.text_input("🔍 Search", placeholder="keyword, tag, or note...", key="txn_search")

        # Sort and Tag filters
        fs1, fs2 = st.columns(2)
        with fs1:
            sort_by = st.selectbox("Sort By", ["Date (Newest)", "Date (Oldest)", "Amount (Highest)", "Amount (Lowest)", "Category (A-Z)"], key="txn_sort")
        with fs2:
            f_tag = st.text_input("🏷️ Filter by Tag", placeholder="e.g. vacation", key="txn_tag")

        filters = {}
        if f_month != "All":    filters["month"]    = f_month
        if f_cat   != "All":    filters["category"] = f_cat
        if f_type  != "All":    filters["type"]     = f_type
        if f_search:            filters["search"]   = f_search
        if f_tag:               filters["tag"]      = f_tag

        df = get_df(uid, filters)

        if df.empty:
            empty_state("🔍", "No transactions found", "Try adjusting your filters.")
            return

        # Sort the DataFrame
        if sort_by == "Date (Newest)":
            df = df.sort_values(["trans_date", "id"], ascending=[False, False])
        elif sort_by == "Date (Oldest)":
            df = df.sort_values(["trans_date", "id"], ascending=[True, True])
        elif sort_by == "Amount (Highest)":
            df = df.sort_values("amount", ascending=False)
        elif sort_by == "Amount (Lowest)":
            df = df.sort_values("amount", ascending=True)
        elif sort_by == "Category (A-Z)":
            df = df.sort_values("category", ascending=True)

        # Summary strip
        total_inc = df[df["type"] == "income"]["amount"].sum()
        total_exp = df[df["type"] == "expense"]["amount"].sum()
        st.markdown(f"""
        <div style="display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap;">
            <div style="background:#0f2a1f;border:1px solid #00B894;border-radius:8px;
                        padding:0.4rem 1rem;font-size:0.85rem;color:#00B894;font-weight:600;">
                ↑ Income: {fmt_currency(total_inc, sym)}
            </div>
            <div style="background:#2a0f0f;border:1px solid #FF6B6B;border-radius:8px;
                        padding:0.4rem 1rem;font-size:0.85rem;color:#FF6B6B;font-weight:600;">
                ↓ Expense: {fmt_currency(total_exp, sym)}
            </div>
            <div style="background:#1a1a2e;border:1px solid rgba(255,255,255,0.1);
                        border-radius:8px;padding:0.4rem 1rem;
                        font-size:0.85rem;color:#a0a0c0;">
                {len(df)} transactions
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Bulk Delete Option
        with st.expander("🚨 Bulk Delete Actions"):
            txn_options = df["id"].tolist()
            def get_txn_label(i):
                match = df[df['id'] == i]
                if not match.empty:
                    row_val = match.iloc[0]
                    note_val = row_val.get('note') or row_val.get('category') or "Unspecified"
                    return f"ID {i} — {note_val} ({fmt_currency(row_val['amount'], sym)})"
                return f"ID {i}"
            
            bulk_del_ids = st.multiselect(
                "Select Transactions to Delete",
                options=txn_options,
                format_func=get_txn_label
            )
            if bulk_del_ids:
                if st.button("🚨 Bulk Delete Selected", type="primary", use_container_width=True, key="bulk_del_btn"):
                    for tid in bulk_del_ids:
                        delete_transaction(tid, uid)
                    st.success("Selected transactions deleted successfully.")
                    st.rerun()

        # Transaction list with edit/delete
        for _, row in df.iterrows():
            color   = "#00B894" if row["type"] == "income" else "#FF6B6B"
            sign    = "+" if row["type"] == "income" else "-"
            cat_dot = CATEGORY_COLORS.get(row["category"], "#888")

            # Format tags list
            tags_html = ""
            if row.get("tags"):
                tags_list = [t.strip() for t in row["tags"].split(",") if t.strip()]
                tags_html = " ".join(f"<span style='background:rgba(108,92,231,0.15);color:#a29bfe;padding:1px 6px;font-size:0.7rem;border-radius:4px;margin-right:4px;'>#{t}</span>" for t in tags_list)

            col_main, col_actions = st.columns([5, 1])
            with col_main:
                st.markdown(f"""
                <div style="display:flex;align-items:center;justify-content:space-between;
                            padding:0.7rem 1rem;border-radius:10px;
                            background:#1a1a2e;border:1px solid rgba(255,255,255,0.05);">
                    <div style="display:flex;align-items:center;gap:0.8rem;">
                        <div style="width:9px;height:9px;border-radius:50%;
                                    background:{cat_dot};flex-shrink:0;"></div>
                        <div>
                            <div style="font-weight:600;font-size:0.88rem;color:#f0f0ff;">
                                {row.get('note') or row['category']}
                            </div>
                            <div style="font-size:0.75rem;color:#a0a0c0;">
                                {row['category']} • {row['trans_date'].strftime('%d %b %Y')} • {row.get('payment_mode','')} {tags_html}
                            </div>
                        </div>
                    </div>
                    <div style="font-family:'Sora',sans-serif;font-weight:700;
                                font-size:0.95rem;color:{color};">
                        {sign}{fmt_currency(row['amount'], sym)}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_actions:
                if st.button("🗑️", key=f"del_{row['id']}", help="Delete"):
                    delete_transaction(row["id"], uid)
                    st.success("Deleted.")
                    st.rerun()

        # Edit/Duplicate form in expander
        with st.expander("✏️ Edit or Duplicate a Transaction"):
            txn_ids = df["id"].tolist()
            if txn_ids:
                sel_id = st.selectbox(
                    "Select Transaction ID to Edit/Duplicate",
                    txn_ids,
                    format_func=lambda i: f"ID {i} — {df[df['id']==i]['note'].values[0] or df[df['id']==i]['category'].values[0]} ({fmt_currency(df[df['id']==i]['amount'].values[0], sym)})"
                )
                sel_row = df[df["id"] == sel_id].iloc[0]
                with st.form("edit_txn"):
                    e_amount = st.number_input("Amount", value=float(sel_row["amount"]),
                                               min_value=0.01, step=0.01)
                    e_cat    = st.selectbox("Category",
                                            EXPENSE_CATEGORIES if sel_row["type"] == "expense"
                                            else INCOME_CATEGORIES,
                                            index=(EXPENSE_CATEGORIES if sel_row["type"] == "expense"
                                                   else INCOME_CATEGORIES).index(sel_row["category"])
                                            if sel_row["category"] in (EXPENSE_CATEGORIES
                                            if sel_row["type"] == "expense" else INCOME_CATEGORIES) else 0)
                    e_note   = st.text_input("Note", value=sel_row.get("note", "") or "")
                    e_mode   = st.selectbox("Payment Mode", list(PAYMENT_MODES),
                                            index=PAYMENT_MODES.index(sel_row["payment_mode"])
                                            if sel_row["payment_mode"] in PAYMENT_MODES else 0)
                    e_date   = st.date_input("Date", value=sel_row["trans_date"].date())
                    e_tags   = st.text_input("Tags", value=sel_row.get("tags", "") or "")

                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.form_submit_button("✅ Update Transaction", use_container_width=True):
                            ok_amt, err_amt = validate_amount(e_amount)
                            ok_note, err_note = validate_note(e_note)
                            if not ok_amt:
                                st.error(err_amt)
                            elif not ok_note:
                                st.error(err_note)
                            else:
                                update_transaction(sel_id, uid, amount=e_amount,
                                                   category=e_cat, note=e_note,
                                                   payment_mode=e_mode,
                                                   trans_date=str(e_date), tags=e_tags)
                                st.success("Transaction updated!")
                                st.rerun()
                    with c_btn2:
                        if st.form_submit_button("👯 Duplicate Transaction", use_container_width=True):
                            ok_amt, err_amt = validate_amount(e_amount)
                            ok_note, err_note = validate_note(e_note)
                            if not ok_amt:
                                st.error(err_amt)
                            elif not ok_note:
                                st.error(err_note)
                            else:
                                add_transaction(uid, sel_row["type"], e_amount, e_cat,
                                                f"Copy: {e_note}" if e_note else f"Copy: {e_cat}",
                                                e_mode, str(e_date), tags=e_tags)
                                st.success("Transaction duplicated!")
                                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

def page_analytics():
    uid = st.session_state["user_id"]
    section_title("📊", "Analytics", "Deep dive into your spending patterns and trends")

    # Ratio indicator
    db_metrics = get_dashboard_metrics(uid)
    st.markdown(f"""
    <div style="background:#1a1a2e;padding:0.7rem 1.2rem;border-radius:10px;margin-bottom:1.2rem;border:1px solid rgba(255,255,255,0.05);display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:0.88rem;color:#a0a0c0;">📉 Income vs Expense Ratio (All Time)</span>
        <span style="font-family:'Sora';font-weight:700;font-size:1.1rem;color:{'#00B894' if db_metrics['income_vs_expense_ratio']<=100 else '#FF6B6B'};">{db_metrics['income_vs_expense_ratio']}%</span>
    </div>
    """, unsafe_allow_html=True)

    months = ["All"] + month_options(12)
    sel_month = st.selectbox("Filter by Month", months, key="anal_month")
    filter_m  = None if sel_month == "All" else sel_month

    # Row 1
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(chart_income_vs_expense(uid), use_container_width=True, key="ch_inc_exp")
    with c2:
        st.plotly_chart(chart_expense_trend(uid),     use_container_width=True, key="ch_exp_trend")

    # Row 2
    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(chart_category_pie(uid, filter_m),    use_container_width=True, key="ch_cat_pie")
    with c4:
        st.plotly_chart(chart_top_categories(uid, filter_m),  use_container_width=True, key="ch_top_cat")

    # Row 3
    c5, c6 = st.columns(2)
    with c5:
        st.plotly_chart(chart_savings_trend(uid),             use_container_width=True, key="ch_savings")
    with c6:
        st.plotly_chart(chart_daily_spending(uid, filter_m),  use_container_width=True, key="ch_daily")

    # Payment mode
    st.plotly_chart(chart_payment_mode(uid), use_container_width=True, key="ch_pay_mode")

    # Row 4: Trend prediction & Monthly comparison
    st.markdown("<br>", unsafe_allow_html=True)
    c7, c8 = st.columns(2)
    with c7:
        st.plotly_chart(chart_spending_prediction(uid), use_container_width=True, key="ch_predict")
    with c8:
        st.plotly_chart(chart_monthly_comparison(uid), use_container_width=True, key="ch_monthly_comp")

    # Row 5: Yearly summary & MoM category comparison
    st.markdown("<br>", unsafe_allow_html=True)
    c9, c10 = st.columns(2)
    with c9:
        st.plotly_chart(chart_yearly_summary(uid), use_container_width=True, key="ch_yearly")
    with c10:
        st.markdown("<div class='card' style='height:100%;'>", unsafe_allow_html=True)
        st.markdown("<div class='card-title'>📈 MoM Category Growth Comparison</div>", unsafe_allow_html=True)
        cat_comp_df = get_category_comparison(uid)
        if not cat_comp_df.empty:
            cat_comp_disp = cat_comp_df.copy()
            cat_comp_disp.columns = ["Category", "Prev Month Spend", "Curr Month Spend", "Difference", "Change %"]
            st.dataframe(cat_comp_disp, use_container_width=True, hide_index=True)
        else:
            st.info("Insufficient data to compare MoM categories growth.")
        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# BUDGET PLANNER
# ══════════════════════════════════════════════════════════════════════════════

def page_budget():
    uid = st.session_state["user_id"]
    sym = get_sym()
    section_title("📋", "Budget Planner", "Set monthly budgets and track your progress")

    months = month_options(6)
    sel_month = st.selectbox("Month", months, index=0)

    tab_view, tab_set = st.tabs(["📊 Track Budget", "➕ Set Budget"])

    with tab_set:
        with st.form("set_budget_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                b_cat = st.selectbox("Category", EXPENSE_CATEGORIES)
            with c2:
                b_amt = st.number_input("Budget Amount", min_value=1.0, step=100.0)
            with c3:
                b_month = st.selectbox("Month", months, key="bset_month")
            if st.form_submit_button("💾 Save Budget"):
                set_budget(uid, b_cat, b_month, b_amt)
                st.success(f"Budget for {b_cat} in {b_month} set to {fmt_currency(b_amt, sym)}")
                st.rerun()

    with tab_view:
        df_budget = get_budget_comparison(uid, sel_month)
        if df_budget.empty:
            empty_state("📋", "No budgets set",
                        f"Set budgets for {sel_month} using the 'Set Budget' tab above.")
            return

        # Overall budget utilization indicator
        total_budget = df_budget["budget"].sum()
        total_spent = df_budget["spent"].sum()
        if total_budget > 0:
            total_pct = (total_spent / total_budget) * 100
            total_pct_cap = min(total_pct, 100.0)
            overall_fill_class = "ok" if total_pct <= 75 else ("warn" if total_pct <= 100 else "over")
            
            st.markdown(f"""
            <div class="card" style="margin-bottom:1.5rem;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;">
                    <span style="font-weight:700;font-size:0.95rem;color:#f0f0ff;">📊 Overall Budget Utilization</span>
                    <span style="font-family:'Sora';font-weight:700;font-size:1.05rem;color:{'#00B894' if total_pct <= 100 else '#FF6B6B'}">
                        {fmt_currency(total_spent, sym)} / {fmt_currency(total_budget, sym)} ({total_pct:.1f}%)
                    </span>
                </div>
                <div class="progress-bar" style="height:10px;margin-bottom:0.4rem;">
                    <div class="progress-fill {overall_fill_class}" style="width:{total_pct_cap}%;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Overall or critical category warnings
            overspent_cats = df_budget[df_budget["pct_used"] > 100]
            warning_cats = df_budget[(df_budget["pct_used"] > 80) & (df_budget["pct_used"] <= 100)]
            
            for _, row in overspent_cats.iterrows():
                over_amt = row["spent"] - row["budget"]
                insight_card("⚠️", f"Budget Exceeded: {row['category']}", 
                             f"You have spent {fmt_currency(row['spent'], sym)} against a budget of {fmt_currency(row['budget'], sym)} (exceeded by {fmt_currency(over_amt, sym)}).", 
                             "warning")
            for _, row in warning_cats.iterrows():
                insight_card("💡", f"Approaching Budget Limit: {row['category']}", 
                             f"You have used {row['pct_used']}% of your budget ({fmt_currency(row['spent'], sym)} of {fmt_currency(row['budget'], sym)}).", 
                             "info")
            st.markdown("<br>", unsafe_allow_html=True)

        for _, row in df_budget.iterrows():
            pct  = row["pct_used"]
            fill_class = "ok" if pct <= 75 else ("warn" if pct <= 100 else "over")
            pct_capped = min(pct, 100)

            st.markdown(f"""
            <div class="budget-item">
                <div class="budget-header">
                    <div class="budget-category">
                        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                                     background:{CATEGORY_COLORS.get(row['category'],'#888')};
                                     margin-right:6px;"></span>
                        {row['category']}
                    </div>
                    <div class="budget-amounts">
                        {fmt_currency(row['spent'], sym)} / {fmt_currency(row['budget'], sym)}
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill {fill_class}" style="width:{pct_capped}%;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <div class="budget-pct">
                        {'⚠️ OVER BUDGET' if pct > 100 else f'{pct:.1f}% used'}
                    </div>
                    <div class="budget-pct">
                        Remaining: {fmt_currency(max(row['remaining'], 0), sym)}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Delete button
            if st.button(f"🗑️ Remove {row['category']} budget", key=f"del_b_{row['id']}"):
                delete_budget(int(row["id"]), uid)
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SAVINGS GOALS
# ══════════════════════════════════════════════════════════════════════════════

def page_goals():
    uid = st.session_state["user_id"]
    sym = get_sym()
    section_title("🎯", "Savings Goals", "Create and track your financial goals")

    tab_view, tab_add = st.tabs(["🎯 My Goals", "➕ New Goal"])

    with tab_add:
        with st.form("add_goal_form"):
            c1, c2 = st.columns(2)
            with c1:
                g_name   = st.text_input("Goal Name", placeholder="e.g. New Laptop")
                g_target = st.number_input("Target Amount", min_value=1.0, step=500.0)
                g_priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)
            with c2:
                g_saved    = st.number_input("Already Saved", min_value=0.0, step=100.0)
                g_deadline = st.date_input("Target Date (optional)",
                                           value=date.today() + timedelta(days=180))
            if st.form_submit_button("🎯 Create Goal", use_container_width=True):
                if g_name.strip():
                    add_goal(uid, g_name.strip(), g_target, g_saved,
                             str(g_deadline), priority=g_priority)
                    st.success(f"Goal '{g_name}' created!")
                    st.rerun()
                else:
                    st.error("Please enter a goal name.")

    with tab_view:
        goals = get_goals(uid)
        if not goals:
            empty_state("🎯", "No goals yet", "Create your first savings goal above.")
            return

        for g in goals:
            pct     = (g["saved_amount"] / g["target_amount"] * 100) if g["target_amount"] > 0 else 0
            pct_cap = min(pct, 100)
            remain  = g["target_amount"] - g["saved_amount"]

            # Priority flags display next to goal name
            p_val = g.get("priority", "Medium") or "Medium"
            if p_val == "High":
                p_flag = "<span style='background:rgba(255,107,107,0.15);color:#FF6B6B;padding:2px 8px;font-size:0.75rem;border-radius:4px;font-weight:600;margin-left:8px;'>🔴 HIGH PRIORITY</span>"
            elif p_val == "Low":
                p_flag = "<span style='background:rgba(116,185,255,0.15);color:#74B9FF;padding:2px 8px;font-size:0.75rem;border-radius:4px;font-weight:600;margin-left:8px;'>🔵 LOW PRIORITY</span>"
            else:
                p_flag = "<span style='background:rgba(253,203,110,0.15);color:#FDCB6E;padding:2px 8px;font-size:0.75rem;border-radius:4px;font-weight:600;margin-left:8px;'>🟡 MEDIUM PRIORITY</span>"

            # Estimate days / months to reach goal based on 3-month savings average
            df_all = get_df(uid)
            eta = ""
            deadline_status = ""
            avg_save = 0.0
            
            if not df_all.empty:
                monthly_inc = df_all[df_all["type"] == "income"].groupby("month")["amount"].sum()
                monthly_exp = df_all[df_all["type"] == "expense"].groupby("month")["amount"].sum()
                # Get the last 3 active months
                all_active_months = sorted(list(set(monthly_inc.index) | set(monthly_exp.index)))
                last3_months = all_active_months[-3:]
                
                savings_sum = 0.0
                for m in last3_months:
                    savings_sum += (monthly_inc.get(m, 0.0) - monthly_exp.get(m, 0.0))
                
                avg_save = savings_sum / max(len(last3_months), 1)
                
                if remain <= 0:
                    eta = "Goal Achieved! 🎉"
                elif avg_save > 0:
                    daily_save = avg_save / 30.437 # average days in a month
                    days_needed = int(math.ceil(remain / daily_save))
                    comp_date = date.today() + timedelta(days=days_needed)
                    eta = f"Est. Completion: {comp_date.strftime('%d %b %Y')} (~{days_needed} days remaining, at {fmt_currency(avg_save, sym)}/mo savings)"
                    
                    # On track logic
                    g_deadline_str = g.get("deadline")
                    if g_deadline_str:
                        try:
                            g_deadline_dt = datetime.strptime(g_deadline_str, "%Y-%m-%d").date()
                            days_to_deadline = (g_deadline_dt - date.today()).days
                            if days_to_deadline > 0:
                                required_monthly = (remain / days_to_deadline) * 30.437
                                if avg_save >= required_monthly:
                                    deadline_status = "<span style='background:rgba(0,184,148,0.15);color:#00B894;padding:2px 8px;font-size:0.75rem;border-radius:4px;font-weight:600;margin-left:8px;'>✓ ON TRACK</span>"
                                else:
                                    deadline_status = f"<span style='background:rgba(255,107,107,0.15);color:#FF6B6B;padding:2px 8px;font-size:0.75rem;border-radius:4px;font-weight:600;margin-left:8px;'>⚠️ OFF TRACK (Needs {fmt_currency(required_monthly, sym)}/mo)</span>"
                        except Exception:
                            pass
                else:
                    eta = "⚠️ Savings rate is negative or zero. Increase savings to meet goal."
            else:
                eta = "Add transactions to estimate completion timeline"

            st.markdown(f"""
            <div class="goal-card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div>
                        <div class="goal-name">🎯 {g['name']} {p_flag} {deadline_status}</div>
                        <div class="goal-meta">
                            Target: {fmt_currency(g['target_amount'], sym)} &nbsp;•&nbsp;
                            Saved: {fmt_currency(g['saved_amount'], sym)} &nbsp;•&nbsp;
                            Deadline: {g.get('deadline', '—') or '—'}
                        </div>
                    </div>
                    <div class="goal-pct">{pct_cap:.1f}%</div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill {'ok' if pct_cap >= 80 else 'warn'}"
                         style="width:{pct_cap}%;"></div>
                </div>
                <div style="font-size:0.78rem;color:#a0a0c0;margin-top:0.3rem;">
                    {fmt_currency(remain, sym)} remaining &nbsp;•&nbsp; {eta}
                </div>
            </div>
            """, unsafe_allow_html=True)

            c_upd, c_del = st.columns([3, 1])
            with c_upd:
                with st.expander(f"✏️ Edit details for '{g['name']}'"):
                    with st.form(f"edit_goal_form_{g['id']}"):
                        e_name = st.text_input("Goal Name", value=g["name"])
                        e_target = st.number_input("Target Amount", value=float(g["target_amount"]), min_value=1.0)
                        e_saved = st.number_input("Saved Amount", value=float(g["saved_amount"]), min_value=0.0)
                        e_priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=["High", "Medium", "Low"].index(p_val))
                        
                        d_val = date.today() + timedelta(days=180)
                        if g.get("deadline"):
                            try:
                                d_val = datetime.strptime(g["deadline"], "%Y-%m-%d").date()
                            except Exception:
                                pass
                        e_deadline = st.date_input("Target Date", value=d_val)
                        
                        if st.form_submit_button("💾 Save Changes", use_container_width=True):
                            if e_name.strip():
                                update_goal(g["id"], uid, e_saved, name=e_name.strip(), target_amount=e_target, deadline=str(e_deadline), priority=e_priority)
                                st.success("Goal details updated!")
                                st.rerun()
                            else:
                                st.error("Goal name cannot be empty.")
            with c_del:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(f"🗑️ Delete Goal", key=f"del_goal_{g['id']}", use_container_width=True):
                    delete_goal(g["id"], uid)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# AI INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════

def page_insights():
    uid = st.session_state["user_id"]
    sym = get_sym()
    section_title("🤖", "AI Insights", "Smart analysis of your spending — no API keys needed")

    with st.spinner("Analysing your data..."):
        insights = get_insights(uid, sym)

    # Legend
    st.markdown("""
    <div style="display:flex;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap;font-size:0.78rem;">
        <span style="color:#74B9FF;">🔵 Info</span>
        <span style="color:#FDCB6E;">🟡 Warning</span>
        <span style="color:#00B894;">🟢 Success</span>
        <span style="color:#6C5CE7;">🟣 Tip</span>
    </div>
    """, unsafe_allow_html=True)

    for ins in insights:
        insight_card(ins["icon"], ins["title"], ins["detail"], ins["level"])


# ══════════════════════════════════════════════════════════════════════════════
# RECURRING TRANSACTIONS
# ══════════════════════════════════════════════════════════════════════════════

def page_recurring():
    uid = st.session_state["user_id"]
    sym = get_sym()
    section_title("🔄", "Recurring Transactions",
                  "Set up automatic income/expense templates")

    tab_list, tab_add = st.tabs(["📋 Active Recurring", "➕ Add Recurring"])

    with tab_add:
        with st.form("add_recurring_form"):
            c1, c2 = st.columns(2)
            with c1:
                r_type  = st.radio("Type", ["expense", "income"], horizontal=True,
                                   format_func=str.capitalize)
                cats    = EXPENSE_CATEGORIES if r_type == "expense" else INCOME_CATEGORIES
                r_cat   = st.selectbox("Category", cats)
                r_amt   = st.number_input("Amount", min_value=1.0, step=10.0)
            with c2:
                r_note  = st.text_input("Note / Label")
                r_mode  = st.selectbox("Payment Mode", PAYMENT_MODES)
                r_freq  = st.selectbox("Frequency", ["monthly", "weekly"])
                r_date  = st.date_input("Next Due Date",
                                        value=date.today() + timedelta(days=30))
            if st.form_submit_button("💾 Save Recurring"):
                add_recurring(uid, r_type, r_amt, r_cat, r_note, r_mode, r_freq, str(r_date))
                st.success("Recurring transaction saved!")
                st.rerun()

    with tab_list:
        recs = get_recurring(uid)
        if not recs:
            empty_state("🔄", "No recurring transactions",
                        "Add salary, rent, subscriptions, etc.")
            return

        for r in recs:
            color = "#00B894" if r["type"] == "income" else "#FF6B6B"
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
                        padding:0.8rem 1.1rem;border-radius:10px;margin-bottom:0.5rem;
                        background:#1a1a2e;border:1px solid rgba(255,255,255,0.06);">
                <div>
                    <div style="font-weight:600;font-size:0.9rem;color:#f0f0ff;">
                        {r.get('note') or r['category']}
                    </div>
                    <div style="font-size:0.78rem;color:#a0a0c0;">
                        {r['category']} • {r['frequency'].capitalize()} •
                        Next: {r.get('next_date','—')}
                    </div>
                </div>
                <div style="font-family:'Sora';font-weight:700;color:{color};">
                    {fmt_currency(r['amount'], sym)}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"🗑️ Remove", key=f"del_rec_{r['id']}"):
                delete_recurring(r["id"], uid)
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# IMPORT (Phase 1 — Bank Statement, Phase 2 — OCR, Phase 3 — Gmail)
# ══════════════════════════════════════════════════════════════════════════════

def page_import():
    # Lazy imports — only loaded when user visits Import page
    from bank_parser import parse_statement_to_df, parse_statement, get_supported_banks
    from ocr_parser import parse_screenshot, parse_upi_screenshot
    from gmail_parser import (
        is_credentials_available, is_authenticated, get_auth_url,
        authenticate_with_code, authenticate_local, sync_gmail_transactions,
        disconnect, get_connected_email
    )

    uid = st.session_state["user_id"]
    sym = get_sym()
    section_title("📥", "Import Transactions",
                  "Import from bank statements, UPI screenshots, or email")

    tab_bank, tab_ocr, tab_email = st.tabs([
        "🏦 Bank Statement", "📸 UPI Screenshot", "📧 Gmail Sync"
    ])

    # ── BANK STATEMENT TAB ────────────────────────────────────────────────────
    with tab_bank:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📄 Upload Bank Statement</div>',
                    unsafe_allow_html=True)

        # Supported banks info
        banks = get_supported_banks()
        bank_names = [b["name"] for b in banks]
        st.markdown(f"""
        <div style="font-size:0.82rem;color:#a0a0c0;margin-bottom:1rem;">
            Supports <strong>{len(banks)} banks</strong>: {', '.join(bank_names[:6])} and more.
            Upload CSV, Excel, or PDF from your net banking.
        </div>
        """, unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Choose a bank statement file",
            type=["csv", "xlsx", "xls", "pdf"],
            key="bank_upload",
        )

        # Optional bank override
        bank_keys = ["Auto-Detect"] + [b["key"] for b in banks]
        sel_bank = st.selectbox("Bank (optional)", bank_keys, index=0,
                                help="Leave on Auto-Detect — we'll identify your bank automatically.")
        bank_hint = None if sel_bank == "Auto-Detect" else sel_bank

        if uploaded:
            ext = uploaded.name.rsplit(".", 1)[-1] if "." in uploaded.name else ""
            file_bytes = uploaded.read()

            with st.spinner("Parsing statement..."):
                try:
                    df, bank_name = parse_statement_to_df(file_bytes, ext, bank_hint)
                except Exception as e:
                    st.error(f"❌ Failed to parse: {e}")
                    st.markdown('</div>', unsafe_allow_html=True)
                    return

            if df.empty:
                empty_state("📭", "No transactions found",
                            "The file was parsed but no valid transactions were detected.")
                st.markdown('</div>', unsafe_allow_html=True)
                return

            # Detection info
            st.success(f"🏦 Detected: **{bank_name}** — {len(df)} transactions found")

            # Duplicate transaction check
            from bank_parser import flag_duplicate_transactions_in_df
            df_flagged = flag_duplicate_transactions_in_df(df, uid)
            dup_db_count = len(df_flagged[df_flagged["Status"] == "Duplicate (Exists)"])
            dup_file_count = len(df_flagged[df_flagged["Status"] == "Duplicate (File)"])
            total_dup = dup_db_count + dup_file_count
            
            if total_dup > 0:
                warn_msg = f"⚠️ Found **{total_dup} duplicate transactions** in this statement."
                if dup_db_count > 0:
                    warn_msg += f" {dup_db_count} already exist in your database."
                if dup_file_count > 0:
                    warn_msg += f" {dup_file_count} are duplicates within the file itself."
                warn_msg += " Duplicate transactions will be automatically skipped on import."
                st.warning(warn_msg)

            # Summary strip
            inc_count = len(df[df['type'] == 'income'])
            exp_count = len(df[df['type'] == 'expense'])
            total_inc = df[df['type'] == 'income']['amount'].sum()
            total_exp = df[df['type'] == 'expense']['amount'].sum()
            st.markdown(f"""
            <div style="display:flex;gap:1rem;margin:1rem 0;flex-wrap:wrap;">
                <div style="background:#0f2a1f;border:1px solid #00B894;border-radius:8px;
                            padding:0.4rem 1rem;font-size:0.85rem;color:#00B894;font-weight:600;">
                    ↑ {inc_count} Income: {fmt_currency(total_inc, sym)}
                </div>
                <div style="background:#2a0f0f;border:1px solid #FF6B6B;border-radius:8px;
                            padding:0.4rem 1rem;font-size:0.85rem;color:#FF6B6B;font-weight:600;">
                    ↓ {exp_count} Expenses: {fmt_currency(total_exp, sym)}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Preview table
            st.markdown("**Preview (first 20 rows):**")
            preview = df_flagged.head(20).copy()
            preview["trans_date"] = preview["trans_date"].astype(str)
            cols_order = ["Status", "trans_date", "type", "amount", "category", "note", "payment_mode"]
            cols_order = [c for c in cols_order if c in preview.columns]
            st.dataframe(preview[cols_order], use_container_width=True, hide_index=True)

            # Import button
            if st.button("✅ Import All Transactions", use_container_width=True,
                         type="primary", key="import_btn"):
                with st.spinner("Importing..."):
                    uploaded.seek(0)
                    result = parse_statement(file_bytes, ext, uid, bank_hint)
                st.success(result["message"])
                if result["imported"] > 0:
                    st.balloons()
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ── UPI SCREENSHOT TAB ─────────────────────────────────────────────────────
    with tab_ocr:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📸 UPI Screenshot OCR</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:0.82rem;color:#a0a0c0;margin-bottom:1rem;">
            Upload a payment screenshot from <strong>Google Pay, PhonePe, Paytm,
            BHIM, Amazon Pay, or CRED</strong>. We'll extract the amount, merchant,
            and date automatically using local OCR. <em>No data leaves your machine.</em>
        </div>
        """, unsafe_allow_html=True)

        ocr_file = st.file_uploader(
            "Upload UPI screenshot",
            type=["png", "jpg", "jpeg", "webp"],
            key="ocr_upload",
            accept_multiple_files=False,
        )

        if ocr_file:
            img_bytes = ocr_file.read()

            # Show uploaded image
            st.image(img_bytes, caption="Uploaded Screenshot", width=300)

            with st.spinner("🔍 Running OCR (this may take a moment on first run)..."):
                try:
                    parsed = parse_screenshot(img_bytes)
                except Exception as e:
                    st.error(f"❌ OCR failed: {e}")
                    st.markdown('</div>', unsafe_allow_html=True)
                    return

            if not parsed["amount"]:
                st.warning("⚠️ Could not extract amount. Try a clearer screenshot.")
                with st.expander("🔎 Raw OCR text (debug)"):
                    st.code(parsed["raw_text"])
                st.markdown('</div>', unsafe_allow_html=True)
                return

            # Show extracted data
            st.success(f"✅ Detected: **{parsed['app'].replace('_', ' ').title()}** screenshot")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div style="background:#1a1a2e;border:1px solid #6C5CE7;border-radius:10px;
                            padding:1rem;margin:0.5rem 0;">
                    <div style="color:#a0a0c0;font-size:0.75rem;">AMOUNT</div>
                    <div style="color:#6C5CE7;font-size:1.6rem;font-weight:700;">₹{parsed['amount']:,.2f}</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div style="background:#1a1a2e;border:1px solid #00B894;border-radius:10px;
                            padding:1rem;margin:0.5rem 0;">
                    <div style="color:#a0a0c0;font-size:0.75rem;">MERCHANT</div>
                    <div style="color:#00B894;font-size:1.1rem;font-weight:600;">{parsed['merchant']}</div>
                </div>
                """, unsafe_allow_html=True)

            # Editable fields before import
            st.markdown("---")
            st.markdown("**Review & Edit before importing:**")

            edit_c1, edit_c2, edit_c3 = st.columns(3)
            with edit_c1:
                edit_amount = st.number_input("Amount (₹)", value=parsed["amount"],
                                              min_value=0.01, key="ocr_amount")
            with edit_c2:
                # Type toggle — default from OCR detection
                txn_type_options = ["expense", "income"]
                default_type_idx = 1 if parsed.get("type") == "income" else 0
                edit_type = st.selectbox(
                    "Type",
                    options=["💸 Expense", "💰 Income"],
                    index=default_type_idx,
                    key="ocr_type"
                )
                is_income = (edit_type == "💰 Income")
            with edit_c3:
                edit_date = st.date_input("Date", value=parsed["date"], key="ocr_date")

            # Category — show income or expense categories based on type
            from utils import auto_detect_category, EXPENSE_CATEGORIES, INCOME_CATEGORIES
            txn_type_str = "income" if is_income else "expense"
            default_cat = auto_detect_category(parsed["merchant"], txn_type_str)
            cat_list = list(INCOME_CATEGORIES) if is_income else list(EXPENSE_CATEGORIES)
            cat_idx = cat_list.index(default_cat) if default_cat in cat_list else 0
            edit_category = st.selectbox("Category", cat_list, index=cat_idx, key="ocr_cat")

            edit_note = st.text_input("Note", value=parsed["merchant"][:80], key="ocr_note")

            # Extra info
            if parsed["upi_id"] or parsed["txn_id"]:
                info_parts = []
                if parsed["upi_id"]: info_parts.append(f"UPI: {parsed['upi_id']}")
                if parsed["txn_id"]: info_parts.append(f"Txn ID: {parsed['txn_id']}")
                st.caption(" | ".join(info_parts))

            # Import button
            if st.button("✅ Import Transaction", use_container_width=True,
                         type="primary", key="ocr_import_btn"):
                from database import add_transaction
                try:
                    add_transaction(
                        uid, txn_type_str, float(edit_amount), edit_category,
                        edit_note[:100], "UPI", str(edit_date)
                    )
                    icon = "💰" if is_income else "💸"
                    st.success(f"✅ Imported {icon} ₹{edit_amount:,.2f} → {edit_category}")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Import failed: {e}")

            # Debug expander
            with st.expander("🔎 Raw OCR text"):
                st.code(parsed["raw_text"])

        st.markdown('</div>', unsafe_allow_html=True)

    # ── EMAIL SYNC TAB ───────────────────────────────────────────────────────
    with tab_email:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📧 Gmail Transaction Sync</div>',
                    unsafe_allow_html=True)

        if not is_credentials_available():
            # No credentials.json — show setup instructions
            st.markdown("""
            <div style="font-size:0.85rem;color:#a0a0c0;">
                <strong>One-time setup required:</strong>
                <ol style="margin-top:0.5rem;">
                    <li>Go to <a href="https://console.cloud.google.com" target="_blank"
                        style="color:#6C5CE7;">Google Cloud Console</a></li>
                    <li>Create a project &rarr; Enable <strong>Gmail API</strong></li>
                    <li>Create <strong>OAuth 2.0 Client ID</strong> (Desktop app type)</li>
                    <li>Download <code>credentials.json</code></li>
                    <li>Place it in: <code>finance_tracker/data/</code></li>
                    <li>Reload this page</li>
                </ol>
                <p style="margin-top:0.5rem;color:#FF6B6B;">
                    ⚠️ This uses <strong>Gmail read-only</strong> access.
                    We only read bank alert emails. No emails are modified or deleted.
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Debug expander — shows exactly why credentials failed to load
            with st.expander("🔍 Debug: Why isn't Gmail loading? (click to check)"):
                from gmail_parser import get_credentials_debug_info
                st.code(get_credentials_debug_info())

        elif is_authenticated():
            # Connected — show sync controls
            email = get_connected_email()
            st.markdown(f"""
            <div style="background:#0f2a1f;border:1px solid #00B894;border-radius:10px;
                        padding:0.8rem 1rem;margin-bottom:1rem;display:flex;
                        align-items:center;gap:0.5rem;">
                <span style="font-size:1.2rem;">✅</span>
                <div>
                    <div style="color:#00B894;font-weight:600;">Connected</div>
                    <div style="color:#a0a0c0;font-size:0.8rem;">{email or 'Gmail account'}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            days = st.slider("Scan emails from last N days", 7, 90, 30, key="gmail_days")

            col_sync, col_disconnect = st.columns([3, 1])
            with col_sync:
                if st.button("🔄 Sync Now", use_container_width=True,
                             type="primary", key="gmail_sync_btn"):
                    with st.spinner("📧 Scanning Gmail for bank alerts..."):
                        result = sync_gmail_transactions(uid, days)
                    st.success(result["message"])
                    if result["imported"] > 0:
                        st.balloons()
                        # Show imported transactions
                        st.markdown("**Imported transactions:**")
                        for t in result.get("transactions", []):
                            st.markdown(
                                f"- {t['bank']}: {t['type'].title()} "
                                f"₹{t['amount']:,.2f} — {t['merchant']} "
                                f"({t['date']}) via {t['payment_mode']}"
                            )
            with col_disconnect:
                if st.button("❌ Disconnect", use_container_width=True,
                             key="gmail_disconnect_btn"):
                    disconnect()
                    st.rerun()

        else:
            # Credentials exist but not authenticated — show connect flow
            st.markdown("""
            <div style="font-size:0.82rem;color:#a0a0c0;margin-bottom:1rem;">
                Connect your Gmail to automatically import bank transaction alerts from
                <strong>SBI, HDFC, ICICI, Axis, Kotak</strong> and more.
                We use <strong>read-only</strong> access — no emails are modified.
            </div>
            """, unsafe_allow_html=True)

            auth_url = get_auth_url()
            if auth_url:
                st.markdown("""
                <div style="background:#1a1a2e;border:1px solid #6C5CE7;border-radius:12px;
                            padding:1.2rem;margin-bottom:1rem;">
                    <div style="color:#f0f0ff;font-weight:600;margin-bottom:0.8rem;">
                        🔐 How to Connect Gmail (3 steps):
                    </div>
                    <div style="color:#a0a0c0;font-size:0.85rem;line-height:1.8;">
                        <b style="color:#6C5CE7;">Step 1:</b> Click the button below → Google sign-in opens<br>
                        <b style="color:#6C5CE7;">Step 2:</b> Allow access → browser shows an error page
                        <span style="color:#FDCB6E;">(that's normal! ✓)</span><br>
                        <b style="color:#6C5CE7;">Step 3:</b> Copy the <b>full URL</b> from your browser's address bar
                        and paste it below
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.link_button("🔐 Step 1: Open Google Authorization", auth_url,
                               use_container_width=True, type="primary")

                st.markdown("""
                <div style="font-size:0.8rem;color:#FDCB6E;margin:0.5rem 0;">
                    ⚠️ After clicking Allow on Google, your browser will redirect to
                    <code>http://localhost/?code=...</code> and show "This site can't be reached"
                    — that's expected! Just copy the entire URL from the address bar.
                </div>
                """, unsafe_allow_html=True)

                redirect_url = st.text_input(
                    "📋 Step 3: Paste the full redirect URL here (or just the code after 'code=')",
                    key="gmail_code",
                    placeholder="http://localhost/?code=4/0AX4XfW... OR just the code itself"
                )
                if redirect_url and st.button("✅ Connect Gmail", key="gmail_code_btn",
                                              use_container_width=True, type="primary"):
                    with st.spinner("Verifying..."):
                        result = authenticate_with_code(redirect_url.strip())
                    if result["success"]:
                        st.success(result["message"])
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(result["message"])

        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def page_export():
    uid = st.session_state["user_id"]
    sym = get_sym()
    section_title("📤", "Export Reports", "Download your data as Excel or PDF")

    months = ["All"] + month_options(12)
    sel_month = st.selectbox("Filter by Month (optional)", months)
    filter_m  = None if sel_month == "All" else sel_month

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("""
        <div class="card">
            <div class="card-title">📊 Excel Report</div>
            <div style="color:#a0a0c0;font-size:0.85rem;margin-bottom:1rem;">
                Includes transactions, summary, and goals in separate sheets.
            </div>
        </div>
        """, unsafe_allow_html=True)
        xlsx_data = export_excel(uid, filter_m, sym)
        fname = f"finance_{filter_m or 'all'}_{date.today()}.xlsx"
        st.download_button("⬇️ Download Excel", xlsx_data,
                           file_name=fname,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

    with c2:
        st.markdown("""
        <div class="card">
            <div class="card-title">📄 PDF Summary</div>
            <div style="color:#a0a0c0;font-size:0.85rem;margin-bottom:1rem;">
                A professional printable report with summary, transactions, and goals.
            </div>
        </div>
        """, unsafe_allow_html=True)
        pdf_data = export_pdf(uid, filter_m, sym)
        pname = f"finance_report_{filter_m or 'all'}_{date.today()}.pdf"
        st.download_button("⬇️ Download PDF", pdf_data,
                           file_name=pname,
                           mime="application/pdf",
                           use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

def page_settings():
    uid  = st.session_state["user_id"]
    user = get_current_user()
    cfg  = get_settings(uid)
    section_title("⚙️", "Settings & Profile", "Manage your preferences and account")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">👤 Profile</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="margin-bottom:1rem;">
            <div style="font-size:0.78rem;color:#a0a0c0;">Full Name</div>
            <div style="font-weight:600;">{user.get('full_name') or '—'}</div>
        </div>
        <div style="margin-bottom:1rem;">
            <div style="font-size:0.78rem;color:#a0a0c0;">Username</div>
            <div style="font-weight:600;">@{user.get('username','')}</div>
        </div>
        <div style="margin-bottom:1rem;">
            <div style="font-size:0.78rem;color:#a0a0c0;">Email</div>
            <div style="font-weight:600;">{user.get('email','')}</div>
        </div>
        <div>
            <div style="font-size:0.78rem;color:#a0a0c0;">Member Since</div>
            <div style="font-weight:600;">{str(user.get('created_at',''))[:10]}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🔧 Preferences</div>', unsafe_allow_html=True)
        with st.form("settings_form"):
            curr_keys   = list(CURRENCIES.keys())
            curr_idx    = curr_keys.index(cfg.get("currency", "INR (₹)")) \
                          if cfg.get("currency") in curr_keys else 0
            sel_currency = st.selectbox("Currency", curr_keys, index=curr_idx)
            sel_theme    = st.selectbox("Theme", ["dark", "light"],
                                        index=0 if cfg.get("theme","dark") == "dark" else 1)
            if st.form_submit_button("💾 Save Settings"):
                update_settings(uid, sel_currency, sel_theme)
                st.success("Settings saved!")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Danger zone
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("⚠️ Danger Zone — Reset Data"):
        st.warning("This will permanently delete ALL your transactions, budgets, and goals. "
                   "Your account will remain.")
        confirm = st.text_input("Type **RESET** to confirm", key="reset_confirm")
        if st.button("🗑️ Reset All My Data", type="primary"):
            if confirm == "RESET":
                reset_user_data(uid)
                st.success("All data deleted.")
                st.rerun()
            else:
                st.error("Please type RESET to confirm.")

    # JSON Backup & Restore section
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card-title">💾 JSON Data Backup & Restore</div>', unsafe_allow_html=True)
    cb1, cb2 = st.columns(2)
    with cb1:
        st.markdown("""
        <div class="card">
            <div class="card-title">📥 Export JSON Backup</div>
            <div style="color:#a0a0c0;font-size:0.85rem;margin-bottom:1rem;">
                Download your full transactions, budgets, goals, and preferences in a single portable JSON file.
            </div>
        </div>
        """, unsafe_allow_html=True)
        try:
            backup_dict = backup_user_data(uid)
            backup_json = json.dumps(backup_dict, indent=2)
            st.download_button("⬇️ Download JSON Backup", backup_json,
                               file_name=f"finance_data_{date.today()}.json",
                               mime="application/json",
                               use_container_width=True,
                               key="json_backup_btn")
        except Exception as e:
            st.error(f"Failed to generate backup: {e}")

    with cb2:
        st.markdown("""
        <div class="card">
            <div class="card-title">📤 Import JSON Backup</div>
            <div style="color:#a0a0c0;font-size:0.85rem;margin-bottom:1rem;">
                Restore all your data from a valid JSON backup file.
                <span style="color:#FF6B6B;">⚠️ Warning: This will overwrite your current settings, budgets, transactions, and goals!</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        restore_file = st.file_uploader("Upload JSON backup", type=["json"], key="json_restore_upload")
        if restore_file:
            try:
                restore_data = json.loads(restore_file.read().decode("utf-8"))
                if st.button("🚨 Confirm and Restore Data", type="primary", use_container_width=True, key="confirm_json_restore_btn"):
                    if restore_user_data(uid, restore_data):
                        st.success("✅ Financial data successfully restored!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Failed to restore data. Check backup file format.")
            except Exception as e:
                st.error(f"❌ Error parsing backup: {e}")

    # DB Backup
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card-title">💾 SQLite Database Backup</div>', unsafe_allow_html=True)
    db_path = os.path.join(os.path.dirname(__file__), "data", "finance.db")
    if os.path.exists(db_path):
        with open(db_path, "rb") as f:
            db_bytes = f.read()
        st.download_button("⬇️ Download Database Backup (.db)",
                           db_bytes,
                           file_name=f"finance_backup_{date.today()}.db",
                           mime="application/octet-stream",
                           use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if not is_logged_in():
        page_auth()
        return

    current_page = sidebar_nav()

    page_map = {
        "Dashboard":     page_dashboard,
        "Transactions":  page_transactions,
        "Import":        page_import,
        "Analytics":     page_analytics,
        "Budget Planner":page_budget,
        "Savings Goals": page_goals,
        "AI Insights":   page_insights,
        "Recurring":     page_recurring,
        "Export":        page_export,
        "Settings":      page_settings,
    }

    fn = page_map.get(current_page, page_dashboard)
    fn()


if __name__ == "__main__":
    import time
    from nexpulse_telemetry import report_page_run
    _started_at = time.monotonic()
    try:
        main()
    finally:
        report_page_run(st.session_state.get("current_page", "auth"), _started_at)
