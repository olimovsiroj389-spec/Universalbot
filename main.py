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
import asyncio
import operator as op
from datetime import datetime, date, timedelta
from urllib.parse import quote_plus
from pathlib import Path

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

TOKEN = "8797534923:AAGTo8zHfhgIPDheIfPJgWjpI1cRkh63dHA"
ADMIN_ID = 8824266579
OPENROUTER_API_KEY = "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"
OPENROUTER_MODEL = "openrouter/free"
JAMENDO_CLIENT_ID = "95572ec9"
# Persistent DB: Render Persistent Disk bo'lsa /var/data ishlatiladi.
# Lokal ishlaganda odatdagi hammasi_birda.db saqlanadi.
DEFAULT_DB_DIR = "/var/data" if os.path.isdir("/var/data") else "."
DB_FILE = os.getenv("DB_FILE") or os.path.join(DEFAULT_DB_DIR, "hammasi_birda.db")

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS payment_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT '',
        reviewed_at TEXT DEFAULT ''
    )
    """)

    con.commit()
    con.close()
    if not get_config("vip_price_uzs"):
        set_config("vip_price_uzs", "20000")
    if not get_config("vip_days"):
        set_config("vip_days", "30")
    if not get_config("vip_enabled"):
        set_config("vip_enabled", "1")

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

def balance_uzs(user_id):
    row=user_row(user_id)
    return int(row[3] or 0) if row else 0

def is_vip(user_id):
    con=db()
    row=con.execute("SELECT expires_at FROM vip_users WHERE user_id=?",(user_id,)).fetchone()
    con.close()
    if not row or not row[0]:
        return False
    try:
        return datetime.fromisoformat(row[0]) > datetime.now()
    except Exception:
        return False

def set_vip(user_id, days):
    expires=datetime.now()+timedelta(days=days)
    con=db()
    con.execute("INSERT OR REPLACE INTO vip_users(user_id,expires_at) VALUES(?,?)",(user_id,expires.isoformat(timespec="seconds")))
    con.commit(); con.close()
    return expires

def create_payment(user_id, amount):
    con=db()
    cur=con.execute("INSERT INTO payment_requests(user_id,amount,created_at) VALUES(?,?,?)",(user_id,amount,datetime.now().isoformat(timespec="seconds")))
    pid=cur.lastrowid
    con.commit(); con.close()
    return pid

def get_payment(pid):
    con=db(); row=con.execute("SELECT id,user_id,amount,status,created_at FROM payment_requests WHERE id=?",(pid,)).fetchone(); con.close(); return row

def set_payment_status(pid,status):
    con=db(); con.execute("UPDATE payment_requests SET status=?,reviewed_at=? WHERE id=?",(status,datetime.now().isoformat(timespec="seconds"),pid)); con.commit(); con.close()

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

LANGS={
    "uz": {
        "ai":"◈ Ai studio","dl":"↗ Yuklash","music":"♫ Musiqa","media":"▧ Media","games":"◇ O'yinlar","wallet":"◫ Hamyon","tools":"⌘ Asboblar","search":"⌕ Qidiruv","group":"◎ Guruh","bonus":"✦ Bonus","vip":"♕ Vip","settings":"⚙ Sozlamalar","profile":"♙ Profil","help":"ⓘ Yordam","back":"🔙 Bosh menyu","lang":"🌐 Til","deposit":"💳 Pul kiritish","buy_vip":"♕ Vip sotib olish"
    },
    "ru": {
        "ai":"◈ Ai studio","dl":"↗ Загрузить","music":"♫ Музыка","media":"▧ Медиа","games":"◇ Игры","wallet":"◫ Кошелёк","tools":"⌘ Инструменты","search":"⌕ Поиск","group":"◎ Группа","bonus":"✦ Бонус","vip":"♕ Vip","settings":"⚙ Настройки","profile":"♙ Профиль","help":"ⓘ Помощь","back":"🔙 Главное меню","lang":"🌐 Язык","deposit":"💳 Пополнить баланс","buy_vip":"♕ Купить Vip"
    },
    "en": {
        "ai":"◈ Ai studio","dl":"↗ Upload","music":"♫ Music","media":"▧ Media","games":"◇ Games","wallet":"◫ Wallet","tools":"⌘ Tools","search":"⌕ Search","group":"◎ Group","bonus":"✦ Bonus","vip":"♕ Vip","settings":"⚙ Settings","profile":"♙ Profile","help":"ⓘ Help","back":"🔙 Main menu","lang":"🌐 Language","deposit":"💳 Add funds","buy_vip":"♕ Buy Vip"
    }
}

def user_lang(user_id):
    row=user_row(user_id)
    return row[7] if row and row[7] in LANGS else "uz"

def tr(user_id,key):
    return LANGS[user_lang(user_id)].get(key,key)

def set_user_lang(user_id,lang):
    if lang not in LANGS: return
    con=db(); con.execute("UPDATE users SET lang=? WHERE user_id=?",(lang,user_id)); con.commit(); con.close()

def home_reply_kb(user_id=None):
    lang=user_lang(user_id) if user_id else "uz"
    L=LANGS[lang]
    rows=[
        [KeyboardButton(L["ai"]),KeyboardButton(L["dl"])],
        [KeyboardButton(L["music"]),KeyboardButton(L["media"])],
        [KeyboardButton(L["games"]),KeyboardButton(L["wallet"])],
        [KeyboardButton(L["tools"]),KeyboardButton(L["search"])],
        [KeyboardButton(L["group"]),KeyboardButton(L["bonus"])],
        [KeyboardButton(L["vip"]),KeyboardButton(L["settings"])],
        [KeyboardButton(L["profile"]),KeyboardButton(L["help"])],
    ]
    if user_id is not None and is_admin_user(user_id): rows.append([KeyboardButton("👑 Botni boshqarish")])
    return ReplyKeyboardMarkup(rows,resize_keyboard=True,is_persistent=True)

def admin_reply_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Statistika"),KeyboardButton("📢 Reklama")],
        [KeyboardButton("📣 Majburiy obuna"),KeyboardButton("👑 VIP sozlash")],
        [KeyboardButton("💳 Karta sozlash"),KeyboardButton("👥 User boshqaruv")],
        [KeyboardButton("📝 Start qismi"),KeyboardButton("⚙️ Bot sozlamalari")],
        [KeyboardButton("🔙 Bosh menyu")],
    ],resize_keyboard=True,is_persistent=True)

async def subscription_status(bot,user_id):
    channel_id=get_config("force_channel_id") or os.getenv("FORCE_CHANNEL_ID", "")
    if not channel_id:
        return True
    try:
        try:
            chat_id=int(channel_id)
        except (TypeError, ValueError):
            chat=await bot.get_chat(str(channel_id))
            chat_id=chat.id
        m=await bot.get_chat_member(chat_id,user_id)
        if m.status in (ChatMemberStatus.MEMBER,ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.OWNER):
            return True
        if m.status == ChatMemberStatus.RESTRICTED:
            return bool(getattr(m,"is_member",False))
        return False
    except Exception as e:
        log.warning("Force subscription check: %s",e)
        return False

async def require_subscription(update,context):
    user=update.effective_user
    if not user or is_admin_user(user.id) or await subscription_status(context.bot,user.id):
        return True
    link=get_config("force_channel_link") or os.getenv("FORCE_CHANNEL_LINK", "")
    if not link:
        username=get_config("force_channel_username") or os.getenv("FORCE_CHANNEL_USERNAME", "")
        if username:
            link="https://t.me/"+username.lstrip("@")
    buttons=[]
    if link:
        buttons.append([InlineKeyboardButton("📣 Kanalga obuna bo'lish",url=link)])
    buttons.append([InlineKeyboardButton("🔄 Obunani tekshirish",callback_data="check_subscription")])
    text="📣 <b>Majburiy obuna</b>\n\nBotdan foydalanishdan oldin quyidagi kanalga obuna bo'ling."
    if update.callback_query:
        await update.callback_query.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(buttons))
    elif update.effective_message:
        await update.effective_message.reply_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(buttons))
    return False


BOT_USERNAME=os.getenv("BOT_USERNAME","UniversalProBot")

def bot_username_text(): return "@"+BOT_USERNAME.lstrip("@")
def bonus_remaining_text():
    now=datetime.now(); tomorrow=datetime.combine(now.date()+timedelta(days=1),datetime.min.time()); seconds=max(0,int((tomorrow-now).total_seconds())); hours,rem=divmod(seconds,3600); minutes,secs=divmod(rem,60); return f"{hours:02d}:{minutes:02d}:{secs:02d}"
def group_add_url(): return f"https://t.me/{BOT_USERNAME.lstrip('@')}?startgroup=add"

def kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(text,callback_data=data) for text,data in row] for row in rows])

def back(): return kb([[('🔙 Bosh menyu','home_reply')]])
def back2(*rows): return kb(list(rows)+[[('🔙 Bosh menyu','home_reply')]])

def home_kb(user_id=None):
    L=LANGS[user_lang(user_id) if user_id else "uz"]
    return kb([
        [(L["ai"],"menu_ai"),(L["dl"],"menu_dl")],
        [(L["music"],"menu_music"),(L["media"],"menu_media")],
        [(L["games"],"menu_games"),(L["wallet"],"menu_wallet")],
        [(L["tools"],"menu_tools"),(L["search"],"menu_search")],
        [(L["group"],"menu_group"),(L["bonus"],"bonus")],
        [(L["vip"],"menu_vip"),(L["settings"],"menu_settings")],
        [(L["profile"],"profile"),(L["help"],"help")]
    ])

def ai_kb(): return kb([[('💬 AI Chat','ai_chat'),('✍️ Matn yozish','ai_write')],[('📝 Qisqartirish','ai_summary'),('🌐 Tarjima','ai_translate')],[('💻 Kod yordamchi','ai_code'),('🎯 Prompt generator','ai_prompt')],[('🔙 Bosh menyu','home_reply')]])
def dl_kb(): return kb([
    [('◈ YouTube','dl_youtube'),('◈ Instagram','dl_instagram')],
    [('◈ TikTok','dl_tiktok'),('◈ Facebook','dl_facebook')],
    [('◇ Universal URL','dl_url'),('ⓘ Qoidalar','dl_rules')],
    [('‹ Bosh sahifa','home_reply')]
])
def music_kb(): return kb([[ ("🔎 Qo'shiq qidirish","music_search"),("🎤 Artist","music_artist") ],[("🔥 Trend","music_trend"),("🎧 Audio","music_audio")],[("📃 Lyrics","music_lyrics"),("ℹ️ Yordam","music_help")],[("🔙 Bosh menyu","home_reply")]])
def media_kb(): return kb([[('🗜 Siqish','media_compress'),("📐 O'lcham",'media_resize')],[('⚫ Qora-oq','media_gray'),('🔄 JPG/PNG','media_convert')],[('🔍 OCR','media_ocr'),('📄 PDF','media_pdf')],[('🔙 Bosh menyu','home_reply')]])
def games_kb(): return kb([[('🎲 Zar','game_dice'),('🪙 Coin','game_coin')],[('🎰 Slot','game_slot'),('🧠 Son topish','game_guess')],[('🏆 TOP 10',"ranking"),("🎯 21 o'yini",'game_21')],[('🔙 Bosh menyu','home_reply')]])
def tools_kb(): return kb([[('🧮 Kalkulyator','tool_calc'),('🔗 QR','tool_qr')],[('🔐 Parol','tool_password'),('🆔 UUID','tool_uuid')],[('🌐 Tarjimon','tool_translate'),('📊 Matn stats','tool_stats')],[('🔢 Base converter','tool_base'),('🔡 Case converter','tool_case')],[('🕐 Vaqt','tool_time'),('📅 Sana','tool_date')],[('🔙 Bosh menyu','home_reply')]])
def group_kb(): return kb([[ ("➕ Guruhga qo'shish","group_add") ],[("🛡 Anti-spam","group_antispam"),("🔗 Link filter","group_links")],[("👋 Welcome","group_welcome"),("⚠️ Warn","group_warn")],[("🔇 Mute","group_mute"),("🚫 Ban","group_ban")],[("📌 Pin","group_pin"),("🧹 Delete","group_delete")],[("ℹ️ Admin yordam","group_help")],[("🔙 Bosh menyu","home_reply")]])
def settings_kb(): return kb([[('🌐 Til','setting_lang'),('🔔 Bildirishnoma','setting_notify')],[('🧹 Sessiyani tozalash','setting_clear'),('👤 Profil','profile')],[('🔙 Bosh menyu','home_reply')]])


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
    if not OPENROUTER_API_KEY:
        return "🤖 <b>AI API ulanmagan.</b>"
    if aiohttp is None:
        return "❌ aiohttp o'rnatilmagan."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Hammasi Birda Bot",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role":"system",
                "content":"HammasiBirdaBot AI yordamchisisiz. O'zbek tilida aniq, foydali va xavfsiz javob bering."
            },
            {"role":"user","content":prompt}
        ],
        "temperature":0.7,
    }
    try:
        timeout=aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url,headers=headers,json=payload) as r:
                data=await r.json(content_type=None)
                if r.status != 200:
                    log.error("OpenRouter %s: %s",r.status,data)
                    if r.status in (401,403):
                        return "❌ OpenRouter API key noto'g'ri yoki faol emas."
                    if r.status == 429:
                        return "⏳ AI bepul limitiga vaqtincha yetildi. Birozdan keyin qayta urinib ko'ring."
                    return "❌ AI API xatolik qaytardi."
                content=((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                return (content or "❌ AI javob qaytarmadi.").strip()
    except Exception as e:
        log.exception(e)
        return "❌ AI bilan ulanishda xatolik."


def ai_to_telegram_html(text):
    """Convert common Markdown from AI into safe Telegram HTML."""
    import html
    if not text:
        return "🤖 Javob bo'sh qaytdi."
    text=text.replace("\r\n","\n").replace("\r","\n")
    # Protect fenced code blocks first.
    blocks=[]
    def block_repl(m):
        lang=(m.group(1) or "").strip()
        code=html.escape(m.group(2).strip("\n"))
        label=f"<b>{html.escape(lang)}</b>\n" if lang else ""
        token=f"@@CODEBLOCK{len(blocks)}@@"
        blocks.append(f"<pre>{label}{code}</pre>")
        return token
    text=re.sub(r"```([^\n]*)\n?(.*?)```", block_repl, text, flags=re.S)
    text=html.escape(text)
    # Inline code
    text=re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Bold / italic / strike
    text=re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.S)
    text=re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    text=re.sub(r"~~(.+?)~~", r"<s>\1</s>", text, flags=re.S)
    # Markdown headings
    text=re.sub(r"(?m)^#{1,6}\s+(.+)$", r"<b>\1</b>", text)
    # Bullet lists -> Telegram-friendly bullets
    text=re.sub(r"(?m)^\s*[-*]\s+", "• ", text)
    # Numbered list stays readable.
    for i, block in enumerate(blocks):
        text=text.replace(f"@@CODEBLOCK{i}@@", block)
    return text[:4000]


def pretty_ai_card(title, prompt, answer):
    import html
    return (
        f"✨ <b>{html.escape(title)}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💬 <b>Savol</b>\n{html.escape(prompt[:700])}\n\n"
        f"🤖 <b>AI javobi</b>\n"
        f"{ai_to_telegram_html(answer)}\n"
        f"━━━━━━━━━━━━━━"
    )

async def youtube_music_search(query, limit=8):
    """Search YouTube for the requested song/artist without a separate API key."""
    if yt_dlp is None:
        return []
    def worker():
        opts={"quiet":True,"no_warnings":True,"skip_download":True,"extract_flat":True}
        with yt_dlp.YoutubeDL(opts) as y:
            info=y.extract_info(f"ytsearch{min(max(limit,1),10)}:{query}", download=False)
            entries=info.get("entries") or []
            out=[]
            for x in entries:
                if not x: continue
                vid=x.get("id")
                if not vid: continue
                out.append({
                    "provider":"youtube",
                    "id":str(vid),
                    "title":x.get("title") or "Noma'lum",
                    "artist":x.get("channel") or x.get("uploader") or "",
                    "url":f"https://www.youtube.com/watch?v={vid}",
                    "page_url":f"https://www.youtube.com/watch?v={vid}",
                    "image":x.get("thumbnail") or "",
                })
            return out
    try:
        return await asyncio.to_thread(worker)
    except Exception as e:
        log.warning("YouTube music search: %s",e)
        return []

async def music_search_best(query, limit=8, artist_only=False):
    # First try Jamendo (download-allowed catalog), then YouTube search for mainstream requests.
    results=await jamendo_search_api(query,limit,artist_only=artist_only)
    if results:
        qparts=[x.lower() for x in re.findall(r"[\w']+",query) if len(x)>2]
        def score(x):
            hay=(x.get("title","")+" "+x.get("artist","")).lower()
            return sum(1 for part in qparts if part in hay)
        results.sort(key=score,reverse=True)
        if any(score(x)==len(qparts) for x in results if qparts):
            return results
    yt=await youtube_music_search(query,limit)
    return yt or results

async def translate(target,text):
    if GoogleTranslator is None:
        return "❌ deep-translator o'rnatilmagan."
    return await asyncio.to_thread(
        lambda: GoogleTranslator(source="auto",target=target).translate(text)
    )

async def jamendo_search_api(query, limit=8, artist_only=False, featured=False):
    """Search Jamendo's catalog. Only tracks that allow application downloads are returned."""
    if aiohttp is None or not JAMENDO_CLIENT_ID:
        return []
    params={
        "client_id":JAMENDO_CLIENT_ID,
        "format":"json",
        "limit":min(max(int(limit),1),20),
        "type":"single albumtrack",
        "audioformat":"mp31",
        "audiodlformat":"mp32",
    }
    if featured:
        params["featured"]="1"
        params["boost"]="popularity_month"
    elif artist_only:
        params["artist_name"]=query
    else:
        params["search"]=query
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get("https://api.jamendo.com/v3.0/tracks/",params=params,headers={"User-Agent":"HammasiBirdaBot/1.0"}) as r:
                data=await r.json(content_type=None)
                if r.status != 200:
                    log.warning("Jamendo API %s: %s",r.status,data)
                    return []
        results=[]
        for x in data.get("results",[]):
            download_url=x.get("audiodownload") or ""
            if not download_url or x.get("audiodownload_allowed") is False:
                continue
            results.append({
                "provider":"jamendo",
                "id":str(x.get("id","")),
                "title":x.get("name") or "Noma'lum",
                "artist":x.get("artist_name") or "",
                "url":download_url,
                "page_url":x.get("shareurl") or x.get("shorturl") or "",
                "image":x.get("album_image") or x.get("image") or "",
            })
            if len(results)>=limit:
                break
        return results
    except Exception as e:
        log.warning("Jamendo search: %s",e)
        return []

async def music_search_api(query, limit=5):
    return await jamendo_search_api(query,limit)

async def download_jamendo_audio(url,title="Audio",track_id=""):
    if aiohttp is None:
        raise RuntimeError("aiohttp o'rnatilmagan.")
    os.makedirs("downloads",exist_ok=True)
    safe=re.sub(r"[^a-zA-Z0-9._-]+","_",title).strip("._")[:70] or "audio"
    suffix=track_id or secrets.token_hex(4)
    filename=os.path.join("downloads",f"{safe}-{suffix}.mp3")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
            async with session.get(url,headers={"User-Agent":"HammasiBirdaBot/1.0"}) as r:
                if r.status != 200:
                    raise RuntimeError(f"Jamendo audio HTTP {r.status}")
                total=0
                with open(filename,"wb") as f:
                    async for chunk in r.content.iter_chunked(64*1024):
                        total+=len(chunk)
                        if total>49*1024*1024:
                            raise RuntimeError("Audio fayli 49 MB dan katta.")
                        f.write(chunk)
        return filename,title
    except Exception:
        if os.path.exists(filename):
            try: os.remove(filename)
            except Exception: pass
        raise


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


async def download_audio(url):
    if yt_dlp is None:
        raise RuntimeError("yt-dlp o'rnatilmagan.")
    os.makedirs("downloads", exist_ok=True)
    template = os.path.join("downloads", "%(title).70s-%(id)s.%(ext)s")

    opts = {
        "outtmpl": template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "format": "bestaudio/best",
        "max_filesize": 49 * 1024 * 1024,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    def worker():
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=True)
            prepared = y.prepare_filename(info)
            mp3 = os.path.splitext(prepared)[0] + ".mp3"
            if not os.path.exists(mp3):
                # Some yt-dlp versions can return a different extension.
                candidates = list(Path("downloads").glob(f"{Path(prepared).stem}.*"))
                if candidates:
                    return str(candidates[0]), info.get("title", "Audio")
                raise RuntimeError("MP3 fayl yaratilmadi.")
            return mp3, info.get("title", "Audio")

    return await asyncio.to_thread(worker)


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


# ============================================================
# START / HELP
# ============================================================

async def start(update, context):
    ensure_user(update.effective_user)
    context.user_data.clear()
    if not await require_subscription(update,context):
        return

    user = update.effective_user
    import html
    name = html.escape(user.first_name or "Foydalanuvchi")
    username = html.escape(f"@{user.username}" if user.username else "yo'q")
    user_id = str(user.id)
    mention = f'<a href="tg://user?id={user.id}">{name}</a>'

    start_text = get_config("start_text") or os.getenv("START_TEXT", "").strip() or (
        "😈 <b>HAMMASI BIRDA BOT</b>\n\n"
        f"Salom, <b>{name}</b>!\n"
        "👇 Kerakli xizmatni tanlang:"
    )

    start_text = (
        start_text
        .replace("{name}", name)
        .replace("{username}", username)
        .replace("{id}", user_id)
        .replace("{mention}", mention)
    )

    await update.message.reply_text(
        start_text, parse_mode="HTML",
        reply_markup=home_reply_kb(user.id)
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
# WALLET / PAYMENTS
# ============================================================
def wallet_kb(user_id):
    return kb([[('💳 Pul kiritish','wallet_deposit'),('👑 VIP sotib olish','vip_buy')],[('🔙 Bosh menyu','home_reply')]])

def payment_card_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("💸 To'lov qildim",callback_data="payment_done")],[InlineKeyboardButton('🔙 Bosh menyu',callback_data='home_reply')]])

def lang_kb():
    return kb([[("🇺🇿 O'zbekcha","lang_uz")],[('🇷🇺 Русский','lang_ru')],[('🇬🇧 English','lang_en')],[('🔙 Bosh menyu','home_reply')]])

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
            await q.edit_message_text("✅ <b>Obuna tasdiqlandi!</b>\n\nEndi botdan foydalanishingiz mumkin.",parse_mode="HTML",reply_markup=home_kb(user.id))
            await context.bot.send_message(user.id,"🏠 Bosh menyu",reply_markup=home_reply_kb(user.id))
        else:
            await require_subscription(update,context)
        return
    if d in ("home","home_reply"):
        context.user_data.clear()
        try: await q.message.delete()
        except Exception: pass
        await context.bot.send_message(user.id,"🏠 <b>BOSH MENYU</b>\n\n👇 Bo'limni tanlang:",parse_mode="HTML",reply_markup=home_reply_kb(user.id))
        return
    if d.startswith("lang_"):
        lang=d.split("_",1)[1]
        set_user_lang(user.id,lang)
        await q.edit_message_text("✅ Til o'zgartirildi.",reply_markup=home_kb(user.id))
        await context.bot.send_message(user.id,"🏠 Bosh menyu",reply_markup=home_reply_kb(user.id))
        return
    if d != "home" and not await require_subscription(update,context):
        return

    if d == "wallet_deposit":
        context.user_data['mode']='deposit_amount'
        await q.edit_message_text("💳 <b>PUL KIRITISH</b>\n\nQancha UZS kiritmoqchisiz?\nMasalan: <code>20000</code>",parse_mode="HTML",reply_markup=back())
        return
    if d == "payment_done":
        pid=context.user_data.get('payment_id')
        if not pid:
            await q.answer("Avval to'lov miqdorini tanlang.",show_alert=True); return
        context.user_data['mode']='payment_receipt'
        await q.edit_message_text("📸 <b>Chekni yuboring</b>\n\nTo'lov qilganingizni tasdiqlovchi screenshotni rasm qilib yuboring.",parse_mode="HTML",reply_markup=back())
        return
    if d == "vip_buy":
        enabled=get_config('vip_enabled','1')=='1'; price=int(get_config('vip_price_uzs','20000') or 20000); days=int(get_config('vip_days','30') or 30)
        if is_vip(user.id):
            con=db(); row=con.execute("SELECT expires_at FROM vip_users WHERE user_id=?",(user.id,)).fetchone(); con.close()
            expires=row[0] if row else ""
            await q.edit_message_text(f"👑 <b>Sizda VIP allaqachon faol.</b>\n\n⏳ Tugash vaqti: <b>{expires.replace('T',' ')}</b>",parse_mode="HTML",reply_markup=back())
            return
        if not enabled:
            await q.edit_message_text("❌ VIP hozircha o'chirilgan.",reply_markup=back()); return
        bal=balance_uzs(user.id)
        if bal < price:
            await q.edit_message_text(f"❌ Mablag' yetarli emas.\n\n💰 Balans: <b>{bal:,} UZS</b>\n👑 VIP: <b>{price:,} UZS</b>",parse_mode='HTML',reply_markup=wallet_kb(user.id)); return
        add_coins(user.id,-price); expires=set_vip(user.id,days)
        await q.edit_message_text(f"🎉 <b>Tabriklaymiz! VIP sotib olindi.</b>\n\n💳 {price:,} UZS yechildi.\n📅 Muddat: {days} kun.\n⏳ {expires:%d.%m.%Y %H:%M}",parse_mode='HTML',reply_markup=back())
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

    # ---------------- AUDIO DOWNLOAD ----------------
    if d.startswith("audio_dl:"):
        key = d.split(":", 1)[1]
        item = context.user_data.get("audio_store", {}).get(key)
        if not item:
            await q.edit_message_text("❌ Audio havolasi eskirgan. Qo'shiqni qayta qidiring.", reply_markup=music_kb())
            return
        await q.answer("Audio yuklanmoqda...", show_alert=False)
        status = await q.message.reply_text("📥 <b>Audio yuklanmoqda...</b> ⏳", parse_mode="HTML")
        filename = None
        try:
            if item.get("provider")=="jamendo":
                filename,title=await download_jamendo_audio(item["url"],item.get("title","Audio"),item.get("id",""))
            elif item.get("provider")=="youtube":
                filename,title=await download_audio(item["url"])
            else:
                filename,title=await download_audio(item["url"])
            if not os.path.exists(filename): raise RuntimeError("Audio fayli topilmadi.")
            if os.path.getsize(filename)>49*1024*1024: raise RuntimeError("Audio fayli juda katta.")
            with open(filename,"rb") as f:
                await q.message.reply_audio(f,title=title[:64],performer=(item.get("artist") or "")[:64],caption=f"🎵 {title}")
            await status.delete()
            add_xp(user.id,5)
        except Exception as e:
            log.exception(e)
            try: await status.edit_text(f"❌ Audioni yuklab bo'lmadi:\n{str(e)[:500]}")
            except Exception: pass
        finally:
            if filename and os.path.exists(filename):
                try: os.remove(filename)
                except Exception: pass
        return

    # ---------------- DOWNLOADER ----------------
    if d == "menu_dl":
        await q.edit_message_text(
            "◈ <b>Downloader</b>\n\n"
            "Kerakli platformani tanlang yoki havolani yuboring.",
            parse_mode="HTML",reply_markup=dl_kb()
        ); return

    if d in ("dl_youtube","dl_instagram","dl_tiktok","dl_facebook","dl_url"):
        context.user_data["mode"]="download"
        await q.edit_message_text(
            "◇ <b>Havola yuboring</b>\n\n"
            "Video yoki media havolasini yuboring.\n"
            "Bot uni mos formatda tayyorlaydi.",
            parse_mode="HTML",reply_markup=back()
        ); return

    if d == "dl_rules":
        await q.edit_message_text(
            "ⓘ <b>Qoidalar</b>\n\n"
            "Faqat foydalanishga haqqingiz bo‘lgan kontentni yuklab oling.\n\n"
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
        context.user_data["mode"]="music_trend"
        await q.edit_message_text("🔥 <b>TREND</b>\n\nJanr yoki mavzuni yuboring. Masalan: <code>pop</code>, <code>rock</code>, <code>relaxation</code>.",parse_mode="HTML",reply_markup=back()); return

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
        r=user_row(user.id); bal=r[3]
        await q.edit_message_text(
            f"💰 <b>HAMYON</b>\n\n💳 Balans: <b>{bal:,} UZS</b>\n⭐ XP: <b>{r[4]}</b>\n🏆 Level: <b>{r[5]}</b>",
            parse_mode="HTML", reply_markup=wallet_kb(user.id))
        return

    if d == "bonus":
        r=user_row(user.id); today=date.today().isoformat()
        if r[6]==today:
            await q.edit_message_text(
                "🎁 <b>Bugungi bonusni oldingiz!</b>\n\n"
                f"⏳ Keyingi bonusgacha: <b>{bonus_remaining_text()}</b>",
                parse_mode="HTML", reply_markup=back()
            ); return
        con=db()
        con.execute("""
            UPDATE users SET coins=coins+100,xp=xp+10,last_bonus=?
            WHERE user_id=?
        """,(today,user.id))
        con.commit(); con.close()
        await q.edit_message_text(
            "🎁 <b>Bugungi bonusni oldingiz!</b>\n\n"
            "🪙 +100 Coin\n⭐ +10 XP\n\n"
            f"⏳ Keyingi bonusgacha: <b>{bonus_remaining_text()}</b>",
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
        me = await context.bot.get_me()
        uname = "@" + (me.username or BOT_USERNAME).lstrip("@")
        await q.edit_message_text(
            "🔎 <b>QIDIRUV</b>\n\n"
            "Inline rejimdan foydalaning:\n"
            f"<code>{uname} 25+35</code>\n"
            f"<code>{uname} musiqa Artist</code>\n\n"
            "Bot username'i avtomatik ko'rsatiladi.",
            parse_mode="HTML",reply_markup=back()
        ); return

    # ---------------- GROUP ----------------
    if d=="group_add":
        me = await context.bot.get_me()
        uname = me.username or BOT_USERNAME
        add_url = f"https://t.me/{uname}?startgroup=add"
        await q.edit_message_text(
            "👥 <b>BOTNI GURUHGA QO'SHISH</b>\n\n"
            "1️⃣ Tugmani bosing va guruhni tanlang.\n"
            "2️⃣ Botni guruhga qo'shing.\n"
            "3️⃣ Telegram oynasida botga <b>administrator</b> huquqlarini bering.\n\n"
            "⚠️ Bot o'zini o'zi admin qila olmaydi — admin huquqini guruh egasi/admini tasdiqlaydi.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Guruhga qo'shish", url=add_url)],
                [InlineKeyboardButton("🔙 Guruh menyusi", callback_data="menu_group")]
            ])
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
        enabled=get_config("vip_enabled","1")=="1"; price=int(get_config("vip_price_uzs","20000") or 20000); days=int(get_config("vip_days","30") or 30)
        status="🟢 Yoqilgan" if enabled else "🔴 O'chirilgan"
        own="" if not is_vip(user.id) else "\n\n✅ Sizda VIP faol."
        buy_button=[] if is_vip(user.id) else [('👑 VIP sotib olish','vip_buy')]
        await q.edit_message_text(f"👑 <b>VIP</b>\n\nHolat: {status}\n💳 Narx: <b>{price:,} UZS</b>\n📅 Muddat: <b>{days} kun</b>{own}",parse_mode='HTML',reply_markup=kb(([buy_button] if buy_button else [])+[[('🔙 Bosh menyu','home_reply')]])); return

    # ---------------- SETTINGS ----------------
    if d=="menu_settings":
        await q.edit_message_text(
            "⚙️ <b>SOZLAMALAR</b>\n\nTanlang:",
            parse_mode="HTML",reply_markup=settings_kb()
        ); return

    if d=="setting_lang":
        await q.edit_message_text("🌐 <b>TILNI TANLANG</b>",parse_mode='HTML',reply_markup=lang_kb()); return

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
        "menu_search":(f"🔎 <b>QIDIRUV</b>\n\nInline rejimdan foydalaning:\n<code>{bot_username_text()} 25+35</code>\n<code>{bot_username_text()} musiqa Artist</code>",back()),
        "menu_group":("👥 <b>GURUH BOSHQARUVI</b>\n\nBot guruhda admin bo'lsa moderatsiya funksiyalari ishlaydi.",group_kb()),
        "menu_wallet":(f"💰 <b>HAMYON</b>\n\n💳 Balans: <b>{balance_uzs(update.effective_user.id):,} UZS</b>",wallet_kb(update.effective_user.id)),
        "menu_vip":(f"👑 <b>VIP</b>\n\n💳 Narx: <b>{int(get_config('vip_price_uzs','20000')):,} UZS</b>\n📅 Muddat: <b>{int(get_config('vip_days','30'))} kun</b>" + ("\n\n✅ Sizda VIP faol." if is_vip(update.effective_user.id) else ""), kb(([[("👑 VIP sotib olish","vip_buy")]] if not is_vip(update.effective_user.id) else [])+[[('🔙 Bosh menyu','home_reply')]])),
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
            await update.message.reply_text("🎁 <b>Bugungi bonusni oldingiz!</b>\n\n" f"⏳ Keyingi bonusgacha: <b>{bonus_remaining_text()}</b>",parse_mode="HTML",reply_markup=home_reply_kb(update.effective_user.id)); return
        con=db(); con.execute("UPDATE users SET coins=coins+100,xp=xp+10,last_bonus=? WHERE user_id=?",(today,update.effective_user.id)); con.commit(); con.close()
        await update.message.reply_text("🎁 <b>Bugungi bonusni oldingiz!</b>\n\n🪙 +100 Coin\n⭐ +10 XP\n\n" f"⏳ Keyingi bonusgacha: <b>{bonus_remaining_text()}</b>",parse_mode="HTML",reply_markup=home_reply_kb(update.effective_user.id))
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
    L=LANGS[user_lang(user.id)]
    main_routes={
        L["ai"]:"menu_ai",L["dl"]:"menu_dl",L["music"]:"menu_music",L["media"]:"menu_media",
        L["games"]:"menu_games",L["wallet"]:"menu_wallet",L["tools"]:"menu_tools",L["search"]:"menu_search",
        L["group"]:"menu_group",L["bonus"]:"bonus",L["vip"]:"menu_vip",L["settings"]:"menu_settings",
        L["profile"]:"profile",L["help"]:"help"
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
        await text_menu_dispatch(update,context,d)
        return

    if mode=="deposit_amount":
        try:
            amount=int(text.replace(',','').replace(' ',''))
            if amount<1000 or amount>100000000: raise ValueError
        except Exception:
            await update.message.reply_text("❌ Miqdorni to'g'ri kiriting. Masalan: 20000 UZS",reply_markup=back()); return
        card=get_config("payment_card","")
        if not card:
            await update.message.reply_text("❌ To'lov kartasi hali admin tomonidan sozlanmagan.",reply_markup=home_reply_kb(user.id)); return
        pid=create_payment(user.id,amount)
        context.user_data["payment_id"]=pid
        context.user_data.pop("mode",None)
        await update.message.reply_text(f"💳 <b>TO'LOV</b>\n\n💰 Miqdor: <b>{amount:,} UZS</b>\n💳 Karta: <code>{card}</code>\n\nTo'lovni amalga oshiring. Keyin <b>To'lov qildim</b> tugmasini bosing.",parse_mode='HTML',reply_markup=payment_card_kb()); return

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
        card_title={"ai":"AI CHAT","ai_write":"MATN YOZISH","ai_summary":"QISQARTIRISH","ai_code":"KOD YORDAMCHI","ai_prompt":"PROMPT GENERATOR"}.get(mode,"AI")
        await update.message.reply_text(
            pretty_ai_card(card_title,text,result),
            parse_mode="HTML",
            reply_markup=back()
        )
        add_xp(user.id,3); return

    if mode=="ai_translate":
        result=await ai("Quyidagi matnni ma'nosini saqlagan holda tarjima qiling:\n"+text)
        await update.message.reply_text(
            pretty_ai_card("TARJIMA",text,result),
            parse_mode="HTML",
            reply_markup=back()
        ); return

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

    if mode == "music_trend":
        results = await jamendo_search_api(text, 8, featured=True)
        if not results:
            await update.message.reply_text("❌ Trend musiqalarini olib bo'lmadi.",reply_markup=music_kb()); return
        buttons=[]
        lines=["🔥 <b>TREND MUSIQALAR</b>","","📚 Manba: Jamendo"]
        for i,item in enumerate(results,1):
            lines.append(f"{i}. <b>{item.get('title','Noma’lum')}</b> — {item.get('artist','')}")
            key=secrets.token_urlsafe(8); context.user_data.setdefault("audio_store",{})[key]=item
            buttons.append([InlineKeyboardButton(f"📥 {i}. {item.get('title','Audio')[:28]}",callback_data=f"audio_dl:{key}")])
        await update.message.reply_text("\n".join(lines)[:4000],parse_mode="HTML",reply_markup=InlineKeyboardMarkup(buttons)); add_xp(user.id,3); return

    if mode in ("music_search", "music_artist"):
        results = await music_search_best(text, 8, artist_only=(mode=="music_artist"))
        if not results:
            await update.message.reply_text(
                "❌ Jamendo'da musiqa topilmadi yoki API vaqtincha javob bermayapti.",
                reply_markup=music_kb()
            )
            return

        lines=["🎵 <b>MUSIQA NATIJALARI</b>","","📚 Manba: Jamendo"]
        buttons=[]
        for i,item in enumerate(results,1):
            title=item.get("title","Noma'lum")
            artist=item.get("artist","")
            lines.append(f"{i}. <b>{title}</b>" + (f" — {artist}" if artist else ""))
            key=secrets.token_urlsafe(8)
            context.user_data.setdefault("audio_store",{})[key]=item
            buttons.append([InlineKeyboardButton(f"📥 {i}. {title[:28]}",callback_data=f"audio_dl:{key}")])
        await update.message.reply_text("\n".join(lines)[:4000],parse_mode="HTML",reply_markup=InlineKeyboardMarkup(buttons))
        add_xp(user.id,3)
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
        results = await jamendo_search_api(text, 1)
        if not results:
            await update.message.reply_text("❌ Qo'shiq topilmadi.", reply_markup=music_kb())
            return
        item = results[0]
        url = item.get("url")
        if url:
            key = secrets.token_urlsafe(8)
            audio_store = context.user_data.setdefault("audio_store", {})
            audio_store[key] = {
                "url": url,
                "title": item.get("title", "Audio"),
                "artist": item.get("artist", "")
            }
            if len(audio_store) > 20:
                for old_key in list(audio_store)[:-20]:
                    audio_store.pop(old_key, None)

            await update.message.reply_text(
                f"🎧 <b>{item.get('title', 'Noma’lum')}</b>\n"
                f"{item.get('artist','')}\n\n"
                "🔗 Havola tayyor. Pastdagi tugma orqali audio faylni yuklab oling.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Audioni yuklab olish", callback_data=f"audio_dl:{key}")]
                ])
            )
        else:
            await update.message.reply_text(
                f"🎧 {item.get('title', 'Noma’lum')}\n"
                "❌ Audio havolasi topilmadi.",
                reply_markup=music_kb()
            )
        add_xp(user.id, 3)
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
    mode=context.user_data.get("mode")
    if mode=="payment_receipt":
        pid=context.user_data.get("payment_id")
        payment=get_payment(pid) if pid else None
        if not payment or payment[3]!="pending":
            await update.message.reply_text("❌ To'lov arizasi topilmadi.",reply_markup=home_reply_kb(user.id)); return
        admin_text=f"💳 <b>YANGI TO'LOV ZAYAVKASI</b>\n\n🆔 User ID: <code>{user.id}</code>\n👤 @{user.username or 'yoq'}\n💰 Summa: <b>{payment[2]:,} UZS</b>\n🧾 Ariza: <code>#{pid}</code>"
        kb_admin=InlineKeyboardMarkup([[InlineKeyboardButton('✅ Tasdiqlash',callback_data=f'pay_confirm:{pid}'),InlineKeyboardButton('❌ Rad etish',callback_data=f'pay_reject:{pid}')]])
        try:
            await context.bot.send_photo(ADMIN_ID,update.message.photo[-1].file_id,caption=admin_text,parse_mode='HTML',reply_markup=kb_admin)
            context.user_data.pop('mode',None); context.user_data.pop('payment_id',None)
            await update.message.reply_text("✅ Chek adminga yuborildi. Tasdiqlanishini kuting.",reply_markup=home_reply_kb(user.id))
        except Exception as e:
            log.exception(e); await update.message.reply_text("❌ Chekni adminga yuborib bo'lmadi.",reply_markup=home_reply_kb(user.id))
        return
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
    try:
        me=await context.bot.get_me()
        uname="@"+(me.username or BOT_USERNAME).lstrip("@")
    except Exception:
        uname=bot_username_text()

    if not raw:
        results=[
            InlineQueryResultArticle(
                id="calc",
                title="🧮 Kalkulyator",
                description="25+35*2",
                input_message_content=InputTextMessageContent(
                    "🧮 Misol: " + uname + " 25+35*2"
                )
            ),
            InlineQueryResultArticle(
                id="music",
                title="🎵 Musiqa",
                description="Artist yoki qo'shiq",
                input_message_content=InputTextMessageContent(
                    "🎵 Misol: " + uname + " musiqa Artist"
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
            song=raw.split(maxsplit=1)[1].strip()
            music_results=await music_search_best(song,8)
            if music_results:
                for idx,item in enumerate(music_results[:8],1):
                    title=item.get("title","Noma'lum")
                    artist=item.get("artist","")
                    results.insert(0,InlineQueryResultArticle(
                        id=f"music_result_{idx}",
                        title=f"🎵 {title}",
                        description=artist or "Musiqa",
                        input_message_content=InputTextMessageContent(
                            f"🎵 <b>{title}</b>" + (f" — {artist}" if artist else "") + "\n\n📥 Audio uchun botdagi Musiqa → Audio bo'limidan foydalaning.",
                            parse_mode="HTML"
                        )
                    ))
            else:
                results.insert(0,InlineQueryResultArticle(
                    id="music_result_empty",
                    title=f"🎵 {song}",
                    description="Musiqa topilmadi",
                    input_message_content=InputTextMessageContent(f"❌ <b>{song}</b> topilmadi.",parse_mode="HTML")
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
    if not is_admin_user(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q."); return
    con=db()
    users=con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    balance=con.execute("SELECT COALESCE(SUM(coins),0) FROM users").fetchone()[0]
    today=con.execute("SELECT messages FROM stats WHERE day=?",(date.today().isoformat(),)).fetchone()
    vip_count=con.execute("SELECT COUNT(*) FROM vip_users WHERE expires_at>?",(datetime.now().isoformat(),)).fetchone()[0]
    payments=con.execute("SELECT COUNT(*),COALESCE(SUM(amount),0) FROM payment_requests WHERE status='approved'").fetchone()
    pending=con.execute("SELECT COUNT(*) FROM payment_requests WHERE status='pending'").fetchone()[0]
    con.close()
    await update.message.reply_text(
        f"📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users:,}</b>\n"
        f"💳 Jami balans: <b>{balance:,} UZS</b>\n"
        f"👑 Aktiv VIP: <b>{vip_count:,}</b>\n"
        f"💰 Tasdiqlangan to'lov: <b>{payments[1]:,} UZS</b> ({payments[0]} ta)\n"
        f"⏳ Kutilayotgan to'lovlar: <b>{pending}</b>\n"
        f"💬 Bugungi xabarlar: <b>{today[0] if today else 0:,}</b>",parse_mode="HTML")


async def admin_text_router(update,context,text):
    user=update.effective_user
    mode=context.user_data.get("admin_mode")
    if mode=="payment_card":
        card=re.sub(r"[^0-9 ]","",text).strip()
        if len(re.sub(r"\D","",card))<12:
            await update.message.reply_text("❌ Karta raqami noto'g'ri.",reply_markup=admin_reply_kb()); return
        set_config("payment_card",card); context.user_data.pop("admin_mode",None)
        await update.message.reply_text(f"✅ Karta saqlandi: <code>{card}</code>",parse_mode='HTML',reply_markup=admin_reply_kb()); return
    if mode=="user_manage":
        try: uid=int(text); r=user_row(uid)
        except: r=None
        if not r:
            await update.message.reply_text("❌ User topilmadi.",reply_markup=admin_reply_kb()); return
        context.user_data["managed_user"]=uid; context.user_data.pop("admin_mode",None)
        kb_user=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Pul qo'shish",callback_data=f'user_add:{uid}'),InlineKeyboardButton('➖ Pul ayirish',callback_data=f'user_sub:{uid}')]])
        await update.message.reply_text(f"👤 <b>USER</b>\n\nID: <code>{uid}</code>\nUsername: @{r[1] or 'yoq'}\n💳 Balans: <b>{r[3]:,} UZS</b>",parse_mode='HTML',reply_markup=kb_user); return
    if mode=="admin_amount_add" or mode=="admin_amount_sub":
        try: amount=int(text.replace(',','').replace(' ',''))
        except: await update.message.reply_text("❌ Faqat raqam kiriting.",reply_markup=admin_reply_kb()); return
        uid=context.user_data.get("managed_user")
        if not uid: await update.message.reply_text("❌ User tanlanmagan.",reply_markup=admin_reply_kb()); return
        if mode=="admin_amount_sub": amount=-abs(amount)
        else: amount=abs(amount)
        add_coins(uid,amount); context.user_data.pop("admin_mode",None)
        await update.message.reply_text(f"✅ Balans o'zgartirildi: {amount:+,} UZS",reply_markup=admin_reply_kb())
        try: await context.bot.send_message(uid,f"💳 Hisobingizga <b>{amount:+,} UZS</b> o'zgartirish kiritildi.",parse_mode='HTML')
        except: pass
        return
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
        # Start matni bot_config jadvaliga doimiy saqlanadi.
        # Keyingi /start aynan shu qiymatni o'qiydi.
        clean_text = text.strip()
        if not clean_text:
            await update.message.reply_text("❌ Start matni bo'sh bo'lishi mumkin emas.",reply_markup=admin_reply_kb())
            return
        set_config("start_text", clean_text)
        saved = get_config("start_text")
        context.user_data.pop("admin_mode",None)
        if saved == clean_text:
            await update.message.reply_text("✅ Start matni saqlandi va tekshirildi. Endi o'zi qaytib ketmaydi.",reply_markup=admin_reply_kb())
        else:
            await update.message.reply_text("❌ Start matnini saqlashda xatolik yuz berdi.",reply_markup=admin_reply_kb())
        return
    if mode=="vip_price":
        try: price=max(0,int(text)); set_config("vip_price_uzs",price); context.user_data.pop("admin_mode",None); await update.message.reply_text(f"✅ VIP narxi: {price:,} UZS",reply_markup=admin_reply_kb())
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
        context.user_data["managed_user"]=uid
        manage_kb=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Pul qo'shish",callback_data=f"user_add:{uid}"),InlineKeyboardButton("➖ Pul ayirish",callback_data=f"user_sub:{uid}")]])
        await update.message.reply_text(f"👤 <b>USER</b>\n\nID: <code>{r[0]}</code>\nUsername: @{r[1] or 'yo‘q'}\nIsm: {r[2]}\n💳 Balans: <b>{r[3]:,} UZS</b>\n⭐ XP: {r[4]}\n🏆 Level: {r[5]}",parse_mode="HTML",reply_markup=manage_kb); return

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
        price=get_config("vip_price_uzs","20000"); days=get_config("vip_days","30"); enabled=get_config("vip_enabled","1")
        await update.message.reply_text(f"👑 <b>VIP SOZLAMALARI</b>\n\nHolat: {'✅ Yoqilgan' if enabled=='1' else '❌ O‘chirilgan'}\n💰 Narx: {price} 🪙\n📅 Muddat: {days} kun",parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💰 Narx",callback_data="admin_vip_price"),InlineKeyboardButton("📅 Muddat",callback_data="admin_vip_days")],[InlineKeyboardButton("🔄 ON/OFF",callback_data="admin_vip_toggle")]])); return
    if text=="💳 Karta sozlash":
        current=get_config("payment_card","o'rnatilmagan")
        context.user_data["admin_mode"]="payment_card"
        await update.message.reply_text(f"💳 <b>KARTA SOZLASH</b>\n\nHozirgi: <code>{current}</code>\n\nYangi karta raqamini yuboring:",parse_mode='HTML',reply_markup=admin_reply_kb()); return
    if text=="👥 User boshqaruv":
        context.user_data["admin_mode"]="user_lookup"
        await update.message.reply_text("👥 User ID yuboring:",reply_markup=admin_reply_kb()); return
    if text=="📝 Start qismi":
        current=get_config("start_text") or os.getenv("START_TEXT", "").strip() or "Standart start matni"
        await update.message.reply_text("📝 <b>START QISMI</b>\n\nHozirgi matn:\n"+current+"\n\nYangi start matnini yuboring:",parse_mode="HTML",reply_markup=admin_reply_kb()); context.user_data["admin_mode"]="start_text"; return
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
# PAYMENT / USER ADMIN CALLBACKS
# ============================================================
async def payment_user_admin_callback(update,context):
    q=update.callback_query; await q.answer()
    if not is_admin_user(q.from_user.id): return
    d=q.data
    if d.startswith('pay_confirm:') or d.startswith('pay_reject:'):
        pid=int(d.split(':',1)[1]); payment=get_payment(pid)
        if not payment or payment[3] != 'pending':
            await q.answer("Ariza allaqachon ko'rilgan.",show_alert=True); return
        uid,amount=payment[1],payment[2]
        if d.startswith('pay_confirm:'):
            add_coins(uid,amount); set_payment_status(pid,'approved')
            await q.edit_message_caption(caption=f"✅ <b>TASDIQLANDI</b>\n\n🆔 {uid}\n💰 {amount:,} UZS\n🧾 #{pid}",parse_mode='HTML')
            await context.bot.send_message(uid,f"🎉 <b>To'lov tasdiqlandi!</b>\n\nHisobingizga <b>{amount:,} so'm</b> qo'shildi.\n💳 Yangi balans: <b>{balance_uzs(uid):,} UZS</b>",parse_mode='HTML')
        else:
            set_payment_status(pid,'rejected')
            await q.edit_message_caption(caption=f"❌ <b>RAD ETILDI</b>\n\n🆔 {uid}\n💰 {amount:,} UZS\n🧾 #{pid}",parse_mode='HTML')
            await context.bot.send_message(uid,f"❌ <b>To'lov zayavkangiz rad etildi.</b>\n\nAriza: #{pid}",parse_mode='HTML')
        return
    if d.startswith('user_add:') or d.startswith('user_sub:'):
        uid=int(d.split(':',1)[1]); context.user_data['managed_user']=uid; context.user_data['admin_mode']='admin_amount_add' if d.startswith('user_add:') else 'admin_amount_sub'
        await q.message.reply_text('💰 Summani UZS da yuboring:',reply_markup=admin_reply_kb()); return

# ============================================================
# ERROR / MAIN
# ============================================================

async def error_handler(update,context):
    log.exception("Unhandled error",exc_info=context.error)

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variableini kiriting.")

    init_db()
    log.info("Database: %s", os.path.abspath(DB_FILE))

    app=Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CommandHandler("admin",admin_cmd))
    app.add_handler(CommandHandler("adminstats",adminstats))
    app.add_handler(InlineQueryHandler(inline))
    app.add_handler(CallbackQueryHandler(payment_user_admin_callback, pattern=r"^(pay_confirm|pay_reject|user_add|user_sub):"))
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
