import os, requests
from flask import Flask, request, jsonify

app = Flask(__name__)
SIG_BASE = os.getenv("SIGNAL_API_BASE", "http://signal-api:8080")
SIG_NUMBER = os.environ["SIGNAL_NUMBER"]
TOKEN = os.environ["GATEWAY_TOKEN"]

@app.post("/notify")
def notify():
    if request.headers.get("Authorization") != f"Bearer {TOKEN}":
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True)
    to = data.get("to")              # "+1XXXXXXXXXX" or group id
    msg = data.get("message", "")
    if not to or not msg:
        return jsonify({"error":"missing to/message"}), 400
    payload = {"number": SIG_NUMBER, "recipients": [to], "message": msg}

    # Optional attachment URLs -> downloaded by signal-api if accessible; else skip
    if "attachments" in data:
        payload["attachments"] = data["attachments"]

    r = requests.post(f"{SIG_BASE}/v2/send", json=payload, timeout=10)
    return (r.text, r.status_code, {"Content-Type": r.headers.get("Content-Type","application/json")})

@app.get("/healthz")
def healthz():
    return "ok", 200

