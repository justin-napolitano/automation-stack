import os
import time
import json
import threading
from typing import Dict, Any, List

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# -------------------------
# Config
# -------------------------
SIG_BASE = os.getenv("SIGNAL_API_BASE", "http://signal-api:8080")
SIG_NUMBER = os.getenv("SIGNAL_NUMBER", "")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "10"))

# receive / forward settings
RECEIVE_TIMEOUT = int(os.getenv("RECEIVE_TIMEOUT", "25"))  # seconds; signal server long-poll
ENABLE_FORWARD = os.getenv("ENABLE_FORWARD", "false").lower() in {"1", "true", "yes", "on"}
INBOX_URL = os.getenv("INBOX_URL", "")
INBOX_TOKEN = os.getenv("INBOX_TOKEN", "")

# comma-separated allowlist of E.164 numbers (+1xxx), or "*" to allow all
ALLOW_SENDERS = {s.strip() for s in os.getenv("ALLOW_SENDERS", "*").split(",") if s.strip()}

# -------------------------
# Poller control (no Flask hooks)
# -------------------------
_poller_thread: threading.Thread | None = None
_stop_event = threading.Event()
_started_flag = threading.Event()  # avoid double-start within a worker

def _allowed(sender: str) -> bool:
    if "*" in ALLOW_SENDERS:
        return True
    return sender in ALLOW_SENDERS

def _normalize(envelope: Dict[str, Any]) -> Dict[str, Any]:
    dm = envelope.get("dataMessage") or {}
    return {
        "transport": "signal",
        "sender": envelope.get("source"),
        "timestamp": envelope.get("timestamp"),  # ms
        "text": dm.get("message"),
        "groupInfo": dm.get("groupInfo"),
        "raw": envelope,
    }

def _forward(payload: Dict[str, Any]) -> None:
    if not (INBOX_URL and INBOX_TOKEN):
        return
    try:
        r = requests.post(
            INBOX_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {INBOX_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
    except Exception as e:
        app.logger.exception("Inbox forward failed: %s", e)

def _receive_once() -> Dict[str, Any]:
    """
    Hit signal-cli-rest-api receive once (long-poll). Returns summary + raw items (limited).
    """
    url = f"{SIG_BASE}/v1/receive/{SIG_NUMBER}"
    params = {"timeout": RECEIVE_TIMEOUT}
    try:
        r = requests.get(url, params=params, timeout=RECEIVE_TIMEOUT + 10)
        # 204 No Content is normal on timeout with no messages
        if r.status_code == 204:
            return {"ok": True, "received": 0, "forwarded": 0, "dropped": 0, "status": 204}#

        r.raise_for_status()
        envelopes = r.json()
        if not isinstance(envelopes, list):
            return {"ok": False, "error": "Unexpected response shape", "status": r.status_code}#
        received = 0
        forwarded = 0
        dropped = 0
        samples: List[Dict[str, Any]] = []#

        for env in envelopes:
            dm = env.get("dataMessage") or {}
            sender = env.get("source")
            text = dm.get("message")
            if not sender or not text:
                continue

            received += 1
            if not _allowed(sender):
                dropped += 1
                app.logger.warning("Dropping non-allowed sender: %s", sender)
                continue

            payload = _normalize(env)
            if ENABLE_FORWARD:
                _forward(payload)
                forwarded += 1

            # include up to 5 sample items in response for visibility
            if len(samples) < 5:
                samples.append(payload)

        return {
            "ok": True,
            "status": r.status_code,
            "received": received,
            "forwarded": forwarded,
            "dropped": dropped,
            "samples": samples,
        }
    except requests.exceptions.Timeout:
        return {"ok": True, "status": 204, "received": 0, "forwarded": 0, "dropped": 0}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.route("/receive_once", methods=["GET", "POST"])
def receive_once():
    """
    One-shot poll of signal-cli REST: GET /v1/receive/<number>
    - Handles 204 No Content
    - Handles empty bodies / non-JSON
    - Surfaces upstream error text
    """
    if not SIG_NUMBER:
        return jsonify({"error": "SIG_NUMBER not set"}), 500

    # Keep it reasonable; the REST image refuses very long timeouts
    poll_timeout = max(1, min(RECEIVE_TIMEOUT, 30))
    url = f"{SIG_BASE}/v1/receive/{SIG_NUMBER}"
    params = {"timeout": RECEIVE_TIMEOUT}

    try:
        r = requests.get(url, params=params, timeout=poll_timeout + 5)

        # No messages within the timeout window
        if r.status_code == 204 or not r.text.strip():
            return jsonify({
                "messages": [],
                "status": "no_content",
                "upstream_status": r.status_code
            }), 200

        # Any non-2xx: return the upstream body for debugging
        if not r.ok:
            return jsonify({
                "error": "upstream_error",
                "upstream_status": r.status_code,
                "upstream_body": r.text[:2000]  # avoid huge dumps
            }), 502

        # Try to parse JSON; if it fails, pass through raw text
        try:
            payload = r.json()
            # Normalize to always be a list
            if isinstance(payload, dict):
                payload = [payload]
            elif payload is None:
                payload = []
            return jsonify({"messages": payload, "upstream_status": r.status_code}), 200
        except ValueError:
            # Upstream returned something that isn’t JSON
            return jsonify({
                "error": "invalid_json_from_upstream",
                "upstream_status": r.status_code,
                "upstream_body": r.text[:2000]
            }), 502

    except requests.exceptions.RequestException as e:
        app.logger.exception("receive_once: request error")
        return jsonify({"error": "request_exception", "detail": str(e)}), 502
    except Exception as e:
        app.logger.exception("receive_once: unexpected error")
        return jsonify({"error": "unexpected_exception", "detail": str(e)}), 500

def _poll_loop():
    app.logger.info("Signal poller started (timeout=%s, forward=%s)", RECEIVE_TIMEOUT, ENABLE_FORWARD)
    backoff = 1
    while not _stop_event.is_set():
        res = _receive_once()
        # Reset backoff on a normal/empty receive
        if res.get("ok", False):
            backoff = 1
        else:
            app.logger.warning("receive_once error: %s", res)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    app.logger.info("Signal poller stopped.")

# -------------------------
# Routes
# -------------------------
@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "signal_api": SIG_BASE,
        "number": SIG_NUMBER[:4] + "…" if SIG_NUMBER else "",
        "forward_enabled": ENABLE_FORWARD,
        "poller_running": _poller_thread is not None and _poller_thread.is_alive(),
    })

@app.get("/config")
def config():
    # Redact sensitive bits
    redacted_token = f"{INBOX_TOKEN[:6]}…" if INBOX_TOKEN else ""
    return jsonify({
        "SIGNAL_API_BASE": SIG_BASE,
        "SIGNAL_NUMBER_set": bool(SIG_NUMBER),
        "RECEIVE_TIMEOUT": RECEIVE_TIMEOUT,
        "ENABLE_FORWARD": ENABLE_FORWARD,
        "INBOX_URL_set": bool(INBOX_URL),
        "INBOX_TOKEN_preview": redacted_token,
        "ALLOW_SENDERS": list(ALLOW_SENDERS),
    })

@app.post("/send")
def send():
    if not SIG_NUMBER:
        return jsonify({"error": "SIGNAL_NUMBER not configured"}), 400

    data = request.get_json(silent=True) or {}
    to = data.get("to")
    message = data.get("message")

    if not to or not message:
        return jsonify({"error": "Missing 'to' or 'message'"}), 400

    recipients = [to] if isinstance(to, str) else to if isinstance(to, list) else None
    if recipients is None:
        return jsonify({"error": "Field 'to' must be string or list"}), 400

    payload = {"number": SIG_NUMBER, "recipients": recipients, "message": message}
    try:
        resp = requests.post(f"{SIG_BASE}/v2/send", json=payload, timeout=HTTP_TIMEOUT)
        return jsonify({"ok": resp.ok, "status": resp.status_code, "response": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

#@app.post("/receive_once")
#def receive_once():
#    if not SIG_NUMBER:
#        return jsonify({"error": "SIGNAL_NUMBER not configured"}), 400
#    result = _receive_once()
#    code = 200 if result.get("ok", False) else 500
#    return jsonify(result), code

@app.post("/start_poller")
def start_poller():
    global _poller_thread
    if not SIG_NUMBER:
        return jsonify({"error": "SIGNAL_NUMBER not configured"}), 400
    if _poller_thread and _poller_thread.is_alive():
        return jsonify({"ok": True, "message": "poller already running"}), 200
    if _started_flag.is_set():
        # should not normally happen, but defend anyway
        try:
            if _poller_thread and not _poller_thread.is_alive():
                _poller_thread.join(timeout=0.1)
        except Exception:
            pass

    _stop_event.clear()
    _started_flag.set()
    _poller_thread = threading.Thread(target=_poll_loop, name="signal-receive-poller", daemon=True)
    _poller_thread.start()
    return jsonify({"ok": True, "message": "poller started"}), 202

@app.post("/stop_poller")
def stop_poller():
    global _poller_thread
    _stop_event.set()
    if _poller_thread and _poller_thread.is_alive():
        # give it a moment to exit
        _poller_thread.join(timeout=1.0)
    running = _poller_thread is not None and _poller_thread.is_alive()
    return jsonify({"ok": True, "poller_running": running})

# -------------------------
# Dev run
# -------------------------
#if __name__ == "__main__":
#    app.run(host="0.0.0.0", port=8787)
