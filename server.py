
import os
import hmac
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API_KEY = os.environ["SITE_API_KEY"]


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
            json={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=15
        )
        result = response.json()

        if not response.ok or not result.get("ok"):
            app.logger.error("Telegram API rejected the message")
            return jsonify({"error": "Telegram delivery failed"}), 502

    except (requests.RequestException, ValueError):
        app.logger.exception("Telegram request failed")
        return jsonify({"error": "Telegram service unavailable"}), 502

    return jsonify({"success": True})


@app.get("/")
def health():
    return jsonify({"status": "running"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

SITE_ORIGIN = os.environ["SITE_ORIGIN"]

CORS(app, resources={
    r"/send-fixed": {"origins": [SITE_ORIGIN]}
})

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]
)

@app.post("/send-fixed")
@limiter.limit("5 per hour")
def send_fixed_message():
    origin = request.headers.get("Origin", "")

    if origin != SITE_ORIGIN:
        return jsonify({"error": "Forbidden"}), 403

    message = "مرحبًا! تم إرسال الرسالة من الموقع بنجاح."

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message},
            timeout=15
        )

        if not response.ok or not response.json().get("ok"):
            return jsonify({"error": "Telegram delivery failed"}), 502

    except (requests.RequestException, ValueError):
        return jsonify({"error": "Telegram service unavailable"}), 502

    return jsonify({"success": True})

