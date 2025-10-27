import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# basic config
SIG_BASE = os.getenv("SIGNAL_API_BASE", "http://signal-api:8080")
SIG_NUMBER = os.getenv("SIGNAL_NUMBER", "")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "10"))

@app.get("/health")
def health():
    return jsonify({"status": "ok", "signal_api": SIG_BASE, "number": SIG_NUMBER})

@app.post("/send")
def send():
    """
    POST JSON:
    {
      "to": "+1XXXXXXXXXX",     # or list of numbers
      "message": "hello world"
    }
    """
    if not SIG_NUMBER:
        return jsonify({"error": "SIGNAL_NUMBER not configured"}), 400

    data = request.get_json(silent=True) or {}
    to = data.get("to")
    message = data.get("message")

    if not to or not message:
        return jsonify({"error": "Missing 'to' or 'message'"}), 400

    if isinstance(to, str):
        recipients = [to]
    elif isinstance(to, list):
        recipients = to
    else:
        return jsonify({"error": "Field 'to' must be string or list"}), 400

    payload = {
        "number": SIG_NUMBER,
        "recipients": recipients,
        "message": message,
    }

    try:
        resp = requests.post(f"{SIG_BASE}/v2/send", json=payload, timeout=HTTP_TIMEOUT)
        return jsonify({"ok": resp.ok, "status": resp.status_code, "response": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8787)
