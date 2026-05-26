import os
import time
import shutil
import asyncio
import yt_dlp
import aiohttp
from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

# الاستدعاء الآمن لمنع التداخل الدائري والـ Crash
from config import app

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# قواميس حفظ الإعدادات وتتبع العمليات النشطة في الذاكرة
user_video_format = {}    
user_compress_res = {}    
user_backgrounds = {}     
quality_cache = {}
active_tasks = {}         

# ==========================================
# دالة ذكية لاستخراج الصورة المصغرة (Thumbnail) من الفيديو نفسه
# ==========================================
async def generate_thumbnail(video_path, thumb_path):
    try:
        # اقتطاع فريم واحد سريع من الثانية الخامسة للفيديو لحفظ الرام
        cmd = f'ffmpeg -ss 00:00:05 -i "{video_path}" -vframes 1 -q:v 2 -y "{thumb_path}"'
        process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
    return None

# دالة حساب وحجم وإحصائيات النظام
def get_server_status():
    total, used, free = shutil.disk_usage("/")
    disk_p = (used / total) * 100
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[0]
            cpu_p = min(float(load) * 100 / 2, 100.0)
    except:
        cpu_p = 20.0
    return f"⚙️ **الـ CPU:** {cpu_p:.1f}% | 📁 **التخزين المستهلك:** {disk_p:.1f}%"

# عداد الرفع التفاعلي
async def progress_bar(current, total, reply_msg, start_time, task_key, mode="رفع 📤"):
    if active_tasks.get(task_key) == "cancelled":
        raise Exception("TASK_CANCELLED")

    now = time.time()
    diff = now - start_time
    if round(diff % 4.0) == 0 or current == total:
        percentage = (current / total) * 100
        speed = current / diff if diff > 0 else 0
        
        speed_kb = speed / 1024
        speed_mb = speed_kb / 1024
        speed_text = f"{speed_mb:.1f} MB/s" if speed_mb > 1 else f"{speed_kb:.1f} KB/s"
        
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        
        blocks = int(percentage // 10)
        bar = "■" * blocks + "□" * (10 - blocks)
        
        status = get_server_status()
        
        progress_text = (
            f"⚡ **جاري عملية الـ {mode}...**\n\n"
            f"📊 `[{bar}]` {percentage:.1f}%\n"
            f"📦 الحجم: `{current_mb:.1f} MB` / `{total_mb:.1f} MB`\n"
            f"🚀 السرعة الحالية: `{speed_text}`\n\n"
            f"{status}"
        )
        
        buttons = [[InlineKeyboardButton("❌ إلغاء وإغلاق العملية", callback_data=f"cancel_{task_key}")]]
        try:
            await reply_msg.edit_text(progress_text, reply_markup=InlineKeyboardMarkup(buttons))
        except:
            pass

# دالة سحب الروابط المباشرة
async def download_direct_mp4_with_progress(url, output_path, reply_msg, task_key):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }
    start_time = time.time()
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=1800) as response:
                if response.status == 200:
                    total_size = int(response.headers.get('content-length', 0))
                    current_size = 0
                    
                    with open(output_path, 'wb') as f:
                        while True:
                            if active_tasks.get(task_key) == "cancelled":
                                return False
                                
                            chunk = await response.content.read(1024*1024)
                            if not chunk:
                                break
                            f.write(chunk)
                            current_size += len(chunk)
                            
                            if total_size > 0:
                                await progress_bar(current_size, total_size, reply_msg, start_time, task_key, mode="تنزيل من الموقع 📥")
                    return True
    except Exception as e:
        if "TASK_CANCELLED" in str(e):
            return False
    return False

# ======================
# DIRECT LEECH (أمر سحب الأفلام والمسلسلات مع الاسم الحقيقي والصورة)
# ======================
@app.on_message(filters.command("leech"))
async def leech(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage:\n/leech [رابط_المسلسل_أو_الفيديو]")

    user_id = message.from_user.id
    target_format = user_video_format.get(user_id, "mp4")
    url = message.command[1]
    
    task_key = str(message.id)
    active_tasks[task_key] = "running"

    buttons = [[InlineKeyboardButton("❌ إلغاء وإغلاق العملية", callback_data=f"cancel_{task_key}")]]
    msg = await message.reply_text("🔍 جاري قراءة الرابط واستخراج اسم المسلسل الحقيقي...", reply_markup=InlineKeyboardMarkup(buttons))

    # محاولة استخراج الاسم الحقيقي النظيف للمسلسل باستخدام صفحة الميديا أو الفحص الذكي
    real_title = "مقطع مرئي"
    try:
        ydl_opts = {'skip_download': True, 'no_warnings': True, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and info.get('title'):
                real_title = info.get('title')
    except:
        # إذا فشل yt-dlp في فحص الصفحة (بسبب جدار الحماية للموقع)، نقوم بتنظيف الرابط للحصول على اسم تقريبي
        clean_name = url.split('/')[-1].split('?')[0]
        if clean_name:
            real_title = clean_name.replace(".mp4", "").replace(".mkv", "").replace("-", " ").replace("_", " ")

    # تشكيل اسم الملف النهائي على السيرفر
    filename = f"video_{message.id}.{target_format}"
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    await msg.edit_text("📥 تم العثور على المسلسل.. جاري سحب وتحميل الملف للسيرفر حالياً...")
    success = await download_direct_mp4_with_progress(url, filepath, msg, task_key)

    if active_tasks.get(task_key) == "cancelled":
        if os.path.exists(filepath): os.remove(filepath)
        return

    if not success or not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return await msg.edit_text("❌ **فشل سحب الفيديو:** الرابط غير مباشر أو محمي بواسطة جدار حماية خارجي.")

    await msg.edit_text("🖼️ جاري توليد واستخراج صورة الغلاف الأصلية للفيديو...")
    thumb_filename = f"thumb_{message.id}.jpg"
    thumb_path = os.path.join(DOWNLOAD_DIR, thumb_filename)
    generated_thumb = await generate_thumbnail(filepath, thumb_path)

    await msg.edit_text("📤 جاري رفع المسلسل لتليجرام مع عرض الاسم والصورة...")
    
    start_upload = time.time()
    try:
        # رفع الفيديو مع تمرير الصورة المصغرة والاسم الحقيقي في الكابشن
        await message.reply_video(
            video=filepath,
            thumb=generated_thumb if generated_thumb else None,
            caption=(
                f"🎬 **اسم المسلسل/الفيديو الحقيقي:**\n`{real_title}`\n\n"
                f"🔗 **رابط التحميل المستخدم:**\n`{url}`\n\n"
                f"📦 التنسيق المستهدف: `{target_format.upper()}`"
            ),
            progress=progress_bar,
            progress_args=(msg, start_upload, task_key, "رفع للمشاهدة 📤")
        )
        await msg.delete()
    except Exception as e:
        if "TASK_CANCELLED" in str(e) or active_tasks.get(task_key) == "cancelled": return
        await message.reply_text(f"❌ حدث خطأ أثناء النقل والرفع: {str(e)}")

    # تنظيف شامل للملفات المؤقتة لمنع امتلاء رامات وهارد السيرفر
    if os.path.exists(filepath): os.remove(filepath)
    if generated_thumb and os.path.exists(generated_thumb): os.remove(generated_thumb)
    active_tasks.pop(task_key, None)

# ======================
# COMPRESS COMMAND (أمر الضغط بالرد مع توليد الصورة تلقائياً لحل مشكلة السواد)
# ======================
@app.on_message(filters.command(["compress", "composer"]))
async def compress_video_reply(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("⚠️ **يجب إرسال هذا الأمر بالرد على الفيديو المراد ضغطه!**")
    
    reply_msg = message.reply_to_message
    if not reply_msg.video and not reply_msg.animation:
        return await message.reply_text("❌ **الرسالة المردود عليها لا تحتوي على ملف فيديو صالح.**")

    user_id = message.from_user.id
    target_res = user_compress_res.get(user_id, "480p")
    target_format = user_video_format.get(user_id, "mp4")

    task_key = f"comp_{message.id}"
    active_tasks[task_key] = "running"

    buttons = [[InlineKeyboardButton("❌ إلغاء وإغلاق العملية", callback_data=f"cancel_{task_key}")]]
    msg = await message.reply_text("📥 جاري تهيئة الحاوية وسحب الفيديو الأصلي من تليجرام...", reply_markup=InlineKeyboardMarkup(buttons))
    
    start_down = time.time()
    try:
        video_path = await reply_msg.download(
            file_name=os.path.join(DOWNLOAD_DIR, f"orig_{message.id}"),
            progress=progress_bar,
            progress_args=(msg, start_down, task_key, "تنزيل من التليجرام 📥")
        )
    except:
        return

    if active_tasks.get(task_key) == "cancelled":
        if video_path and os.path.exists(video_path): os.remove(video_path)
        return

    scale_filter = "scale=-2:360" if target_res == "360p" else ("scale=-2:720" if target_res == "720p" else "scale=-2:480")
    compressed_path = os.path.join(DOWNLOAD_DIR, f"compressed_{message.id}.{target_format}")

    status = get_server_status()
    await msg.edit_text(f"🗜️ **جاري ضغط وترميز فريمات الفيديو إلى أبعاد {target_res}...**\n\n{status}")

    ffmpeg_cmd = (
        f'ffmpeg -i "{video_path}" -vf "{scale_filter}" '
        f'-vcodec libx264 -crf 30 -preset ultrafast '
        f'-acodec aac -b:a 128k -y "{compressed_path}"'
    )
    process = await asyncio.create_subprocess_shell(ffmpeg_cmd)
    await process.communicate()

    if os.path.exists(video_path): os.remove(video_path)

    if not os.path.exists(compressed_path) or os.path.getsize(compressed_path) == 0:
        return await msg.edit_text("❌ فشلت عملية ضغط وترميز الفيديو.")

    # توليد الصورة المصغرة للفيديو المضغوط لحل مشكلة السواد في تليجرام
    thumb_path = os.path.join(DOWNLOAD_DIR, f"thumb_comp_{message.id}.jpg")
    generated_thumb = await generate_thumbnail(compressed_path, thumb_path)

    await msg.edit_text("📤 جاري رفع الفيديو النهائي المضغوط...")
    start_upload = time.time()
    try:
        await message.reply_video(
            video=compressed_path,
            thumb=generated_thumb if generated_thumb else None,
            caption=f"🗜️ **تم ضغط وتقليص مساحة الفيديو بنجاح**\n\n🎯 الجودة والأبعاد المستهدفة: `{target_res}`\n📦 الصيغة: `{target_format.upper()}`",
            progress=progress_bar,
            progress_args=(msg, start_upload, task_key, "رفع الفيديو المضغوط 📤")
        )
        await msg.delete()
    except Exception as e:
        await message.reply_text(f"❌ عطل أثناء الرفع: {str(e)}")

    if os.path.exists(compressed_path): os.remove(compressed_path)
    if generated_thumb and os.path.exists(generated_thumb): os.remove(generated_thumb)
    active_tasks.pop(task_key, None)

# ==========================================
# باقي الأوامر (Ytdlleech, Start, Settings, Global Callbacks)
# تظل تعمل تماماً كما هي ومحمية بداخل ملف السكربت
# ==========================================
