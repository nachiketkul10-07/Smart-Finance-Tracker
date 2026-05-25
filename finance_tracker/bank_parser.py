"""
bank_parser.py
--------------
Universal bank statement parser supporting 14+ Indian banks.
Handles CSV, Excel, and PDF formats with auto-detection.
"""

import io
import re
import pandas as pd
from datetime import datetime
from typing import Optional
from database import add_transaction, get_transactions
from utils import auto_detect_category

# ══════════════════════════════════════════════════════════════════════════════
# BANK PROFILES — column mappings & date formats per bank
# ══════════════════════════════════════════════════════════════════════════════

BANK_PROFILES = {
    "SBI": {
        "name": "State Bank of India",
        "date_cols":    ["Txn Date", "Transaction Date", "Value Date", "Date"],
        "narration_cols": ["Description", "Narration", "Particulars", "Ref No./Cheque No."],
        "debit_cols":   ["Debit", "Debit (\u20b9)", "Debit (Rs)", "Withdrawal", "Debit Amount", "Dr"],
        "credit_cols":  ["Credit", "Credit (\u20b9)", "Credit (Rs)", "Deposit", "Credit Amount", "Cr"],
        "balance_cols": ["Balance", "Balance (\u20b9)", "Balance (Rs)", "Closing Balance"],
        "ref_cols":     ["Ref No", "Reference", "Chq/Ref No", "Ref No./Cheque No."],
        "date_formats": ["%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y", "%Y-%m-%d"],
        "skip_keywords": ["SAMPLE BANK STATEMENT", "Account Holder", "Account Number", "Statement Period", "Branch", "IFSC", "Customer", "CIF"],
        "detect_keywords": ["SBI", "State Bank", "SBIN"],
    },
    "HDFC": {
        "name": "HDFC Bank",
        "date_cols":    ["Date", "Transaction Date", "Value Dt"],
        "narration_cols": ["Narration", "Description", "Particulars"],
        "debit_cols":   ["Withdrawal Amount", "Debit Amount", "Debit", "Withdrawal Amt."],
        "credit_cols":  ["Deposit Amount", "Credit Amount", "Credit", "Deposit Amt."],
        "balance_cols": ["Closing Balance", "Balance"],
        "ref_cols":     ["Chq./Ref.No.", "Ref No", "Reference No"],
        "date_formats": ["%d/%m/%y", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y"],
        "skip_keywords": ["HDFC BANK", "Branch", "Account", "IFSC"],
        "detect_keywords": ["HDFC", "HDFCBANK"],
    },
    "ICICI": {
        "name": "ICICI Bank",
        "date_cols":    ["Transaction Date", "Value Date", "Date", "S No."],
        "narration_cols": ["Transaction Remarks", "Particulars", "Description"],
        "debit_cols":   ["Withdrawal Amount (INR )", "Debit", "Withdrawal Amount", "Withdrawal"],
        "credit_cols":  ["Deposit Amount (INR )", "Credit", "Deposit Amount", "Deposit"],
        "balance_cols": ["Balance (INR )", "Balance"],
        "ref_cols":     ["Cheque Number", "Ref No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y"],
        "skip_keywords": ["ICICI", "Branch", "Account"],
        "detect_keywords": ["ICICI"],
    },
    "Axis": {
        "name": "Axis Bank",
        "date_cols":    ["Tran Date", "Transaction Date", "Date"],
        "narration_cols": ["Particulars", "Description", "Narration"],
        "debit_cols":   ["Debit", "Dr Amount", "Withdrawal"],
        "credit_cols":  ["Credit", "Cr Amount", "Deposit"],
        "balance_cols": ["Balance", "Closing Balance"],
        "ref_cols":     ["Chq No", "Ref No"],
        "date_formats": ["%d-%m-%Y", "%d/%m/%Y"],
        "skip_keywords": ["Axis Bank", "Branch"],
        "detect_keywords": ["AXIS", "UTIB"],
    },
    "Kotak": {
        "name": "Kotak Mahindra Bank",
        "date_cols":    ["Date", "Transaction Date", "Sl. No."],
        "narration_cols": ["Description", "Narration", "Particulars"],
        "debit_cols":   ["Debit", "Dr", "Withdrawal"],
        "credit_cols":  ["Credit", "Cr", "Deposit"],
        "balance_cols": ["Balance", "Closing Balance"],
        "ref_cols":     ["Chq / Ref number", "Ref No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%d %b %Y"],
        "skip_keywords": ["Kotak", "Branch"],
        "detect_keywords": ["KOTAK", "KKBK"],
    },
    "PNB": {
        "name": "Punjab National Bank",
        "date_cols":    ["Date", "Transaction Date"],
        "narration_cols": ["Particulars", "Description", "Narration"],
        "debit_cols":   ["Debit", "Withdrawal"],
        "credit_cols":  ["Credit", "Deposit"],
        "balance_cols": ["Balance"],
        "ref_cols":     ["Ref No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y"],
        "skip_keywords": ["Punjab National", "PNB"],
        "detect_keywords": ["PNB", "PUNB"],
    },
    "BOB": {
        "name": "Bank of Baroda",
        "date_cols":    ["Date", "Transaction Date", "Txn Date"],
        "narration_cols": ["Particulars", "Description"],
        "debit_cols":   ["Debit", "Withdrawal"],
        "credit_cols":  ["Credit", "Deposit"],
        "balance_cols": ["Balance"],
        "ref_cols":     ["Ref No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y"],
        "skip_keywords": ["Bank of Baroda", "BOB"],
        "detect_keywords": ["BOB", "BARODA", "BARB"],
    },
    "IndusInd": {
        "name": "IndusInd Bank",
        "date_cols":    ["Transaction Date", "Date"],
        "narration_cols": ["Transaction Particulars", "Description"],
        "debit_cols":   ["Debit", "Withdrawal Amount"],
        "credit_cols":  ["Credit", "Deposit Amount"],
        "balance_cols": ["Balance", "Running Balance"],
        "ref_cols":     ["Cheque / Reference No"],
        "date_formats": ["%d-%m-%Y", "%d/%m/%Y"],
        "skip_keywords": ["IndusInd"],
        "detect_keywords": ["INDUSIND", "INDB"],
    },
    "Yes Bank": {
        "name": "Yes Bank",
        "date_cols":    ["Transaction Date", "Date"],
        "narration_cols": ["Description", "Particulars"],
        "debit_cols":   ["Debit", "Withdrawal"],
        "credit_cols":  ["Credit", "Deposit"],
        "balance_cols": ["Balance"],
        "ref_cols":     ["Reference No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y"],
        "skip_keywords": ["Yes Bank"],
        "detect_keywords": ["YES BANK", "YESB"],
    },
    "Union Bank": {
        "name": "Union Bank of India",
        "date_cols":    ["Date", "Transaction Date"],
        "narration_cols": ["Particulars", "Narration"],
        "debit_cols":   ["Debit", "Withdrawal"],
        "credit_cols":  ["Credit", "Deposit"],
        "balance_cols": ["Balance"],
        "ref_cols":     ["Ref No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y"],
        "skip_keywords": ["Union Bank"],
        "detect_keywords": ["UNION", "UBIN"],
    },
    "Canara Bank": {
        "name": "Canara Bank",
        "date_cols":    ["Txn Date", "Date"],
        "narration_cols": ["Particulars", "Description"],
        "debit_cols":   ["Debit", "Withdrawal"],
        "credit_cols":  ["Credit", "Deposit"],
        "balance_cols": ["Balance"],
        "ref_cols":     ["Ref No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y"],
        "skip_keywords": ["Canara"],
        "detect_keywords": ["CANARA", "CNRB"],
    },
    "IDBI": {
        "name": "IDBI Bank",
        "date_cols":    ["Transaction Date", "Date"],
        "narration_cols": ["Narration", "Description"],
        "debit_cols":   ["Debit", "Withdrawal"],
        "credit_cols":  ["Credit", "Deposit"],
        "balance_cols": ["Balance"],
        "ref_cols":     ["Ref No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y"],
        "skip_keywords": ["IDBI"],
        "detect_keywords": ["IDBI", "IBKL"],
    },
    "Federal Bank": {
        "name": "Federal Bank",
        "date_cols":    ["Date", "Transaction Date"],
        "narration_cols": ["Particulars", "Description"],
        "debit_cols":   ["Debit", "Withdrawal"],
        "credit_cols":  ["Credit", "Deposit"],
        "balance_cols": ["Balance"],
        "ref_cols":     ["Ref No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y"],
        "skip_keywords": ["Federal Bank"],
        "detect_keywords": ["FEDERAL", "FDRL"],
    },
    "RBL Bank": {
        "name": "RBL Bank",
        "date_cols":    ["Date", "Transaction Date"],
        "narration_cols": ["Description", "Particulars"],
        "debit_cols":   ["Debit", "Withdrawal"],
        "credit_cols":  ["Credit", "Deposit"],
        "balance_cols": ["Balance"],
        "ref_cols":     ["Ref No"],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y"],
        "skip_keywords": ["RBL"],
        "detect_keywords": ["RBL", "RATN"],
    },
}

# Fallback for unrecognised banks
GENERIC_PROFILE = {
    "name": "Unknown Bank",
    "date_cols":    ["Date", "Transaction Date", "Txn Date", "Value Date"],
    "narration_cols": ["Description", "Narration", "Particulars", "Details", "Remarks"],
    "debit_cols":   ["Debit", "Withdrawal", "Dr", "Debit Amount"],
    "credit_cols":  ["Credit", "Deposit", "Cr", "Credit Amount"],
    "balance_cols": ["Balance", "Closing Balance", "Running Balance"],
    "ref_cols":     ["Ref No", "Reference", "Chq No", "Cheque No"],
    "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y",
                     "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%y"],
    "skip_keywords": [],
    "detect_keywords": [],
}


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-DETECT BANK
# ══════════════════════════════════════════════════════════════════════════════

def detect_bank(df: pd.DataFrame = None, raw_text: str = "") -> str:
    """Try to identify the bank from column headers or raw text."""
    search_str = ""
    if df is not None:
        search_str = " ".join(str(c) for c in df.columns).upper()
    search_str += " " + raw_text.upper()

    for bank_key, profile in BANK_PROFILES.items():
        for kw in profile["detect_keywords"]:
            if kw.upper() in search_str:
                return bank_key
    return "Generic"


def _get_profile(bank: str) -> dict:
    return BANK_PROFILES.get(bank, GENERIC_PROFILE)


# ══════════════════════════════════════════════════════════════════════════════
# COLUMN NORMALISER
# ══════════════════════════════════════════════════════════════════════════════

def _find_column(df_columns: list, candidates: list) -> Optional[str]:
    """Find the first matching column name.
    
    Matching strategy (in order of preference):
    1. Exact case-insensitive match
    2. Column starts with candidate (e.g. 'Debit' matches 'Debit (₹)')
    3. Candidate is a substring of column name
    """
    clean = {c.strip().lower(): c for c in df_columns}
    # Pass 1: Exact match
    for cand in candidates:
        cand_lower = cand.strip().lower()
        if cand_lower in clean:
            return clean[cand_lower]
    # Pass 2: Starts-with match
    for cand in candidates:
        cand_lower = cand.strip().lower()
        for col_lower, col_orig in clean.items():
            if col_lower.startswith(cand_lower):
                return col_orig
    # Pass 3: Contains match
    for cand in candidates:
        cand_lower = cand.strip().lower()
        if len(cand_lower) >= 3:  # Avoid too-short substring matches
            for col_lower, col_orig in clean.items():
                if cand_lower in col_lower:
                    return col_orig
    return None


def normalize_columns(df: pd.DataFrame, profile: dict) -> pd.DataFrame:
    """Map bank-specific columns to standard schema."""
    cols = list(df.columns)
    mapping = {}

    date_col = _find_column(cols, profile["date_cols"])
    narr_col = _find_column(cols, profile["narration_cols"])
    debit_col = _find_column(cols, profile["debit_cols"])
    credit_col = _find_column(cols, profile["credit_cols"])
    ref_col = _find_column(cols, profile["ref_cols"])

    result = pd.DataFrame()

    # Always create 'date' column — empty string if no date column found
    if date_col:
        result["date"] = df[date_col]
    else:
        result["date"] = ""

    if narr_col:
        result["description"] = df[narr_col].fillna("")
    elif ref_col:
        result["description"] = df[ref_col].fillna("")
    else:
        result["description"] = ""

    # Handle amount — some banks have single Amount column, others have Debit/Credit
    if debit_col and credit_col:
        result["debit"] = pd.to_numeric(
            df[debit_col].astype(str).str.replace(",", "").str.replace(" ", "").str.strip(), errors="coerce"
        ).fillna(0)
        result["credit"] = pd.to_numeric(
            df[credit_col].astype(str).str.replace(",", "").str.replace(" ", "").str.strip(), errors="coerce"
        ).fillna(0)
    else:
        # Try single "Amount" column
        amt_col = _find_column(cols, ["Amount", "Transaction Amount", "Txn Amount"])
        if amt_col:
            amounts = pd.to_numeric(
                df[amt_col].astype(str).str.replace(",", "").str.strip(), errors="coerce"
            ).fillna(0)
            result["debit"] = amounts.apply(lambda x: abs(x) if x < 0 else 0)
            result["credit"] = amounts.apply(lambda x: x if x > 0 else 0)
        else:
            result["debit"] = 0
            result["credit"] = 0

    if ref_col and ref_col != narr_col:
        result["reference"] = df[ref_col].fillna("")
    else:
        result["reference"] = ""

    return result


# ══════════════════════════════════════════════════════════════════════════════
# DATE PARSING
# ══════════════════════════════════════════════════════════════════════════════

def _parse_date(val, formats: list):
    """Try parsing a date string with multiple formats.
    
    Handles:
    - Text dates: '01-04-2026', '01/04/2026'
    - ISO timestamps from Excel: '2026-04-01 00:00:00'
    - Excel serial numbers: '46113'
    - Named months: '01 Apr 2026', '01-Apr-2026'
    """
    if pd.isna(val) or str(val).strip() == "":
        return None
    s = str(val).strip()

    # Strip time portion if present (e.g. "2026-04-01 00:00:00" → "2026-04-01")
    s = re.sub(r'\s+\d{1,2}:\d{2}(:\d{2})?(\s*(AM|PM))?$', '', s, flags=re.IGNORECASE).strip()

    # Handle Excel serial number (pure numeric, typically 5 digits like 46113)
    if re.match(r'^\d{5}(\.\d+)?$', s):
        try:
            from datetime import timedelta
            serial = float(s)
            # Excel epoch: Jan 0, 1900 (with the 1900 leap year bug)
            base = datetime(1899, 12, 30)
            return (base + timedelta(days=serial)).date()
        except Exception:
            pass

    # Try explicit formats first
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue

    # Try common additional formats not in the profile
    extra_formats = [
        "%Y-%m-%d",      # ISO: 2026-04-01
        "%Y/%m/%d",      # ISO variant
        "%d-%m-%Y",      # DD-MM-YYYY
        "%d/%m/%Y",      # DD/MM/YYYY
        "%d-%b-%Y",      # 01-Apr-2026
        "%d %b %Y",      # 01 Apr 2026
        "%d %B %Y",      # 01 April 2026
        "%m-%d-%Y",      # MM-DD-YYYY (US)
        "%m/%d/%Y",      # MM/DD/YYYY (US)
        "%d/%m/%y",      # DD/MM/YY
        "%d-%m-%y",      # DD-MM-YY
    ]
    for fmt in extra_formats:
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue

    # Last resort — pandas auto-detection
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN & FILTER
# ══════════════════════════════════════════════════════════════════════════════

def _clean_dataframe(df: pd.DataFrame, profile: dict) -> pd.DataFrame:
    """Remove metadata rows, empty rows, and header duplicates."""
    # Drop rows where all values are NaN
    df = df.dropna(how="all")

    # Drop rows where debit AND credit are both 0 or NaN
    if "debit" in df.columns and "credit" in df.columns:
        df = df[(df["debit"] > 0) | (df["credit"] > 0)]

    return df.reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# DUPLICATE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def _check_duplicates(transactions: list, user_id: int) -> tuple:
    """Split into new and duplicate transactions."""
    existing = get_transactions(user_id)
    existing_set = set()
    for e in existing:
        key = (str(e["trans_date"])[:10], float(e["amount"]), e.get("note", "")[:30])
        existing_set.add(key)

    new_txns = []
    dup_txns = []
    for t in transactions:
        key = (str(t["trans_date"])[:10], float(t["amount"]), str(t.get("note", ""))[:30])
        if key in existing_set:
            dup_txns.append(t)
        else:
            new_txns.append(t)
            existing_set.add(key)  # Prevent self-duplicates in batch

    return new_txns, dup_txns


# ══════════════════════════════════════════════════════════════════════════════
# FILE READERS
# ══════════════════════════════════════════════════════════════════════════════

def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    """Read CSV, trying multiple encodings."""
    for enc in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc, dtype=str)
            if len(df.columns) >= 3:
                return df
        except Exception:
            continue
    raise ValueError("Could not parse CSV file with any known encoding.")


def _read_excel(file_bytes: bytes) -> pd.DataFrame:
    """Read Excel file with smart header row detection.
    
    Many bank statements (especially SBI) have metadata rows before the actual
    column headers. This function scans the first 20 rows for one that looks
    like a header (contains keywords like 'date', 'debit', 'credit', etc.).
    """
    # First, read without header to inspect all rows
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)

    header_keywords = {
        "date", "txn date", "transaction date", "value date",
        "description", "narration", "particulars",
        "debit", "credit", "withdrawal", "deposit", "amount",
        "balance", "closing balance", "ref", "cheque",
    }

    best_row = 0
    best_score = 0
    for i in range(min(20, len(raw))):
        row_vals = [str(v).strip().lower() for v in raw.iloc[i] if pd.notna(v)]
        score = sum(1 for v in row_vals if any(kw in v for kw in header_keywords))
        if score > best_score:
            best_score = score
            best_row = i

    if best_score >= 2:
        # Use detected row as header, skip everything before it
        df = pd.read_excel(io.BytesIO(file_bytes), header=best_row, dtype=str)
    else:
        # Fallback: use row 0
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)

    # Drop fully empty columns (Unnamed columns with no data)
    df = df.dropna(axis=1, how="all")

    return df


# Known date-like patterns to identify header rows
_DATE_PATTERN = re.compile(
    r'\b(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\b',
    re.IGNORECASE
)

def _read_pdf(file_bytes: bytes) -> pd.DataFrame:
    """Extract tables from PDF using pdfplumber with smart header detection."""
    import pdfplumber

    all_rows = []  # (is_header_candidate, row_list)

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                for row in table:
                    cleaned = [str(c).strip().replace('\n', ' ') if c else "" for c in row]
                    if any(cleaned):
                        all_rows.append(cleaned)

    if not all_rows:
        raise ValueError("No table found in PDF.")

    # Find header row — the first row that doesn't look like a date/amount row
    # but looks like column labels (contains keywords like Date, Amount, Debit, etc.)
    header_kw = {"date", "amount", "debit", "credit", "balance", "narration",
                 "description", "particulars", "withdrawal", "deposit",
                 "txn", "transaction", "ref", "sl", "no", "dr", "cr"}
    header_idx = 0
    for i, row in enumerate(all_rows[:15]):  # Only check first 15 rows
        row_lower = " ".join(row).lower()
        matches = sum(1 for kw in header_kw if kw in row_lower)
        if matches >= 2:  # At least 2 header keywords → this is the header
            header_idx = i
            break

    headers = all_rows[header_idx]
    data_rows = all_rows[header_idx + 1:]

    # Ensure all rows match header length (pad or trim)
    n = len(headers)
    data = []
    for r in data_rows:
        if len(r) < n:
            r = r + [""] * (n - len(r))
        data.append(r[:n])

    # Remove duplicate header rows that sneak in from multi-page PDFs
    header_set = set(h.lower().strip() for h in headers)
    data = [r for r in data if not (sum(1 for c in r if c.lower().strip() in header_set) >= 3)]

    return pd.DataFrame(data, columns=headers)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PARSER — called by API and Streamlit
# ══════════════════════════════════════════════════════════════════════════════

def parse_statement_to_df(file_bytes: bytes, ext: str, bank_hint: str = None) -> tuple:
    """
    Parse a bank statement file into a normalized DataFrame.
    Returns (df, bank_name) where df has columns:
        trans_date, type, amount, category, note, payment_mode
    """
    # 1. Read the file
    ext = ext.lower().lstrip(".")
    if ext == "csv":
        raw_df = _read_csv(file_bytes)
    elif ext in ("xls", "xlsx"):
        raw_df = _read_excel(file_bytes)
    elif ext == "pdf":
        raw_df = _read_pdf(file_bytes)
    else:
        raise ValueError(f"Unsupported format: {ext}")

    # 2. Detect bank
    raw_text = " ".join(raw_df.columns) + " " + " ".join(raw_df.head(5).values.astype(str).flatten())
    bank = bank_hint if bank_hint and bank_hint in BANK_PROFILES else detect_bank(raw_df, raw_text)
    profile = _get_profile(bank)

    # 3. Normalize columns
    norm_df = normalize_columns(raw_df, profile)

    # 4. Parse dates
    if "date" not in norm_df.columns or norm_df["date"].astype(str).str.strip().eq("").all():
        raise ValueError(
            f"Could not find a date column in the statement. "
            f"Columns found: {list(raw_df.columns)}. "
            f"Try selecting your bank manually."
        )
    norm_df["trans_date"] = norm_df["date"].apply(lambda x: _parse_date(x, profile["date_formats"]))
    norm_df = norm_df.dropna(subset=["trans_date"])

    # 5. Clean
    norm_df = _clean_dataframe(norm_df, profile)
    if norm_df.empty:
        return norm_df, profile["name"]

    # 6. Determine type and amount
    norm_df["type"] = norm_df.apply(
        lambda r: "income" if r["credit"] > 0 else "expense", axis=1
    )
    norm_df["amount"] = norm_df.apply(
        lambda r: r["credit"] if r["credit"] > 0 else r["debit"], axis=1
    )

    # 7. Auto-categorize from description
    norm_df["category"] = norm_df.apply(
        lambda r: auto_detect_category(r["description"], r["type"]), axis=1
    )

    # 8. Extract payment mode from description
    norm_df["payment_mode"] = norm_df["description"].apply(_detect_payment_mode)

    # 9. Build note from description
    norm_df["note"] = norm_df["description"].apply(lambda x: str(x)[:100] if x else "")

    # 10. Select final columns
    result = norm_df[["trans_date", "type", "amount", "category", "note", "payment_mode"]].copy()
    result = result[result["amount"] > 0].reset_index(drop=True)

    return result, profile["name"]


def _detect_payment_mode(desc: str) -> str:
    """Guess payment mode from bank narration."""
    d = str(desc).upper()
    if "UPI" in d:
        return "UPI"
    elif "NEFT" in d or "RTGS" in d or "IMPS" in d:
        return "Net Banking"
    elif "ATM" in d:
        return "Cash"
    elif "POS" in d or "CARD" in d or "SWIPE" in d:
        return "Debit Card"
    elif "AUTO" in d or "NACH" in d or "ECS" in d or "MANDATE" in d:
        return "Auto-Debit"
    elif "CASH" in d:
        return "Cash"
    elif "CHQ" in d or "CHEQUE" in d:
        return "Cash"
    return "Net Banking"


# ══════════════════════════════════════════════════════════════════════════════
# IMPORT — saves parsed transactions to database
# ══════════════════════════════════════════════════════════════════════════════

def parse_statement(file_bytes: bytes, ext: str, user_id: int,
                    bank_hint: str = None) -> dict:
    """
    Full pipeline: parse → deduplicate → import.
    Returns ImportResult dict.
    """
    df, bank_name = parse_statement_to_df(file_bytes, ext, bank_hint)

    if df.empty:
        return {
            "imported": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "message": f"No transactions found in the {bank_name} statement.",
        }

    # Convert to list of dicts
    transactions = df.to_dict("records")

    # Deduplicate
    new_txns, dup_txns = _check_duplicates(transactions, user_id)

    # Import new ones
    errors = 0
    for t in new_txns:
        try:
            add_transaction(
                user_id,
                t["type"],
                float(t["amount"]),
                t["category"],
                t.get("note", ""),
                t.get("payment_mode", "Net Banking"),
                str(t["trans_date"]),
            )
        except Exception:
            errors += 1

    imported = len(new_txns) - errors
    return {
        "imported": imported,
        "duplicates_skipped": len(dup_txns),
        "errors": errors,
        "message": (
            f"✅ {bank_name}: {imported} transactions imported, "
            f"{len(dup_txns)} duplicates skipped"
            + (f", {errors} errors" if errors else "")
            + "."
        ),
    }


def get_supported_banks() -> list:
    """Return list of supported bank names."""
    return [{"key": k, "name": v["name"]} for k, v in BANK_PROFILES.items()]
