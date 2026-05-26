import os
from pyrogram import Client

# قراءة المتغيرات من Railway
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

DOWNLOAD_DIR = "downloads"

# إنشاء كائن البوت هنا لمنع التداخل الدائري (Circular Import)
app = Client(
    "qb_leech_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)
