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
import cv2
import numpy as np
from datetime import datetime, date
from typing import Optional

# Lazy-load EasyOCR reader (downloads ~100MB model on first use)
_reader = None

def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE PREPROCESSING — Multiple strategies for different screenshot types
# ══════════════════════════════════════════════════════════════════════════════

def _decode_image(img_bytes: bytes) -> np.ndarray:
    """Decode image bytes to OpenCV BGR image."""
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Check file format.")
    return img


def _upscale_if_small(img: np.ndarray, min_dim: int = 1200) -> np.ndarray:
    """Upscale small images for better OCR accuracy."""
    h, w = img.shape[:2]
    if max(h, w) < min_dim:
        scale = min_dim / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return img


def preprocess_v1_adaptive(img: np.ndarray) -> np.ndarray:
    """Strategy 1: Adaptive threshold — good for light mode screenshots."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8
    )
    return cv2.fastNlMeansDenoising(binary, h=10)


def preprocess_v2_contrast(img: np.ndarray) -> np.ndarray:
    """Strategy 2: CLAHE contrast enhancement — good for dark mode screenshots."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def preprocess_v3_sharpen(img: np.ndarray) -> np.ndarray:
    """Strategy 3: Sharpen + simple threshold — good for blurry screenshots."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    _, binary = cv2.threshold(sharpened, 127, 255, cv2.THRESH_BINARY)
    return binary


def preprocess_v4_invert(img: np.ndarray) -> np.ndarray:
    """Strategy 4: Inverted for dark mode — white text on dark background."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_val = np.mean(gray)
    if mean_val < 128:  # Dark mode detected
        gray = cv2.bitwise_not(gray)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


# ══════════════════════════════════════════════════════════════════════════════
# TEXT EXTRACTION — Multi-pass OCR for maximum accuracy
# ══════════════════════════════════════════════════════════════════════════════

def extract_text(img_bytes: bytes) -> list:
    """
    Run EasyOCR with multiple preprocessing strategies.
    Returns list of (text, confidence) tuples sorted top-to-bottom.
    """
    reader = _get_reader()
    img = _decode_image(img_bytes)
    img = _upscale_if_small(img)

    all_results = []

    # Pass 1: Raw image (often best for modern screenshots)
    try:
        results = reader.readtext(img, detail=1, paragraph=False)
        all_results.extend(results)
    except Exception:
        pass

    # Pass 2: CLAHE contrast enhanced (dark mode)
    try:
        processed = preprocess_v2_contrast(img)
        results = reader.readtext(processed, detail=1, paragraph=False)
        all_results.extend(results)
    except Exception:
        pass

    # Pass 3: Inverted dark mode
    try:
        processed = preprocess_v4_invert(img)
        results = reader.readtext(processed, detail=1, paragraph=False)
        all_results.extend(results)
    except Exception:
        pass

    # Pass 4: Adaptive threshold (light mode)
    try:
        processed = preprocess_v1_adaptive(img)
        results = reader.readtext(processed, detail=1, paragraph=False)
        all_results.extend(results)
    except Exception:
        pass

    if not all_results:
        raise ValueError("OCR could not extract any text from the image.")

    # Deduplicate: keep highest confidence per unique text
    seen = {}
    for r in all_results:
        txt = r[1].strip()
        conf = r[2]
        if txt and len(txt) >= 1:
            key = txt.lower()
            if key not in seen or conf > seen[key][2]:
                seen[key] = r

    results = list(seen.values())
    results.sort(key=lambda r: r[0][0][1])  # Sort by Y position (top to bottom)

    return [(r[1].strip(), r[2]) for r in results if r[1].strip()]


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
    # Fix common OCR mistakes: 'O' → '0', 'l' → '1', 'S' → '5'
    s = s.replace("O", "0").replace("o", "0")
    s = s.replace("l", "1").replace("I", "1")
    s = s.replace("S", "5").replace("s", "5")
    s = s.replace(" ", "")  # Remove spaces OCR puts in numbers
    # Remove any remaining non-numeric chars except , and .
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


def _extract_amount(text: str) -> Optional[float]:
    """Extract monetary amount from text. Enhanced for OCR edge cases."""
    candidates = []

    # Normalize text — fix common OCR issues
    normalized = text.replace("₨", "₹").replace("Rs.", "₹").replace("RS.", "₹")
    normalized = normalized.replace("Rs", "₹").replace("INR", "₹")

    # Strategy 1: ₹ symbol followed by amount (highest priority)
    for m in re.finditer(r'₹\s?([0-9O][0-9,.\sOlIS]*)', normalized):
        val = _clean_ocr_amount(m.group(1))
        if val:
            candidates.append(("currency", val, m.start()))

    # Strategy 2: Rs. / INR prefix
    for m in re.finditer(r'(?:Rs\.?|INR|Rupees)\s?([0-9O][0-9,.\sOlIS]*)', text, re.IGNORECASE):
        val = _clean_ocr_amount(m.group(1))
        if val:
            candidates.append(("currency", val, m.start()))

    # Strategy 3: Context words near amount
    for m in re.finditer(
        r'(?:paid|received|debited|credited|amount|total|sent|money sent)\s*:?\s*(?:₹|Rs\.?|INR)?\s?([0-9O][0-9,.\sOlIS]*)',
        text, re.IGNORECASE
    ):
        val = _clean_ocr_amount(m.group(1))
        if val:
            candidates.append(("context", val, m.start()))

    # Strategy 4: Standalone number lines (common in payment screenshots)
    for line in text.split("\n"):
        line = line.strip()
        # Match lines that look like money amounts
        if re.match(r'^[₹]?\s?[0-9,]+\.?\d{0,2}$', line):
            val = _clean_ocr_amount(line.replace("₹", ""))
            if val and val >= 1:
                candidates.append(("standalone", val, 0))

    # Strategy 5: Large bold numbers (OCR often reads the big amount first)
    for m in re.finditer(r'\b(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b', text):
        val = _clean_ocr_amount(m.group(1))
        if val and val >= 10:  # Skip tiny numbers
            candidates.append(("numeric", val, m.start()))

    if not candidates:
        return None

    # Priority: currency > context > standalone > numeric
    # Among same priority, prefer larger amounts (the main transaction amount)
    priority = {"currency": 0, "context": 1, "standalone": 2, "numeric": 3}
    candidates.sort(key=lambda x: (priority.get(x[0], 9), -x[1]))
    return candidates[0][1]


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
    patterns = [
        # DD/MM/YYYY or DD-MM-YYYY
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', ["%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]),
        # DD/MM/YY
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})\b', ["%d/%m/%y", "%m/%d/%y"]),
        # DD Mon YYYY (e.g., 15 May 2024)
        (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s,]+(\d{4})',
         ["%d %b %Y", "%d %B %Y"]),
        # Mon DD, YYYY (e.g., May 15, 2024)
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{1,2}),?\s+(\d{4})',
         ["%b %d %Y", "%B %d %Y"]),
        # YYYY-MM-DD (ISO format)
        (r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', ["%Y-%m-%d", "%Y/%m/%d"]),
    ]
    for pat, fmts in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            date_str = match.group(0).replace(",", "").strip()
            for fmt in fmts:
                try:
                    parsed = datetime.strptime(date_str, fmt).date()
                    # Sanity check: not in the future, not too old
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
    patterns = [
        # "Paid to <name>" / "Sent to <name>"
        r'(?:paid to|sent to|payment to|money sent to)\s+([A-Za-z][A-Za-z\s.\&\'\-]{1,35})',
        # "Received from <name>"
        r'(?:received from|got from)\s+([A-Za-z][A-Za-z\s.\&\'\-]{1,35})',
        # "To <NAME>" (capitalized name on its own line)
        r'(?:^|\n)\s*(?:To|FROM|Paid)\s+([A-Z][a-zA-Z\s.\&\'\-]{2,25})',
        # Name followed by UPI ID on next line (GPay pattern)
        r'([A-Za-z][A-Za-z\s]{2,25})\n\s*[a-z0-9._\-]+@',
        # Generic "to/from <name>"
        r'(?:to|from)\s+([A-Z][a-zA-Z\s.\&\'\-]{2,25})',
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if match:
            name = match.group(1).strip()
            # Clean trailing noise
            name = re.sub(r'\s+(on|at|via|upi|payment|transaction|ref|dated|using|with).*',
                         '', name, flags=re.IGNORECASE)
            name = name.strip()
            if len(name) >= 2 and not name.isdigit():
                return name[:50]
    return "UPI Transaction"


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
    """Detect if it's a debit (expense) or credit (income)."""
    lower = text.lower()
    credit_kw = ["received", "credited", "got from", "money received",
                 "cashback", "refund", "received from"]
    debit_kw = ["paid", "sent", "debited", "payment to", "money sent",
                "paid to", "sent to", "transferred"]

    credit_score = sum(1 for kw in credit_kw if kw in lower)
    debit_score = sum(1 for kw in debit_kw if kw in lower)

    return "income" if credit_score > debit_score else "expense"


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
