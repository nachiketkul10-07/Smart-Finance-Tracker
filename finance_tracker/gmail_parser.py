"""
gmail_parser.py
---------------
Gmail API integration for auto-importing bank transaction alerts.
Uses OAuth2 for secure authentication. Runs 100% locally.

Setup required:
1. Go to https://console.cloud.google.com
2. Create a project → Enable Gmail API
3. Create OAuth2 credentials (Desktop app)
4. Download credentials.json → place in finance_tracker/data/
"""

import os
import re
import json
import base64
import pickle
from datetime import datetime, date
from typing import Optional
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent / "data"
CREDENTIALS_FILE = DATA_DIR / "credentials.json"
TOKEN_FILE = DATA_DIR / "gmail_token.pickle"

# Gmail API scope — read-only access to emails
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# How many emails to fetch per sync
MAX_RESULTS = 50

# Search query for bank transaction emails
BANK_EMAIL_SENDERS = [
    "alerts@sbi.co.in", "alert@hdfcbank.net", "alerts@hdfcbank.net",
    "alerts@icicibank.com", "transaction@icicibank.com",
    "alerts@axisbank.com", "alerts@kotak.com",
    "alerts@pnb.co.in", "alerts@unionbankofindia.co.in",
    "alerts@bobfinancial.com", "alerts@indusind.com",
    "alerts@yesbank.in", "alerts@federalbank.co.in",
    "alerts@idbibankltd.co.in", "alerts@rblbank.com",
    "noreply@phonepe.com", "noreply@paytm.com",
    "noreply@googlepaytez.com",
]


# ══════════════════════════════════════════════════════════════════════════════
# OAUTH2 AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════

def is_credentials_available() -> bool:
    """Check if Google OAuth2 credentials file exists. Auto-creates from Streamlit secrets if on cloud."""
    if CREDENTIALS_FILE.exists():
        return True
    # Try creating from Streamlit secrets (for cloud deployment)
    try:
        import streamlit as st
        if "gmail_credentials" in st.secrets:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            cred_data = dict(st.secrets["gmail_credentials"])
            # Detect credential type: Desktop app = "installed", Web app = "web"
            # st.secrets doesn't support .get() at top level — use try/except
            try:
                cred_type = str(st.secrets["gmail_credentials_type"])
            except (KeyError, Exception):
                cred_type = "installed"
            with open(CREDENTIALS_FILE, "w") as f:
                json.dump({cred_type: cred_data}, f)
            return True
    except Exception as e:
        # Store error for display in UI
        try:
            import streamlit as st
            st.session_state["gmail_cred_error"] = str(e)
        except Exception:
            pass
    return False


def get_credentials_debug_info() -> str:
    """Returns debug info about why credentials loading failed (for display in UI)."""
    try:
        import streamlit as st
        lines = []
        lines.append(f"CREDENTIALS_FILE path: {CREDENTIALS_FILE}")
        lines.append(f"File exists: {CREDENTIALS_FILE.exists()}")
        lines.append(f"DATA_DIR exists: {DATA_DIR.exists()}")
        if "gmail_credentials" in st.secrets:
            lines.append("gmail_credentials key: FOUND in secrets ✅")
            try:
                cred_data = dict(st.secrets["gmail_credentials"])
                lines.append(f"Keys in gmail_credentials: {list(cred_data.keys())}")
            except Exception as e:
                lines.append(f"Error reading gmail_credentials: {e}")
        else:
            lines.append("gmail_credentials key: NOT FOUND in secrets ❌")
            lines.append(f"Available secret keys: {list(st.secrets.keys())}")
        if "gmail_cred_error" in st.session_state:
            lines.append(f"Last error: {st.session_state['gmail_cred_error']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Debug failed: {e}"


def is_authenticated() -> bool:
    """Check if we have a valid Gmail token."""
    if not TOKEN_FILE.exists():
        return False
    try:
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
        return creds and creds.valid
    except Exception:
        return False


def _get_cred_type() -> str:
    """Detect if credentials.json is 'web' or 'installed' type."""
    try:
        with open(CREDENTIALS_FILE) as f:
            data = json.load(f)
        if "web" in data:
            return "web"
        return "installed"
    except Exception:
        return "installed"


def get_auth_url() -> Optional[str]:
    """Generate OAuth2 authorization URL for the user to visit."""
    if not is_credentials_available():
        return None

    from google_auth_oauthlib.flow import Flow, InstalledAppFlow
    cred_type = _get_cred_type()

    if cred_type == "web":
        flow = Flow.from_client_secrets_file(
            str(CREDENTIALS_FILE), SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob"
        )
    else:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    return auth_url


def authenticate_with_code(auth_code: str) -> dict:
    """Complete OAuth2 flow with the authorization code."""
    if not is_credentials_available():
        return {"success": False, "message": "credentials.json not found in data/"}

    try:
        from google_auth_oauthlib.flow import Flow, InstalledAppFlow
        cred_type = _get_cred_type()

        if cred_type == "web":
            flow = Flow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"
            )
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

        flow.fetch_token(code=auth_code)
        creds = flow.credentials

        DATA_DIR.mkdir(exist_ok=True)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", "unknown")

        return {"success": True, "message": f"Connected to {email}", "email": email}
    except Exception as e:
        return {"success": False, "message": f"Authentication failed: {e}", "email": ""}


def authenticate_local() -> dict:
    """Run local OAuth2 flow (opens browser)."""
    if not is_credentials_available():
        return {"success": False, "message": "credentials.json not found in data/"}

    try:
        from google_auth_oauthlib.flow import Flow, InstalledAppFlow
        cred_type = _get_cred_type()

        if cred_type == "web":
            flow = Flow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES,
                redirect_uri="http://localhost:8085/"
            )
            auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")

            import webbrowser
            webbrowser.open(auth_url)

            # Start a simple local server to catch the redirect
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import urllib.parse

            auth_code_holder = [None]

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    query = urllib.parse.urlparse(self.path).query
                    params = urllib.parse.parse_qs(query)
                    auth_code_holder[0] = params.get("code", [None])[0]
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<h2>Success! You can close this tab.</h2>")

                def log_message(self, *args):
                    pass

            server = HTTPServer(("localhost", 8085), Handler)
            server.handle_request()

            if auth_code_holder[0]:
                flow.fetch_token(code=auth_code_holder[0])
                creds = flow.credentials
            else:
                return {"success": False, "message": "No authorization code received."}
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        DATA_DIR.mkdir(exist_ok=True)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", "unknown")

        return {"success": True, "message": f"Connected to {email}", "email": email}
    except Exception as e:
        return {"success": False, "message": f"Authentication failed: {e}", "email": ""}


def _get_gmail_service():
    """Get authenticated Gmail API service."""
    if not TOKEN_FILE.exists():
        raise ValueError("Not authenticated. Please connect Gmail first.")

    from google.auth.transport.requests import Request
    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)
        else:
            raise ValueError("Gmail token expired. Please re-authenticate.")

    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds)


def disconnect():
    """Remove saved Gmail token."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    return {"success": True, "message": "Gmail disconnected."}


def get_connected_email() -> Optional[str]:
    """Get the email address of the connected account."""
    try:
        service = _get_gmail_service()
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress")
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL FETCHER
# ══════════════════════════════════════════════════════════════════════════════

def _build_search_query(days_back: int = 30) -> str:
    """Build Gmail search query for bank transaction emails."""
    sender_query = " OR ".join(f"from:{s}" for s in BANK_EMAIL_SENDERS)
    # Also search for common transaction alert subjects
    subject_query = (
        'subject:"transaction alert" OR subject:"debit alert" OR '
        'subject:"credit alert" OR subject:"payment" OR '
        'subject:"debited" OR subject:"credited" OR '
        'subject:"UPI" OR subject:"NEFT" OR subject:"IMPS"'
    )
    date_query = f"newer_than:{days_back}d"
    return f"({sender_query} OR {subject_query}) {date_query}"


def fetch_bank_emails(days_back: int = 30, max_results: int = MAX_RESULTS) -> list:
    """
    Fetch bank transaction alert emails from Gmail.
    Returns list of dicts: {subject, from, date, body, message_id}
    """
    service = _get_gmail_service()
    query = _build_search_query(days_back)

    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        try:
            full = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()

            headers = {h["name"].lower(): h["value"] for h in full["payload"]["headers"]}
            body = _extract_body(full["payload"])

            emails.append({
                "message_id": msg["id"],
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "date": headers.get("date", ""),
                "body": body,
            })
        except Exception:
            continue

    return emails


def _extract_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    body = ""

    if "body" in payload and payload["body"].get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")

    if "parts" in payload:
        for part in payload["parts"]:
            mime = part.get("mimeType", "")
            if mime == "text/plain" and part["body"].get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                break
            elif mime == "text/html" and part["body"].get("data") and not body:
                html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                # Strip HTML tags for plain text
                body = re.sub(r'<[^>]+>', ' ', html)
                body = re.sub(r'\s+', ' ', body).strip()
            elif "parts" in part:
                body = _extract_body(part) or body

    return body


# ══════════════════════════════════════════════════════════════════════════════
# BANK EMAIL PARSERS
# ══════════════════════════════════════════════════════════════════════════════

def _parse_email_amount(text: str) -> Optional[float]:
    """Extract amount from bank email text."""
    patterns = [
        r'(?:Rs\.?|INR|₹)\s?([\d,]+\.?\d*)',
        r'(?:debited|credited|amount)\s*(?:of|:)?\s*(?:Rs\.?|INR|₹)?\s?([\d,]+\.?\d*)',
        r'([\d,]+\.\d{2})\s*(?:has been|was|is)',
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            try:
                val = float(m.replace(",", ""))
                if 1 <= val <= 10_000_000:
                    return val
            except ValueError:
                continue
    return None


def _parse_email_type(text: str) -> str:
    """Determine if transaction is debit or credit."""
    lower = text.lower()
    debit_kw = ["debited", "debit", "withdrawn", "spent", "paid", "purchase", "payment"]
    credit_kw = ["credited", "credit", "received", "refund", "deposit", "cashback"]

    debit_score = sum(1 for kw in debit_kw if kw in lower)
    credit_score = sum(1 for kw in credit_kw if kw in lower)

    return "income" if credit_score > debit_score else "expense"


def _parse_email_date(text: str, email_date: str = "") -> date:
    """Extract transaction date from email body or header."""
    # Try body first
    patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2})\b',
        r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s,]+(\d{4})',
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            try:
                s = match.group(0).replace(",", "")
                for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d %b %Y", "%d %B %Y"]:
                    try:
                        return datetime.strptime(s, fmt).date()
                    except ValueError:
                        continue
            except Exception:
                pass

    # Fallback: parse email header date
    if email_date:
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(email_date).date()
        except Exception:
            pass

    return date.today()


def _parse_email_merchant(text: str) -> str:
    """Extract merchant/payee from email text."""
    patterns = [
        r'(?:at|to|from|merchant|payee)[:\s]+([A-Za-z][\w\s.&\'-]{2,35})',
        r'(?:transferred to|paid to|sent to)\s+([A-Za-z][\w\s.&\'-]{2,35})',
        r'(?:Info|Ref(?:erence)?|Desc(?:ription)?)[:\s]+([A-Za-z][\w\s.&\'-]{2,35})',
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\s+(on|at|via|upi|ref|dated).*', '', name, flags=re.IGNORECASE)
            if len(name) > 2:
                return name[:50]
    return "Bank Transaction"


def _parse_email_payment_mode(text: str) -> str:
    """Detect payment mode from email."""
    upper = text.upper()
    if "UPI" in upper:
        return "UPI"
    elif "NEFT" in upper or "RTGS" in upper or "IMPS" in upper:
        return "Net Banking"
    elif "ATM" in upper:
        return "Cash"
    elif "POS" in upper or "CARD" in upper or "DEBIT CARD" in upper:
        return "Debit Card"
    elif "CREDIT CARD" in upper:
        return "Credit Card"
    elif "NACH" in upper or "ECS" in upper or "AUTO" in upper:
        return "Auto-Debit"
    return "Net Banking"


def _detect_bank_from_email(sender: str, body: str) -> str:
    """Detect which bank sent the email."""
    combined = (sender + " " + body[:200]).upper()
    bank_map = {
        "SBI": ["SBI", "STATE BANK"],
        "HDFC": ["HDFC", "HDFCBANK"],
        "ICICI": ["ICICI"],
        "Axis": ["AXIS"],
        "Kotak": ["KOTAK"],
        "PNB": ["PNB", "PUNJAB NATIONAL"],
        "BOB": ["BARODA", "BOB"],
        "IndusInd": ["INDUSIND"],
        "Yes Bank": ["YES BANK"],
        "Union Bank": ["UNION BANK"],
        "PhonePe": ["PHONEPE"],
        "Paytm": ["PAYTM"],
        "Google Pay": ["GOOGLEPAYTEZ", "GOOGLE PAY"],
    }
    for bank, keywords in bank_map.items():
        for kw in keywords:
            if kw in combined:
                return bank
    return "Bank"


def parse_bank_email(email: dict) -> Optional[dict]:
    """
    Parse a single bank email into a transaction dict.
    Returns None if the email doesn't contain valid transaction data.
    """
    body = email["body"]
    subject = email["subject"]
    full_text = subject + "\n" + body

    amount = _parse_email_amount(full_text)
    if not amount:
        return None

    txn_type = _parse_email_type(full_text)
    txn_date = _parse_email_date(body, email.get("date", ""))
    merchant = _parse_email_merchant(full_text)
    payment_mode = _parse_email_payment_mode(full_text)
    bank = _detect_bank_from_email(email.get("from", ""), body)

    return {
        "amount": amount,
        "type": txn_type,
        "date": txn_date,
        "merchant": merchant,
        "payment_mode": payment_mode,
        "bank": bank,
        "subject": subject[:80],
        "message_id": email.get("message_id", ""),
    }


# ══════════════════════════════════════════════════════════════════════════════
# IMPORT PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def sync_gmail_transactions(user_id: int, days_back: int = 30) -> dict:
    """
    Full pipeline: fetch emails → parse → deduplicate → import.
    Returns result dict with counts and messages.
    """
    from database import add_transaction, get_transactions
    from utils import auto_detect_category

    # 1. Fetch emails
    try:
        emails = fetch_bank_emails(days_back)
    except ValueError as e:
        return {"imported": 0, "skipped": 0, "errors": 0, "message": str(e),
                "transactions": []}
    except Exception as e:
        return {"imported": 0, "skipped": 0, "errors": 0,
                "message": f"Failed to fetch emails: {e}", "transactions": []}

    if not emails:
        return {"imported": 0, "skipped": 0, "errors": 0,
                "message": "No bank transaction emails found in the last "
                           f"{days_back} days.",
                "transactions": []}

    # 2. Parse all emails
    parsed = []
    for email in emails:
        txn = parse_bank_email(email)
        if txn:
            parsed.append(txn)

    if not parsed:
        return {"imported": 0, "skipped": 0, "errors": 0,
                "message": f"Found {len(emails)} emails but none contained "
                           "valid transaction data.",
                "transactions": []}

    # 3. Deduplicate against existing DB
    existing = get_transactions(user_id)
    existing_set = set()
    for e in existing:
        key = (str(e["trans_date"])[:10], float(e["amount"]), e.get("note", "")[:30])
        existing_set.add(key)

    new_txns = []
    skipped = 0
    for t in parsed:
        key = (str(t["date"])[:10], float(t["amount"]), t["merchant"][:30])
        if key in existing_set:
            skipped += 1
        else:
            new_txns.append(t)
            existing_set.add(key)

    # 4. Import
    errors = 0
    imported_list = []
    for t in new_txns:
        category = auto_detect_category(t["merchant"], t["type"])
        note = f"{t['bank']}: {t['merchant']}"
        if len(note) > 100:
            note = note[:100]
        try:
            add_transaction(
                user_id, t["type"], float(t["amount"]),
                category, note, t["payment_mode"], str(t["date"])
            )
            imported_list.append(t)
        except Exception:
            errors += 1

    imported = len(imported_list)
    msg = (
        f"📧 Scanned {len(emails)} emails → found {len(parsed)} transactions.\n"
        f"✅ {imported} imported, {skipped} duplicates skipped"
        + (f", {errors} errors" if errors else "") + "."
    )

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "message": msg,
        "transactions": imported_list,
    }
