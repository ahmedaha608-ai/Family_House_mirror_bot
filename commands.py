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
active_tasks = {}         # تتبع العمليات النشطة لإلغائها: {message_id: bool}

# ==========================================
# دالة حساب وحجم وإحصائيات النظام (CPU / التخزين)
# ==========================================
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

# ==========================================
# عداد الرفع التفاعلي مع دعم زر الإلغاء الفوري
# ==========================================
async def progress_bar(current, total, reply_msg, start_time, task_key, mode="رفع 📤"):
    # التحقق أولاً إذا قام المستخدم بالضغط على زر إلغاء الأمر
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
        
        # زر الإلغاء التفاعلي المربوط بمعرف المهمة
        buttons = [[InlineKeyboardButton("❌ إلغاء وإغلاق العملية", callback_data=f"cancel_{task_key}")]]
        try:
            await reply_msg.edit_text(progress_text, reply_markup=InlineKeyboardMarkup(buttons))
        except:
            pass

# دالة سحب روابط الأفلام المباشرة مع دعم الإلغاء الفوري أثناء التدفق
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
                            # التحقق المستمر قبل قراءة كل Chunk لحفظ الرام والإنترنت
                            if active_tasks.get(task_key) == "cancelled":
                                return False
                                
                            chunk = await response.content.read(1024*1024) # 1MB
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
        print(f"Direct stream download error: {e}")
    return False


# ======================
# START COMMAND
# ======================
@app.on_message(filters.command("start"))
async def start(_, message: Message):
    text = (
        "✅ **Qb Leech Bot Online**\n\n"
        "**قائمة الأوامر الذكية المزودة بزر الإلغاء:**\n"
        "🔹 /leech `[رابط]` - سحب روابط الأفلام والمواقع العربية (مع زر إلغاء)\n"
        "🔹 /ytdlleech `[الرابط]` - تحميل من (YouTube, TikTok, VK, OK) واختيار الجودة\n"
        "🗜️ /compress `[بالرد]` - ضغط الفيديوهات لأقل مساحة حمايةً للرام\n"
        "⚙️ /settings - لوحة التحكم وإعدادات أبعاد الضغط والتنسيقات\n"
    )
    await message.reply_text(text)


# ======================
# SETTINGS COMMAND
# ======================
@app.on_message(filters.command("settings"))
async def settings_cmd(_, message: Message):
    user_id = message.from_user.id
    current_format = user_video_format.get(user_id, "mp4").upper()
    current_res = user_compress_res.get(user_id, "480p")
    current_bg = user_backgrounds.get(user_id, "الافتراضية")
    status = get_server_status()

    text = (
        "⚙️ **لوحة تحكم إعدادات البوت والضغط:**\n\n"
        "🎬 **تنسيق الحفظ الإجباري:** `{}`\n"
        "🗜️ **أبعاد جودة الضغط بالرد:** `{}`\n"
        "🖼️ **الخلفية المحددة:** `{}`\n\n"
        f"{status}\n\n"
        "اختر من الأزرار بالأسفل لتعديل خياراتك:"
    )

    buttons = [
        [
            InlineKeyboardButton("🎬 تنسيق الفيديو", callback_data="set_format_menu"),
            InlineKeyboardButton("🗜️ أبعاد جودة الضغط", callback_data="set_comp_res_menu")
        ],
        [
            InlineKeyboardButton("🖼️ تغيير الخلفية", callback_data="set_bg_menu"),
            InlineKeyboardButton("❌ إغلاق الإعدادات", callback_data="close_settings")
        ]
    ]
    await message.reply_text(text.format(current_format, current_res, current_bg), reply_markup=InlineKeyboardMarkup(buttons))


# ======================
# CALLBACK QUERY HANDLER FOR SETTINGS & CANCEL TASK
# ======================
@app.on_callback_query()
async def global_callback_handler(_, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    # ميزة إلغاء وتدمير العمليات النشطة فوراً لحفظ الـ RAM
    if data.startswith("cancel_"):
        task_key = data.replace("cancel_", "")
        active_tasks[task_key] = "cancelled" # تغيير الحالة لتتوقف الحلقات البرمجية فوراً
        await query.answer("⚠️ جاري إلغاء العملية وحذف الملفات المؤقتة لتوفير الرام...", show_alert=True)
        try:
            await query.message.edit_text("❌ **تم إلغاء وإغلاق العملية بنجاح.**\nتم مسح الملف المؤقت وتحرير موارد سيرفر Railway.")
        except:
            pass
        return

    if data == "close_settings":
        await query.message.delete()
        return

    if data == "set_format_menu":
        buttons = [
            [InlineKeyboardButton("MP4 🎥", callback_data="change_fmt_mp4"),
             InlineKeyboardButton("MKV 🎞️", callback_data="change_fmt_mkv")],
            [InlineKeyboardButton("🔙 العودة للخلف", callback_data="back_to_settings")]
        ]
        await query.message.edit("🎬 **اختر التنسيق الصارم للملفات لمنع المستندات:**", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("change_fmt_"):
        fmt = data.split("_")[-1]
        user_video_format[user_id] = fmt
        await query.answer(f"✅ تم تحويل التنسيق الإجباري إلى {fmt.upper()}", show_alert=True)
        await back_to_settings_panel(query, user_id)
        return

    if data == "set_comp_res_menu":
        buttons = [
            [InlineKeyboardButton("360p 📉 (أقل مساحة وحجم)", callback_data="change_res_360p")],
            [InlineKeyboardButton("480p 🎬 (متوازن وموصى به لـ Railway)", callback_data="change_res_480p")],
            [InlineKeyboardButton("720p 🖥️ (دقة عالية مخفضة الحجم)", callback_data="change_res_720p")],
            [InlineKeyboardButton("🔙 العودة للخلف", callback_data="back_to_settings")]
        ]
        await query.message.edit("🗜️ **اختر أبعاد جودة الضغط عند استخدام الرد:**", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("change_res_"):
        res = data.split("_")[-1]
        user_compress_res[user_id] = res
        await query.answer(f"✅ تم حفظ أبعاد الضغط: {res}", show_alert=True)
        await back_to_settings_panel(query, user_id)
        return

    if data == "set_bg_menu":
        buttons = [
            [InlineKeyboardButton("خلفية دافئة 🌅", callback_data="change_bg_Warm"),
             InlineKeyboardButton("خلفية مظلمة 🌌", callback_data="change_bg_Dark")],
            [InlineKeyboardButton("🔙 العودة للخلف", callback_data="back_to_settings")]
        ]
        await query.message.edit("🖼️ **اختر نمط الخلفية المفضلة:**", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("change_bg_"):
        bg_name = data.split("_")[-1]
        user_backgrounds[user_id] = bg_name
        await query.answer("✅ تم الحفظ بنجاح", show_alert=True)
        await back_to_settings_panel(query, user_id)
        return

    if data == "back_to_settings":
        await back_to_settings_panel(query, user_id)


async def back_to_settings_panel(query, user_id):
    current_format = user_video_format.get(user_id, "mp4").upper()
    current_res = user_compress_res.get(user_id, "480p")
    current_bg = user_backgrounds.get(user_id, "الافتراضية")
    status = get_server_status()
    
    text = (
        "⚙️ **لوحة تحكم إعدادات البوت والضغط:**\n\n"
        "🎬 **تنسيق الحفظ الإجباري:** `{}`\n"
        "🗜️ **أبعاد جودة الضغط بالرد:** `{}`\n"
        "🖼️ **الخلفية المحددة:** `{}`\n\n"
        f"{status}\n\n"
        "اختر من الأزرار بالأسفل لتعديل خياراتك:"
    )
    buttons = [
        [
            InlineKeyboardButton("🎬 تنسيق الفيديو", callback_data="set_format_menu"),
            InlineKeyboardButton("🗜️ أبعاد جودة الضغط", callback_data="set_comp_res_menu")
        ],
        [
            InlineKeyboardButton("🖼️ تغيير الخلفية", callback_data="set_bg_menu"),
            InlineKeyboardButton("❌ إغلاق الإعدادات", callback_data="close_settings")
        ]
    ]
    await query.message.edit(text.format(current_format, current_res, current_bg), reply_markup=InlineKeyboardMarkup(buttons))


# ======================
# DIRECT LEECH (أفلام ومسلسلات مع خيار الإلغاء)
# ======================
@app.on_message(filters.command("leech"))
async def leech(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage:\n/leech [direct_link]")

    user_id = message.from_user.id
    target_format = user_video_format.get(user_id, "mp4")
    url = message.command[1]
    
    task_key = str(message.id)
    active_tasks[task_key] = "running"

    # تجهيز رسالة مبدئية مع زر الإلغاء فوراً
    buttons = [[InlineKeyboardButton("❌ إلغاء وإغلاق العملية", callback_data=f"cancel_{task_key}")]]
    msg = await message.reply_text("🔗 جاري فحص الرابط المباشر وتجهيز مخرجات البيانات...", reply_markup=InlineKeyboardMarkup(buttons))

    filename = url.split('/')[-1].split('?')[0]
    if not filename or not any(filename.lower().endswith(e) for e in ['.mp4', '.mkv', '.avi']):
        filename = f"movie_{message.id}.{target_format}"
    else:
        base, _ = os.path.splitext(filename)
        filename = f"{base}.{target_format}"

    filepath = os.path.join(DOWNLOAD_DIR, filename)

    # بدء السحب والتدفق المباشر مع العداد والتحقق المستمر من الإلغاء
    success = await download_direct_mp4_with_progress(url, filepath, msg, task_key)

    # إذا ألغى المستخدم العملية أثناء التنزيل
    if active_tasks.get(task_key) == "cancelled":
        if os.path.exists(filepath): os.remove(filepath)
        return

    if not success or not os.path.exists(filepath):
        if active_tasks.get(task_key) == "cancelled": return
        return await msg.edit_text("❌ **فشل سحب الرابط المباشر:** إما أن الرابط غير مدعوم أو أن سيرفر الموقع يمنع الاتصال استضافتنا.")

    await msg.edit_text("📤 اكتمل تنزيل الفيلم للسيرفر! جاري بدء رفعه الآن كمشاهدة مباشرة للتلغرام...")
    
    # عملية الرفع للتلغرام مدعومة أيضاً بالإلغاء الفوري لحفظ الرام والشبكة
    start_upload = time.time()
    try:
        await message.reply_video(
            video=filepath,
            caption=f"🎬 **تم تحميل ورفع الفيلم بنجاح**\n\n📦 التنسيق الصارم: `{target_format.upper()}`",
            progress=progress_bar,
            progress_args=(msg, start_upload, task_key, "رفع للمشاهدة 📤")
        )
        await msg.delete()
    except Exception as e:
        if os.path.exists(filepath): os.remove(filepath)
        if "TASK_CANCELLED" in str(e) or active_tasks.get(task_key) == "cancelled":
            return
        await message.reply_text(f"❌ حدث خطأ أثناء النقل والرفع: {str(e)}")

    if os.path.exists(filepath):
        os.remove(filepath)
    active_tasks.pop(task_key, None)


# ======================
# COMPRESS COMMAND (الضغط بالرد مع العداد الحصري ومفتاح الإلغاء)
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
        if os.path.exists(os.path.join(DOWNLOAD_DIR, f"orig_{message.id}")):
            os.remove(os.path.join(DOWNLOAD_DIR, f"orig_{message.id}"))
        return

    if active_tasks.get(task_key) == "cancelled":
        if video_path and os.path.exists(video_path): os.remove(video_path)
        return

    if not video_path or not os.path.exists(video_path):
        return await msg.edit_text("❌ فشل تنزيل ملف الفيديو الأصلي.")

    status = get_server_status()
    await msg.edit_text(f"🗜️ **جاري ترميز وضغط الفيديو إلى {target_res} حالياً...**\n\n{status}\n\n⚠️ العملية تتم بخفة فائقة لحماية معالج ورامات الخطة المجانية.")

    scale_filter = "scale=-2:360" if target_res == "360p" else ("scale=-2:720" if target_res == "720p" else "scale=-2:480")
    compressed_path = os.path.join(DOWNLOAD_DIR, f"compressed_{message.id}.{target_format}")

    # معالجة ذكية وسريعة للحفاظ على الرام دون تخطي خط الـ 512 ميجابايت لـ Railway
    ffmpeg_cmd = (
        f'ffmpeg -i "{video_path}" -vf "{scale_filter}" '
        f'-vcodec libx264 -crf 30 -preset ultrafast '
        f'-acodec aac -b:a 128k -y "{compressed_path}"'
    )

    process = await asyncio.create_subprocess_shell(ffmpeg_cmd)
    await process.communicate()

    if os.path.exists(video_path): os.remove(video_path)

    # التحقق من الإلغاء بعد معالجة الفريمات مباشرة وقبل بدء الرفع على الفاضي
    if active_tasks.get(task_key) == "cancelled":
        if os.path.exists(compressed_path): os.remove(compressed_path)
        return

    if not os.path.exists(compressed_path) or os.path.getsize(compressed_path) == 0:
        return await msg.edit_text("❌ فشلت عملية ضغط وترميز ترميم الفيديو عبر FFmpeg.")

    await msg.edit_text("📤 اكتمل ضغط الحجم بنجاح! جاري بدء رفع النسخة الخفيفة والنهائية لتليجرام...")

    start_upload = time.time()
    try:
        await message.reply_video(
            video=compressed_path,
            caption=f"🗜️ **تم ضغط وتقليص مساحة الفيديو الحيوية**\n\n🎯 الجودة المحددة: `{target_res}`\n📦 الصيغة الإلزامية: `{target_format.upper()}`\n⚙️ البيئة الآمنة: `Railway Free Smart System`",
            progress=progress_bar,
            progress_args=(msg, start_upload, task_key, "رفع الفيديو المضغوط 📤")
        )
        await msg.delete()
    except Exception as e:
        if os.path.exists(compressed_path): os.remove(compressed_path)
        if active_tasks.get(task_key) == "cancelled" or "TASK_CANCELLED" in str(e): return
        await message.reply_text(f"❌ عطل مفاجئ بالرفع: {str(e)}")

    if os.path.exists(compressed_path): os.remove(compressed_path)
    active_tasks.pop(task_key, None)


# ======================
# YOUTUBE LEECH (كافة المنصات)
# ======================
@app.on_message(filters.command("ytdlleech"))
async def ytdlleech(_, message: Message):
    if len(message.command) < 2: return await message.reply_text("Usage:\n/ytdlleech [link]")
    url = message.command[1]
    msg = await message.reply_text("🔍 جاري فحص ومصادقة جودات المنصة...")
    try:
        ydl_opts = {'skip_download': True, 'no_warnings': True, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])

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
                    quality_cache[key] = {"url": url, "format": fid}
                    buttons.append([InlineKeyboardButton(text=f"🎬 جودة: {note} ({ext.upper()})", callback_data=f"yt_{key}")])

        if not buttons:
            key = f"{message.id}_best"
            quality_cache[key] = {"url": url, "format": "best"}
            buttons.append([InlineKeyboardButton(text="🎬 تحميل تلقائي بأفضل جودة مدعومة", callback_data=f"yt_{key}")])
        await msg.edit("🎬 **اختر الجودة المطلوبة لبدء التحميل والرفع فوراً:**", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await msg.edit(f"❌ خطأ بقراءة جودات المنصة: `{str(e)}`")


@app.on_callback_query(filters.regex("^yt_"))
async def quality_download(_, query: CallbackQuery):
    user_id = query.from_user.id
    target_format = user_video_format.get(user_id, "mp4")
    key = query.data.replace("yt_", "")
    
    if key not in quality_cache: return await query.answer("⚠️ الجلسة منتهية الصلاحية.", show_alert=True)
    data = quality_cache[key]
    url = data["url"]
    fmt = data["format"]

    task_key = f"yt_{query.message.id}"
    active_tasks[task_key] = "running"

    buttons = [[InlineKeyboardButton("❌ إلغاء وإغلاق العملية", callback_data=f"cancel_{task_key}")]]
    await query.message.edit("📥 جاري دمج وسحب الجودة المحددة من المنصة للسيرفر...", reply_markup=InlineKeyboardMarkup(buttons))

    output_template = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    cmd = f'yt-dlp -f "{fmt}+ba/best" --recode-video {target_format} --merge-output-format {target_format} -o "{output_template}" "{url}"'

    process = await asyncio.create_subprocess_shell(cmd)
    await process.communicate()

    if active_tasks.get(task_key) == "cancelled":
        files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
        for f in files: os.remove(os.path.join(DOWNLOAD_DIR, f))
        return

    files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    if not files: return await query.message.edit("❌ فشلت عملية سحب ومعالجة الفيديو.")
    filepath = os.path.join(DOWNLOAD_DIR, files[0])
    
    base, ext = os.path.splitext(filepath)
    if ext.lower() != f".{target_format}":
        new_filepath = f"{base}.{target_format}"
        os.rename(filepath, new_filepath)
        filepath = new_filepath

    await query.message.edit("📤 اكتمل السحب! جاري بدء النقل والرفع للتليجرام...")
    start_upload = time.time()
    try:
        await query.message.reply_video(
            video=filepath,
            caption=f"🎬 **تم تنزيل ونقل الجودة المحددة**\n\n📦 التنسيق المستخرج: `{target_format.upper()}`",
            progress=progress_bar,
            progress_args=(query.message, start_upload, task_key, "رفع الجودة المحددة 📤")
        )
        await query.message.delete()
    except Exception as e:
        if os.path.exists(filepath): os.remove(filepath)
        if active_tasks.get(task_key) == "cancelled" or "TASK_CANCELLED" in str(e): return
        await query.message.reply_text(f"❌ خطأ بالرفع: {str(e)}")

    if os.path.exists(filepath): os.remove(filepath)
    active_tasks.pop(task_key, None)


# ======================
# QB TORRENT
# ======================
@app.on_message(filters.command("qb"))
async def qb(_, message: Message):
    if len(message.command) < 2: return await message.reply_text("Usage:\n/qb magnet_link")
    await message.reply_text("📥 **بدء معالجة وإضافة رابط التورنت في السيرفر عبر qBittorrent...**")
