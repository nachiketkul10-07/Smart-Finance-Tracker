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
        "debit_cols":   ["Debit", "Withdrawal", "Debit Amount", "Dr"],
        "credit_cols":  ["Credit", "Deposit", "Credit Amount", "Cr"],
        "balance_cols": ["Balance", "Closing Balance"],
        "ref_cols":     ["Ref No", "Reference", "Chq/Ref No", "Ref No./Cheque No."],
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y", "%Y-%m-%d"],
        "skip_keywords": ["Statement", "Branch", "Account", "IFSC", "Customer", "CIF"],
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
    """Find the first matching column name (case-insensitive, stripped)."""
    clean = {c.strip().lower(): c for c in df_columns}
    for cand in candidates:
        if cand.strip().lower() in clean:
            return clean[cand.strip().lower()]
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

    if date_col:
        result["date"] = df[date_col]
    if narr_col:
        result["description"] = df[narr_col].fillna("")
    elif ref_col:
        result["description"] = df[ref_col].fillna("")
    else:
        result["description"] = ""

    # Handle amount — some banks have single Amount column, others have Debit/Credit
    if debit_col and credit_col:
        result["debit"] = pd.to_numeric(
            df[debit_col].astype(str).str.replace(",", "").str.strip(), errors="coerce"
        ).fillna(0)
        result["credit"] = pd.to_numeric(
            df[credit_col].astype(str).str.replace(",", "").str.strip(), errors="coerce"
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
    """Try parsing a date string with multiple formats."""
    if pd.isna(val) or str(val).strip() == "":
        return None
    s = str(val).strip()
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    # Last resort — pandas
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN & FILTER
# ══════════════════════════════════════════════════════════════════════════════

def _clean_dataframe(df: pd.DataFrame, profile: dict) -> pd.DataFrame:
    """Remove metadata rows, empty rows, and header duplicates."""
    skip_kw = profile.get("skip_keywords", [])

    # Drop rows where all values are NaN
    df = df.dropna(how="all")

    # Drop rows that look like headers or metadata
    if skip_kw:
        mask = df.apply(
            lambda row: any(
                kw.lower() in str(v).lower()
                for v in row.values for kw in skip_kw
            ), axis=1
        )
        df = df[~mask]

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
    """Read Excel file."""
    return pd.read_excel(io.BytesIO(file_bytes), dtype=str)


def _read_pdf(file_bytes: bytes) -> pd.DataFrame:
    """Extract tables from PDF using pdfplumber."""
    import pdfplumber

    all_data = []
    headers = None

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                for row in table:
                    cleaned = [str(c).strip() if c else "" for c in row]
                    if not headers and any(cleaned):
                        # Use first non-empty row as header
                        headers = cleaned
                    else:
                        all_data.append(cleaned)

    if not headers:
        raise ValueError("No table found in PDF.")

    # Ensure all rows match header length
    data = [r for r in all_data if len(r) == len(headers)]
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
