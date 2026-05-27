import os
import time
import shutil
import asyncio
import yt_dlp
import json
import re
import urllib.parse
import http.client
from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BotCommand
)

# الاستدعاء الآمن لربط التطبيق الخاص بك
from config import app

# 👑 معرف الأدمن والمطور الرئيسي للحماية والتحكم
ADMIN_ID = 7030252495  

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# الذاكرة المؤقتة لحفظ إعدادات المستخدمين والجلسات
user_video_format = {}    
user_compress_res = {}    
user_backgrounds = {}     
quality_cache = {}
active_tasks = {}         

# =========================================================
# 🔍 المحرك الاحترافي المطور لتخطي حماية وسحب ميديا Krakenfiles
# =========================================================
def bypass_and_get_clean_title(url):
    default_title = ""
    target_url = url
    
    # 1. إذا كان الرابط Krakenfiles، نستخدم المنطق الخاص بك (مستقر جداً)
    if "krakenfiles.com" in url:
        try:
            url = url.replace("/download/", "/view/")
            parsed_url = urllib.parse.urlparse(url)
            conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=15)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': url
            }
            conn.request("GET", parsed_url.path, headers=headers)
            response = conn.getresponse()
            html_content = response.read().decode('utf-8', errors='ignore')
            conn.close()
            
            # استخراج العنوان
            title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
            if title_match:
                default_title = re.sub(r'(?i)-\s*KrakenFiles\.com', '', title_match.group(1)).strip()
            
            # استخراج الرابط
            stream_url_match = re.search(r'data-url=["\']([^"\']+?)["\']', html_content)
            if stream_url_match:
                target_url = "https:" + stream_url_match.group(1) if stream_url_match.group(1).startswith("//") else stream_url_match.group(1)
        except Exception as e:
            print(f"Kraken Engine Error: {e}")

    # 2. التعديل الشامل: إذا لم يكن الرابط Kraken، نحاول جلب العنوان فقط ليظهر للمستخدم
    else:
        try:
            # محاولة بسيطة لجلب عنوان الصفحة (Page Title) لأي رابط آخر
            parsed_url = urllib.parse.urlparse(url)
            conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=10)
            conn.request("GET", parsed_url.path, headers={'User-Agent': 'Mozilla/5.0'})
            response = conn.getresponse()
            if response.status == 200:
                html = response.read().decode('utf-8', errors='ignore')
                title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                if title_match:
                    default_title = title_match.group(1).strip()
            conn.close()
        except:
            default_title = "فيديو غير معروف" # عنوان احتياطي
            
    return target_url, default_title


# =========================================================
# 🎬 دالة ذكية لتنظيف وتنسيق المسميات (عربي وأجنبي)
# =========================================================
def clean_filename_title(raw_title):
    if not raw_title:
        return "مقطع مرئي غير مسمى"
    
    # إزالة امتدادات الملفات لو وجدت بالاسم
    for ext in [".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".html", ".htm"]:
        raw_title = re.sub(re.escape(ext), "", raw_title, flags=re.IGNORECASE)
        
    # تنظيف شامل لإعلانات ومسميات المواقع لتظهر التسمية نقية تماماً
    junk_patterns = [
        r'\[.*?\]', r'\(.*?\)', r'\{.*?\}',
        r'(?i)arabseed', r'(?i)tuktukcima', r'(?i)cima', r'(?i)egybest', r'(?i)wecima', r'(?i)mycima', r'(?i)vod',
        r'عرب\s*سيد', r'توك\s*توك\s*سيما', r'ماي\s*سيما', r'ايجي\s*بست', r'موقع', r'تحميل', r'مشاهدة', r'فيلم', r'كامل', r'مترجم'
    ]
    for pattern in junk_patterns:
        raw_title = re.sub(pattern, "", raw_title)
        
    # استبدال النقاط والخطوط بفراغات منسقة ومريحة للعين
    raw_title = raw_title.replace(".", " ").replace("-", " ").replace("_", " ").replace("+", " ")
    
    # تنظيف الفراغات المزدوجة الناتجة عن مسح الإعلانات
    clean_title = re.sub(r'\s+', ' ', raw_title).strip()
    
    return clean_title if clean_title else "مقطع مرئي"

# =========================================================
# ⚙️ أدوات مساعدة: قراءة البيانات، التوليد، وحسابات الخادم
# =========================================================
async def get_video_metadata(video_path):
    metadata = {"width": None, "height": None, "duration": 0}
    try:
        cmd = f'ffprobe -v error -show_entries format=duration:stream=width,height -of json "{video_path}"'
        process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await process.communicate()
        data = json.loads(stdout.decode('utf-8'))
        
        if "streams" in data and len(data["streams"]) > 0:
            metadata["width"] = data["streams"][0].get("width")
            metadata["height"] = data["streams"][0].get("height")
        if "format" in data:
            metadata["duration"] = int(float(data["format"].get("duration", 0)))
    except Exception as e:
        print(f"Error reading metadata: {e}")
    return metadata

async def generate_thumbnail(video_path, thumb_path):
    try:
        cmd = f'ffmpeg -ss 00:00:05 -i "{video_path}" -vframes 1 -q:v 4 -y "{thumb_path}"'
        process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path
    except:
        pass
    return None

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

# =========================================================
# 📊 شريط العداد الذكي لعمليات التنزيل والرفع
# =========================================================
async def progress_bar(current, total, reply_msg, start_time, task_key, mode="رفع 📤"):
    if active_tasks.get(task_key) == "cancelled":
        raise Exception("TASK_CANCELLED")

    now = time.time()
    diff = now - start_time
    if round(diff % 4.0) == 0 or current == total:
        percentage = (current / total) * 100 if total > 0 else 0
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

# =========================================================
# 🔄 نظام المعالجة الثنائي (Dual-Engine) لحل مشكلة فشل السحب
# =========================================================
async def download_direct_mp4_with_progress(url, output_path, reply_msg, task_key):
    start_time = time.time()
    
    def hook(d):
        if active_tasks.get(task_key) == "cancelled":
            raise Exception("TASK_CANCELLED")
            
        if d['status'] == 'downloading':
            current = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total > 0:
                asyncio.run_coroutine_threadsafe(
                    progress_bar(current, total, reply_msg, start_time, task_key, mode="تنزيل توربو ⚡📥"),
                    asyncio.get_event_loop()
                )

    # 1. المحاولة الأولى: استخدام Aria2c الخارجي لسرعة التحميل المتعدد
    ydl_opts_aria = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'progress_hooks': [hook],
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'external_downloader': 'aria2c',
        'external_downloader_args': ['-j', '16', '-x', '16', '-s', '16', '-k', '1M', '--allow-overwrite=true']
    }
    
    try:
        await asyncio.to_thread(yt_dlp.YoutubeDL(ydl_opts_aria).download, [url])
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1048576:
            return True
    except:
        pass

    # 2. المحرك الاحتياطي: التحويل التلقائي والآمن للمحرك الداخلي لبايثون في حال عطل الأداة الخارجية
    ydl_opts_native = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'progress_hooks': [hook],
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        await asyncio.to_thread(yt_dlp.YoutubeDL(ydl_opts_native).download, [url])
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1048576:
            return True
    except:
        pass
        
    return False

# =========================================================
# 🚀 الأوامر البرمجية (الخاص والمجموعات بشكل صارم وسريع)
# =========================================================

# --- START COMMAND ---
@app.on_message(filters.command("start") & (filters.private | filters.group))
async def start(_, message: Message):
    text = (
        "✅ **Qb Leech Bot Online (Kraken Dual-Engine)**\n\n"
        "**الأوامر المتاحة والمصلحة بالكامل:**\n"
        "🔹 /leech `[الرابط]` - سحب سريع مع اقتناص الاسم الحقيقي الذكي\n"
        "🔹 /ytdlleech `[الرابط]` - تنزيل المنصات واختيار الجودات\n"
        "🗜️ /compress `[بالرد]` - ضغط فيديو تلقائياً وتوفير المساحة\n"
        "⚙️ /settings - لوحة التحكم الشاملة بالتنسيقات وأبعاد المعالجة\n"
    )
    if message.from_user.id == ADMIN_ID:
        text += "👑 **مرحباً بك يا أدمن! يمكنك استخدام أمر /clean لتنظيف السيرفر.**"
    await message.reply_text(text)

# --- CLEAN COMMAND ---
@app.on_message(filters.command(["clean", "cleankmd"]) & (filters.private | filters.group))
async def clean_server_storage(_, message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply_text("❌ **عذراً، هذا الأمر مخصص فقط لمطور وأدمن البوت الرئيسي!**")

    msg = await message.reply_text("🔄 **جاري بدء عملية تهيئة السيرفر وتنظيف المساحة...**")
    start_time = time.time()
    deleted_files_count = 0
    released_space = 0

    try:
        if os.path.exists(DOWNLOAD_DIR):
            for filename in os.listdir(DOWNLOAD_DIR):
                file_path = os.path.join(DOWNLOAD_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        released_space += os.path.getsize(file_path)
                        os.unlink(file_path)
                        deleted_files_count += 1
                    elif os.path.isdir(file_path):
                        for root, dirs, files in os.walk(file_path):
                            released_space += sum(os.path.getsize(os.path.join(root, f)) for f in files)
                        shutil.rmtree(file_path)
                        deleted_files_count += 1
                except:
                    pass

        active_tasks.clear()
        quality_cache.clear()

        released_mb = released_space / (1024 * 1024)
        execution_time = time.time() - start_time
        current_status = get_server_status()

        success_text = (
            "🧹 **تم تنظيف وتهيئة سيرفر Railway بنجاح!**\n\n"
            f"🗑️ **الملفات المحذوفة:** `{deleted_files_count} ملف/مجلد مؤقت`\n"
            f"💾 **المساحة التي تم تحريرها:** `{released_mb:.2f} MB`\n"
            f"🧠 **الذاكرة العشوائية (RAM):** تم تصفير الكاش المعلق بالكامل\n"
            f"⚡ **وقت التنفيذ:** `{execution_time:.2f} ثانية`\n\n"
            f"{current_status}"
        )
        await msg.edit_text(success_text)
    except Exception as e:
        await msg.edit_text(f"❌ **حدث خطأ غير متوقع أثناء عملية التهيئة:**\n`{str(e)}`")

# --- DIRECT LEECH COMMAND ---
@app.on_message(filters.command(["leech", "leechkmd"]) & (filters.private | filters.group))
async def leech(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage:\n/leech [رابط_الفيديو]")

    user_id = message.from_user.id
    target_format = user_video_format.get(user_id, "mp4")
    raw_url = message.command[1]
    
    task_key = str(message.id)
    active_tasks[task_key] = "running"

    buttons = [[InlineKeyboardButton("❌ إلغاء وإغلاق العملية", callback_data=f"cancel_{task_key}")]]
    msg = await message.reply_text("🔍 جاري فك شفرات الحماية للموقع واقتناص الاسم النظيف...", reply_markup=InlineKeyboardMarkup(buttons))

    # فك الرابط واقتناص الاسم النظيف من صفحة العرض
    url, page_extracted_title = bypass_and_get_clean_title(raw_url)

    if not page_extracted_title:
        try:
            ydl_opts_meta = {'quiet': True, 'no_warnings': True, 'nocheckcertificate': True}
            with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
                info = ydl.extract_info(url, download=False)
                page_extracted_title = info.get('title', '')
        except:
            pass

    if not page_extracted_title:
        try:
            decoded_url = urllib.parse.unquote(raw_url)
            page_extracted_title = decoded_url.split('/')[-1].split('?')[0]
        except:
            page_extracted_title = f"مسلسل_أو_فيلم_{message.id}"

    # تمرير الاسم عبر دالة التنظيف المعتمدة ليعود بشكل نقي
    real_title = clean_filename_title(page_extracted_title)
    
    filename = f"video_{message.id}.{target_format}"
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    await msg.edit_text(f"🎬 **الاسم المستخرج الحقيقي:**\n🎯 `{real_title}`\n\nجاري السحب والتحميل الفعلي المتوازن...")
    success = await download_direct_mp4_with_progress(url, filepath, msg, task_key)

    if active_tasks.get(task_key) == "cancelled":
        if os.path.exists(filepath): os.remove(filepath)
        return

    # فحص أمني لمنع رفع الملفات المعطلة أو الصفحات الوهمية أقل من 1 ميجابايت
    if not success or not os.path.exists(filepath) or os.path.getsize(filepath) < 1048576:
        if os.path.exists(filepath): os.remove(filepath)
        return await msg.edit_text("❌ **فشلت عملية سحب ومعالجة حجم الفيديو الفعلي:** تأكد من إرسال رابط العرض (View Link) وليس رابط التنزيل المباشر الموقوف.")

    await msg.edit_text("🖼️ جاري قراءة الأبعاد وتوليد بوستر العرض الذكي...")
    meta = await get_video_metadata(filepath)
    
    thumb_filename = f"thumb_{message.id}.jpg"
    thumb_path = os.path.join(DOWNLOAD_DIR, thumb_filename)
    generated_thumb = await generate_thumbnail(filepath, thumb_path)

    await msg.edit_text("📤 اكتمل السحب! جاري الرفع بالاسم الصحيح الحقيقي...")
    
    start_upload = time.time()
    try:
        await message.reply_video(
            video=filepath,
            thumb=generated_thumb if generated_thumb else None,
            width=meta["width"] if meta["width"] else 1280,   
            height=meta["height"] if meta["height"] else 720, 
            duration=meta["duration"],                       
            caption=(
                f"🎬 **اسم المسلسل / الفيلم:**\n`{real_title}`\n\n"
                f"📦 المحرك المستخدم: `Kraken Dual-Engine`"
            ),
            progress=progress_bar,
            progress_args=(msg, start_upload, task_key, "رفع للمشاهدة 📤")
        )
        await msg.delete()
    except Exception as e:
        if os.path.exists(filepath): os.remove(filepath)
        if "TASK_CANCELLED" in str(e) or active_tasks.get(task_key) == "cancelled": return
        await message.reply_text(f"❌ حدث خطأ أثناء الرفع: {str(e)}")

    if os.path.exists(filepath): os.remove(filepath)
    if generated_thumb and os.path.exists(generated_thumb): os.remove(generated_thumb)
    active_tasks.pop(task_key, None)

# --- COMPRESS COMMAND ---
@app.on_message(filters.command(["compress", "compresskmd"]) & (filters.private | filters.group))
async def compress_video_reply(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("⚠️ **يجب إرسال هذا الأمر بالرد على الفيديو المراد ضغطه!**")
    
    reply_msg = message.reply_to_message
    if not reply_msg.video and not reply_msg.animation:
        return await message.reply_text("❌ **الرسالة المردود عليها لا تحتوي على ميديا فيديو صالحة.**")

    user_id = message.from_user.id
    target_res = user_compress_res.get(user_id, "480p")
    target_format = user_video_format.get(user_id, "mp4")

    task_key = f"comp_{message.id}"
    active_tasks[task_key] = "running"

    buttons = [[InlineKeyboardButton("❌ إلغاء وإغلاق العملية", callback_data=f"cancel_{task_key}")]]
    msg = await message.reply_text("📥 جاري سحب الفيديو الأصلي من تليجرام...", reply_markup=InlineKeyboardMarkup(buttons))
    
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
    await msg.edit_text(f"🗜️ **جاري معالجة الكودك وضغط الفريمات عبر FFmpeg المدمج {target_res}...**\n\n{status}")

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

    meta = await get_video_metadata(compressed_path)
    thumb_path = os.path.join(DOWNLOAD_DIR, f"thumb_comp_{message.id}.jpg")
    generated_thumb = await generate_thumbnail(compressed_path, thumb_path)

    await msg.edit_text("📤 اكتمل الضغط! جاري بدء رفع الفيديو النهائي...")
    start_upload = time.time()
    try:
        await message.reply_video(
            video=compressed_path,
            thumb=generated_thumb if generated_thumb else None,
            width=meta["width"] if meta["width"] else 854,
            height=meta["height"] if meta["height"] else 480,
            duration=meta["duration"],
            caption=f"🗜️ **تم ضغط وتقليص مساحة الفيديو بنجاح**\n\n🎯 الجودة المحددة: `{target_res}`\n📦 الصيغة الإلزامية: `{target_format.upper()}`",
            progress=progress_bar,
            progress_args=(msg, start_upload, task_key, "رفع الفيديو المضغوط 📤")
        )
        await msg.delete()
    except Exception as e:
        await message.reply_text(f"❌ عطل أثناء الرفع: {str(e)}")

    if os.path.exists(compressed_path): os.remove(compressed_path)
    if generated_thumb and os.path.exists(generated_thumb): os.remove(generated_thumb)
    active_tasks.pop(task_key, None)

# --- YOUTUBE-DL MULTI-PLATFORM ---
@app.on_message(filters.command(["ytdlleech", "ytdlleechkmd"]) & (filters.private | filters.group))
async def ytdlleech(_, message: Message):
    if len(message.command) < 2: return await message.reply_text("Usage:\n/ytdlleech [link]")
    raw_url = message.command[1]
    msg = await message.reply_text("🔍 جاري فحص ومصادقة جودات المنصة المتاحة...")
    
    url, page_extracted_title = bypass_and_get_clean_title(raw_url)
    try:
        ydl_opts = {
            'skip_download': True, 
            'no_warnings': True, 
            'quiet': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])
            if not page_extracted_title:
                page_extracted_title = info.get("title", "")

        buttons = []
        seen_resolutions = set()
        for f in formats:
            if f.get("vcodec") != "none":
                res = f.get("height")
                if res and res not in seen_resolutions:
                    seen_resolutions.add(res)
                    fid = f.get("format_id")
                    note = f.get("format_note") or f"{res}p"
                    ext = f.get("ext", "mp4")
                    key = f"{message.id}_{fid}"
                    quality_cache[key] = {"url": url, "format": fid, "raw_url": raw_url, "title": page_extracted_title}
                    buttons.append([InlineKeyboardButton(text=f"🎬 جودة: {note} ({ext.upper()})", callback_data=f"yt_{key}")])

        if not buttons:
            key = f"{message.id}_best"
            quality_cache[key] = {"url": url, "format": "best", "raw_url": raw_url, "title": page_extracted_title}
            buttons.append([InlineKeyboardButton(text="🎬 تحميل تلقائي بأفضل جودة", callback_data=f"yt_{key}")])
        await msg.edit("🎬 **اختر الجودة المطلوبة لبدء السحب والرفع:**", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await msg.edit("🎬 **جاري التحويل التلقائي للسحب عبر محرك العناوين الحقيقي المباشر...**")
        message.command = ["leech", raw_url]
        await leech(_, message)

@app.on_callback_query(filters.regex("^yt_"))
async def quality_download(_, query: CallbackQuery):
    await query.answer("🚀 جاري دمج البيانات وسحب الملف الفعلي..")
    
    user_id = query.from_user.id
    target_format = user_video_format.get(user_id, "mp4")
    key = query.data.replace("yt_", "")
    
    if key not in quality_cache: 
        return await query.message.edit("⚠️ **انتهت صلاحية البيانات المؤقتة بالجلسة الكاش.**")
        
    data = quality_cache[key]
    url = data["url"]
    fmt = data["format"]
    raw_url = data["raw_url"]
    cached_title = data["title"]

    task_key = f"yt_{query.message.id}"
    active_tasks[task_key] = "running"

    buttons = [[InlineKeyboardButton("❌ إلغاء وإغلاق العملية", callback_data=f"cancel_{task_key}")]]
    await query.message.edit("📥 جاري سحب الجودة الحقيقية للملف من السيرفر...", reply_markup=InlineKeyboardMarkup(buttons))

    output_template = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    
    def hook(d):
        if d['status'] == 'downloading':
            current = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total > 0:
                asyncio.run_coroutine_threadsafe(
                    progress_bar(current, total, query.message, time.time(), task_key, mode="تنزيل من المنصة 📥"),
                    asyncio.get_event_loop()
                )

    cmd_opts = {
        'format': f"{fmt}+ba/best",
        'outtmpl': output_template,
        'merge_output_format': target_format,
        'recode_video': target_format,
        'progress_hooks': [hook],
        'quiet': True
    }

    # التحقق من تثبيت aria2c برمجياً للمنصات
    if os.path.exists("/usr/bin/aria2c") or os.path.exists("/usr/local/bin/aria2c"):
        cmd_opts['external_downloader'] = 'aria2c'
        cmd_opts['external_downloader_args'] = ['-j', '16', '-x', '16', '-s', '16']

    try:
        await asyncio.to_thread(yt_dlp.YoutubeDL(cmd_opts).download, [url])
    except:
        pass

    if active_tasks.get(task_key) == "cancelled":
        files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
        for f in files: os.remove(os.path.join(DOWNLOAD_DIR, f))
        return

    files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    if not files or os.path.getsize(os.path.join(DOWNLOAD_DIR, files[0])) < 1048576: 
        files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
        for f in files: os.remove(os.path.join(DOWNLOAD_DIR, f))
        return await query.message.edit("❌ فشلت عملية سحب ومعالجة حجم الفيديو الفعلي.")
        
    filepath = os.path.join(DOWNLOAD_DIR, files[0])
    
    base, ext = os.path.splitext(filepath)
    if ext.lower() != f".{target_format}":
        new_filepath = f"{base}.{target_format}"
        os.rename(filepath, new_filepath)
        filepath = new_filepath

    meta = await get_video_metadata(filepath)
    thumb_path = os.path.join(DOWNLOAD_DIR, f"thumb_yt_{query.message.id}.jpg")
    generated_thumb = await generate_thumbnail(filepath, thumb_path)

    await query.message.edit("📤 جاري بدء رفع الميديا الفعلية...")
    start_upload = time.time()
    try:
        clean_display_name = clean_filename_title(cached_title)

        await query.message.reply_video(
            video=filepath,
            thumb=generated_thumb if generated_thumb else None,
            width=meta["width"] if meta["width"] else 1280,
            height=meta["height"] if meta["height"] else 720,
            duration=meta["duration"],
            caption=f"🎬 **اسم المسلسل / الفيلم:**\n`{clean_display_name}`\n\n🔗 **الرابط الأصلي:**\n`{raw_url}`",
            progress=progress_bar,
            progress_args=(query.message, start_upload, task_key, "رفع الجودة المحددة 📤")
        )
        await query.message.delete()
    except Exception as e:
        if os.path.exists(filepath): os.remove(filepath)
        if active_tasks.get(task_key) == "cancelled" or "TASK_CANCELLED" in str(e): return
        await query.message.reply_text(f"❌ خطأ بالرفع: {str(e)}")

    if os.path.exists(filepath): os.remove(filepath)
    if generated_thumb and os.path.exists(generated_thumb): os.remove(generated_thumb)
    active_tasks.pop(task_key, None)

# ======================
# CONTROL PANEL & SETTINGS
# ======================
@app.on_message(filters.command(["settings", "settingskmd"]) & (filters.private | filters.group))
async def settings_cmd(_, message: Message):
    user_id = message.from_user.id
    current_format = user_video_format.get(user_id, "mp4").upper()
    current_res = user_compress_res.get(user_id, "480p")
    current_bg = user_backgrounds.get(user_id, "الافتراضية")
    status = get_server_status()
    text = f"⚙️ **لوحة تحكم إعدادات البوت والضغط:**\n\n🎬 **تنسيق الحفظ الإجباري:** `{current_format}`\n🗜️ **أبعاد جودة الضغط بالرد:** `{current_res}`\n🖼️ **الخلفية المحددة:** `{current_bg}`\n\n{status}"
    buttons = [[InlineKeyboardButton("🎬 تنسيق الفيديو", callback_data="set_format_menu"), InlineKeyboardButton("🗜️ أبعاد جودة الضغط", callback_data="set_comp_res_menu")], [InlineKeyboardButton("🖼️ تغيير الخلفية", callback_data="set_bg_menu"), InlineKeyboardButton("❌ إغلاق الإعدادات", callback_data="close_settings")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query()
async def global_callback_handler(_, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("change_") or data in ["close_settings", "set_format_menu", "set_comp_res_menu", "back_to_settings"]:
        await query.answer()

    if data.startswith("cancel_"):
        task_key = data.replace("cancel_", "")
        active_tasks[task_key] = "cancelled"
        await query.answer("⚠️ جاري إلغاء العملية وحذف الكاش...", show_alert=True)
        try: await query.message.edit_text("❌ **تم إلغاء وإغلاق العملية بنجاح.**\nتم مسح الملف المؤقت وتحرير موارد سيرفر Railway.")
        except: pass
        return
    if data == "close_settings":
        await query.message.delete()
        return
    if data == "set_format_menu":
        buttons = [[InlineKeyboardButton("MP4 🎥", callback_data="change_fmt_mp4"), InlineKeyboardButton("MKV 🎞️", callback_data="change_fmt_mkv")], [InlineKeyboardButton("🔙 العودة للخلف", callback_data="back_to_settings")]]
        await query.message.edit("🎬 **اختر التنسيق الصارم للملفات لمنع المستندات:**", reply_markup=InlineKeyboardMarkup(buttons))
        return
    if data.startswith("change_fmt_"):
        fmt = data.split("_")[-1]
        user_video_format[user_id] = fmt
        await query.answer(f"✅ تم تحويل التنسيق الإجباري إلى {fmt.upper()}", show_alert=True)
        await back_to_settings_panel(query, user_id)
        return
    if data == "set_comp_res_menu":
        buttons = [[InlineKeyboardButton("360p 📉", callback_data="change_res_360p")], [InlineKeyboardButton("480p 🎬", callback_data="change_res_480p")], [InlineKeyboardButton("720p 🖥️", callback_data="change_res_720p")], [InlineKeyboardButton("🔙 العودة للخلف", callback_data="back_to_settings")]]
        await query.message.edit("🗜️ **اختر أبعاد جودة الضغط عند استخدام الرد:**", reply_markup=InlineKeyboardMarkup(buttons))
        return
    if data.startswith("change_res_"):
        res = data.split("_")[-1]
        user_compress_res[user_id] = res
        await query.answer(f"✅ تم حفظ أبعاد الضغط: {res}", show_alert=True)
        await back_to_settings_panel(query, user_id)
        return
    if data == "back_to_settings":
        await back_to_settings_panel(query, user_id)

async def back_to_settings_panel(query, user_id):
    current_format = user_video_format.get(user_id, "mp4").upper()
    current_res = user_compress_res.get(user_id, "480p")
    current_bg = user_backgrounds.get(user_id, "الافتراضية")
    status = get_server_status()
    text = f"⚙️ **لوحة تحكم إعدادات البوت والضغط:**\n\n🎬 **تنسيق الحفظ الإجباري:** `{current_format}`\n🗜️ **أبعاد جودة الضغط بالرد:** `{current_res}`\n🖼️ **الخلفية المحددة:** `{current_bg}`\n\n{status}"
    buttons = [[InlineKeyboardButton("🎬 تنسيق الفيديو", callback_data="set_format_menu"), InlineKeyboardButton("🗜️ أبعاد جودة الضغط", callback_data="set_comp_res_menu")], [InlineKeyboardButton("🖼️ تغيير الخلفية", callback_data="set_bg_menu"), InlineKeyboardButton("❌ إغلاق الإعدادات", callback_data="close_settings")]]
    await query.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons))

async def setup_bot_commands(client):
    commands = [
        BotCommand("start", "🚀 تشغيل وتهيئة البوت واكتشاف الخدمات"),
        BotCommand("leech", "🎬 سحب سريع متعدد الخيوط مع العداد للروابط المباشرة"),
        BotCommand("ytdlleech", "📥 سحب ميديا المنصات واختيار الجودات والعناوين الحقيقية"),
        BotCommand("compress", "🗜️ ضغط الفيديو (بالرد)"),
        BotCommand("settings", "⚙️ فتح لوحة التحكم بالإعدادات والصيغ"),
        BotCommand("clean", "👑 [للأدمن] تنظيف السيرفر وتفريغ المساحة تماماً")
    ]
    try: await client.set_bot_commands(commands)
    except: pass
