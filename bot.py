import os
import requests
from http.cookiejar import MozillaCookieJar
from flask import Flask, request, jsonify
from pyrogram import Client, filters

# ─── ENV ───
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Render URL

# ─── LOAD COOKIES ───
cookies = MozillaCookieJar("cookies.txt")
cookies.load(ignore_discard=True, ignore_expires=True)

session = requests.Session()
session.cookies = cookies
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 14)",
    "Referer": "https://dm.1024terabox.com/",
    "Accept": "*/*"
})

# ─── PYROGRAM APP (WEBHOOK MODE) ───
app = Client(
    "terabox-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ─── FLASK WEB ───
web = Flask(__name__)

# 🔹 Home / Health
@web.route("/")
def home():
    return "✅ Bot is running", 200

# 🔹 Cookie Check Endpoint
@web.route("/health")
def cookie_health():
    try:
        r = session.get(
            "https://dm.1024terabox.com/api/user/info",
            timeout=15
        )
        if r.status_code == 200:
            return jsonify({
                "status": "ok",
                "cookie": "valid"
            })
        return jsonify({
            "status": "error",
            "cookie": "invalid",
            "code": r.status_code
        }), 401
    except Exception as e:
        return jsonify({
            "status": "error",
            "msg": str(e)
        }), 500


# ─── TELEGRAM HANDLER ───
@app.on_message(filters.text & ~filters.command)
async def terabox_handler(client, message):
    text = message.text.strip()

    if "terabox" not in text:
        return

    await message.reply("⏳ Processing Terabox link...")

    try:
        api = "https://dm.1024terabox.com/api/shorturlinfo"
        res = session.get(api, params={"shorturl": text}, timeout=20).json()
        video_url = res["list"][0]["dlink"]

        await message.reply_video(
            video=video_url,
            caption="✅ Terabox Video"
        )

    except Exception:
        await message.reply("❌ Failed (cookie / link issue)")


# ─── WEBHOOK ROUTE ───
@web.route("/webhook", methods=["POST"])
async def telegram_webhook():
    await app.process_update(request.get_json())
    return "ok"


# ─── START EVERYTHING ───
if __name__ == "__main__":
    app.start()
    app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    web.run(host="0.0.0.0", port=8080)
