import os, time, shutil, asyncio, yt_dlp
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from config import app

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
user_thumbs = {}
active_tasks = {}

# ==========================================
# 🛠️ دالة الرد الآمن (الإلغاء والتحميل)
# ==========================================
async def cancel_task(key):
    active_tasks[key] = "cancelled"
    path = os.path.join(DOWNLOAD_DIR, f"{key}.mp4")
    if os.path.exists(path): os.remove(path)

# ==========================================
# 🚀 الأوامر والخدمات
# ==========================================
@app.on_message(filters.command("setthumb") & filters.reply)
async def set_thumb(_, m: Message):
    if not m.reply_to_message.photo: return await m.reply("❌ يجب الرد على صورة.")
    path = await m.reply_to_message.download(file_name=f"thumb_{m.from_user.id}.jpg")
    user_thumbs[m.from_user.id] = path
    await m.reply("✅ تم حفظ الصورة كخلفية للفيديو.")

@app.on_message(filters.command("Leechmicky"))
async def leech_micky(_, m: Message):
    if len(m.command) < 2: return await m.reply("أرسل الرابط بعد الأمر.")
    url, key = m.command[1], str(m.id)
    active_tasks[key] = "active"
    msg = await m.reply("📥 جاري التحميل التوربو...")
    path = os.path.join(DOWNLOAD_DIR, f"{key}.mp4")
    
    def hook(d):
        if active_tasks.get(key) == "cancelled": raise Exception("CANCELLED")
    
    opts = {'outtmpl': path, 'progress_hooks': [hook], 'quiet': True}
    try:
        await asyncio.to_thread(yt_dlp.YoutubeDL(opts).download, [url])
        await msg.edit("📤 جاري الرفع...")
        await m.reply_video(path, thumb=user_thumbs.get(m.from_user.id))
        await msg.delete()
    except: await msg.edit("❌ تم إلغاء العملية أو فشل التحميل.")
    if os.path.exists(path): os.remove(path)

@app.on_message(filters.command("reduce"))
async def reduce_micky(_, m: Message):
    if not m.reply_to_message or not m.reply_to_message.video: return await m.reply("❌ رد على فيديو.")
    msg = await m.reply("🗜️ جاري الضغط (Reduce)...")
    path = await m.reply_to_message.download()
    out = f"comp_{m.id}.mp4"
    await (await asyncio.create_subprocess_shell(f'ffmpeg -i "{path}" -vf scale=-2:480 -vcodec libx265 -crf 28 "{out}"')).communicate()
    await m.reply_video(out, thumb=user_thumbs.get(m.from_user.id))
    os.remove(path); os.remove(out); await msg.delete()

@app.on_message(filters.command("Ytdlleechmicky"))
async def ytdl_micky(_, m: Message):
    url = m.command[1]
    msg = await m.reply("🔍 جاري جلب الجودات...")
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        btns = [[InlineKeyboardButton(f"{f.get('format_note')}p", callback_data=f"dl_{f.get('format_id')}")] for f in info['formats'] if f.get('height')]
        await msg.edit("اختر الجودة:", reply_markup=InlineKeyboardMarkup(btns))

@app.on_message(filters.command("Settingmicky"))
async def settings_micky(_, m: Message):
    txt = "⚙️ **قائمة الأوامر الأساسية:**\n\n🎬 `/Leechmicky [URL]` - تحميل سريع\n🗜️ `/reduce` - ضغط الفيديو بالرد\n🖼️ `/setthumb` - حفظ صورة الغلاف\n🧹 `/cleanmicky` - تنظيف السيرفر"
    await m.reply(txt)

@app.on_message(filters.command("cleanmicky"))
async def clean_micky(_, m: Message):
    if m.from_user.id != 7030252495: return await m.reply("للأدمن فقط!")
    for f in os.listdir(DOWNLOAD_DIR): 
        try: os.remove(os.path.join(DOWNLOAD_DIR, f))
        except: pass
    await m.reply("🧹 تم تنظيف السيرفر بنجاح.")

@app.on_callback_query(filters.regex("^cancel_"))
async def cancel(_, q):
    key = q.data.split("_")[1]
    await cancel_task(key)
    await q.message.edit("❌ تم الإلغاء.")
