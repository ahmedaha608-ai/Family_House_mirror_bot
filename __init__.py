import os
from pyrogram import Client
import config

print("⚡ الجاري تهيئة البوت والمصادقة...")

try:
    API_ID = int(os.getenv("API_ID", config.API_ID))
    API_HASH = os.getenv("API_HASH", config.API_HASH).strip()
    BOT_TOKEN = os.getenv("BOT_TOKEN", config.BOT_TOKEN).strip()
except Exception as e:
    print(f"❌ خطأ في قراءة متغيرات البيئة: {e}")
    API_ID = 12345
    API_HASH = "placeholder"
    BOT_TOKEN = "placeholder"

# إنشاء كائن البوت
app = Client(
    "qb_leech_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# تأكيد قراءة الأوامر بربطها بـ app
with app:
    import commands
    print("✅ تم تحميل ملف الأوامر commands.py بنجاح")

if __name__ == "__main__":
    print("🚀 البوت يعمل الآن ومستعد لاستقبال الأوامر...")
    app.run()
