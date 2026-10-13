import os
import hmac
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API_KEY = os.environ["SITE_API_KEY"]
SITE_ORIGIN = os.environ["SITE_ORIGIN"].rstrip("/")

# Allow requests from your website
CORS(
    app,
    resources={r"/*": {"origins": [SITE_ORIGIN]}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"]
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]
)


@app.get("/")
def health():
    return jsonify({"status": "running"})


@app.route("/send-fixed", methods=["POST", "OPTIONS"])
@limiter.limit("5 per hour")
def send_fixed_message():
    if request.method == "OPTIONS":
        return "", 204

    origin = request.headers.get("Origin", "").rstrip("/")
    if origin != SITE_ORIGIN:
        return jsonify({"error": "Origin not allowed"}), 403

    message = "مرحبًا! تم إرسال الرسالة من الموقع بنجاح."

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message},
            timeout=15
        )
        result = response.json()

        if not response.ok or not result.get("ok"):
            app.logger.error("Telegram delivery failed")
            return jsonify({"error": "Telegram delivery failed"}), 502

        return jsonify({"success": True})

    except (requests.RequestException, ValueError):
        app.logger.exception("Telegram request failed")
        return jsonify({"error": "Telegram service unavailable"}), 502


@app.post("/send")
def send_message():
    supplied_key = request.headers.get("X-API-Key", "")

    if not hmac.compare_digest(supplied_key, API_KEY):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    message = data.get("message", "")

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Message is required"}), 400

    if len(message) > 3500:
        return jsonify({"error": "Message too long"}), 400

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message},
            timeout=15
        )
        result = response.json()

        if not response.ok or not result.get("ok"):
            app.logger.error("Telegram delivery failed")
            return jsonify({"error": "Telegram delivery failed"}), 502

        return jsonify({"success": True})

    except (requests.RequestException, ValueError):
        app.logger.exception("Telegram request failed")
        return jsonify({"error": "Telegram service unavailable"}), 502
