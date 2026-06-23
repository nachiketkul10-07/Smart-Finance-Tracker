# 💰 Smart Finance Tracker v2.0

A **production-quality**, fully local Personal Finance Manager built with Python + Streamlit.  
No API keys. No cloud. Everything runs locally on your machine.

---

## ✨ Features at a Glance

| Feature | Description |
|---|---|
| 🔐 Auth | Register / Login / Logout with bcrypt password hashing |
| 🏠 Dashboard | KPI cards, growth MoM deltas, financial health score, best/worst month stats, recent transactions |
| 💸 Transactions | Add, edit, duplicate, search, sort, and tag income & expenses with auto-category detection |
| 📊 Analytics | 10 interactive Plotly charts (trend, pie, bar, savings, regression prediction, monthly/yearly summaries, category comparisons) |
| 📋 Budget Planner | Set category budgets with progress bars, overall utilization card, and overspending warnings |
| 🎯 Savings Goals | Priority ranking, target date, days remaining, target completion prediction using 3-month savings average, track status |
| 🤖 AI Insights | Offline rule-based insights, risk alerts, subscription alerts, weekend analysis, and ML expense prediction |
| 🔄 Recurring | Templates for auto-debit, subscriptions, and salary with weekly/monthly frequency |
| 📥 Import Pipeline | Parse bank statements (CSV/Excel/PDF for 14+ banks), UPI screenshots (local Tesseract OCR), or Gmail alert synchronization with pre-save duplicate checking |
| 📤 Export | Download professionally styled Excel (.xlsx) and PDF reports with stats tables and progress bars |
| ⚙️ Settings | Currency selection, light/dark preference, profile information, and SQLite (.db) / JSON backup & restore |
| 🎲 Demo Data | One-click sample data loader for testing dashboard and analytics |

---

## 📁 Project Structure

```
finance_tracker/
├── app.py                  # Main Streamlit UI, routing, page view templates
├── database.py             # SQLite database schemas, CRUD operations, backup/restore helpers
├── auth.py                 # User auth logic, password hashing, session management
├── analytics.py            # Pandas calculations, cached query aggregates, Plotly charts
├── ai_insights.py          # Local rules-based engine, alerts, regression forecast model
├── bank_parser.py          # Column normalizer, multi-format (CSV/Excel/PDF) bank statement parser, duplicate flagger
├── ocr_parser.py           # Screenshot text extractor using local Tesseract OCR engine
├── gmail_parser.py         # Gmail read-only OAuth credentials, fetch alerts, sync transactions
├── export_utils.py         # Formatted Excel exporter, ReportLab PDF layout generator
├── utils.py                # Helpers, input validation rules, constants, sample dataset
├── requirements.txt        # Python package dependencies
├── README.md               # This file
├── assets/
│   └── style.css           # Premium dark-mode styling variables and UI components
└── data/
    └── finance.db          # SQLite local database file (auto-initialized and migrated)
```

---

## 🚀 Quick Start

### 1. Clone / Download

```bash
git clone <repo-url>
cd finance_tracker
```

### 2. Create a virtual environment

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

### 4. Install Tesseract OCR (Optional — for UPI Screenshot upload)
- Download and install Tesseract OCR for your system (e.g., from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)).
- Add Tesseract to your PATH or verify its installation to enable UPI payment screenshot reading.

### 5. Run the app

```bash
streamlit run app.py
```

The app opens automatically at **http://localhost:8501**

---

## 🖥️ Screen Guide

### Auth Screen
- **Register** a new account with username, email, password.
- **Login** with secure bcrypt credentials validation.

### Dashboard
- Comprehensive metrics header showing Income, Expenses, Net Savings, and Month Growth deltas.
- **Advanced Stats**: Financial Health Score (0-100), Top Category, Best/Worst month, and Expense/Savings Trend indicators.
- Donut & Grouped Bar interactive charts for visual breakdowns.
- Activity feed showing recent transaction logs.

### Transactions
- **Add Transactions**: Input amount, select category, select date/payment mode, add description and comma-separated tags.
- **Manage Transactions**: Search note/tags, filter by category/month/type, and sort (newest, oldest, highest, lowest).
- **Edit / Duplicate**: Easily clone or update existing transactions without losing context.
- **Bulk Delete**: Safely select multiple items and delete them in one action.

### Import Transactions
- **Bank Statement**: Import PDF, CSV, or Excel net banking exports. Auto-detects column mappings and banks. Checks for duplicates and alerts you before importing.
- **UPI Screenshot**: Upload screenshots from Google Pay, PhonePe, Paytm, CRED, etc. Extracts merchant, amount, date using local OCR.
- **Gmail Sync**: Authenticate with Gmail OAuth to pull transactions directly from your email alerts.

### Budget Planner
- Set monthly limits per category.
- Displays an **Overall Budget Utilization** progress indicator.
- Highlights approaching and over-budget limits using warning banners.

### Savings Goals
- Set target amount, deadline, and priority rank (High, Medium, Low).
- Shows progress bar, remaining amount, and days remaining.
- Predicts completion dates based on a rolling 3-month savings average.
- Indicators display if goals are **On Track** or **Off Track**.

### AI Insights (100% Local)
- Deep analysis of spending patterns compared to the previous month.
- Detects recurring subscription bills and anomalous spikes (2.5x mean).
- Recommends optimizations for weekend/weekday habits.
- Predicts end-of-month expenses using scikit-learn Linear Regression.

### Settings & Backup
- Save preferences such as display currency and base theme.
- **JSON Backup**: Download a clean, portable backup JSON and restore it at any time with a click.
- **SQLite Database**: Download a raw database copy (.db) for backup/migrations.

---

## 📜 License

MIT — free to use, modify, and distribute.

---

*Built with ❤️ using Python + Streamlit. 100% local, 100% private.*
