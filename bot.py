import re
import requests
from http.cookiejar import MozillaCookieJar
from pyrogram import Client, filters

# ── CONFIG ──
API_ID = 123456
API_HASH = "API_HASH"
BOT_TOKEN = "BOT_TOKEN"

# ── OPTIONAL FREE PROXIES (unstable; try only if cookies fail) ──
PROXIES = [
    # "http://username:password@ip:port",
    # "http://ip:port",
]

def get_session(use_proxy=False):
    cookies = MozillaCookieJar("cookies.txt")
    cookies.load(ignore_discard=True, ignore_expires=True)

    s = requests.Session()
    s.cookies = cookies
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

session = get_session(use_proxy=False)

app = Client("terabox-simple", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ── HELPERS ──
def extract_surl(link):
    m = re.search(r"(surl=|/s/)([A-Za-z0-9_-]+)", link)
    return m.group(2) if m else None

def api_shortinfo(surl):
    url = "https://dm.1024terabox.com/api/shorturlinfo"
    r = session.get(url, params={"surl": surl}, timeout=20)
    if r.status_code != 200:
        raise Exception(f"API HTTP {r.status_code}")
    data = r.json()
    if "list" not in data:
        # common reasons: private / expired / password
        raise Exception(data.get("errmsg", "Private / expired / blocked"))
    return data["list"]

def collect_files(items, base_path=""):
    files = []
    for it in items:
        if it.get("isdir") == 1:
            # folder → recurse via list API
            fs_id = it.get("fs_id")
            if not fs_id:
                continue
            url = "https://dm.1024terabox.com/api/list"
            r = session.get(url, params={"dir": fs_id}, timeout=20)
            if r.status_code != 200:
                continue
            j = r.json()
            files += collect_files(j.get("list", []), base_path + it.get("name", "") + "/")
        else:
            if it.get("dlink"):
                files.append((base_path + it.get("name", "video.mp4"), it["dlink"]))
    return files

def resolve_all_videos(link):
    # follow redirects (supports teraboxlink / www / dm / wap)
    r = session.get(link, allow_redirects=True, timeout=20)
    surl = extract_surl(r.url)
    if not surl:
        raise Exception("Invalid Terabox link")

    root_list = api_shortinfo(surl)
    files = collect_files(root_list)

    if not files:
        raise Exception("No downloadable videos found")
    return files

# ── BOT ──
@app.on_message(filters.text & ~filters.command)
async def handler(_, message):
    text = message.text.strip()
    if "tera" not in text.lower():
        return

    m = await message.reply("⏳ Resolving link...")

    try:
        files = resolve_all_videos(text)

        sent = 0
        for name, dlink in files:
            await message.reply_video(
                video=dlink,
                caption=f"🎬 {name}"
            )
            sent += 1
            if sent >= 5:  # safety cap (avoid spam)
                break

        await m.edit_text(f"✅ Sent {sent} video(s)")

    except Exception as e:
        # retry once with proxy if configured
        try:
            global session
            session = get_session(use_proxy=True)
            files = resolve_all_videos(text)
            name, dlink = files[0]
            await message.reply_video(video=dlink, caption=f"🎬 {name}")
            await m.edit_text("⚠️ Used proxy fallback, sent 1 video")
        except Exception as e2:
            await m.edit_text(f"❌ Error: {str(e)}")

app.run()
