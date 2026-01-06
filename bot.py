import os
import re
import threading
import requests
from http.cookiejar import MozillaCookieJar
from flask import Flask
from pyrogram import Client, filters

# ─────────── ENV ───────────
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─────────── FLASK (Render Web Service needs port) ───────────
web = Flask(__name__)

@web.route("/")
def home():
    return "✅ Terabox Bot is running"

def run_web():
    web.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web, daemon=True).start()

# ─────────── REQUEST SESSION (COOKIE SAFE) ───────────
def create_session():
    jar = MozillaCookieJar("cookies.txt")
    jar.load(ignore_discard=True, ignore_expires=True)

    s = requests.Session()
    s.cookies = jar
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://dm.1024terabox.com/",
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive",
    })
    return s

session = create_session()

# ─────────── PYROGRAM BOT ───────────
app = Client(
    "terabox-final-safe",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ─────────── HELPERS ───────────
def extract_surl(link: str):
    m = re.search(r"(surl=|/s/)([A-Za-z0-9_-]+)", link)
    return m.group(2) if m else None


def shorturl_info(surl: str):
    """
    SAFE: direct API call (no redirect)
    """
    api = "https://dm.1024terabox.com/api/shorturlinfo"
    r = session.get(api, params={"surl": surl}, timeout=30)

    if r.status_code != 200:
        raise Exception(f"Terabox API HTTP {r.status_code}")

    data = r.json()
    if "list" not in data:
        raise Exception(
            data.get("errmsg", "Private / expired / blocked link")
        )

    return data["list"]


def collect_files(items, path=""):
    files = []
    for item in items:
        if item.get("isdir") == 1:
            fs_id = item.get("fs_id")
            if not fs_id:
                continue

            api = "https://dm.1024terabox.com/api/list"
            r = session.get(api, params={"dir": fs_id}, timeout=30)
            if r.status_code != 200:
                continue

            j = r.json()
            files.extend(
                collect_files(
                    j.get("list", []),
                    path + item.get("name", "") + "/"
                )
            )
        else:
            if item.get("dlink"):
                files.append(
                    (path + item.get("name", "video.mp4"), item["dlink"])
                )
    return files


def resolve_videos(link: str):
    surl = extract_surl(link)
    if not surl:
        raise Exception("Invalid Terabox link")

    root_items = shorturl_info(surl)
    videos = collect_files(root_items)

    if not videos:
        raise Exception("No downloadable videos found")

    return videos

# ─────────── COMMANDS ───────────
@app.on_message(filters.command("start"))
async def start_cmd(_, message):
    await message.reply(
        "👋 **Welcome!**\n\n"
        "📥 Send any **Terabox link** and I will fetch & send the video.\n\n"
        "✅ Supports:\n"
        "• Single video\n"
        "• Folder (multiple videos)\n\n"
        "❌ Not supported:\n"
        "• Private / password links\n"
        "• Expired links",
        quote=True
    )

# ─────────── MAIN HANDLER ───────────
@app.on_message(filters.text)
async def handler(_, message):
    text = message.text.strip()

    if text.startswith("/"):
        return

    if "tera" not in text.lower():
        return

    status = await message.reply("⏳ Processing Terabox link...")

    try:
        videos = resolve_videos(text)

        sent = 0
        for name, url in videos:
            await message.reply_video(
                video=url,
                caption=f"🎬 {name}"
            )
            sent += 1
            if sent >= 5:   # anti-spam safety
                break

        await status.edit_text(f"✅ Sent {sent} video(s)")

    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")

# ─────────── START ───────────
print("🤖 Terabox bot started (FINAL SAFE MODE)")
app.run()
