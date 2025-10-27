import os, threading, time, logging, requests
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("signal-gateway")

# --- outbound (existing) ---
SIG_BASE   = os.getenv("SIGNAL_API_BASE", "http://signal-api:8080")
SIG_NUMBER = os.environ["SIGNAL_NUMBER"]
TOKEN      = os.environ["GATEWAY_TOKEN"]

# --- inbound forwarding (new) ---
INBOX_URL       = os.getenv("INBOX_URL", "http://assistant-core:8088/inbox")
INBOX_TOKEN     = os.getenv("INBOX_TOKEN", TOKEN)   # default to gateway token
RECEIVE_TIMEOUT = int(os.getenv("RECEIVE_TIMEOUT", "60"))
ALLOW_SENDERS   = {s.strip() for s in os.getenv("ALLOW_SENDERS", "").split(",") if s.strip()}
ENABLE_FORWARD  = os.getenv("ENABLE_FORWARD", "true").lower() in ("1","true","yes")

@app.post("/notify")
def notify():
    if request.headers.get("Authorization") != f"Bearer {TOKEN}":
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True)
    to  = data.get("to")
    msg = data.get("message", "")
    if not to or not msg:
        return jsonify({"error":"missing to/message"}), 400

    payload = {"number": SIG_NUMBER, "recipients": [to], "message": msg}
    if "attachments" in data:
        payload["attachments"] = data["attachments"]

    r = requests.post(f"{SIG_BASE}/v2/send", json=payload, timeout=10)
    return (r.text, r.status_code, {"Content-Type": r.headers.get("Content-Type","application/json")})

@app.get("/healthz")
def healthz():
    return "ok", 200

# ---- inbound: poll signal-api and forward to assistant-core ----
def _allowed(sender: str) -> bool:
    return (not ALLOW_SENDERS) or (sender in ALLOW_SENDERS)

def _normalize(env: dict) -> dict:
    dm = env.get("dataMessage") or {}
    grp = dm.get("groupInfo") or {}
    return {
        "from": env.get("source"),
        "timestamp": env.get("timestamp"),
        "message": dm.get("message"),
        "group": {"id": grp.get("groupId"), "name": grp.get("name"), "type": grp.get("type")} if grp else None,
        "raw": env,
    }

def _forward(payload: dict):
    try:
        r = requests.post(
            INBOX_URL,
            json=payload,
            headers={"Authorization": f"Bearer {INBOX_TOKEN}", "Content-Type": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:
        log.exception("Inbox forward failed: %s", e)

def _poll_loop():
    url = f"{SIG_BASE}/v1/receive/{SIG_NUMBER}"
    params = {"timeout": RECEIVE_TIMEOUT}
    backoff = 1
    log.info("Starting long-poll: %s (timeout=%s)", url, RECEIVE_TIMEOUT)
    while True:
        try:
            r = requests.get(url, params=params, timeout=RECEIVE_TIMEOUT + 10)
            if r.status_code == 204:
                backoff = 1
                continue
            r.raise_for_status()
            envelopes = r.json()
            if isinstance(envelopes, list):
                for env in envelopes:
                    dm = env.get("dataMessage") or {}
                    sender = env.get("source")
                    text = dm.get("message")
                    if not sender or not text:
                        continue
                    if not _allowed(sender):
                        log.warning("Dropping non-allowed sender: %s", sender)
                        continue
                    if ENABLE_FORWARD:
                        _forward(_normalize(env))
            backoff = 1
        except requests.exceptions.Timeout:
            backoff = 1
            continue
        except Exception as e:
            log.warning("receive error: %s (backoff=%s)", e, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

@app.before_serving
def _start_poller():
    if ENABLE_FORWARD:
        threading.Thread(target=_poll_loop, name="signal-receive-poller", daemon=True).start()
        log.info("Inbound forwarder running → %s", INBOX_URL)
    else:
        log.info("Inbound forwarder disabled")
