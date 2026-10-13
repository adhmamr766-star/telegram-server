
import os
import hmac
import requests
from urllib.parse import urlparse
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API_KEY = os.environ["SITE_API_KEY"]
SITE_ORIGIN = os.environ["SITE_ORIGIN"].rstrip("/")

CORS(
    app,
    resources={r"/*": {"origins": [SITE_ORIGIN]}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
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

    data = request.get_json(silent=True) or {}
    page_url = data.get("page_url", "")

    if not isinstance(page_url, str) or not page_url or len(page_url) > 2000:
        return jsonify({"error": "Invalid page URL"}), 400

    page = urlparse(page_url)
    site = urlparse(SITE_ORIGIN)

    if page.scheme not in ("http", "https") or not page.netloc:
        return jsonify({"error": "Invalid page URL"}), 400

    if page.netloc.lower() != site.netloc.lower():
        return jsonify({
            "error": "Page domain does not match SITE_ORIGIN",
            "received_host": page.netloc,
            "expected_host": site.netloc
        }), 400

    message = (
        "📩 تم إرسال نموذج من موقع Pearly Kidz\n"
        f"🌐 الصفحة: {page_url}"
    )

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message},
            timeout=15,
        )
        result = response.json()

        if not response.ok or not result.get("ok"):
            app.logger.error(
                "Telegram API rejected the fixed message: %s",
                result.get("description", "Unknown error")
            )
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
            timeout=15,
        )
        result = response.json()

        if not response.ok or not result.get("ok"):
            app.logger.error(
                "Telegram API rejected the message: %s",
                result.get("description", "Unknown error")
            )
            return jsonify({"error": "Telegram delivery failed"}), 502

        return jsonify({"success": True})

    except (requests.RequestException, ValueError):
        app.logger.exception("Telegram request failed")
        return jsonify({"error": "Telegram service unavailable"}), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )
