import os
import asyncio
from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from bot import app

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# قواميس لحفظ إعدادات المستخدمين مؤقتاً في الذاكرة
user_video_format = {}  # الافتراضي سيكون MP4 إذا لم يحدد المستخدم
user_backgrounds = {}   # لحفظ رابط أو نوع الخلفية المفضلة للمستخدم
quality_cache = {}

# ======================
# START COMMAND
# ======================
@app.on_message(filters.command("start"))
async def start(_, message: Message):
    text = (
        "✅ **Qb Leech Bot Online**\n\n"
        "**قائمة الأوامر المتاحة:**\n"
        "🔹 /leech `[رابط]` - تحميل الروابط المباشرة\n"
        "🔹 /ytdlleech `[رابط يوتيوب]` - تحميل فيديوهات اليوتيوب\n"
        "🔹 /qb `[رابط ماجنت]` - تحميل ملفات التورنت\n"
        "⚙️ /settings - إعدادات الخلفية وتنسيق الفيديو\n"
    )
    await message.reply_text(text)


# ======================
# SETTINGS COMMAND (الاعدادات)
# ======================
@app.on_message(filters.command("settings"))
async def settings_cmd(_, message: Message):
    user_id = message.from_user.id
    current_format = user_video_format.get(user_id, "mp4")
    current_bg = user_backgrounds.get(user_id, "الافتراضية")

    text = (
        "⚙️ **إعدادات البوت الخاصة بك:**\n\n"
        "🎬 **تنسيق الفيديو الحالي:** `{}`\n"
        "🖼️ **الخلفية الحالية:** `{}`\n\n"
        "اختر من الأزرار بالأسفل لتعديل الإعدادات:".format(current_format.upper(), current_bg)
    )

    buttons = [
        [
            InlineKeyboardButton("🎬 تنسيق الفيديو (Format)", callback_data="set_format_menu"),
            InlineKeyboardButton("🖼️ تغيير الخلفية", callback_data="set_bg_menu")
        ],
        [InlineKeyboardButton("❌ إغلاق الإعدادات", callback_data="close_settings")]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ======================
# CALLBACK QUERY HANDLER (معالج الأزرار)
# ======================
@app.on_callback_query(filters.regex("^(set_|change_|close_)"))
async def settings_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if data == "close_settings":
        await query.message.delete()
        return

    # قائمة اختيار التنسيق
    if data == "set_format_menu":
        buttons = [
            [InlineKeyboardButton("MP4 🎥", callback_data="change_fmt_mp4"),
             InlineKeyboardButton("MKV 🎞️", callback_data="change_fmt_mkv")],
            [InlineKeyboardButton("🔙 العودة للخلف", callback_data="back_to_settings")]
        ]
        await query.message.edit("🎬 **اختر تنسيق الفيديو الإجباري لعمليات التحميل:**\n(سيتم تحويل أي صيغة أخرى أو رفعها بالتنسيق المختار فقط، ولن يتم إرسالها كمستندات).", reply_markup=InlineKeyboardMarkup(buttons))
        return

    # تنفيذ تغيير التنسيق
    if data.startswith("change_fmt_"):
        fmt = data.split("_")[-1]
        user_video_format[user_id] = fmt
        await query.answer(f"✅ تم تغيير تنسيق الفيديو المفضل إلى {fmt.upper()}", show_alert=True)
        await back_to_settings_panel(query, user_id)
        return

    # قائمة اختيار الخلفية
    if data == "set_bg_menu":
        buttons = [
            [InlineKeyboardButton("خلفية 1 (مظلمة)", callback_data="change_bg_Dark"),
             InlineKeyboardButton("خلفية 2 (فاتحة)", callback_data="change_bg_Light")],
            [InlineKeyboardButton("🔙 العودة للخلف", callback_data="back_to_settings")]
        ]
        await query.message.edit("🖼️ **اختر الخلفية المفضلة للعرض:**", reply_markup=InlineKeyboardMarkup(buttons))
        return

    # تنفيذ تغيير الخلفية
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
        "🎬 **تنسيق الفيديو الحالي:** `{}`\n"
        "🖼️ **الخلفية الحالية:** `{}`\n\n"
        "اختر من الأزرار بالأسفل لتعديل الإعدادات:".format(current_format.upper(), current_bg)
    )
    buttons = [
        [
            InlineKeyboardButton("🎬 تنسيق الفيديو (Format)", callback_data="set_format_menu"),
            InlineKeyboardButton("🖼️ تغيير الخلفية", callback_data="set_bg_menu")
        ],
        [InlineKeyboardButton("❌ إغلاق الإعدادات", callback_data="close_settings")]
    ]
    await query.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons))


# ======================
# DIRECT LEECH WITH FORMAT ENFORCEMENT
# ======================
@app.on_message(filters.command("leech"))
async def leech(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ **الاستخدام الخاطئ!**\nالصيغة الصحيحة: `/leech [الرابط]`")

    user_id = message.from_user.id
    # جلب الصيغة المفضلة للمستخدم (الافتراضي mp4)
    target_format = user_video_format.get(user_id, "mp4")

    url = message.command[1]
    msg = await message.reply_text("📥 **جاري تحميل وفحص الملف...**")

    # أمر التحميل مع دمج الصوت والفيديو وتحويل الصيغة تلقائياً إلى الصيغة المختارة عبر yt-dlp
    output = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    cmd = f'yt-dlp -f "bv+ba/b" --recode-video {target_format} -o "{output}" "{url}"'

    process = await asyncio.create_subprocess_shell(cmd)
    await process.communicate()

    files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    if not files:
        return await msg.edit("❌ **فشل تحميل الرابط أو صيغة الملف غير مدعومة.**")

    # استهداف أول ملف تم تحميله
    filename = files[0]
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    
    # التأكد التام من تعديل الامتداد برمجياً إذا لزم الأمر ليطابق اختيار المستخدم
    base, ext = os.path.splitext(filepath)
    if ext.lower() != f".{target_format}":
        new_filepath = f"{base}.{target_format}"
        os.rename(filepath, new_filepath)
        filepath = new_filepath

    await msg.edit(f"📤 **جاري رفع الفيديو بصيغة {target_format.upper()} حصراً...**")

    # الرفع كـ فيديو دائماً وليس كمستند بناءً على طلبك
    try:
        await message.reply_video(video=filepath, caption=f"🎬 تم التحويل والرفع بصيغة: {target_format.upper()}")
    except Exception as e:
        await message.reply_text(f"❌ حدث خطأ أثناء رفع الفيديو: {str(e)}")

    if os.path.exists(filepath):
        os.remove(filepath)
    await msg.delete()
