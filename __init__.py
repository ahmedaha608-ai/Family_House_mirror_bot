import os
from pyrogram import Client
import config

# قراءة المتغيرات بأمان
API_ID = int(os.getenv("API_ID", config.API_ID))
API_HASH = os.getenv("API_HASH", config.API_HASH).strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", config.BOT_TOKEN).strip()

app = Client(
    "qb_leech_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# استيراد ملف الأوامر بشكل صحيح من المجلد الرئيسي
import commands

if __name__ == "__main__":
    app.run()
