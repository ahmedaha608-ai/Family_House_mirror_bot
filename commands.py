import os
import asyncio
import yt_dlp
from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

# تعديل الاستدعاء ليقرأ من المجلد الرئيسي مباشرة لتجنب خطأ ModuleNotFoundError
from __init__ import app

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# قواميس لحفظ إعدادات المستخدمين في ذاكرة السيرفر مؤقتاً
user_video_format = {}  # الصيغة الافتراضية MP4
user_backgrounds = {}   # الخلفية الافتراضية للمخدم
quality_cache = {}

# ======================
# START COMMAND
# ======================
@app.on_message(filters.command("start"))
async def start(_, message: Message):
    text = (
        "✅ **Qb Leech Bot Online**\n\n"
        "**قائمة الأوامر المتاحة:**\n"
        "🔹 /leech `[رابط مباشر]` - تحميل الروابط والملفات المباشرة\n"
        "🔹 /ytdlleech `[رابط يوتيوب]` - تحميل فيديوهات اليوتيوب واختيار الجودة\n"
        "🔹 /qb `[رابط ماجنت]` - تحميل وإدارة ملفات التورنت\n"
        "⚙️ /settings - إعدادات البوت وتنسيق الفيديو والخلفية\n"
    )
    await message.reply_text(text)


# ======================
# SETTINGS COMMAND
# ======================
@app.on_message(filters.command("settings"))
async def settings_cmd(_, message: Message):
    user_id = message.from_user.id
    current_format = user_video_format.get(user_id, "mp4")
    current_bg = user_backgrounds.get(user_id, "الافتراضية")

    text = (
        "⚙️ **إعدادات البوت الخاصة بك:**\n\n"
        "🎬 **تنسيق الفيديو الإجباري:** `{}`\n"
        "🖼️ **الخلفية المحددة:** `{}`\n\n"
        "اختر من الأزرار بالأسفل لتعديل خياراتك:".format(current_format.upper(), current_bg)
    )

    buttons = [
        [
            InlineKeyboardButton("🎬 تنسيق الفيديو (Format)", callback_data="set_format_menu"),
            InlineKeyboardButton("🖼️ تغيير Background", callback_data="set_bg_menu")
        ],
        [InlineKeyboardButton("❌ إغلاق الإعدادات", callback_data="close_settings")]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ======================
# CALLBACK QUERY HANDLER FOR SETTINGS
# ======================
@app.on_callback_query(filters.regex("^(set_|change_|close_|back_)"))
async def settings_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if data == "close_settings":
        await query.message.delete()
        return

    if data == "set_format_menu":
        buttons = [
            [InlineKeyboardButton("MP4 🎥", callback_data="change_fmt_mp4"),
             InlineKeyboardButton("MKV 🎞️", callback_data="change_fmt_mkv")],
            [InlineKeyboardButton("🔙 العودة للخلف", callback_data="back_to_settings")]
        ]
        await query.message.edit(
            "🎬 **اختر تنسيق الفيديو الإجباري للتحميل:**\n"
            "سيتم تحويل أي فيديو تلقائياً للصيغة المختارة ورفعه كمشاهدة مباشرة ولن يُرسل كمستند بتاتاً.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data.startswith("change_fmt_"):
        fmt = data.split("_")[-1]
        user_video_format[user_id] = fmt
        await query.answer(f"✅ تم تحويل التنسيق الإجباري إلى {fmt.upper()}", show_alert=True)
        await back_to_settings_panel(query, user_id)
        return

    if data == "set_bg_menu":
        buttons = [
            [InlineKeyboardButton("خلفية دافئة 🌅", callback_data="change_bg_Warm"),
             InlineKeyboardButton("خلفية مظلمة 🌌", callback_data="change_bg_Dark")],
            [InlineKeyboardButton("🔙 العودة للخلف", callback_data="back_to_settings")]
        ]
        await query.message.edit("🖼️ **اختر الخلفية المفضلة لعرض البوت:**", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("change_bg_"):
        bg_name = data.split("_")[-1]
        user_backgrounds[user_id] = bg_name
        await query.answer(f"✅ تم اختيار الخلفية: {bg_name}", show_alert=True)
        await back_to_settings_panel(query, user_id)
        return

    if data == "back_to_settings":
        await back_to_settings_panel(query, user_id)


async def back_to_settings_panel(query, user_id):
    current_format = user_video_format.get(user_id, "mp4")
    current_bg = user_backgrounds.get(user_id, "الافتراضية")
    text = (
        "⚙️ **إعدادات البوت الخاصة بك:**\n\n"
        "🎬 **تنسيق الفيديو الإجباري:** `{}`\n"
        "🖼️ **الخلفية المحددة:** `{}`\n\n"
        "اختر من الأزرار بالأسفل لتعديل خياراتك:".format(current_format.upper(), current_bg)
    )
    buttons = [
        [
            InlineKeyboardButton("🎬 تنسيق الفيديو (Format)", callback_data="set_format_menu"),
            InlineKeyboardButton("🖼️ تغيير Background", callback_data="set_bg_menu")
        ],
        [InlineKeyboardButton("❌ إغلاق الإعدادات", callback_data="close_settings")]
    ]
    await query.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons))


# ======================
# DIRECT LEECH
# ======================
@app.on_message(filters.command("leech"))
async def leech(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage:\n/leech link")

    user_id = message.from_user.id
    target_format = user_video_format.get(user_id, "mp4")

    url = message.command[1]
    msg = await message.reply_text("📥 Downloading...")

    output = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    
    # إجبار التنسيق المطلوب عن طريق أداة yt-dlp
    cmd = f'yt-dlp -f "bv+ba/b" --recode-video {target_format} -o "{output}" "{url}"'

    process = await asyncio.create_subprocess_shell(cmd)
    await process.communicate()

    files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    if not files:
        return await msg.edit("❌ Failed")

    filename = files[0]
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    # التحقق وتعديل الامتداد برمجياً للتأكيد
    base, ext = os.path.splitext(filepath)
    if ext.lower() != f".{target_format}":
        new_filepath = f"{base}.{target_format}"
        os.rename(filepath, new_filepath)
        filepath = new_filepath

    await msg.edit(f"📤 Uploading as {target_format.upper()} video...")

    # الرفع الإجباري كفيديو تفاعلي وليس كمستند
    try:
        await message.reply_video(video=filepath, caption=f"🎬 الصيغة: {target_format.upper()}")
    except Exception as e:
        await message.reply_text(f"❌ حدث خطأ أثناء رفع الفيديو: {str(e)}")

    if os.path.exists(filepath):
        os.remove(filepath)
    await msg.delete()


# ======================
# YOUTUBE LEECH WITH QUALITY EXTRESCTION
# ======================
@app.on_message(filters.command("ytdlleech"))
async def ytdlleech(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage:\n/ytdlleech youtube_link")

    url = message.command[1]
    msg = await message.reply_text("🔍 Extracting qualities...")

    try:
        ydl_opts = {}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])

        buttons = []
        for f in formats:
            if f.get("vcodec") != "none" and f.get("acodec") != "none":
                res = f.get("format_note", "Unknown")
                fid = f.get("format_id")
                ext = f.get("ext", "mp4")
                
                key = f"{message.id}_{fid}"
                quality_cache[key] = {"url": url, "format": fid}

                buttons.append([
                    InlineKeyboardButton(
                        text=f"🎬 {res} ({ext})",
                        callback_data=f"yt_{key}"
                    )
                ])

        await msg.edit("🎬 اختر الجودة لتنزيلها كفيديو:", reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        await msg.edit(str(e))


@app.on_callback_query(filters.regex("^yt_"))
async def quality_download(_, query: CallbackQuery):
    user_id = query.from_user.id
    target_format = user_video_format.get(user_id, "mp4")

    key = query.data.replace("yt_", "")

    if key not in quality_cache:
        return await query.answer("Expired")

    data = quality_cache[key]
    url = data["url"]
    fmt = data["format"]

    await query.message.edit("📥 Downloading selected quality...")

    output = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    
    # دمج الجودة المختارة مع معالجة وتحويل الصيغة المفضلة للمستخدم
    cmd = f'yt-dlp -f {fmt} --recode-video {target_format} -o "{output}" "{url}"'

    process = await asyncio.create_subprocess_shell(cmd)
    await process.communicate()

    files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    if not files:
        return await query.message.edit("❌ Failed")

    filepath = f"{DOWNLOAD_DIR}/{files[0]}"
    
    base, ext = os.path.splitext(filepath)
    if ext.lower() != f".{target_format}":
        new_filepath = f"{base}.{target_format}"
        os.rename(filepath, new_filepath)
        filepath = new_filepath

    await query.message.edit(f"📤 Uploading as {target_format.upper()}...")

    try:
        await query.message.reply_video(video=filepath, caption=f"🎬 تم التحميل والتنسيق: {target_format.upper()}")
    except Exception as e:
        await query.message.reply_text(f"❌ خطأ بالرفع: {str(e)}")

    if os.path.exists(filepath):
        os.remove(filepath)
    await query.message.delete()


# ======================
# QB TORRENT
# ======================
@app.on_message(filters.command("qb"))
async def qb(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage:\n/qb magnet_link")
    
    await message.reply_text("📥 **بدء معالجة وإضافة رابط التورنت...**")
