# 💰 Smart Finance Tracker

A **production-quality**, fully local Personal Finance Manager built with Python + Streamlit.  
No API keys. No cloud. Everything runs on your machine.

---

## ✨ Features at a Glance

| Feature | Description |
|---|---|
| 🔐 Auth | Register / Login / Logout with bcrypt password hashing |
| 🏠 Dashboard | KPI cards, recent transactions, monthly summary |
| 💸 Transactions | Add, edit, delete income & expenses with auto-category detection |
| 📊 Analytics | 7 interactive Plotly charts (trend, pie, bar, savings) |
| 📋 Budget Planner | Set monthly budgets with progress bars & alerts |
| 🎯 Savings Goals | Create goals with ETA estimation |
| 🤖 AI Insights | 10+ smart rule-based insights + ML expense prediction |
| 🔄 Recurring | Set up salary, rent, subscriptions as recurring entries |
| 📤 Export | Download Excel (.xlsx) and PDF reports |
| ⚙️ Settings | Currency selection, theme, profile, data backup |
| 🎲 Demo Data | One-click sample data loader |

---

## 📁 Project Structure

```
finance_tracker/
├── app.py                  # Main Streamlit app + all page routers
├── database.py             # SQLite schema + all CRUD helpers
├── auth.py                 # Registration, login, bcrypt hashing
├── analytics.py            # Pandas aggregations + Plotly charts
├── ai_insights.py          # Rule-based + sklearn insights engine
├── export_utils.py         # Excel (xlsxwriter) + PDF (reportlab) export
├── utils.py                # Constants, category maps, sample data
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── assets/
│   └── style.css           # Premium dark-mode CSS theme
└── data/
    └── finance.db          # SQLite database (auto-created on first run)
```

---

## 🚀 Quick Start

### 1. Clone / Download

```bash
git clone <repo-url>
cd finance_tracker
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app opens automatically at **http://localhost:8501**

---

## 🖥️ Screen Guide

### Auth Screen
- **Register** a new account (username, email, password)
- **Login** with your credentials
- Passwords are hashed with bcrypt — never stored in plain text

### Dashboard
- See total income, expenses, net savings at a glance
- Current month KPIs with savings rate
- Income vs Expense bar chart + category pie chart
- Scrollable recent transactions list

### Transactions
- **Add** income or expenses with date, category, payment mode, notes
- **Auto-detect** category from note keywords (e.g. "Swiggy" → Food)
- **Quick Add** buttons for common expenses
- **Filter** by month, category, type, or search by note
- **Edit** any transaction inline
- **Delete** with one click

### Analytics
- Monthly expense trend (line chart)
- Income vs Expense grouped bar (last 6 months)
- Category pie/donut chart
- Top spending categories (horizontal bar)
- Cumulative savings trend
- Daily spending calendar
- Payment mode distribution

### Budget Planner
- Set per-category monthly budgets
- Visual progress bars (green → yellow → red as you approach/exceed)
- Warning when budget is 80%+ used
- Over-budget alert

### Savings Goals
- Create goals with target, current saved, and deadline
- Progress bar with %
- ETA estimation based on your last 3 months average savings

### AI Insights
- Category spending change vs last month
- Top spending category
- Unusual high expense detection (2.5x average)
- Budget exceeded warnings
- Linear regression–based month-end expense prediction
- Best day of week (lowest spending)
- Savings rate feedback
- Weekend vs weekday spending analysis
- Subscription cost alert

### Recurring Transactions
- Save templates for salary, rent, Netflix, etc.
- Choose monthly or weekly frequency
- Set next due date

### Export
- **Excel**: 3 sheets — Transactions, Summary, Goals (styled with xlsxwriter)
- **PDF**: Professional A4 report with summary table, recent transactions, goals

### Settings
- Change display currency (INR, USD, EUR, GBP, JPY)
- View profile details
- Reset all financial data (with confirmation)
- Download database backup (.db file)

---

## 🔮 AI Insights (No API)

The insights engine works entirely offline using:

1. **Pandas rules** — compares current month vs previous month per category
2. **Statistical thresholds** — flags transactions > 2.5x the monthly average
3. **Budget tracking** — reads your set budgets and compares against actual spend
4. **scikit-learn LinearRegression** — fits a cumulative spending curve to predict end-of-month total
5. **Day-of-week analysis** — finds your cheapest and most expensive days

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web UI framework |
| `pandas` | Data processing |
| `plotly` | Interactive charts |
| `bcrypt` | Password hashing |
| `openpyxl` / `xlsxwriter` | Excel export |
| `reportlab` | PDF export |
| `scikit-learn` | Expense prediction |
| `numpy` | Numerical ops |

---

## 🛠️ Future Improvements

- [ ] Multi-currency conversion with live rates
- [ ] Bank statement CSV import
- [ ] Email report scheduling
- [ ] Mobile PWA wrapper
- [ ] Budget vs actual line chart overlay
- [ ] Investment portfolio tracker
- [ ] Tax report generator
- [ ] Dark/light theme toggle in UI

---

## 📜 License

MIT — free to use, modify, and distribute.

---

*Built with ❤️ using Python + Streamlit. 100% local, 100% private.*
