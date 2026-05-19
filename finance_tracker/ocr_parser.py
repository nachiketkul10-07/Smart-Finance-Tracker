"""
ocr_parser.py
-------------
UPI screenshot OCR parser.
Extracts transaction details from Google Pay, PhonePe, Paytm screenshots
using EasyOCR + OpenCV preprocessing. Runs 100% locally — no cloud API.
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
# IMAGE PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def preprocess_image(img_bytes: bytes) -> np.ndarray:
    """Convert raw bytes → cleaned image for OCR."""
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Check file format.")

    # Resize if too small (OCR works better on larger images)
    h, w = img.shape[:2]
    if max(h, w) < 800:
        scale = 800 / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Adaptive thresholding for varied screenshot backgrounds
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8
    )

    # Denoise
    denoised = cv2.fastNlMeansDenoising(binary, h=10)

    return denoised


# ══════════════════════════════════════════════════════════════════════════════
# TEXT EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def extract_text(img_bytes: bytes) -> list:
    """
    Run EasyOCR on image bytes.
    Returns list of (text, confidence) tuples sorted top-to-bottom.
    Uses dual-pass: preprocessed image + raw image, picks best results.
    """
    reader = _get_reader()

    all_results = []

    # Pass 1: preprocessed image
    try:
        processed = preprocess_image(img_bytes)
        results1 = reader.readtext(processed, detail=1)
        all_results.extend(results1)
    except Exception:
        pass

    # Pass 2: raw image (often better for amounts/symbols)
    try:
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        results2 = reader.readtext(img, detail=1)
        all_results.extend(results2)
    except Exception:
        pass

    if not all_results:
        raise ValueError("OCR could not extract any text from the image.")

    # Deduplicate by text content, keep highest confidence
    seen = {}
    for r in all_results:
        txt = r[1].strip()
        conf = r[2]
        if txt and (txt not in seen or conf > seen[txt][2]):
            seen[txt] = r

    results = list(seen.values())
    # Sort by vertical position (top of bounding box)
    results.sort(key=lambda r: r[0][0][1])

    # Return (text, confidence) pairs
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
        "paid to", "received from", "upi transaction",
    ],
    "phonepe": [
        "phonepe", "phone pe", "payment done", "payment successful",
        "paid to", "transaction successful",
    ],
    "paytm": [
        "paytm", "payment successful", "paid to",
        "paytm wallet", "transaction id",
    ],
    "bhim": [
        "bhim", "bhim upi", "transaction successful",
    ],
    "amazon_pay": [
        "amazon pay", "amazon upi",
    ],
    "cred": [
        "cred", "cred upi", "payment done",
    ],
}


def detect_upi_app(text: str) -> str:
    """Detect which UPI app the screenshot is from."""
    lower = text.lower()
    scores = {}
    for app, keywords in UPI_APP_SIGNATURES.items():
        scores[app] = sum(1 for kw in keywords if kw in lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "generic"


# ══════════════════════════════════════════════════════════════════════════════
# REGEX EXTRACTORS
# ══════════════════════════════════════════════════════════════════════════════

def _extract_amount(text: str) -> Optional[float]:
    """Extract monetary amount from text. Handles OCR edge cases."""
    candidates = []

    # Strategy 1: Look for ₹ symbol followed by amount
    for m in re.finditer(r'₹\s?([\d,]+\.?\d*)', text):
        try:
            val = float(m.group(1).replace(",", ""))
            if 1 <= val <= 10_000_000:
                candidates.append(("currency", val))
        except ValueError:
            pass

    # Strategy 2: Rs. / INR prefix
    for m in re.finditer(r'(?:Rs\.?|INR)\s?([\d,]+\.?\d*)', text, re.IGNORECASE):
        try:
            val = float(m.group(1).replace(",", ""))
            if 1 <= val <= 10_000_000:
                candidates.append(("currency", val))
        except ValueError:
            pass

    # Strategy 3: Lines that are ONLY a number (standalone amount lines)
    # OCR often outputs the big amount as its own line like "1,250.00"
    for line in text.split("\n"):
        line = line.strip()
        # Match lines that are purely numeric (with optional commas/dots)
        if re.match(r'^[\d,]+\.\d{2}$', line):
            try:
                val = float(line.replace(",", ""))
                if 1 <= val <= 10_000_000:
                    candidates.append(("standalone", val))
            except ValueError:
                pass

    # Strategy 4: Amount near context words
    for m in re.finditer(
        r'(?:paid|received|debited|credited|amount)\s*(?:₹|Rs\.?|INR)?\s?([\d,]+\.?\d*)',
        text, re.IGNORECASE
    ):
        try:
            val = float(m.group(1).replace(",", ""))
            if 1 <= val <= 10_000_000:
                candidates.append(("context", val))
        except ValueError:
            pass

    if not candidates:
        return None

    # Priority: currency > standalone > context
    priority = {"currency": 0, "standalone": 1, "context": 2}
    candidates.sort(key=lambda x: priority.get(x[0], 9))
    return candidates[0][1]


def _extract_upi_id(text: str) -> Optional[str]:
    """Extract UPI ID like user@bank."""
    match = re.search(r'[a-zA-Z0-9._\-]+@[a-z]{2,}', text)
    return match.group(0) if match else None


def _extract_transaction_id(text: str) -> Optional[str]:
    """Extract 12-digit UPI transaction ID."""
    match = re.search(r'\b(\d{12,16})\b', text)
    return match.group(1) if match else None


def _extract_date(text: str) -> Optional[date]:
    """Extract date from screenshot text."""
    patterns = [
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', "%d/%m/%Y"),
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})\b', "%d/%m/%y"),
        (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})',
         "%d %b %Y"),
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{1,2}),?\s+(\d{4})',
         "%b %d %Y"),
    ]
    for pat, fmt in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            try:
                date_str = match.group(0).replace(",", "")
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
    return None


def _extract_merchant(text: str) -> str:
    """Extract merchant/payee name from text."""
    patterns = [
        r'(?:paid to|sent to|payment to)\s+([A-Za-z][\w\s.&\'-]{2,30})',
        r'(?:received from|from)\s+([A-Za-z][\w\s.&\'-]{2,30})',
        r'(?:to|from)\s+([A-Z][\w\s.&\'-]{2,25})',
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean trailing junk
            name = re.sub(r'\s+(on|at|via|upi|payment).*', '', name, flags=re.IGNORECASE)
            return name[:50]
    return "UPI Transaction"


def _extract_status(text: str) -> str:
    """Check if transaction was successful."""
    lower = text.lower()
    if any(kw in lower for kw in ["successful", "success", "completed", "done", "paid"]):
        return "success"
    if any(kw in lower for kw in ["failed", "failure", "declined", "pending"]):
        return "failed"
    return "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PARSER — combines all extractors
# ══════════════════════════════════════════════════════════════════════════════

def parse_screenshot(img_bytes: bytes) -> dict:
    """
    Parse a UPI screenshot and extract transaction details.
    Returns dict with: amount, merchant, date, upi_id, txn_id, app, status, raw_text
    """
    raw_text = get_raw_text(img_bytes)
    app = detect_upi_app(raw_text)
    amount = _extract_amount(raw_text)
    merchant = _extract_merchant(raw_text)
    txn_date = _extract_date(raw_text) or date.today()
    upi_id = _extract_upi_id(raw_text)
    txn_id = _extract_transaction_id(raw_text)
    status = _extract_status(raw_text)

    return {
        "amount": amount,
        "merchant": merchant,
        "date": txn_date,
        "upi_id": upi_id,
        "txn_id": txn_id,
        "app": app,
        "status": status,
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
            "message": "❌ Could not extract amount from screenshot. Try a clearer image.",
        }

    if result["status"] == "failed":
        return {
            "imported": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "message": "⚠️ This transaction appears to have failed. Skipping import.",
        }

    # Auto-categorize from merchant name
    category = auto_detect_category(result["merchant"], "expense")
    note = result["merchant"]
    if result["upi_id"]:
        note += f" ({result['upi_id']})"

    try:
        add_transaction(
            user_id,
            "expense",
            result["amount"],
            category,
            note[:100],
            "UPI",
            str(result["date"]),
        )
        return {
            "imported": 1,
            "duplicates_skipped": 0,
            "errors": 0,
            "message": (
                f"✅ Imported: ₹{result['amount']:,.2f} to {result['merchant']} "
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
