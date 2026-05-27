import os
import time
import asyncio
import shutil
import yt_dlp
import psutil

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from config import app

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

active_tasks = {}
GLOBAL_TASKS = {}
compress_cache = {}

START_TIME = time.time()

# =========================================================
# 📊 SYSTEM STATS
# =========================================================

def sizeof_fmt(num):

    for unit in ['B', 'KB', 'MB', 'GB']:

        if num < 1024:
            return f"{num:.2f}{unit}"

        num /= 1024

    return f"{num:.2f}TB"

def get_system_stats():

    cpu = psutil.cpu_percent()

    ram = psutil.virtual_memory().percent

    disk = shutil.disk_usage('/').free

    uptime = int(time.time() - START_TIME)

    mins = uptime // 60

    secs = uptime % 60

    return (
        f"CPU : {cpu}% | RAM : {ram}%\n"
        f"FREE : {sizeof_fmt(disk)}\n"
        f"UPTIME : {mins}m {secs}s"
    )

def build_bar(percent):

    filled = int(percent / 10)

    return (
        "▓" * filled
        + "░" * (10 - filled)
    )

# =========================================================
# 🚀 ADVANCED PROGRESS
# =========================================================

async def ultra_progress(
    current,
    total,
    message,
    start,
    task_id,
    filename="video.mp4",
    mode="Leech",
    engine="Aria2"
):

    if task_id not in GLOBAL_TASKS:
        return

    now = time.time()

    diff = now - start

    if diff < 1:
        return

    percentage = (
        current * 100 / total
        if total else 0
    )

    speed = current / diff if diff else 0

    eta = (
        (total - current) / speed
        if speed > 0 else 0
    )

    processed = sizeof_fmt(current)

    total_size = sizeof_fmt(total)

    speed_text = sizeof_fmt(speed) + "/s"

    bar = build_bar(percentage)

    stats = get_system_stats()

    text = (
        f"📥 Downloading...\n\n"
        f"📄 {filename}\n\n"
        f"┌ [{bar}]\n"
        f"├ Process : {percentage:.2f}%\n"
        f"├ Processed : {processed}\n"
        f"├ Total Size : {total_size}\n"
        f"├ Speed : {speed_text}\n"
        f"├ ETA : {int(eta)}s\n"
        f"├ Engine : {engine}\n"
        f"├ Mode : #{mode}\n"
        f"├ User : {message.chat.id}\n"
        f"└ Cancel : /cancel_{task_id}\n\n"
        f"Tasks : {len(GLOBAL_TASKS)}\n\n"
        f"{stats}"
    )

    try:
        await message.edit_text(text)
    except:
        pass

def safe_ultra_progress(
    current,
    total,
    message,
    start,
    task_id,
    filename,
    mode,
    engine
):

    try:

        loop = asyncio.get_running_loop()

        loop.create_task(
            ultra_progress(
                current,
                total,
                message,
                start,
                task_id,
                filename,
                mode,
                engine
            )
        )

    except:
        pass

# =========================================================
# 📥 LEECH COMMAND
# =========================================================

@app.on_message(filters.command(["leech"]))
async def leech(_, message: Message):

    if len(message.command) < 2:
        return await message.reply_text("❌ أرسل رابط.")

    url = message.command[1]

    task_key = str(message.id)

    GLOBAL_TASKS[task_key] = True

    status = await message.reply_text("⏳ بدء التحميل...")

    filepath = os.path.join(
        DOWNLOAD_DIR,
        f"{task_key}.mp4"
    )

    start_time = time.time()

    def hook(d):

        if d['status'] == 'downloading':

            current = d.get('downloaded_bytes', 0)

            total = (
                d.get('total_bytes')
                or d.get('total_bytes_estimate', 0)
            )

            filename = d.get("filename", "video.mp4")

            safe_ultra_progress(
                current,
                total,
                status,
                start_time,
                task_key,
                os.path.basename(filename),
                "Leech",
                "Aria2"
            )

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': filepath,
        'progress_hooks': [hook],
        'quiet': True,
        'retries': 10,
        'fragment_retries': 10,
        'concurrent_fragment_downloads': 8,
        'external_downloader': 'aria2c',
        'external_downloader_args': [
            '-j', '16',
            '-x', '16',
            '-s', '16'
        ]
    }

    try:

        await asyncio.to_thread(
            yt_dlp.YoutubeDL(ydl_opts).download,
            [url]
        )

        await status.edit_text("📤 جاري الرفع...")

        await message.reply_video(
            video=filepath,
            caption="✅ تم التحميل بنجاح"
        )

    except Exception as e:

        await status.edit_text(f"❌ {str(e)}")

    finally:

        GLOBAL_TASKS.pop(task_key, None)

        try:
            os.remove(filepath)
        except:
            pass

# =========================================================
# 🗜️ COMPRESS MENU
# =========================================================

@app.on_message(filters.command(["compress"]))
async def compress_menu(_, message: Message):

    if not message.reply_to_message:
        return await message.reply_text(
            "⚠️ رد على فيديو."
        )

    key = str(message.id)

    compress_cache[key] = message.reply_to_message.id

    buttons = [
        [
            InlineKeyboardButton(
                "144p",
                callback_data=f"compress_144_{key}"
            ),
            InlineKeyboardButton(
                "240p",
                callback_data=f"compress_240_{key}"
            )
        ],
        [
            InlineKeyboardButton(
                "360p",
                callback_data=f"compress_360_{key}"
            ),
            InlineKeyboardButton(
                "480p",
                callback_data=f"compress_480_{key}"
            )
        ],
        [
            InlineKeyboardButton(
                "720p",
                callback_data=f"compress_720_{key}"
            )
        ]
    ]

    await message.reply_text(
        "🗜️ اختر جودة الضغط:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# =========================================================
# 🎬 COMPRESS CALLBACK
# =========================================================

@app.on_callback_query(filters.regex("^compress_"))
async def compress_callback(_, query: CallbackQuery):

    data = query.data.split("_")

    quality = data[1]

    key = data[2]

    await query.answer()

    msg = await query.message.edit_text(
        f"🗜️ جاري الضغط بجودة {quality}p..."
    )

    reply = await query.message.chat.get_messages(
        compress_cache[key]
    )

    input_path = await reply.download(
        file_name=f"{DOWNLOAD_DIR}/input_{key}.mp4"
    )

    output_path = (
        f"{DOWNLOAD_DIR}/compressed_{quality}_{key}.mp4"
    )

    scale_map = {
        "144": "256:144",
        "240": "426:240",
        "360": "640:360",
        "480": "854:480",
        "720": "1280:720"
    }

    scale = scale_map.get(quality, "854:480")

    cmd = (
        f'ffmpeg -i "{input_path}" '
        f'-vf scale={scale} '
        f'-c:v libx265 '
        f'-preset ultrafast '
        f'-crf 30 '
        f'-c:a aac '
        f'-b:a 96k '
        f'-y "{output_path}"'
    )

    process = await asyncio.create_subprocess_shell(cmd)

    await process.communicate()

    await msg.edit_text("📤 جاري رفع الفيديو...")

    await query.message.reply_video(
        video=output_path,
        caption=f"✅ تم الضغط بجودة {quality}p"
    )

    try:
        os.remove(input_path)
    except:
        pass

    try:
        os.remove(output_path)
    except:
        pass

    await msg.delete()
