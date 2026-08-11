import os
import re
import io
import ast
import math
import uuid
import random
import secrets
import string
import sqlite3
import logging
import shutil
import asyncio
import operator as op
from datetime import datetime, date
from html import escape
from urllib.parse import quote_plus

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
# HAMMASI BIRDA BOT 😈
# Bitta main.py. API kalitlari keyin ENV orqali ulanadi.
#
# BOT_TOKEN=...
# ADMIN_ID=...
# OPENAI_API_KEY=...
# MUSIC_API_KEY=...
# YOUTUBE_API_KEY=...
#
# requirements.txt uchun:
# python-telegram-bot>=21,<23
# aiohttp
# Pillow
# qrcode[pil]
# yt-dlp
# deep-translator
# ============================================================

TOKEN = "8797534923:AAHqV2h0ieTmpac0vTOtHcBrfN7MsqwSrGE"
ADMIN_ID = 8824266579
OPENAI_API_KEY = "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"

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MUSIC_API_KEY = "AIzaSyBCjO4wBBcQkI9Q66bqKmhJWJHz-cMzH9Q"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
DB_FILE = os.getenv("DB_FILE", "hammasi_birda.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("HammasiBirdaBot")

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = ImageOps = None

try:
    import qrcode
except ImportError:
    qrcode = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None

try:
    import pytesseract
except ImportError:
    pytesseract = None


# ============================================================
# DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_FILE)

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        first_name TEXT DEFAULT '',
        coins INTEGER DEFAULT 0,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        last_bonus TEXT DEFAULT '',
        lang TEXT DEFAULT 'uz',
        created_at TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        user_id INTEGER PRIMARY KEY,
        welcome INTEGER DEFAULT 1,
        link_filter INTEGER DEFAULT 0,
        anti_spam INTEGER DEFAULT 0,
        notifications INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS warnings(
        chat_id INTEGER,
        user_id INTEGER,
        count INTEGER DEFAULT 0,
        PRIMARY KEY(chat_id,user_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS group_settings(
        chat_id INTEGER PRIMARY KEY,
        anti_spam INTEGER DEFAULT 0,
        link_filter INTEGER DEFAULT 0,
        welcome INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bot_config(
        key TEXT PRIMARY KEY,
        value TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vip_users(
        user_id INTEGER PRIMARY KEY,
        expires_at TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS blocked_users(
        user_id INTEGER PRIMARY KEY
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stats(
        day TEXT PRIMARY KEY,
        users INTEGER DEFAULT 0,
        messages INTEGER DEFAULT 0
    )
    """)

    con.commit()
    con.close()

def ensure_user(user):
    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO users
        (user_id,username,first_name,created_at)
        VALUES(?,?,?,?)
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        datetime.now().isoformat(timespec="seconds")
    ))
    cur.execute("""
        UPDATE users SET username=?,first_name=? WHERE user_id=?
    """, (user.username or "", user.first_name or "", user.id))
    cur.execute("INSERT OR IGNORE INTO settings(user_id) VALUES(?)", (user.id,))
    cur.execute("""
        INSERT OR IGNORE INTO stats(day,users,messages)
        VALUES(?,0,0)
    """, (date.today().isoformat(),))
    con.commit()
    con.close()

def user_row(user_id):
    con = db()
    row = con.execute("""
        SELECT user_id,username,first_name,coins,xp,level,last_bonus,lang
        FROM users WHERE user_id=?
    """, (user_id,)).fetchone()
    con.close()
    return row

def add_coins(user_id, amount):
    con = db()
    con.execute(
        "UPDATE users SET coins=MAX(0,coins+?) WHERE user_id=?",
        (amount, user_id)
    )
    con.commit()
    con.close()

def add_xp(user_id, amount):
    con = db()
    row = con.execute(
        "SELECT xp FROM users WHERE user_id=?", (user_id,)
    ).fetchone()
    if row:
        xp = row[0] + amount
        level = xp // 100 + 1
        con.execute(
            "UPDATE users SET xp=?,level=? WHERE user_id=?",
            (xp, level, user_id)
        )
    con.commit()
    con.close()

def bump_message_stat():
    con = db()
    con.execute("""
        INSERT OR IGNORE INTO stats(day,users,messages)
        VALUES(?,0,0)
    """, (date.today().isoformat(),))
    con.execute(
        "UPDATE stats SET messages=messages+1 WHERE day=?",
        (date.today().isoformat(),)
    )
    con.commit()
    con.close()


# ============================================================
# BOT CONFIG / ACCESS
# ============================================================

def get_config(key, default=""):
    con=db()
    row=con.execute("SELECT value FROM bot_config WHERE key=?",(key,)).fetchone()
    con.close()
    return row[0] if row else default

def set_config(key, value):
    con=db()
    con.execute("INSERT OR REPLACE INTO bot_config(key,value) VALUES(?,?)",(key,str(value)))
    con.commit(); con.close()

def is_admin_user(user_id):
    admins=os.getenv("ADMIN_IDS", str(ADMIN_ID)).replace(" ","")
    try:
        return int(user_id) in {int(x) for x in admins.split(",") if x}
    except Exception:
        return user_id == ADMIN_ID

def home_reply_kb(user_id=None):
    rows=[
        [KeyboardButton("🤖 AI"),KeyboardButton("📥 Downloader")],
        [KeyboardButton("🎵 Musiqa"),KeyboardButton("🖼 Media")],
        [KeyboardButton("🎮 O'yinlar"),KeyboardButton("💰 Hamyon")],
        [KeyboardButton("🛠 Tools"),KeyboardButton("🔎 Qidiruv")],
        [KeyboardButton("👥 Guruh"),KeyboardButton("🎁 Bonus")],
        [KeyboardButton("👑 VIP"),KeyboardButton("⚙️ Sozlamalar")],
        [KeyboardButton("👤 Profil"),KeyboardButton("ℹ️ Yordam")],
    ]
    if user_id is not None and is_admin_user(user_id):
        rows.append([KeyboardButton("👑 Botni boshqarish")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)

def admin_reply_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Statistika"),KeyboardButton("📢 Reklama")],
        [KeyboardButton("📣 Majburiy obuna"),KeyboardButton("👑 VIP sozlash")],
        [KeyboardButton("👥 User boshqaruv"),KeyboardButton("📝 Start qismi")],
        [KeyboardButton("⚙️ Bot sozlamalari"),KeyboardButton("🔙 Bosh menyu")],
    ], resize_keyboard=True, is_persistent=True)

async def subscription_status(bot, user_id):
    channel_id=get_config("force_channel_id")
    if not channel_id:
        return True
    try:
        m=await bot.get_chat_member(int(channel_id), user_id)
        return m.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception as e:
        log.warning("Force subscription check: %s", e)
        return False

async def require_subscription(update, context):
    user=update.effective_user
    if not user or is_admin_user(user.id):
        return True
    if await subscription_status(context.bot,user.id):
        return True
    link=get_config("force_channel_link")
    if not link:
        username=get_config("force_channel_username")
        if username:
            link="https://t.me/"+username.lstrip("@")
    buttons=[]
    if link:
        buttons.append([InlineKeyboardButton("📣 Kanalga obuna bo'lish",url=link)])
    buttons.append([InlineKeyboardButton("🔄 Tekshirish",callback_data="check_subscription")])
    text="📣 <b>Majburiy obuna</b>\n\nBotdan foydalanish uchun kanalga obuna bo'ling."
    if update.callback_query:
        await update.callback_query.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(buttons))
    elif update.effective_message:
        await update.effective_message.reply_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(buttons))
    return False

# ============================================================
# COMMON UI
# ============================================================

def kb(rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data) for text, data in row]
        for row in rows
    ])

def back():
    return kb([[("🔙 Bosh menyu", "home")]])

def back2(*rows):
    return kb(list(rows) + [[("🔙 Orqaga", "home")]])

def home_kb():
    return kb([
        [("🤖 AI", "menu_ai"), ("📥 Downloader", "menu_dl")],
        [("🎵 Musiqa", "menu_music"), ("🖼 Media", "menu_media")],
        [("🎮 O'yinlar", "menu_games"), ("💰 Hamyon", "menu_wallet")],
        [("🛠 Tools", "menu_tools"), ("🔎 Qidiruv", "menu_search")],
        [("👥 Guruh", "menu_group"), ("🎁 Bonus", "bonus")],
        [("👑 VIP", "menu_vip"), ("⚙️ Sozlamalar", "menu_settings")],
        [("👤 Profil", "profile"), ("ℹ️ Yordam", "help")]
    ])

def ai_kb():
    return kb([
        [("💬 AI Chat", "ai_chat"), ("✍️ Matn yozish", "ai_write")],
        [("📝 Qisqartirish", "ai_summary"), ("🌐 Tarjima", "ai_translate")],
        [("💻 Kod yordamchi", "ai_code"), ("🎯 Prompt generator", "ai_prompt")],
        [("🔙 Bosh menyu", "home")]
    ])

def dl_kb():
    return kb([
        [("▶️ YouTube", "dl_youtube"), ("📸 Instagram", "dl_instagram")],
        [("🎵 TikTok", "dl_tiktok"), ("📘 Facebook", "dl_facebook")],
        [("🔗 Universal URL", "dl_url"), ("ℹ️ Qoidalar", "dl_rules")],
        [("🔙 Bosh menyu", "home")]
    ])

def music_kb():
    return kb([
        [("🔎 Qo'shiq qidirish", "music_search"), ("🎤 Artist", "music_artist")],
        [("🔥 Trend", "music_trend"), ("🎧 Audio", "music_audio")],
        [("📃 Lyrics", "music_lyrics"), ("ℹ️ Yordam", "music_help")],
        [("🔙 Bosh menyu", "home")]
    ])

def media_kb():
    return kb([
        [("🗜 Siqish", "media_compress"), ("📐 O'lcham", "media_resize")],
        [("⚫ Qora-oq", "media_gray"), ("🔄 JPG/PNG", "media_convert")],
        [("🔍 OCR", "media_ocr"), ("📄 PDF", "media_pdf")],
        [("🔙 Bosh menyu", "home")]
    ])

def games_kb():
    return kb([
        [("🎲 Zar", "game_dice"), ("🪙 Coin", "game_coin")],
        [("🎰 Slot", "game_slot"), ("🧠 Son topish", "game_guess")],
        [("🏆 TOP 10", "ranking"), ("🎯 21 o'yini", "game_21")],
        [("🔙 Bosh menyu", "home")]
    ])

def tools_kb():
    return kb([
        [("🧮 Kalkulyator", "tool_calc"), ("🔗 QR", "tool_qr")],
        [("🔐 Parol", "tool_password"), ("🆔 UUID", "tool_uuid")],
        [("🌐 Tarjimon", "tool_translate"), ("📊 Matn stats", "tool_stats")],
        [("🔢 Base converter", "tool_base"), ("🔡 Case converter", "tool_case")],
        [("🕐 Vaqt", "tool_time"), ("📅 Sana", "tool_date")],
        [("🔙 Bosh menyu", "home")]
    ])

def group_kb():
    return kb([
        [("🛡 Anti-spam", "group_antispam"), ("🔗 Link filter", "group_links")],
        [("👋 Welcome", "group_welcome"), ("⚠️ Warn", "group_warn")],
        [("🔇 Mute", "group_mute"), ("🚫 Ban", "group_ban")],
        [("📌 Pin", "group_pin"), ("🧹 Delete", "group_delete")],
        [("ℹ️ Admin yordam", "group_help")],
        [("🔙 Bosh menyu", "home")]
    ])

def settings_kb():
    return kb([
        [("🌐 Til", "setting_lang"), ("🔔 Bildirishnoma", "setting_notify")],
        [("🧹 Sessiyani tozalash", "setting_clear"), ("👤 Profil", "profile")],
        [("🔙 Bosh menyu", "home")]
    ])


# ============================================================
# SAFE CALCULATOR
# ============================================================

OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod, ast.Pow: op.pow,
    ast.USub: op.neg, ast.UAdd: op.pos
}

def calc(expr):
    expr = expr.replace("×","*").replace("÷","/")
    if len(expr) > 100 or not re.fullmatch(r"[0-9+\-*/%().\s]+", expr):
        raise ValueError("Noto'g'ri ifoda.")
    tree = ast.parse(expr, mode="eval")

    def walk(n):
        if isinstance(n, ast.Constant) and isinstance(n.value,(int,float)):
            return n.value
        if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
            return OPS[type(n.op)](walk(n.operand))
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            a,b = walk(n.left),walk(n.right)
            if isinstance(n.op,ast.Pow) and abs(b)>10:
                raise ValueError("Daraja katta.")
            x = OPS[type(n.op)](a,b)
            if not math.isfinite(float(x)) or abs(x)>10**15:
                raise ValueError("Natija juda katta.")
            return x
        raise ValueError("Noto'g'ri ifoda.")

    result = walk(tree.body)
    if isinstance(result,float) and result.is_integer():
        return str(int(result))
    return f"{result:.12g}" if isinstance(result,float) else str(result)


# ============================================================
# API HELPERS
# ============================================================

async def ai(prompt):
    if not OPENAI_API_KEY:
        return (
            "🤖 <b>AI API ulanmagan.</b>\n\n"
            "OPENAI_API_KEY berilganda bu funksiya haqiqiy AI "
            "javobini qaytaradi."
        )
    if aiohttp is None:
        return "❌ aiohttp o'rnatilmagan."

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role":"system",
                "content":"HammasiBirdaBot yordamchisisiz. O'zbek tilida aniq javob bering."
            },
            {"role":"user","content":prompt}
        ],
        "temperature":0.7
    }

    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post(url,headers=headers,json=payload) as r:
                data = await r.json()
                if r.status != 200:
                    log.error(data)
                    return "❌ AI API xatolik qaytardi."
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.exception(e)
        return "❌ AI bilan ulanishda xatolik."

async def translate(target,text):
    if GoogleTranslator is None:
        return "❌ deep-translator o'rnatilmagan."
    return await asyncio.to_thread(
        lambda: GoogleTranslator(source="auto",target=target).translate(text)
    )

async def ytm_search_api(query, search_type="all", limit=8):
    """Search YouTube Music through YTM API. No API key is required."""
    if aiohttp is None:
        return []

    def collect_items(obj, out):
        # YTM API response shape can change, so collect useful music objects
        # recursively instead of depending on one exact JSON layout.
        if isinstance(obj, list):
            for item in obj:
                collect_items(item, out)
            return
        if not isinstance(obj, dict):
            return

        title = obj.get("title") or obj.get("name")
        if isinstance(title, dict):
            title = title.get("text") or title.get("runs", [{}])[0].get("text")
        if title:
            artists = obj.get("artists") or obj.get("artist") or obj.get("author")
            artist = ""
            if isinstance(artists, list):
                names = []
                for a in artists:
                    if isinstance(a, dict):
                        n = a.get("name") or a.get("title")
                        if n:
                            names.append(str(n))
                    elif a:
                        names.append(str(a))
                artist = ", ".join(names)
            elif isinstance(artists, dict):
                artist = str(artists.get("name") or artists.get("title") or "")
            elif artists:
                artist = str(artists)

            url = obj.get("url") or obj.get("link") or obj.get("videoUrl")
            video_id = obj.get("videoId") or obj.get("video_id")
            if not url and video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"

            kind = str(obj.get("type") or obj.get("resultType") or "").lower()
            if kind or artist or url:
                out.append({
                    "title": str(title),
                    "artist": artist,
                    "url": url or "",
                    "type": kind or "music",
                })

        for value in obj.values():
            if isinstance(value, (dict, list)):
                collect_items(value, out)

    try:
        params = {"q": query, "type": search_type}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(
                "https://ytm.vrma.dev/search",
                params=params,
                headers={"User-Agent": "HammasiBirdaBot/1.0"}
            ) as response:
                if response.status != 200:
                    log.warning("YTM API status: %s", response.status)
                    return []
                data = await response.json(content_type=None)

        raw = []
        collect_items(data, raw)

        results = []
        seen = set()
        for item in raw:
            key = (item["title"].strip().lower(), item["artist"].strip().lower(), item["url"])
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        log.warning("YTM search: %s", e)
        return []


async def music_search_api(query, limit=5):
    """YTM first, then Deezer, then YouTube Data API fallback."""
    ytm = await ytm_search_api(query, "all", limit)
    if ytm:
        return ytm

    if aiohttp is None:
        return []
    results = []
    try:
        url = f"https://api.deezer.com/search?q={quote_plus(query)}&limit={limit}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.get(url) as r:
                if r.status == 200:
                    data = await r.json()
                    for x in data.get("data", [])[:limit]:
                        results.append({
                            "title": x.get("title", "Noma'lum"),
                            "artist": (x.get("artist") or {}).get("name", ""),
                            "url": x.get("link", ""),
                        })
    except Exception as e:
        log.warning("Deezer search: %s", e)

    if results or not YOUTUBE_API_KEY:
        return results

    try:
        params = {"part":"snippet","q":query,"type":"video","maxResults":limit,"key":YOUTUBE_API_KEY}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.get("https://www.googleapis.com/youtube/v3/search", params=params) as r:
                data = await r.json()
                for x in data.get("items", []):
                    vid=x.get("id",{}).get("videoId")
                    sn=x.get("snippet",{})
                    if vid:
                        results.append({
                            "title":sn.get("title","Noma'lum"),
                            "artist":sn.get("channelTitle",""),
                            "url":f"https://www.youtube.com/watch?v={vid}"
                        })
    except Exception as e:
        log.warning("YouTube search: %s", e)
    return results

async def music_lyrics_api(query):
    """LRCLIB lyrics search; no key required."""
    if aiohttp is None:
        return None
    try:
        url=f"https://lrclib.net/api/search?q={quote_plus(query)}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.get(url, headers={"User-Agent":"HammasiBirdaBot/1.0"}) as r:
                if r.status != 200:
                    return None
                data=await r.json()
                if data:
                    x=data[0]
                    lyrics=x.get("plainLyrics") or x.get("syncedLyrics")
                    if lyrics:
                        return x.get("trackName",query), x.get("artistName",""), lyrics
    except Exception as e:
        log.warning("Lyrics: %s", e)
    return None


async def download_media(url):
    if yt_dlp is None:
        raise RuntimeError("yt-dlp o'rnatilmagan.")
    os.makedirs("downloads",exist_ok=True)
    template = os.path.join("downloads","%(title).70s-%(id)s.%(ext)s")

    opts = {
        "outtmpl":template,
        "noplaylist":True,
        "quiet":True,
        "no_warnings":True,
        "restrictfilenames":True,
        "format":"best[ext=mp4]/best",
        "max_filesize":49*1024*1024
    }

    def worker():
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url,download=True)
            return y.prepare_filename(info), info.get("title","Media")

    return await asyncio.to_thread(worker)


async def download_audio(url):
    """YouTube URLdan audio yuklaydi; ffmpeg bo'lsa MP3ga aylantiradi."""
    if yt_dlp is None:
        raise RuntimeError("yt-dlp o'rnatilmagan.")
    os.makedirs("downloads", exist_ok=True)

    template = os.path.join("downloads", "%(title).70s-%(id)s.%(ext)s")
    has_ffmpeg = shutil.which("ffmpeg") is not None

    opts = {
        "outtmpl": template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "max_filesize": 49 * 1024 * 1024,
    }

    if has_ffmpeg:
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    def worker():
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=True)
            filename = y.prepare_filename(info)
            title = info.get("title", "Musiqa")
            artist = info.get("artist") or info.get("uploader") or ""

            if has_ffmpeg:
                filename = os.path.splitext(filename)[0] + ".mp3"

            return filename, title, artist

    return await asyncio.to_thread(worker)


# ============================================================
# START / HELP
# ============================================================

async def start(update, context):
    ensure_user(update.effective_user)
    context.user_data.clear()
    if not await require_subscription(update,context):
        return
    start_text=get_config("start_text") or (
        "😈 <b>HAMMASI BIRDA BOT</b>\n\n"
        f"Salom, <b>{update.effective_user.first_name}</b>!\n"
        "👇 Kerakli xizmatni tanlang:"
    )
    # Admin panelda yozilgan o'zgaruvchilarni user ma'lumotlari bilan almashtirish.
    u = update.effective_user
    name = escape(u.first_name or "Foydalanuvchi")
    username = escape(f"@{u.username}") if u.username else ""
    mention = f'<a href="tg://user?id={u.id}">{name}</a>'
    start_text = (
        start_text
        .replace("{name}", name)
        .replace("{username}", username)
        .replace("{id}", str(u.id))
        .replace("{mention}", mention)
    )
    await update.message.reply_text(
        start_text, parse_mode="HTML",
        reply_markup=home_reply_kb(update.effective_user.id)
    )

async def help_cmd(update, context):
    await update.message.reply_text(
        "ℹ️ <b>YORDAM</b>\n\n"
        "Barcha xizmatlar menyu ichidagi tugmalar orqali ishlaydi.\n\n"
        "Inline misollar:\n"
        "<code>@BotUsername 25+35*2</code>\n"
        "<code>@BotUsername musiqa Sevara</code>\n\n"
        "API talab qiladigan bo'limlar kalit berilgach to'liq ulanadi.",
        parse_mode="HTML",
        reply_markup=home_kb()
    )


# ============================================================
# CALLBACK ROUTER
# ============================================================

async def cb(update, context):
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    ensure_user(user)
    d = q.data
    if d == "check_subscription":
        if await subscription_status(context.bot,user.id):
            await q.edit_message_text("✅ Obuna tasdiqlandi! /start ni bosing.")
        else:
            await require_subscription(update,context)
        return
    if d != "home" and not await require_subscription(update,context):
        return

    if d == "home":
        context.user_data.clear()
        await q.edit_message_text(
            "😈 <b>HAMMASI BIRDA BOT</b>\n\n👇 Bo'limni tanlang:",
            parse_mode="HTML",reply_markup=home_kb()
        )
        return

    if d == "help":
        await q.edit_message_text(
            "ℹ️ <b>YORDAM</b>\n\n"
            "Tugmani bosasiz → bot kerakli matn/rasm/URLni so'raydi → "
            "funksiya natijani qaytaradi.",
            parse_mode="HTML",reply_markup=home_kb()
        )
        return

    # ---------------- AI ----------------
    if d == "menu_ai":
        await q.edit_message_text(
            "🤖 <b>AI MARKAZI</b>\n\nFunksiyani tanlang:",
            parse_mode="HTML",reply_markup=ai_kb()
        ); return

    ai_modes = {
        "ai_chat":("ai","💬 Savolingizni yuboring."),
        "ai_write":("ai_write","✍️ Yoziladigan matn mavzusini yuboring."),
        "ai_summary":("ai_summary","📝 Qisqartiriladigan matnni yuboring."),
        "ai_translate":("ai_translate","🌐 Tarjima qilinadigan matnni yuboring."),
        "ai_code":("ai_code","💻 Kod topshirig'ini yuboring."),
        "ai_prompt":("ai_prompt","🎯 Qaysi vazifa uchun prompt kerakligini yozing.")
    }
    if d in ai_modes:
        context.user_data["mode"] = ai_modes[d][0]
        await q.edit_message_text(
            ai_modes[d][1],reply_markup=back()
        ); return

    # ---------------- DOWNLOADER ----------------
    if d == "menu_dl":
        await q.edit_message_text(
            "📥 <b>DOWNLOADER</b>\n\nPlatformani tanlang yoki Universal URLni bosing:",
            parse_mode="HTML",reply_markup=dl_kb()
        ); return

    if d in ("dl_youtube","dl_instagram","dl_tiktok","dl_facebook","dl_url"):
        context.user_data["mode"]="download"
        await q.edit_message_text(
            "🔗 <b>URL yuboring</b>\n\n"
            "Bot URLni yt-dlp orqali tekshiradi.\n"
            "Telegram fayl hajmi va platforma cheklovlari amal qiladi.",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d == "dl_rules":
        await q.edit_message_text(
            "ℹ️ <b>DOWNLOADER QOIDALARI</b>\n\n"
            "Faqat yuklab olishga haqqingiz bo'lgan kontentdan foydalaning. "
            "Platforma va mualliflik huquqi qoidalariga rioya qiling.",
            parse_mode="HTML",reply_markup=back()
        ); return

    # ---------------- MUSIC ----------------
    if d == "menu_music":
        await q.edit_message_text(
            "🎵 <b>MUSIQA MARKAZI</b>\n\nFunksiyani tanlang:",
            parse_mode="HTML",reply_markup=music_kb()
        ); return

    if d in ("music_search","music_artist","music_audio","music_lyrics"):
        mode_map = {
            "music_search": "music_search",
            "music_artist": "music_artist",
            "music_audio": "music_audio",
            "music_lyrics": "music_lyrics",
        }
        context.user_data["mode"] = mode_map[d]
        prompts = {
            "music_search":"🔎 Qo'shiq nomi yoki artist nomini yuboring.",
            "music_artist":"🎤 Artist nomini yuboring.",
            "music_audio":"🎧 Qo'shiq nomini yuboring yoki audio URL yuboring.",
            "music_lyrics":"📃 Qo'shiq nomini yuboring."
        }
        await q.edit_message_text(prompts[d],reply_markup=back()); return

    if d == "music_trend":
        await q.edit_message_text(
            "🔥 <b>TREND</b>\n\n"
            "Trend ro'yxatini chiqarish uchun musiqa provider API kerak. "
            "API berilganda bu tugma real natijalarni chiqaradi.",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d == "music_help":
        await q.edit_message_text(
            "🎵 <b>MUSIQA YORDAM</b>\n\n"
            "Qidiruv → qo'shiq/artist yozasiz.\n"
            "Audio → provider orqali audio olinadi.\n"
            "Lyrics → lyrics provider orqali matn olinadi.\n"
            "Trend → provider trend ro'yxati.",
            parse_mode="HTML",reply_markup=back()
        ); return

    # ---------------- MEDIA ----------------
    if d == "menu_media":
        await q.edit_message_text(
            "🖼 <b>MEDIA MARKAZI</b>\n\n"
            "Operatsiyani tanlang, keyin rasm yuboring:",
            parse_mode="HTML",reply_markup=media_kb()
        ); return

    if d.startswith("media_"):
        context.user_data["media"] = d.replace("media_","")
        await q.edit_message_text(
            "🖼 Endi rasm yuboring.",
            reply_markup=back()
        ); return

    # ---------------- GAMES ----------------
    if d == "menu_games":
        await q.edit_message_text(
            "🎮 <b>O'YINLAR</b>\n\nO'yinni tanlang:",
            parse_mode="HTML",reply_markup=games_kb()
        ); return

    if d == "game_dice":
        await q.message.reply_dice(emoji="🎲")
        add_coins(user.id,10); add_xp(user.id,3)
        await q.edit_message_text(
            "🎲 Zar tashlandi!\n🪙 +10 Coin\n⭐ +3 XP",
            reply_markup=back()
        ); return

    if d == "game_coin":
        result=random.choice(["🟢 GERB","🔵 RAQAM"])
        add_coins(user.id,15); add_xp(user.id,2)
        await q.edit_message_text(
            f"🪙 <b>COIN FLIP</b>\n\nNatija: {result}\n🪙 +15 Coin",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d == "game_slot":
        symbols=["🍒","🍋","🔔","⭐","7️⃣"]
        a=[random.choice(symbols) for _ in range(3)]
        if a[0]==a[1]==a[2]:
            reward=300; msg="🎉 JACKPOT!"
        elif len(set(a))==2:
            reward=50; msg="✨ Ikki bir xil!"
        else:
            reward=5; msg="🙂 Omadni yana sinang."
        add_coins(user.id,reward); add_xp(user.id,5)
        await q.edit_message_text(
            f"🎰 <b>SLOT</b>\n\n{' '.join(a)}\n\n{msg}\n🪙 +{reward}",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d == "game_guess":
        context.user_data["guess"]=random.randint(1,10)
        await q.edit_message_text(
            "🧠 <b>SON TOPISH</b>\n\n1 dan 10 gacha son yuboring.",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d == "game_21":
        context.user_data["game21"]=True
        context.user_data["game21_user"]=random.randint(14,21)
        context.user_data["game21_bot"]=random.randint(15,21)
        await q.edit_message_text(
            "🎯 <b>21 O'YINI</b>\n\n"
            "Sizga yashirin son berildi. 1–7 oralig'ida son yuboring "
            "va natijangiz oshadi. 21 ga yaqinlashish kerak.",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d == "ranking":
        con=db()
        rows=con.execute("""
            SELECT first_name,coins,level FROM users
            ORDER BY coins DESC,xp DESC LIMIT 10
        """).fetchall()
        con.close()
        text="🏆 <b>TOP 10</b>\n\n"
        for i,r in enumerate(rows,1):
            text+=f"{i}. {r[0] or 'User'} — {r[1]} 🪙 | Lv.{r[2]}\n"
        await q.edit_message_text(text,parse_mode="HTML",reply_markup=back()); return

    # ---------------- WALLET / BONUS ----------------
    if d == "menu_wallet":
        r=user_row(user.id)
        await q.edit_message_text(
            f"💰 <b>HAMYON</b>\n\n"
            f"🪙 Coin: <b>{r[3]}</b>\n"
            f"⭐ XP: <b>{r[4]}</b>\n"
            f"🏆 Level: <b>{r[5]}</b>",
            parse_mode="HTML",
            reply_markup=kb([
                [("🎁 Kunlik bonus","bonus"),("🏆 TOP","ranking")],
                [("👤 Profil","profile"),("🔙 Bosh menyu","home")]
            ])
        ); return

    if d == "bonus":
        r=user_row(user.id); today=date.today().isoformat()
        if r[6]==today:
            await q.edit_message_text(
                "🎁 Bugungi bonusni allaqachon olgansiz.",
                reply_markup=back()
            ); return
        con=db()
        con.execute("""
            UPDATE users SET coins=coins+100,xp=xp+10,last_bonus=?
            WHERE user_id=?
        """,(today,user.id))
        con.commit(); con.close()
        await q.edit_message_text(
            "🎁 <b>BONUS OLINDI!</b>\n\n🪙 +100 Coin\n⭐ +10 XP",
            parse_mode="HTML",reply_markup=back()
        ); return

    # ---------------- TOOLS ----------------
    if d == "menu_tools":
        await q.edit_message_text(
            "🛠 <b>TOOLS MARKAZI</b>\n\nKerakli vositani tanlang:",
            parse_mode="HTML",reply_markup=tools_kb()
        ); return

    tool_modes={
        "tool_calc":("calc","🧮 Ifodani yuboring. Masalan: <code>25*4+10</code>"),
        "tool_qr":("qr","🔗 QR uchun matn yoki URL yuboring."),
        "tool_password":("password","🔐 Parol uzunligini yuboring: 16"),
        "tool_translate":("translate","🌐 Format: <code>en: Salom dunyo</code>"),
        "tool_stats":("stats","📊 Statistikasi kerak bo'lgan matnni yuboring."),
        "tool_base":("base","🔢 Format: <code>255 16</code>"),
        "tool_case":("case","🔡 Matn yuboring."),
    }
    if d in tool_modes:
        context.user_data["mode"]=tool_modes[d][0]
        await q.edit_message_text(
            tool_modes[d][1],parse_mode="HTML",reply_markup=back()
        ); return

    if d=="tool_uuid":
        await q.edit_message_text(
            f"🆔 <code>{uuid.uuid4()}</code>",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d=="tool_time":
        await q.edit_message_text(
            f"🕐 Server vaqti:\n<code>{datetime.now():%Y-%m-%d %H:%M:%S}</code>",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d=="tool_date":
        now=datetime.now()
        await q.edit_message_text(
            f"📅 Bugun: <b>{now:%d.%m.%Y}</b>\n"
            f"Hafta kuni: <b>{now:%A}</b>",
            parse_mode="HTML",reply_markup=back()
        ); return

    # ---------------- SEARCH ----------------
    if d=="menu_search":
        await q.edit_message_text(
            "🔎 <b>QIDIRUV</b>\n\n"
            "Inline rejimdan foydalaning:\n"
            "<code>@BotUsername 25+35</code>\n"
            "<code>@BotUsername musiqa Artist</code>\n\n"
            "Bot username'ini Telegramda tanlash orqali inline qidiruv ochiladi.",
            parse_mode="HTML",reply_markup=back()
        ); return

    # ---------------- GROUP ----------------
    if d=="menu_group":
        await q.edit_message_text(
            "👥 <b>GURUH BOSHQARUVI</b>\n\n"
            "Bot guruhda admin bo'lsa moderatsiya funksiyalari ishlaydi.",
            parse_mode="HTML",reply_markup=group_kb()
        ); return

    if d.startswith("group_"):
        await group_action(q,context,d); return

    # ---------------- VIP ----------------
    if d=="menu_vip":
        enabled=get_config("vip_enabled","1")=="1"
        price=get_config("vip_price","1000")
        days=get_config("vip_days","30")
        await q.edit_message_text(
            "👑 <b>VIP</b>\n\n"
            + (f"💰 Narx: <b>{price} 🪙</b>\n📅 Muddat: <b>{days} kun</b>\n\n" if enabled else "❌ VIP hozircha o'chirilgan.\n\n")
            + "VIP imkoniyatlari:\n⚡ AI limit\n📥 kengaytirilgan downloader\n🎵 premium music\n🛠 premium tools",
            parse_mode="HTML",reply_markup=back()
        ); return

    # ---------------- SETTINGS ----------------
    if d=="menu_settings":
        await q.edit_message_text(
            "⚙️ <b>SOZLAMALAR</b>\n\nTanlang:",
            parse_mode="HTML",reply_markup=settings_kb()
        ); return

    if d=="setting_lang":
        await q.edit_message_text(
            "🌐 <b>TIL</b>\n\n🇺🇿 O'zbekcha — faol.\n"
            "🇷🇺 Ruscha va 🇬🇧 English interfeyslarini keyin qo'shish mumkin.",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d=="setting_notify":
        await q.edit_message_text(
            "🔔 <b>BILDIRISHNOMALAR</b>\n\n"
            "Bot xabar yuborishi uchun Telegram notification sozlamalaridan foydalaning.",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d=="setting_clear":
        context.user_data.clear()
        await q.edit_message_text(
            "🧹 Aktiv sessiya tozalandi.",reply_markup=back()
        ); return

    # ---------------- PROFILE ----------------
    if d=="profile":
        r=user_row(user.id)
        await q.edit_message_text(
            f"👤 <b>PROFIL</b>\n\n"
            f"🆔 ID: <code>{r[0]}</code>\n"
            f"👤 Ism: {r[2]}\n"
            f"🔗 Username: @{r[1] or 'yo‘q'}\n"
            f"🪙 Coin: {r[3]}\n⭐ XP: {r[4]}\n🏆 Level: {r[5]}",
            parse_mode="HTML",reply_markup=back()
        ); return

    await q.edit_message_text(
        "🚧 Funksiya topilmadi.",reply_markup=home_kb()
    )


# ============================================================
# GROUP MODERATION
# ============================================================

async def is_admin(bot,chat_id,user_id):
    try:
        m=await bot.get_chat_member(chat_id,user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.OWNER)
    except Exception:
        return False

async def group_action(q,context,d):
    chat_id=q.message.chat.id
    user_id=q.from_user.id

    descriptions={
        "group_antispam":"🛡 <b>ANTI-SPAM</b>\n\nSpamni tekshiruvchi rejim. Bot admin bo'lishi kerak.",
        "group_links":"🔗 <b>LINK FILTER</b>\n\nLinklar aniqlanadi va sozlama yoqilgan bo'lsa o'chiriladi.",
        "group_welcome":"👋 <b>WELCOME</b>\n\nYangi a'zolarga salomlashish xabari.",
        "group_warn":"⚠️ <b>WARN</b>\n\nReply qilingan userga ogohlantirish berish.",
        "group_mute":"🔇 <b>MUTE</b>\n\nReply qilingan userni vaqtincha cheklash.",
        "group_ban":"🚫 <b>BAN</b>\n\nReply qilingan userni guruhdan chiqarish.",
        "group_pin":"📌 <b>PIN</b>\n\nReply qilingan xabarni pin qilish.",
        "group_delete":"🧹 <b>DELETE</b>\n\nReply qilingan xabarni o'chirish.",
        "group_help":"ℹ️ <b>ADMIN YORDAM</b>\n\nBu funksiyalar uchun botga tegishli admin huquqlarini bering."
    }

    # Toggleable settings
    if d in ("group_antispam","group_links","group_welcome"):
        field={
            "group_antispam":"anti_spam",
            "group_links":"link_filter",
            "group_welcome":"welcome"
        }[d]
        con=db()
        con.execute("INSERT OR IGNORE INTO group_settings(chat_id) VALUES(?)",(chat_id,))
        con.execute(
            f"UPDATE group_settings SET {field}=1-{field} WHERE chat_id=?",
            (chat_id,)
        )
        value=con.execute(
            f"SELECT {field} FROM group_settings WHERE chat_id=?",(chat_id,)
        ).fetchone()[0]
        con.commit(); con.close()
        state="YOQILDI ✅" if value else "O'CHIRILDI ❌"
        await q.edit_message_text(
            descriptions[d]+f"\n\nHolat: <b>{state}</b>",
            parse_mode="HTML",reply_markup=group_kb()
        )
        return

    await q.edit_message_text(
        descriptions.get(d,"🚧 Funksiya yo'q."),
        parse_mode="HTML",reply_markup=group_kb()
    )


async def group_guard(update,context):
    msg=update.effective_message
    chat=update.effective_chat
    user=update.effective_user

    if not msg or not chat or chat.type not in ("group","supergroup"):
        return
    if not user:
        return

    text=msg.text or msg.caption or ""
    con=db()
    row=con.execute("""
        SELECT anti_spam,link_filter FROM group_settings WHERE chat_id=?
    """,(chat.id,)).fetchone()
    con.close()

    if not row:
        return

    if await is_admin(context.bot,chat.id,user.id):
        return

    anti_spam,link_filter=row

    if link_filter and re.search(r"https?://|t\.me/|www\.",text,re.I):
        try:
            await msg.delete()
        except Exception:
            pass
        return

    if anti_spam and len(text)>3000:
        try:
            await msg.delete()
        except Exception:
            pass


async def text_menu_dispatch(update,context,d):
    # Reply-keyboard main menu -> existing inline callback router logic.
    class Q: pass
    # Use a lightweight synthetic callback object by duplicating only the main-menu screens.
    screens={
        "menu_ai":("🤖 <b>AI MARKAZI</b>\n\nFunksiyani tanlang:",ai_kb()),
        "menu_dl":("📥 <b>DOWNLOADER</b>\n\nPlatformani tanlang yoki Universal URLni bosing:",dl_kb()),
        "menu_music":("🎵 <b>MUSIQA MARKAZI</b>\n\nFunksiyani tanlang:",music_kb()),
        "menu_media":("🖼 <b>MEDIA MARKAZI</b>\n\nOperatsiyani tanlang, keyin rasm yuboring:",media_kb()),
        "menu_games":("🎮 <b>O'YINLAR</b>\n\nO'yinni tanlang:",games_kb()),
        "menu_tools":("🛠 <b>TOOLS MARKAZI</b>\n\nKerakli vositani tanlang:",tools_kb()),
        "menu_search":("🔎 <b>QIDIRUV</b>\n\nInline rejimdan foydalaning:\n<code>@BotUsername 25+35</code>",back()),
        "menu_group":("👥 <b>GURUH BOSHQARUVI</b>\n\nBot guruhda admin bo'lsa moderatsiya funksiyalari ishlaydi.",group_kb()),
        "menu_settings":("⚙️ <b>SOZLAMALAR</b>\n\nTanlang:",settings_kb()),
    }
    if d in screens:
        text,markup=screens[d]
        await update.message.reply_text(text,parse_mode="HTML",reply_markup=markup)
        return
    if d=="profile":
        r=user_row(update.effective_user.id)
        await update.message.reply_text(f"👤 <b>PROFIL</b>\n\n🆔 ID: <code>{r[0]}</code>\n👤 Ism: {r[2]}\n🔗 Username: @{r[1] or 'yo‘q'}\n🪙 Coin: {r[3]}\n⭐ XP: {r[4]}\n🏆 Level: {r[5]}",parse_mode="HTML",reply_markup=back())
        return
    if d=="help":
        await update.message.reply_text("ℹ️ <b>YORDAM</b>\n\nTugmani bosasiz → bot kerakli ma'lumotni so'raydi → natijani qaytaradi.",parse_mode="HTML",reply_markup=home_kb())
        return
    if d=="bonus":
        r=user_row(update.effective_user.id); today=date.today().isoformat()
        if r[6]==today:
            await update.message.reply_text("🎁 Bugungi bonusni allaqachon olgansiz.",reply_markup=home_reply_kb(update.effective_user.id)); return
        con=db(); con.execute("UPDATE users SET coins=coins+100,xp=xp+10,last_bonus=? WHERE user_id=?",(today,update.effective_user.id)); con.commit(); con.close()
        await update.message.reply_text("🎁 <b>BONUS OLINDI!</b>\n\n🪙 +100 Coin\n⭐ +10 XP",parse_mode="HTML",reply_markup=home_reply_kb(update.effective_user.id))
        return
    if d=="menu_wallet":
        r=user_row(update.effective_user.id)
        await update.message.reply_text(f"💰 <b>HAMYON</b>\n\n🪙 Coin: <b>{r[3]}</b>\n⭐ XP: <b>{r[4]}</b>\n🏆 Level: <b>{r[5]}</b>",parse_mode="HTML",reply_markup=back())

# ============================================================
# TEXT ROUTER
# ============================================================

async def text_router(update,context):
    if not update.message:
        return
    user=update.effective_user
    ensure_user(user)
    if not await require_subscription(update,context):
        return
    bump_message_stat()
    text=(update.message.text or "").strip()
    mode=context.user_data.get("mode")

    # Resize reply keyboard main menu
    main_routes={
        "🤖 AI":"menu_ai","📥 Downloader":"menu_dl","🎵 Musiqa":"menu_music",
        "🖼 Media":"menu_media","🎮 O'yinlar":"menu_games","💰 Hamyon":"menu_wallet",
        "🛠 Tools":"menu_tools","🔎 Qidiruv":"menu_search","👥 Guruh":"menu_group",
        "🎁 Bonus":"bonus","👑 VIP":"menu_vip","⚙️ Sozlamalar":"menu_settings",
        "👤 Profil":"profile","ℹ️ Yordam":"help"
    }
    if text == "👑 Botni boshqarish":
        if is_admin_user(user.id):
            context.user_data["admin_panel"]=True
            context.user_data.pop("mode",None)
            await update.message.reply_text("👑 <b>ADMIN PANEL</b>\n\nKerakli bo'limni tanlang:",parse_mode="HTML",reply_markup=admin_reply_kb())
        return
    if text == "🔙 Bosh menyu" and context.user_data.get("admin_panel"):
        context.user_data.clear()
        await update.message.reply_text("🏠 <b>BOSH MENYU</b>\n\nBo'limni tanlang:",parse_mode="HTML",reply_markup=home_reply_kb(user.id))
        return
    if context.user_data.get("admin_panel"):
        if not is_admin_user(user.id):
            context.user_data.clear(); return
        await admin_text_router(update,context,text)
        return
    if text in main_routes:
        d=main_routes[text]
        if d=="bonus":
            # Let the existing callback logic handle bonus consistently.
            await update.message.reply_text("🎁 Bonusni olish uchun tugmani qayta bosing yoki /start orqali menyuni oching.")
            return
        fake_data=d
        # Directly reproduce the callback by routing through a tiny helper.
        await text_menu_dispatch(update,context,fake_data)
        return

    # Guess
    if "guess" in context.user_data and text.isdigit():
        target=context.user_data["guess"]
        n=int(text)
        if n==target:
            add_coins(user.id,100); add_xp(user.id,15)
            context.user_data.pop("guess",None)
            await update.message.reply_text("🎉 TOPDINGIZ!\n🪙 +100 Coin\n⭐ +15 XP")
        elif n<target:
            await update.message.reply_text("⬆️ Kattaroq son.")
        else:
            await update.message.reply_text("⬇️ Kichikroq son.")
        return

    # 21 game
    if context.user_data.get("game21"):
        if text.isdigit() and 1<=int(text)<=7:
            add=int(text)
            total=context.user_data["game21_user"]+add
            if total>21:
                result="💥 Siz 21 dan oshib ketdingiz."
            elif total==21:
                add_coins(user.id,200); add_xp(user.id,20)
                result="🎉 21! Siz yutdingiz. 🪙 +200"
            else:
                bot=context.user_data["game21_bot"]
                if bot>total:
                    result=f"🤖 Bot: {bot}\nSiz: {total}\n😔 Bot yutdi."
                elif bot<total:
                    add_coins(user.id,80); add_xp(user.id,10)
                    result=f"🤖 Bot: {bot}\nSiz: {total}\n🎉 Siz yutdingiz! 🪙 +80"
                else:
                    result=f"🤝 Durrang: {total}"
            context.user_data.pop("game21",None)
            await update.message.reply_text(result)
        return

    if mode=="calc":
        try:
            await update.message.reply_text(f"🧮 {text} = {calc(text)}")
            add_xp(user.id,2)
        except Exception:
            await update.message.reply_text("❌ Matematik ifoda noto'g'ri.")
        return

    if mode=="qr":
        if qrcode is None:
            await update.message.reply_text("❌ qrcode kutubxonasi o'rnatilmagan.")
            return
        image=qrcode.make(text)
        out=io.BytesIO(); image.save(out,format="PNG"); out.seek(0)
        await update.message.reply_photo(out,caption="🔗 QR tayyor.")
        add_xp(user.id,2); return

    if mode=="password":
        try: length=max(8,min(int(text),64))
        except: await update.message.reply_text("❌ Masalan: 20"); return
        alphabet=string.ascii_letters+string.digits+"!@#$%^&*_-+="
        p="".join(secrets.choice(alphabet) for _ in range(length))
        await update.message.reply_text(
            f"🔐 <b>Kuchli parol:</b>\n<code>{p}</code>",
            parse_mode="HTML"
        ); add_xp(user.id,2); return

    if mode=="translate":
        if ":" not in text:
            await update.message.reply_text("Format: en: Salom dunyo"); return
        target,src=text.split(":",1)
        try:
            result=await translate(target.strip().lower(),src.strip())
            await update.message.reply_text(f"🌐 {result}")
        except Exception:
            await update.message.reply_text("❌ Tarjima ishlamadi.")
        return

    if mode=="stats":
        await update.message.reply_text(
            f"📊 <b>MATN STATISTIKASI</b>\n\n"
            f"🔤 Belgilar: {len(text)}\n"
            f"📝 So'zlar: {len(text.split())}\n"
            f"📄 Satrlar: {len(text.splitlines())}\n"
            f"🔢 Raqamlar: {sum(c.isdigit() for c in text)}\n"
            f"🔠 Harflar: {sum(c.isalpha() for c in text)}",
            parse_mode="HTML"
        ); add_xp(user.id,2); return

    if mode=="base":
        p=text.split()
        if len(p)!=2:
            await update.message.reply_text("Format: 255 16"); return
        try:
            n=int(p[0]); base=int(p[1])
            if not 2<=base<=36: raise ValueError
            digits=string.digits+string.ascii_lowercase
            if n==0: result="0"
            else:
                sign="-" if n<0 else ""; n=abs(n); result=""
                while n:
                    result=digits[n%base]+result; n//=base
                result=sign+result
            await update.message.reply_text(f"🔢 Natija: {result}")
        except:
            await update.message.reply_text("❌ Format noto'g'ri.")
        return

    if mode=="case":
        await update.message.reply_text(
            "🔡 <b>CASE</b>\n\n"
            f"UPPER:\n<code>{text.upper()}</code>\n\n"
            f"lower:\n<code>{text.lower()}</code>\n\n"
            f"Title:\n<code>{text.title()}</code>",
            parse_mode="HTML"
        ); return

    if mode=="ai" or mode=="ai_write" or mode=="ai_summary" or mode=="ai_code" or mode=="ai_prompt":
        prompts={
            "ai":text,
            "ai_write":"Shu so'rov asosida chiroyli, tayyor matn yozing:\n"+text,
            "ai_summary":"Quyidagi matnni qisqa va mazmunli qilib bering:\n"+text,
            "ai_code":"Dasturchi yordamchi sifatida yeching. Kerak bo'lsa kod yozing:\n"+text,
            "ai_prompt":"Quyidagi vazifa uchun kuchli, aniq AI prompt tuzing:\n"+text
        }
        await update.message.chat.send_action("typing")
        result=await ai(prompts[mode])
        await update.message.reply_text(result[:4000])
        add_xp(user.id,3); return

    if mode=="ai_translate":
        result=await ai("Quyidagi matnni ma'nosini saqlagan holda tarjima qiling:\n"+text)
        await update.message.reply_text(result[:4000]); return

    if mode=="download":
        if not re.match(r"^https?://",text,re.I):
            await update.message.reply_text("🔗 To'g'ri URL yuboring."); return
        status=await update.message.reply_text("📥 Yuklanmoqda... ⏳")
        try:
            filename,title=await download_media(text)
            if not os.path.exists(filename): raise RuntimeError("Fayl topilmadi.")
            if os.path.getsize(filename)>49*1024*1024:
                os.remove(filename); raise RuntimeError("Fayl juda katta.")
            with open(filename,"rb") as f:
                await update.message.reply_document(f,caption=f"📥 {title}")
            os.remove(filename)
            await status.delete()
            add_xp(user.id,5)
        except Exception as e:
            log.exception(e)
            await status.edit_text(f"❌ Yuklab bo'lmadi:\n{str(e)[:500]}")
        return

    if mode in ("music_search", "music_artist"):
        search_type = "all" if mode == "music_search" else "artists"
        results = await ytm_search_api(text, search_type, 8)
        if not results:
            # Artist-only search may not be supported by every YTM API version.
            # Fall back to the general search so the button still works.
            results = await music_search_api(text, 8)
        if not results:
            await update.message.reply_text(
                "❌ Musiqa topilmadi yoki YTM API vaqtincha javob bermayapti.",
                reply_markup=music_kb()
            )
            return

        lines = ["🎵 <b>MUSIQA NATIJALARI</b>", ""]
        for i, item in enumerate(results, 1):
            title = item.get("title", "Noma'lum")
            artist = item.get("artist", "")
            url = item.get("url", "")
            line = f"{i}. <b>{title}</b>"
            if artist:
                line += f" — {artist}"
            if url:
                line += f"\n   🔗 {url}"
            lines.append(line)
        await update.message.reply_text(
            "\n".join(lines)[:4000],
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        add_xp(user.id, 3)
        return

    if mode == "music_lyrics":
        result = await music_lyrics_api(text)
        if not result:
            await update.message.reply_text("❌ Lyrics topilmadi.", reply_markup=music_kb())
            return
        title, artist, lyrics = result
        await update.message.reply_text(
            f"📃 <b>{title}</b>" + (f" — {artist}" if artist else "") +
            f"\n\n{lyrics[:3900]}",
            parse_mode="HTML"
        )
        add_xp(user.id, 3)
        return

    if mode == "music_audio":
        # Qo'shiq nomi ham, YouTube URL ham qabul qilinadi.
        direct_url = text if re.match(
            r"^https?://(?:www\\.)?(?:youtube\\.com|youtu\\.be)/",
            text,
            re.I
        ) else None

        item = None
        url = direct_url

        if not url:
            results = await ytm_search_api(text, "songs", 1)
            if not results:
                results = await music_search_api(text, 1)
            if not results:
                await update.message.reply_text(
                    "❌ Qo'shiq topilmadi.",
                    reply_markup=music_kb()
                )
                return
            item = results[0]
            url = item.get("url")

        if not url:
            await update.message.reply_text(
                "❌ YouTube havolasi topilmadi.",
                reply_markup=music_kb()
            )
            return

        status = await update.message.reply_text(
            "🎵 <b>Audio tayyorlanmoqda...</b> ⏳",
            parse_mode="HTML"
        )

        filename = None
        try:
            filename, title, artist = await download_audio(url)

            if not os.path.exists(filename):
                raise RuntimeError("Audio fayl topilmadi.")

            if os.path.getsize(filename) > 49 * 1024 * 1024:
                raise RuntimeError("Audio fayl juda katta.")

            ext = os.path.splitext(filename)[1].lower()
            caption = f"🎵 <b>{title}</b>" + (f"\n👤 {artist}" if artist else "")

            with open(filename, "rb") as audio_file:
                if ext in (".mp3", ".m4a"):
                    await update.message.reply_audio(
                        audio_file,
                        title=title[:64],
                        performer=(artist or "")[:64],
                        caption=caption,
                        parse_mode="HTML",
                    )
                else:
                    await update.message.reply_document(
                        audio_file,
                        caption=caption,
                        parse_mode="HTML",
                    )

            await status.delete()
            add_xp(user.id, 5)

        except Exception as e:
            log.exception(e)
            try:
                await status.edit_text(
                    f"❌ Audio yuklab bo'lmadi:\n{str(e)[:500]}",
                    reply_markup=music_kb()
                )
            except Exception:
                pass
        finally:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass
        return

    await update.message.reply_text(
        "😈 Menyudan funksiya tanlang.",
        reply_markup=home_reply_kb(user.id)
    )


# ============================================================
# PHOTO PROCESSING
# ============================================================

async def photo_router(update,context):
    user=update.effective_user
    ensure_user(user)
    mode=context.user_data.get("media","compress")
    photo=update.message.photo[-1]
    f=await context.bot.get_file(photo.file_id)
    data=bytes(await f.download_as_bytearray())

    if Image is None:
        await update.message.reply_text("❌ Pillow o'rnatilmagan."); return

    try:
        image=Image.open(io.BytesIO(data))
        if mode=="ocr":
            if pytesseract is None:
                await update.message.reply_text("❌ OCR uchun pytesseract/Tesseract kerak."); return
            text=await asyncio.to_thread(pytesseract.image_to_string,image)
            await update.message.reply_text(
                "🔍 <b>OCR</b>\n\n"+(text[:4000] or "Matn topilmadi."),
                parse_mode="HTML"
            ); return

        image=image.convert("RGB")
        if mode in ("compress","resize"):
            image.thumbnail((1600,1600))
        if mode=="gray":
            image=ImageOps.grayscale(image).convert("RGB")

        out=io.BytesIO()
        image.save(out,format="JPEG",quality=82,optimize=True)
        out.seek(0)
        await update.message.reply_document(
            out,filename="hammasi_birda.jpg",
            caption=f"🖼 {mode} tayyor."
        )
        add_xp(user.id,3)
    except Exception as e:
        log.exception(e)
        await update.message.reply_text(f"❌ Media xatosi: {str(e)[:400]}")


# ============================================================
# INLINE
# ============================================================

async def inline(update,context):
    raw=update.inline_query.query.strip()
    results=[]

    if not raw:
        results=[
            InlineQueryResultArticle(
                id="calc",
                title="🧮 Kalkulyator",
                description="25+35*2",
                input_message_content=InputTextMessageContent(
                    "🧮 Misol: @BotUsername 25+35*2"
                )
            ),
            InlineQueryResultArticle(
                id="music",
                title="🎵 Musiqa",
                description="Artist yoki qo'shiq",
                input_message_content=InputTextMessageContent(
                    "🎵 Misol: @BotUsername musiqa Artist"
                )
            )
        ]
    else:
        try:
            result=calc(raw)
            results.append(
                InlineQueryResultArticle(
                    id="calc_result",
                    title=f"🧮 {raw} = {result}",
                    description="Natijani yuborish",
                    input_message_content=InputTextMessageContent(
                        f"🧮 {raw} = {result}"
                    )
                )
            )
        except:
            pass

        if raw.lower().startswith(("musiqa ","music ")):
            song=raw.split(maxsplit=1)[1]
            results.insert(0,InlineQueryResultArticle(
                id="music_result",
                title=f"🎵 {song}",
                description="Musiqa qidiruvi",
                input_message_content=InputTextMessageContent(
                    f"🎵 Musiqa: {song}\n\nProvider API ulanadi."
                )
            ))

    await update.inline_query.answer(
        results[:20],cache_time=1,is_personal=True
    )


# ============================================================
# ADMIN
# ============================================================

async def admin_cmd(update,context):
    if not is_admin_user(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    context.user_data["admin_panel"]=True
    context.user_data.pop("admin_mode",None)
    await update.message.reply_text("👑 <b>ADMIN PANEL</b>\n\nKerakli bo'limni tanlang:",parse_mode="HTML",reply_markup=admin_reply_kb())


async def adminstats(update,context):
    if not ADMIN_ID or update.effective_user.id!=ADMIN_ID:
        await update.message.reply_text("⛔ Ruxsat yo'q."); return
    con=db()
    users=con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    coins=con.execute("SELECT COALESCE(SUM(coins),0) FROM users").fetchone()[0]
    row=con.execute(
        "SELECT messages FROM stats WHERE day=?",(date.today().isoformat(),)
    ).fetchone()
    con.close()
    await update.message.reply_text(
        f"👑 <b>ADMIN</b>\n\n👥 Users: {users}\n"
        f"🪙 Coin: {coins}\n💬 Bugungi xabar: {row[0] if row else 0}",
        parse_mode="HTML"
    )


async def admin_text_router(update,context,text):
    user=update.effective_user
    mode=context.user_data.get("admin_mode")
    if mode=="broadcast":
        context.user_data.pop("admin_mode",None)
        con=db(); ids=[r[0] for r in con.execute("SELECT user_id FROM users").fetchall()]; con.close()
        ok=0
        for uid in ids:
            try:
                await context.bot.send_message(uid,text)
                ok+=1
            except Exception:
                pass
            await asyncio.sleep(0.03)
        await update.message.reply_text(f"📢 Reklama tugadi.\n✅ Yuborildi: {ok}/{len(ids)}",reply_markup=admin_reply_kb())
        return
    if mode=="force_channel":
        parts=text.split("|",1)
        channel=parts[0].strip(); link=parts[1].strip() if len(parts)>1 else ""
        try:
            chat=await context.bot.get_chat(channel)
            me=await context.bot.get_chat_member(chat.id,context.bot.id)
            if me.status not in (ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.OWNER):
                await update.message.reply_text("❌ Bot kanalga admin qilib qo'yilmagan.",reply_markup=admin_reply_kb()); return
            username=(chat.username or "").strip("@")
            set_config("force_channel_id",chat.id); set_config("force_channel_username",username); set_config("force_channel_link",link or ("https://t.me/"+username if username else ""))
            context.user_data.pop("admin_mode",None)
            await update.message.reply_text(f"✅ Majburiy obuna ulandi: <b>{chat.title}</b>",parse_mode="HTML",reply_markup=admin_reply_kb())
        except Exception as e:
            await update.message.reply_text(f"❌ Kanalni ulab bo'lmadi: {str(e)[:300]}",reply_markup=admin_reply_kb())
        return
    if mode=="start_text":
        set_config("start_text",text); context.user_data.pop("admin_mode",None)
        await update.message.reply_text("✅ Start matni saqlandi.",reply_markup=admin_reply_kb()); return
    if mode=="vip_price":
        try: price=max(0,int(text)); set_config("vip_price",price); context.user_data.pop("admin_mode",None); await update.message.reply_text(f"✅ VIP narxi: {price} 🪙",reply_markup=admin_reply_kb())
        except: await update.message.reply_text("❌ Faqat raqam kiriting.",reply_markup=admin_reply_kb())
        return
    if mode=="vip_days":
        try: days=max(1,int(text)); set_config("vip_days",days); context.user_data.pop("admin_mode",None); await update.message.reply_text(f"✅ VIP muddati: {days} kun",reply_markup=admin_reply_kb())
        except: await update.message.reply_text("❌ Faqat raqam kiriting.",reply_markup=admin_reply_kb())
        return
    if mode=="user_lookup":
        try: uid=int(text); r=user_row(uid)
        except: r=None
        if not r: await update.message.reply_text("❌ User topilmadi.",reply_markup=admin_reply_kb()); return
        context.user_data.pop("admin_mode",None)
        await update.message.reply_text(f"👤 <b>USER</b>\n\nID: <code>{r[0]}</code>\nUsername: @{r[1] or 'yo‘q'}\nIsm: {r[2]}\n🪙 Coin: {r[3]}\n⭐ XP: {r[4]}\n🏆 Level: {r[5]}",parse_mode="HTML",reply_markup=admin_reply_kb()); return

    if text=="📊 Statistika":
        await adminstats(update,context); return
    if text=="📢 Reklama":
        context.user_data["admin_mode"]="broadcast"
        await update.message.reply_text("📢 Barcha userlarga yuboriladigan xabarni yozing:",reply_markup=admin_reply_kb()); return
    if text=="📣 Majburiy obuna":
        current=get_config("force_channel_username") or get_config("force_channel_id") or "ulanmagan"
        await update.message.reply_text(f"📣 <b>MAJBURIY OBUNA</b>\n\nHozirgi kanal: <b>{current}</b>\n\nKanalni ulang:\n<code>@kanal_username</code>\nyoki private kanal uchun:\n<code>-100123456789|https://t.me/+invite</code>",parse_mode="HTML",reply_markup=admin_reply_kb())
        context.user_data["admin_mode"]="force_channel"; return
    if text=="👑 VIP sozlash":
        price=get_config("vip_price","1000"); days=get_config("vip_days","30"); enabled=get_config("vip_enabled","1")
        await update.message.reply_text(f"👑 <b>VIP SOZLAMALARI</b>\n\nHolat: {'✅ Yoqilgan' if enabled=='1' else '❌ O‘chirilgan'}\n💰 Narx: {price} 🪙\n📅 Muddat: {days} kun",parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💰 Narx",callback_data="admin_vip_price"),InlineKeyboardButton("📅 Muddat",callback_data="admin_vip_days")],[InlineKeyboardButton("🔄 ON/OFF",callback_data="admin_vip_toggle")]])); return
    if text=="👥 User boshqaruv":
        context.user_data["admin_mode"]="user_lookup"
        await update.message.reply_text("👥 User ID yuboring:",reply_markup=admin_reply_kb()); return
    if text=="📝 Start qismi":
        current=get_config("start_text") or "Standart start matni"
        await update.message.reply_text(
            "📝 <b>START QISMI</b>\n\n"
            "Hozirgi matn:\n" + current +
            "\n\nYangi start matnini yuboring.\n\n"
            "🔤 O'zgaruvchilar:\n"
            "<code>{name}</code> — ism\n"
            "<code>{username}</code> — username\n"
            "<code>{id}</code> — Telegram ID\n"
            "<code>{mention}</code> — bosiladigan ism",
            parse_mode="HTML",
            reply_markup=admin_reply_kb()
        )
        context.user_data["admin_mode"]="start_text"
        return
    if text=="⚙️ Bot sozlamalari":
        await update.message.reply_text("⚙️ <b>BOT SOZLAMALARI</b>\n\nAdmin panel orqali asosiy sozlamalar boshqariladi.",parse_mode="HTML",reply_markup=admin_reply_kb()); return

async def admin_callback(update,context):
    q=update.callback_query; await q.answer()
    if not is_admin_user(q.from_user.id): return
    if q.data=="admin_vip_toggle":
        v="0" if get_config("vip_enabled","1")=="1" else "1"; set_config("vip_enabled",v)
        await q.edit_message_text(f"👑 VIP: {'✅ YOQILDI' if v=='1' else '❌ O‘CHIRILDI'}")
    elif q.data=="admin_vip_price":
        context.user_data["admin_mode"]="vip_price"
        await q.edit_message_text("💰 Yangi VIP narxini yuboring:")
    elif q.data=="admin_vip_days":
        context.user_data["admin_mode"]="vip_days"
        await q.edit_message_text("📅 VIP muddatini kunlarda yuboring:")

# ============================================================
# ERROR / MAIN
# ============================================================

async def error_handler(update,context):
    log.exception("Unhandled error",exc_info=context.error)

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variableini kiriting.")

    init_db()

    app=Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CommandHandler("admin",admin_cmd))
    app.add_handler(CommandHandler("adminstats",adminstats))
    app.add_handler(InlineQueryHandler(inline))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_vip_"))
    app.add_handler(CallbackQueryHandler(cb))

    app.add_handler(MessageHandler(
        filters.PHOTO,photo_router
    ))

    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND,
        group_guard,
        block=False
    ))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.ChatType.GROUPS,
        text_router,
        block=False
    ))

    app.add_error_handler(error_handler)

    log.info("😈 HammasiBirdaBot ishga tushdi.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
