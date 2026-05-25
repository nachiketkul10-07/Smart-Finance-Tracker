"""
ocr_parser.py
-------------
UPI screenshot OCR parser — Enhanced v2.
Extracts transaction details from Google Pay, PhonePe, Paytm, CRED,
Amazon Pay, BHIM, WhatsApp Pay, and bank app screenshots.
Uses EasyOCR + OpenCV preprocessing. Runs 100% locally — no cloud API.
"""

import io
import re
from datetime import datetime, date
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# OCR ENGINE — Uses pytesseract (lightweight) with Pillow preprocessing
# ══════════════════════════════════════════════════════════════════════════════

def _ocr_with_pytesseract(img_pil):
    """Run pytesseract OCR on a PIL Image."""
    import pytesseract
    text = pytesseract.image_to_string(img_pil, lang="eng")
    return text


def _preprocess_pil(img_pil):
    """Preprocess PIL image for better OCR: grayscale, contrast, sharpen."""
    from PIL import ImageEnhance, ImageFilter
    gray = img_pil.convert("L")
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.0)
    sharpened = enhanced.filter(ImageFilter.SHARPEN)
    return sharpened


def _preprocess_dark_mode(img_pil):
    """Preprocess dark mode screenshots: invert colors first."""
    from PIL import ImageOps, ImageEnhance, ImageFilter
    gray = img_pil.convert("L")
    import statistics
    pixels = list(gray.getdata())
    mean_val = statistics.mean(pixels[:1000])
    if mean_val < 128:
        gray = ImageOps.invert(gray)
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.0)
    sharpened = enhanced.filter(ImageFilter.SHARPEN)
    return sharpened


def extract_text(img_bytes: bytes) -> list:
    """
    Run OCR with multiple preprocessing strategies using pytesseract.
    Returns list of (text, confidence) tuples.
    """
    from PIL import Image

    img_pil = Image.open(io.BytesIO(img_bytes))

    # Upscale small images
    w, h = img_pil.size
    if max(w, h) < 1200:
        scale = 1200 / max(w, h)
        img_pil = img_pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    all_texts = []

    # Pass 1: Standard preprocessing
    try:
        processed = _preprocess_pil(img_pil)
        text1 = _ocr_with_pytesseract(processed)
        if text1.strip():
            all_texts.append(text1)
    except Exception:
        pass

    # Pass 2: Dark mode preprocessing
    try:
        processed2 = _preprocess_dark_mode(img_pil)
        text2 = _ocr_with_pytesseract(processed2)
        if text2.strip():
            all_texts.append(text2)
    except Exception:
        pass

    # Pass 3: Raw image
    try:
        text3 = _ocr_with_pytesseract(img_pil)
        if text3.strip():
            all_texts.append(text3)
    except Exception:
        pass

    if not all_texts:
        raise ValueError("OCR could not extract any text from the image. "
                         "Make sure tesseract-ocr is installed.")

    # Use the pass with the most extracted text
    best_text = max(all_texts, key=len)

    # Return as list of (line, confidence) tuples
    lines = [line.strip() for line in best_text.split("\n") if line.strip()]
    return [(line, 0.9) for line in lines]


def get_raw_text(img_bytes: bytes) -> str:
    """Get all OCR text as a single joined string."""
    items = extract_text(img_bytes)
    return "\n".join(t for t, c in items)


# ══════════════════════════════════════════════════════════════════════════════
# UPI APP DETECTION
# ══════════════════════════════════════════════════════════════════════════════

UPI_APP_SIGNATURES = {
    "google_pay": [
        "google pay", "gpay", "payment successful", "tez",
        "paid to", "received from", "upi transaction", "g pay",
        "money sent", "you paid",
    ],
    "phonepe": [
        "phonepe", "phone pe", "payment done", "payment successful",
        "paid to", "transaction successful", "phon pe",
    ],
    "paytm": [
        "paytm", "payment successful", "paid to",
        "paytm wallet", "transaction id", "paytm upi",
    ],
    "bhim": [
        "bhim", "bhim upi", "transaction successful",
    ],
    "amazon_pay": [
        "amazon pay", "amazon upi", "a]pay", "amazonpay",
    ],
    "cred": [
        "cred", "cred upi", "payment done", "cred pay",
    ],
    "whatsapp_pay": [
        "whatsapp", "whatsapp payment", "wa pay",
    ],
}


def detect_upi_app(text: str) -> str:
    """Detect which UPI app the screenshot is from."""
    lower = text.lower()
    scores = {}
    for app, keywords in UPI_APP_SIGNATURES.items():
        scores[app] = sum(1 for kw in keywords if kw in lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "generic_upi"


# ══════════════════════════════════════════════════════════════════════════════
# REGEX EXTRACTORS — Enhanced for OCR noise
# ══════════════════════════════════════════════════════════════════════════════

def _clean_ocr_amount(s: str) -> Optional[float]:
    """Clean OCR noise from amount string and return float."""
    s = s.strip()
    s = s.replace(" ", "")  # Remove spaces OCR puts in numbers
    # Remove any non-numeric chars except , and .
    s = re.sub(r'[^\d,.]', '', s)
    if not s:
        return None
    try:
        val = float(s.replace(",", ""))
        if 0.01 <= val <= 10_000_000:
            return val
    except ValueError:
        pass
    return None


def _is_promo_amount(text: str, amount: float, pos: int) -> bool:
    """Check if an amount is from a promotional banner, not the real transaction."""
    # Look at surrounding text (50 chars around the match)
    start = max(0, pos - 60)
    end = min(len(text), pos + 60)
    context = text[start:end].lower()
    promo_kw = ["activate", "fingerprint", "upto", "up to", "limit",
                "offer", "cashback", "earn", "reward", "upgrade", "secure"]
    return any(kw in context for kw in promo_kw)


def _extract_amount(text: str) -> Optional[float]:
    """Extract monetary amount from text. Enhanced for PhonePe/GPay OCR noise."""
    candidates = []

    fixed = text.replace("Paidto", "Paid to").replace("paidto", "paid to")
    fixed = fixed.replace("Debitedfrom", "Debited from")
    fixed = fixed.replace("Receivedfrom", "Received from")

    normalized = fixed.replace("₨", "₹").replace("RS.", "₹").replace("Rs.", "₹")
    normalized = normalized.replace("Rs", "₹").replace("INR", "₹")
    # pytesseract sometimes reads ₹ as %  Z  2  ? or other chars before numbers
    normalized = re.sub(r'[%Z?]\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\b', r'₹\1', normalized)

    lines = fixed.split("\n")
    norm_lines = normalized.split("\n")

    # ── Strategy 1: ₹ symbol followed by amount ──
    for m in re.finditer(r'₹\s?(\d[\d,.]*)', normalized):
        val = _clean_ocr_amount(m.group(1))
        if val and not _is_promo_amount(normalized, val, m.start()):
            candidates.append(("currency", val))

    # ── Strategy 1b: Amount on same line as text (e.g. "Baba 1   ₹3,000") ──
    for line in norm_lines:
        m = re.search(r'₹\s?(\d[\d,.]*)', line)
        if m:
            val = _clean_ocr_amount(m.group(1))
            if val and not _is_promo_amount(line, val, m.start()):
                candidates.append(("inline_currency", val))

    # ── Strategy 2: Amount near "Paid to" / "Received from" ──
    for i, line in enumerate(lines):
        ll = line.strip().lower()
        if any(kw in ll for kw in ["paid to", "sent to", "received from", "credited to"]):
            # Look BEFORE the keyword line
            for j in range(max(0, i - 5), i):
                stripped = lines[j].strip()
                if _near_card_number(lines, j) or _is_time_or_date_line(stripped):
                    continue
                val = _clean_ocr_amount(stripped)
                if val and val >= 1 and not _is_year(val) and not _is_phone_or_id(val):
                    candidates.append(("near_keyword", val))
            # Also look AFTER the keyword line (amount sometimes below)
            for j in range(i + 1, min(len(lines), i + 4)):
                stripped = lines[j].strip()
                if _near_card_number(lines, j) or _is_time_or_date_line(stripped):
                    continue
                val = _clean_ocr_amount(stripped)
                if val and val >= 1 and not _is_year(val) and not _is_phone_or_id(val):
                    candidates.append(("near_keyword", val))

    # ── Strategy 3: Context keywords near amount ──
    for m in re.finditer(
        r'(?:paid|received|debited|credited|amount|total|sent)\s*:?\s*(?:₹|Rs\.?|INR)?\s?(\d[\d,.]*)',
        normalized, re.IGNORECASE
    ):
        val = _clean_ocr_amount(m.group(1))
        if val and not _is_promo_amount(fixed, val, m.start()) and not _is_year(val):
            candidates.append(("context", val))

    # ── Strategy 4: Standalone amount lines (pure numbers only) ──
    for idx, line in enumerate(lines):
        stripped = line.strip()
        # Only match lines that are PURELY numeric (with optional ₹, comma, dot)
        if re.match(r'^[₹]?\s?[\d,]+\.?\d{0,2}$', stripped) and len(stripped) <= 12:
            if _near_card_number(lines, idx) or _is_time_or_date_line(stripped):
                continue
            val = _clean_ocr_amount(stripped.replace("₹", ""))
            if val and val >= 1 and not _is_year(val) and not _is_phone_or_id(val):
                candidates.append(("standalone", val))

    if not candidates:
        return None

    # ── Strategy 5: Duplicate vote ──
    from collections import Counter
    amount_counts = Counter(v for _, v in candidates)
    repeated = [(amt, cnt) for amt, cnt in amount_counts.items() if cnt >= 2]
    if repeated:
        repeated.sort(key=lambda x: x[1], reverse=True)
        return repeated[0][0]

    # ── Strategy 6: Common suffix voting on ALL standalone numbers ──
    all_raw = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^\d[\d,.]*$', stripped) and len(stripped) <= 6:
            val = _clean_ocr_amount(stripped)
            if val and val >= 1 and not _is_year(val):
                all_raw.append(val)
    if len(all_raw) >= 2:
        suffix = _find_common_suffix(all_raw)
        if suffix and suffix >= 1:
            return suffix

    # Priority: currency > inline_currency > near_keyword > context > standalone
    priority = {"currency": 0, "inline_currency": 1, "near_keyword": 2, "context": 3, "standalone": 4}
    candidates.sort(key=lambda x: priority.get(x[0], 9))
    return candidates[0][1]


def _find_common_suffix(vals: list) -> Optional[float]:
    """Find common numeric suffix among values. E.g. [1349, 8349] → 349."""
    strs = [str(int(v)) for v in vals if v == int(v) and v >= 10]
    if len(strs) < 2:
        return None
    for length in range(min(len(s) for s in strs) - 1, 1, -1):
        suffixes = [s[-length:] for s in strs]
        from collections import Counter
        cnt = Counter(suffixes)
        best_suffix, best_count = cnt.most_common(1)[0]
        if best_count >= 2 and best_suffix[0] != '0':
            return float(best_suffix)
    return None


def _near_card_number(lines: list, idx: int) -> bool:
    """Check if a line is near a card/account number pattern (XXXX1853)."""
    check_range = range(max(0, idx - 2), min(len(lines), idx + 3))
    for j in check_range:
        if j == idx:
            continue
        if re.search(r'X{2,}', lines[j], re.IGNORECASE):
            return True
        if re.search(r'debited\s*from|debitedfrom|account|a/c', lines[j], re.IGNORECASE):
            return True
    return False


def _is_year(val: float) -> bool:
    """Check if a number looks like a year (2020-2030)."""
    return 2020 <= val <= 2030 and val == int(val)


def _is_phone_or_id(val: float) -> bool:
    """Check if a number looks like a phone/ID, not an amount."""
    return val > 100000 and val == int(val) and len(str(int(val))) >= 8


def _is_time_or_date_line(line: str) -> bool:
    """Check if a line contains time/date info, not an amount."""
    lower = line.lower()
    # Contains time indicators
    if re.search(r'(?:am|pm|a\.m|p\.m)', lower):
        return True
    # Contains month names
    months = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]
    if any(m in lower for m in months):
        return True
    # Contains "on" with digits (like "08.49 pm on 19")
    if re.search(r'\d.*\bon\b.*\d', lower):
        return True
    # Contains @ with letters around it (not a UPI ID — like "pm@n")
    if re.search(r'[a-z]@[a-z]', lower):
        return True
    return False


def _extract_upi_id(text: str) -> Optional[str]:
    """Extract UPI ID like user@bank."""
    # Common UPI handle patterns
    match = re.search(r'[a-zA-Z0-9._\-]+@[a-z]{2,}(?:bank|upi|pay|axis|hdfc|icici|sbi|kotak|ybl|okhdfcbank|okicici|oksbi|paytm|apl|ibl)?', text, re.IGNORECASE)
    return match.group(0).lower() if match else None


def _extract_transaction_id(text: str) -> Optional[str]:
    """Extract UPI transaction reference ID."""
    # Try labeled patterns first
    for m in re.finditer(r'(?:UPI\s*(?:Ref|ID|Transaction)\s*(?:No\.?|:)?|Transaction\s*ID\s*:?|Ref\s*(?:No\.?|:))\s*(\d{10,16})', text, re.IGNORECASE):
        return m.group(1)
    # Fallback: any 12-digit number
    match = re.search(r'\b(\d{12,16})\b', text)
    return match.group(1) if match else None


def _extract_date(text: str) -> Optional[date]:
    """Extract date from screenshot text. Enhanced patterns."""
    # Normalize: join lines that might split dates across lines
    # e.g. "May\n2026" or "10 May\n2026"
    joined = re.sub(r'\n\s*', ' ', text)

    patterns = [
        # "on DD Mon YYYY" or "on DD Month YYYY" (common in UPI: "08.49 pm on 19 May 2026")
        (r'on\s+(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s,]+(\d{4})',
         ["%d %b %Y", "%d %B %Y"]),
        # DD Mon YYYY (e.g., 15 May 2024)
        (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s,]+(\d{4})',
         ["%d %b %Y", "%d %B %Y"]),
        # Mon DD, YYYY (e.g., May 15, 2024)
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{1,2}),?\s+(\d{4})',
         ["%b %d %Y", "%B %d %Y"]),
        # DD/MM/YYYY or DD-MM-YYYY
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', ["%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]),
        # DD/MM/YY
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})\b', ["%d/%m/%y", "%m/%d/%y"]),
        # YYYY-MM-DD (ISO format)
        (r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', ["%Y-%m-%d", "%Y/%m/%d"]),
    ]
    for pat, fmts in patterns:
        match = re.search(pat, joined, re.IGNORECASE)
        if match:
            date_str = match.group(0).replace(",", "").strip()
            # Remove leading "on " if present
            date_str = re.sub(r'^on\s+', '', date_str, flags=re.IGNORECASE)
            for fmt in fmts:
                try:
                    parsed = datetime.strptime(date_str, fmt).date()
                    if parsed <= date.today() and parsed.year >= 2020:
                        return parsed
                except ValueError:
                    continue
    return None


def _extract_time(text: str) -> Optional[str]:
    """Extract time from screenshot text."""
    match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)', text)
    return match.group(1).strip() if match else None


def _extract_merchant(text: str) -> str:
    """Extract merchant/payee name from text. Enhanced for all UPI apps."""
    # Fix merged OCR text
    fixed = text.replace("Paidto", "Paid to").replace("paidto", "paid to")
    fixed = fixed.replace("Debitedfrom", "Debited from")
    fixed = fixed.replace("Receivedfrom", "Received from")

    # Strategy 1: Look for name on/after "Paid to" or "Received from" line
    lines = fixed.split("\n")
    for i, line in enumerate(lines):
        lower_line = line.strip().lower()
        if any(kw in lower_line for kw in ["paid to", "sent to", "payment to", "received from", "got from"]):
            # Check if name is on the SAME line (after the keyword)
            for kw in ["paid to", "sent to", "received from", "got from", "payment to"]:
                m = re.search(
                    kw + r'\s+([A-Za-z][A-Za-z0-9\s.&\'\-]{1,35})',
                    line, re.IGNORECASE
                )
                if m:
                    name = m.group(1).strip()
                    if len(name) >= 2 and not re.match(r'^\d+$', name):
                        return _clean_merchant_name(name)
            # Check NEXT few lines for name
            for j in range(i + 1, min(len(lines), i + 6)):
                next_line = lines[j].strip()
                if not next_line:
                    continue
                # Skip purely numeric lines (amounts)
                if re.match(r'^[\d,.\s₹%]+$', next_line):
                    continue
                # Skip phone numbers
                if re.match(r'^\+?\d{10,}$', next_line.replace(" ", "")):
                    continue
                # Skip UPI IDs
                if '@' in next_line:
                    continue
                # Skip lines that are duplicates of keywords
                if any(kw in next_line.lower() for kw in ["paid to", "sent to", "received from"]):
                    continue
                # Found a valid merchant name line (allow letters AND digits like "Baba 1")
                if re.match(r'^[A-Za-z]', next_line) and len(next_line) >= 2:
                    return _clean_merchant_name(next_line)

    # Strategy 2: Regex patterns
    patterns = [
        r'(?:paid to|sent to|payment to|money sent to)[ \t]+([A-Za-z][A-Za-z0-9 \t.&\'\-]{1,35})',
        r'(?:received from|got from|credited from)[ \t]+([A-Za-z][A-Za-z0-9 \t.&\'\-]{1,35})',
        r'(?:^|\n)\s*(?:To|FROM|Paid)[ \t]+([A-Z][a-zA-Z0-9 \t.&\'\-]{2,25})',
        r'([A-Za-z][A-Za-z0-9 ]{2,25})\n\s*[a-z0-9._\-]+@',
        r'(?:to|from)[ \t]+([A-Z][a-zA-Z0-9 \t.&\'\-]{2,25})',
    ]
    for pat in patterns:
        match = re.search(pat, fixed, re.IGNORECASE | re.MULTILINE)
        if match:
            name = _clean_merchant_name(match.group(1))
            if len(name) >= 3 and not name.isdigit():
                return name

    # Strategy 3: Extract from UPI ID (e.g. relianceretail2easebuzz@kotakpay → Reliance Retail)
    upi_match = re.search(r'([a-zA-Z0-9._\-]+)@[a-z]+', fixed)
    if upi_match:
        upi_name = upi_match.group(1)
        # Clean numbers and split camelCase
        upi_clean = re.sub(r'\d+', ' ', upi_name)
        upi_clean = re.sub(r'([a-z])([A-Z])', r'\1 \2', upi_clean)
        upi_clean = upi_clean.replace("_", " ").replace(".", " ").strip()
        if len(upi_clean) >= 3:
            # Take first meaningful word(s) from UPI ID
            words = upi_clean.split()
            merchant = " ".join(words[:3]).title()
            return merchant[:50]

    return "UPI Transaction"


def _clean_merchant_name(name: str) -> str:
    """Clean up a merchant name from OCR noise."""
    name = name.strip()
    # Remove trailing noise words
    name = re.sub(r'\s+(on|at|via|upi|payment|transaction|ref|dated|using|with|transfer).*',
                 '', name, flags=re.IGNORECASE)
    # Remove trailing numbers only if they're long (4+ digits = transaction ID, not a name like "Baba 1")
    name = re.sub(r'\d{4,}$', '', name).strip()
    # Remove common OCR noise
    name = re.sub(r'[|\\/{}\[\]<>]', '', name).strip()
    return name[:50] if name else "UPI Transaction"


def _extract_status(text: str) -> str:
    """Check if transaction was successful."""
    lower = text.lower()
    success_kw = ["successful", "success", "completed", "done", "paid",
                  "money sent", "payment done", "transferred"]
    fail_kw = ["failed", "failure", "declined", "pending", "cancelled",
               "timed out", "timeout", "could not"]

    success_score = sum(1 for kw in success_kw if kw in lower)
    fail_score = sum(1 for kw in fail_kw if kw in lower)

    if fail_score > success_score:
        return "failed"
    if success_score > 0:
        return "success"
    return "unknown"


def _detect_transaction_type(text: str) -> str:
    """Detect if it's a debit (expense) or credit (income) with weighted scoring."""
    fixed = text.replace("Paidto", "Paid to").replace("Debitedfrom", "Debited from")
    lower = fixed.lower()

    # ── Strong income signals (weight 3) ──
    strong_income = [
        "money received", "payment received", "received successfully",
        "credited to your account", "you received", "received from",
        "cashback credited", "refund credited", "refund successful",
        "amount credited", "credit alert",
    ]
    # ── Moderate income signals (weight 2) ──
    moderate_income = [
        "received", "credited", "cashback", "refund", "got from",
    ]
    # ── Strong expense signals (weight 3) ──
    strong_expense = [
        "money sent", "paid successfully", "payment successful",
        "debited from", "sent successfully", "amount debited",
        "debit alert", "you paid",
    ]
    # ── Moderate expense signals (weight 2) ──
    moderate_expense = [
        "paid to", "sent to", "payment to", "debited",
    ]
    # ── Weak / ambiguous expense signals (weight 1) ──
    # "paid" alone appears on both sent AND received screens
    weak_expense = ["paid", "sent", "transferred"]

    income_score = 0
    expense_score = 0

    for kw in strong_income:
        if kw in lower:
            income_score += 3
    for kw in moderate_income:
        if kw in lower:
            income_score += 2
    for kw in strong_expense:
        if kw in lower:
            expense_score += 3
    for kw in moderate_expense:
        if kw in lower:
            expense_score += 2
    for kw in weak_expense:
        if kw in lower:
            expense_score += 1

    return "income" if income_score > expense_score else "expense"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PARSER — combines all extractors
# ══════════════════════════════════════════════════════════════════════════════

def parse_screenshot(img_bytes: bytes) -> dict:
    """
    Parse a UPI screenshot and extract transaction details.
    Returns dict with: amount, merchant, date, upi_id, txn_id, app,
                       status, type, raw_text
    """
    raw_text = get_raw_text(img_bytes)
    app = detect_upi_app(raw_text)
    amount = _extract_amount(raw_text)
    merchant = _extract_merchant(raw_text)
    txn_date = _extract_date(raw_text) or date.today()
    txn_time = _extract_time(raw_text)
    upi_id = _extract_upi_id(raw_text)
    txn_id = _extract_transaction_id(raw_text)
    status = _extract_status(raw_text)
    txn_type = _detect_transaction_type(raw_text)

    return {
        "amount": amount,
        "merchant": merchant,
        "date": txn_date,
        "time": txn_time,
        "upi_id": upi_id,
        "txn_id": txn_id,
        "app": app,
        "status": status,
        "type": txn_type,
        "raw_text": raw_text,
    }


# ══════════════════════════════════════════════════════════════════════════════
# IMPORT PIPELINE — parse + categorize + save
# ══════════════════════════════════════════════════════════════════════════════

def parse_upi_screenshot(img_bytes: bytes, user_id: int) -> dict:
    """
    Full pipeline: OCR → extract → categorize → save to DB.
    Called by the API import endpoint.
    """
    from database import add_transaction
    from utils import auto_detect_category

    result = parse_screenshot(img_bytes)

    if not result["amount"]:
        return {
            "imported": 0,
            "duplicates_skipped": 0,
            "errors": 1,
            "message": (
                "❌ Could not extract amount from screenshot.\n"
                "Tips: Use a clear, uncropped screenshot showing the full payment confirmation."
            ),
        }

    if result["status"] == "failed":
        return {
            "imported": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "message": "⚠️ This transaction appears to have failed. Skipping import.",
        }

    # Auto-categorize from merchant name
    txn_type = result["type"]
    category = auto_detect_category(result["merchant"], txn_type)
    note = result["merchant"]
    if result["upi_id"]:
        note += f" ({result['upi_id']})"

    try:
        add_transaction(
            user_id,
            txn_type,
            result["amount"],
            category,
            note[:100],
            "UPI",
            str(result["date"]),
        )
        type_label = "Received" if txn_type == "income" else "Paid"
        return {
            "imported": 1,
            "duplicates_skipped": 0,
            "errors": 0,
            "message": (
                f"✅ {type_label}: ₹{result['amount']:,.2f} — {result['merchant']} "
                f"on {result['date']} via {result['app'].replace('_', ' ').title()}"
            ),
        }
    except Exception as e:
        return {
            "imported": 0,
            "duplicates_skipped": 0,
            "errors": 1,
            "message": f"❌ Failed to save transaction: {e}",
        }
