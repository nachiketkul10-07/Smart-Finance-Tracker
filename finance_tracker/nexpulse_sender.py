"""Privacy-conscious best-effort telemetry sender for the Streamlit app."""
import json
import logging
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import streamlit as st

_LOG = logging.getLogger(__name__)
_HOST = "nexplus-flame.vercel.app"
_PATH = "/api/v1/telemetry/events"
_DEFAULT_INGEST_URL = f"https://{_HOST}{_PATH}"


def report_page_run(page_name: str, started_at: float, status_code: int = 200) -> None:
    """Report coarse page-run metadata only; never send finance/account data."""
    try:
        endpoint = str(st.secrets.get("NEXPULSE_INGEST_URL", _DEFAULT_INGEST_URL)).strip()
        service_id = str(st.secrets.get("NEXPULSE_SERVICE_ID", "")).strip()
        key = str(st.secrets.get("NEXPULSE_INGEST_KEY", "")).strip()
    except Exception:
        return
    parsed = urlsplit(endpoint)
    if not key or not service_id or parsed.scheme != "https" or parsed.hostname != _HOST or parsed.path != _PATH:
        return
    page = re.sub(r"[^a-z0-9_-]+", "-", str(page_name).lower()).strip("-")[:48] or "app"
    now = time.monotonic()
    try:
        previous = st.session_state.get("_nexpulse_last_sent", {})
        if now - float(previous.get(page, 0)) < 20:
            return
        st.session_state["_nexpulse_last_sent"] = {**previous, page: now}
    except Exception:
        return
    payload = {"service_id": service_id, "request_id": str(uuid4()), "method": "GET", "endpoint": f"/streamlit/{page}", "status_code": status_code, "duration_ms": max(0, min(3600000, int((now-started_at)*1000))), "outcome": "success" if status_code < 400 else "error", "metadata": {"source": "streamlit", "page": page}}
    request = Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "X-Ingest-Key": key}, method="POST")
    try:
        with urlopen(request, timeout=1.5) as response:
            if not 200 <= response.status < 300:
                _LOG.warning("NexPulse telemetry returned HTTP %s.", response.status)
    except HTTPError as exc:
        _LOG.warning("NexPulse telemetry rejected the event (HTTP %s).", exc.code)
    except (URLError, TimeoutError, OSError) as exc:
        _LOG.debug("NexPulse telemetry unavailable (%s).", type(exc).__name__)
    except Exception as exc:
        _LOG.debug("NexPulse telemetry failed (%s).", type(exc).__name__)
