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
SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "https://pearlykids-uae.com").rstrip("/")
API_KEY = os.environ.get("SITE_API_KEY", "")

CORS(
    app,
    resources={r"/*": {"origins": [SITE_ORIGIN]}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

limiter = Limiter(get_remote_address, app=app, default_limits=[])


@app.get("/")
def health():
    return jsonify({"status": "running"})


def send_telegram(text):
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=15,
    )
    result = response.json()
    if not response.ok or not result.get("ok"):
        app.logger.error(
            "Telegram API rejected message: %s",
            result.get("description", "Unknown error"),
        )
        return False
    return True



@app.route("/send-order", methods=["POST", "OPTIONS"])
@limiter.limit("10 per hour")
def send_order():
    # السماح بطلب الفحص المسبق الذي يرسله المتصفح
    if request.method == "OPTIONS":
        return "", 204

    origin = request.headers.get("Origin", "").rstrip("/")
    if origin != SITE_ORIGIN:
        return jsonify({"error": "Origin not allowed"}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    page_url = data.get("page_url", "")
    if not isinstance(page_url, str) or not page_url:
        return jsonify({"error": "Invalid page URL"}), 400

    page = urlparse(page_url)
    site = urlparse(SITE_ORIGIN)

    if page.scheme not in ("http", "https") or page.netloc.lower() != site.netloc.lower():
        return jsonify({"error": "Page domain does not match SITE_ORIGIN"}), 400

    customer = data.get("customer", {})
    if not isinstance(customer, dict):
        customer = {}

    items = data.get("items", [])
    if not isinstance(items, list):
        items = []

    lines = [
        "🛍️ طلب جديد من Pearly Kidz",
        f"🌐 الصفحة: {page_url}",
        f"👤 الاسم: {str(customer.get('name', 'غير مذكور'))[:120]}",
        f"📞 الهاتف: {str(customer.get('phone', 'غير مذكور'))[:60]}",
        f"📍 الإمارة: {str(customer.get('emirate', 'غير مذكور'))[:100]}",
        f"🏠 العنوان: {str(customer.get('address', 'غير مذكور'))[:500]}",
        "",
        "📦 المنتجات:"
    ]

    for i, item in enumerate(items[:30], 1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", item.get("name", "منتج")))[:160]
        size = str(item.get("size", "غير محدد"))[:50]
        try:
            quantity = max(1, min(99, int(item.get("quantity", 1))))
        except (TypeError, ValueError):
            quantity = 1
        lines.append(f"{i}. {title} | المقاس: {size} | الكمية: {quantity}")

    subtotal = str(data.get("subtotal", "غير محدد"))[:40]
    currency = str(data.get("currency", ""))[:12]
    payment_method = str(data.get("payment_method", "غير محددة"))[:60]

    lines.extend([
        "",
        f"💰 الإجمالي: {subtotal} {currency}",
        f"💳 طريقة الدفع المختارة: {payment_method}",
        "ℹ️ هذا إشعار بطلب، وليس تأكيدًا على نجاح الدفع."
    ])

    try:
        if not send_telegram("\n".join(lines)[:3900]):
            return jsonify({"error": "Telegram delivery failed"}), 502
        return jsonify({"success": True})
    except (requests.RequestException, ValueError):
        app.logger.exception("Telegram request failed")
        return jsonify({"error": "Telegram service unavailable"}), 502

@limiter.limit("10 per hour")
def send_order():
    if request.method == "OPTIONS":
        return "", 204

    origin = request.headers.get("Origin", "").rstrip("/")
    if origin != SITE_ORIGIN:
        return jsonify({"error": "Origin not allowed"}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    page_url = data.get("page_url", "")
    if not isinstance(page_url, str) or len(page_url) > 2000:
        return jsonify({"error": "Invalid page URL"}), 400

    page = urlparse(page_url)
    site = urlparse(SITE_ORIGIN)
    if page.scheme not in ("http", "https") or page.netloc.lower() != site.netloc.lower():
        return jsonify({"error": "Page domain does not match SITE_ORIGIN"}), 400

    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    items = data.get("items") if isinstance(data.get("items"), list) else []
    items = items[:30]

    # Allowlisted ordinary order details only. Card number, expiry, and CVV are never read.
    lines = [
        "🛍️ طلب جديد من Pearly Kidz",
        f"🌐 الصفحة: {page_url}",
        "",
        "👤 بيانات العميل",
        f"الاسم: {str(customer.get('name', 'غير مذكور'))[:120]}",
        f"📞 الهاتف: {str(customer.get('phone', 'غير مذكور'))[:60]}",
        f"📍 الإمارة: {str(customer.get('emirate', 'غير مذكور'))[:100]}",
        f"🏠 العنوان: {str(customer.get('address', 'غير مذكور'))[:500]}",
        "",
        "📦 المنتجات",
    ]

    if items:
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", item.get("name", "منتج")))[:160]
            size = str(item.get("size", "غير محدد"))[:50]
            try:
                quantity = max(1, min(99, int(item.get("quantity", 1))))
            except (TypeError, ValueError):
                quantity = 1
            lines.append(f"{index}. {title} | المقاس: {size} | الكمية: {quantity}")
    else:
        lines.append("لم تُرفق تفاصيل المنتجات.")

    subtotal = str(data.get("subtotal", "غير محدد"))[:40]
    currency = str(data.get("currency", ""))[:12]
    payment_method = str(data.get("payment_method", "غير محددة"))[:60]
    lines.extend([
        "",
        f"💰 الإجمالي: {subtotal} {currency}".strip(),
        f"💳 طريقة الدفع المختارة: {payment_method}",
        "",
        "ℹ️ هذا إشعار بطلب، وليس تأكيدًا على نجاح الدفع.",
    ])

    message = "\n".join(lines)[:3900]

    try:
        if not send_telegram(message):
            return jsonify({"error": "Telegram delivery failed"}), 502
        return jsonify({"success": True})
    except (requests.RequestException, ValueError):
        app.logger.exception("Telegram request failed")
        return jsonify({"error": "Telegram service unavailable"}), 502


@app.post("/send")
def send_message():
    supplied_key = request.headers.get("X-API-Key", "")
    if not API_KEY or not hmac.compare_digest(supplied_key, API_KEY):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Message is required"}), 400
    if len(message) > 3500:
        return jsonify({"error": "Message too long"}), 400

    try:
        if not send_telegram(message):
            return jsonify({"error": "Telegram delivery failed"}), 502
        return jsonify({"success": True})
    except (requests.RequestException, ValueError):
        app.logger.exception("Telegram request failed")
        return jsonify({"error": "Telegram service unavailable"}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
