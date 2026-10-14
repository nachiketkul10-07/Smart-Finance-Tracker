"""Privacy-conscious, best-effort telemetry for the deployed Streamlit app."""
import json
import logging
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import streamlit as st

_LOGGER = logging.getLogger(__name__)
_ALLOWED_HOST = "nexplus-nachiket-space.vercel.app"
_ALLOWED_PATH = "/api/v1/telemetry/events"


def report_page_run(page_name: str, started_at: float, status_code: int = 200) -> None:
    """Send one coarse page-run event; never include financial or account data."""
    try:
        endpoint = str(st.secrets.get("NEXPULSE_INGEST_URL", "")).strip()
        service_id = str(st.secrets.get("NEXPULSE_SERVICE_ID", "")).strip()
        ingest_key = str(st.secrets.get("NEXPULSE_INGEST_KEY", "")).strip()
    except Exception:
        return  # Secrets are optional; telemetry must never break the finance app.

    if not endpoint or not service_id or not ingest_key:
        return

    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST or parsed.path != _ALLOWED_PATH:
        _LOGGER.warning("NexPulse telemetry skipped: ingestion URL is not an approved HTTPS endpoint.")
        return

    page = re.sub(r"[^a-z0-9_-]+", "-", str(page_name).lower()).strip("-")[:48] or "app"
    now = time.monotonic()
    try:
        last_sent = st.session_state.get("_nexpulse_last_sent", {})
        if now - float(last_sent.get(page, 0)) < 20:
            return
        st.session_state["_nexpulse_last_sent"] = {**last_sent, page: now}
    except Exception:
        return

    duration_ms = max(0, min(3_600_000, int((now - started_at) * 1000)))
    payload = {
        "service_id": service_id,
        "request_id": str(uuid4()),
        "method": "GET",
        "endpoint": f"/streamlit/{page}",
        "status_code": status_code,
        "duration_ms": duration_ms,
        "outcome": "success" if status_code < 400 else "error",
        "metadata": {"source": "streamlit", "page": page},
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Ingest-Key": ingest_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=1.5) as response:
            if not 200 <= response.status < 300:
                _LOGGER.warning("NexPulse telemetry returned HTTP %s.", response.status)
    except HTTPError as exc:
        _LOGGER.warning("NexPulse telemetry rejected the event (HTTP %s).", exc.code)
    except (URLError, TimeoutError, OSError) as exc:
        _LOGGER.debug("NexPulse telemetry unavailable (%s).", type(exc).__name__)
    except Exception as exc:
        _LOGGER.debug("NexPulse telemetry failed (%s).", type(exc).__name__)
