import os
import json
import time
import threading
import logging
import atexit
import threading


from typing import Any, Dict, List, Optional

import requests
from flask import Flask, request, jsonify

# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------
SIG_BASE = os.environ.get("SIGNAL_API_BASE", "http://signal-api:8080").rstrip("/")
SIG_NUMBER = os.environ.get("SIGNAL_NUMBER", "").strip()

INBOX_URL = os.environ.get("INBOX_URL", "").strip()
INBOX_TOKEN = os.environ.get("INBOX_TOKEN", "").strip()

ENABLE_FORWARD = os.environ.get("ENABLE_FORWARD", "true").lower() in {"1", "true", "yes", "y"}
RECEIVE_TIMEOUT = int(os.environ.get("RECEIVE_TIMEOUT", "30"))  # seconds, server long-poll
ALLOWED_SENDERS = {s.strip() for s in os.environ.get("ALLOWED_SENDERS", "").split(",") if s.strip()}

# If you only want a single replica to poll in a multi-replica deploy, gate with POLL_LEADER=1
POLL_LEADER = os.environ.get("POLL_LEADER", "1") in {"1", "true", "yes", "y"}

# Optional: set a User-Agent for forwards, helpful for downstream logs
FORWARD_UA = os.environ.get("FORWARD_USER_AGENT", "signal-notifier-gateway/1.0")

# --- globals near your other globals ---
_poller_thread = None
_poller_started = False
_poller_lock = threading.Lock()

# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("gateway")

# --------------------------------------------------------------------------------------
# HTTP session
# --------------------------------------------------------------------------------------
sig = requests.Session()
sig.headers.update({"Accept": "application/json"})
forward_sess = requests.Session()
forward_sess.headers.update({"Accept": "application/json", "User-Agent": FORWARD_UA})

# --------------------------------------------------------------------------------------
# Flask
# --------------------------------------------------------------------------------------
app = Flask(__name__)

_health = {"status": "starting"}
_stop_event = threading.Event()

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def _allowed(sender: Optional[str]) -> bool:
    if not ALLOWED_SENDERS:
        return True
    return (sender or "").strip() in ALLOWED_SENDERS


def _normalize(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten the Signal REST envelope into a compact, webhook-friendly payload.
    Keep the original for debugging under 'raw' if you want (off by default).
    """
    dm = envelope.get("dataMessage") or {}
    quote = dm.get("quote") or {}

    # Best-effort message text (may be None for pure attachments/reactions)
    text = dm.get("message")

    # Basic attachment info (filenames/size/mime if available)
    atts = []
    for a in dm.get("attachments") or []:
        atts.append({
            "filename": a.get("filename"),
            "contentType": a.get("contentType"),
            "size": a.get("size"),
            "id": a.get("id"),
            # NOTE: actual bytes are not exposed by the REST gateway here
        })

    return {
        "type": "message",
        "timestamp": envelope.get("timestamp"),
        "source": envelope.get("source"),
        "sourceUuid": envelope.get("sourceUuid"),
        "sourceName": envelope.get("sourceName"),
        "groupInfo": dm.get("groupInfo") or {},
        "text": text,
        "quote": {
            "id": quote.get("id"),
            "author": quote.get("author"),
            "text": (quote.get("text") or "")[:500],
        } if quote else None,
        "attachments": atts,
        # Uncomment if you want the full blob forwarded:
        # "raw": envelope,
    }


def _forward(payload: Dict[str, Any]) -> None:
    if not (INBOX_URL and INBOX_TOKEN):
        log.debug("Forward skipped: INBOX_URL/INBOX_TOKEN not configured")
        return

    try:
        r = forward_sess.post(
            INBOX_URL,
            json=payload,
            headers={"Authorization": f"Bearer {INBOX_TOKEN}", "Content-Type": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        log.info("Forwarded → %s (%s)", INBOX_URL, r.status_code)
    except Exception as e:
        log.exception("Inbox forward failed: %s", e)


def _receive_url() -> str:
    if not SIG_NUMBER:
        raise RuntimeError("SIGNAL_NUMBER is not set")
    return f"{SIG_BASE}/v1/receive/{SIG_NUMBER}"


def _poll_once() -> int:
    """
    Do a single long-poll. Returns number of processed messages.
    Raises on hard HTTP errors (caller decides backoff).
    """
    url = _receive_url()
    params = {"timeout": RECEIVE_TIMEOUT}
    r = sig.get(url, params=params, timeout=RECEIVE_TIMEOUT + 15)

    # 204 No Content is normal when long-poll window elapsed
    if r.status_code == 204:
        return 0

    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, list):
        return 0

    processed = 0
    for env in payload:
        dm = env.get("dataMessage") or {}
        sender = env.get("source")
        text = dm.get("message")

        # We only forward texts or attachments; ignore receipts/typing/etc.
        if not sender or (text is None and not dm.get("attachments")):
            continue

        if not _allowed(sender):
            log.warning("Dropping non-allowed sender: %s", sender)
            continue

        processed += 1
        if ENABLE_FORWARD:
            _forward(_normalize(env))

    return processed


def _poll_loop():
    if not POLL_LEADER:
        log.info("Poller disabled on this replica (POLL_LEADER not set).")
        return

    # quick config checks
    try:
        _ = _receive_url()
    except Exception as e:
        log.error("Poller not started: %s", e)
        return

    url = _receive_url()
    log.info("Starting long-poll: %s (timeout=%ss)", url, RECEIVE_TIMEOUT)

    backoff = 1
    while not _stop_event.is_set():
        try:
            cnt = _poll_once()
            if cnt:
                log.debug("Processed %d inbound message(s)", cnt)
            backoff = 1  # reset backoff on any successful HTTP interaction
            continue
        except requests.exceptions.Timeout:
            backoff = 1
            continue
        except Exception as e:
            log.warning("receive error: %s (backoff=%s)", e, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)


# --------------------------------------------------------------------------------------
# Outbound send helper + API
# --------------------------------------------------------------------------------------
def _send_message(recipients: List[str], message: str, attachments: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Minimal wrapper for bbernhard/signal-cli-rest-api v2 send.
    attachments: list of file paths (must be mounted into the signal-api container if used)
    """
    if not SIG_NUMBER:
        raise RuntimeError("SIGNAL_NUMBER is not set")

    url = f"{SIG_BASE}/v2/send"
    body = {
        "number": SIG_NUMBER,
        "recipients": recipients,
        "message": message,
    }
    if attachments:
        body["attachments"] = attachments

    r = sig.post(url, json=body, timeout=20)
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------------------
# Flask endpoints
# --------------------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": _health.get("status", "unknown"), "polling": POLL_LEADER}), 200


@app.route("/send", methods=["POST"])
def send():
    """
    POST JSON:
    {
      "to": ["+1xxx", "+1yyy"],   # or string "+1xxx"
      "message": "hello world",
      "attachments": ["/path/in/container/file.jpg"]   # optional
    }
    """
    try:
        data = request.get_json(force=True, silent=False)
        to = data.get("to")
        if isinstance(to, str):
            to = [to]
        if not to or not isinstance(to, list):
            return jsonify({"error": "`to` (string or list) is required"}), 400

        message = data.get("message", "")
        attachments = data.get("attachments")
        resp = _send_message(to, message, attachments)
        return jsonify({"ok": True, "response": resp}), 200
    except Exception as e:
        log.exception("send failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# --------------------------------------------------------------------------------------
# Lifecycle hooks
# --------------------------------------------------------------------------------------
def _ensure_poller_started():
    """
    Start the long-poll receiver thread once per process.
    Works on Flask 1.x–3.x (no before_serving needed).
    """
    global _poller_thread, _poller_started
    if not ENABLE_FORWARD:
        app.logger.info("ENABLE_FORWARD is false; poller will not start.")
        return

    with _poller_lock:
        if _poller_started and _poller_thread and _poller_thread.is_alive():
            return
        _poller_thread = threading.Thread(target=start_receiver_loop, name="signal-recv", daemon=True)
        _poller_thread.start()
        _poller_started = True
        app.logger.info("Signal long-poll thread started.")

# Kick off once the first request hits this worker
@app.before_first_request
def _kickoff_poller():
    _ensure_poller_started()

# Stop the receiver on process exit
def _shutdown():
    try:
        shutdown_event.set()
    except Exception:
        pass

atexit.register(_shutdown)

#@app.before_serving
#def _start_poller():
#    _health["status"] = "ready"
#    if POLL_LEADER:
#        t = threading.Thread(target=_poll_loop, name="signal-receive-poller", daemon=True)
#        t.start()
#        if ENABLE_FORWARD:
#            log.info("Inbound forwarder running → %s", INBOX_URL or "(disabled)")
#    else:
#        log.info("Poller not started (POLL_LEADER disabled).")


#@app.after_serving
#def _stop():
#    _stop_event.set()


# --------------------------------------------------------------------------------------
# Local dev
# --------------------------------------------------------------------------------------
#if __name__ == "__main__":
    # For local debugging only; in Docker use gunicorn:
    #   gunicorn -w 2 -b 0.0.0.0:8787 app:app
#    app.run(host="0.0.0.0", port=8787, debug=False)
