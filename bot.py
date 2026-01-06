import os
import re
import requests
from http.cookiejar import MozillaCookieJar
from pyrogram import Client, filters

# ─── ENV CONFIG ───
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─── OPTIONAL FREE PROXY (leave empty if not using) ───
PROXIES = [
    # "http://ip:port",
    # "http://user:pass@ip:port"
]

# ─── SESSION CREATOR ───
def create_session(use_proxy=False):
    jar = MozillaCookieJar("cookies.txt")
    jar.load(ignore_discard=True, ignore_expires=True)

    s = requests.Session()
    s.cookies = jar
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 14)",
        "Referer": "https://dm.1024terabox.com/",
        "Accept": "application/json, text/plain, */*",
    })

    if use_proxy and PROXIES:
        s.proxies.update({
            "http": PROXIES[0],
            "https": PROXIES[0],
        })

    return s


session = create_session()

# ─── PYROGRAM BOT ───
app = Client(
    "terabox-link-to-video",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ─── HELPERS ───
def extract_surl(url):
    m = re.search(r"(surl=|/s/)([A-Za-z0-9_-]+)", url)
    return m.group(2) if m else None


def shorturl_info(surl):
    api = "https://dm.1024terabox.com/api/shorturlinfo"
    r = session.get(api, params={"surl": surl}, timeout=20)

    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}")

    data = r.json()
    if "list" not in data:
        raise Exception(data.get("errmsg", "Private / expired / blocked link"))

    return data["list"]


def collect_files(items, path=""):
    files = []

    for item in items:
        if item.get("isdir") == 1:
            fs_id = item.get("fs_id")
            if not fs_id:
                continue

            api = "https://dm.1024terabox.com/api/list"
            r = session.get(api, params={"dir": fs_id}, timeout=20)
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


def resolve_videos(link):
    # follow redirects (teraboxlink / www / dm / wap)
    r = session.get(link, allow_redirects=True, timeout=20)
    surl = extract_surl(r.url)

    if not surl:
        raise Exception("Invalid Terabox link")

    root_items = shorturl_info(surl)
    videos = collect_files(root_items)

    if not videos:
        raise Exception("No downloadable videos found")

    return videos


# ─── BOT HANDLER ───
@app.on_message(filters.text)
async def handle_message(client, message):
    text = message.text.strip()

    # ignore commands
    if text.startswith("/"):
        return

    # quick filter
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

            if sent >= 5:  # anti-spam safety
                break

        await status.edit_text(f"✅ Sent {sent} video(s)")

    except Exception as e:
        # retry once with proxy if available
        try:
            global session
            session = create_session(use_proxy=True)
            videos = resolve_videos(text)
            name, url = videos[0]

            await message.reply_video(
                video=url,
                caption=f"🎬 {name}\n⚠️ Used proxy fallback"
            )
            await status.edit_text("⚠️ Proxy fallback used")

        except Exception as e2:
            await status.edit_text(f"❌ Error: {e}")


# ─── START BOT ───
print("🤖 Terabox bot started")
app.run()
