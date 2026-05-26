from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from __init__ import app

import yt_dlp
import os
import asyncio

DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

quality_cache = {}

@app.on_message(filters.command("start"))
async def start(_, message: Message):

    text = (
        "✅ Qb Leech Bot Online\n\n"
        "Commands:\n"
        "/leech link\n"
        "/ytdlleech youtube_link\n"
        "/qb magnet_link"
    )

    await message.reply_text(text)


# ======================
# DIRECT LEECH
# ======================

@app.on_message(filters.command("leech"))
async def leech(_, message: Message):

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage:\n/leech link"
        )

    url = message.command[1]

    msg = await message.reply_text("📥 Downloading...")

    output = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"

    cmd = f'yt-dlp -o "{output}" "{url}"'

    process = await asyncio.create_subprocess_shell(cmd)
    await process.communicate()

    files = os.listdir(DOWNLOAD_DIR)

    if not files:
        return await msg.edit("❌ Failed")

    filepath = f"{DOWNLOAD_DIR}/{files[0]}"

    await msg.edit("📤 Uploading...")

    await message.reply_document(filepath)

    os.remove(filepath)

    await msg.delete()


# ======================
# YTDL QUALITY MENU
# ======================

@app.on_message(filters.command("ytdlleech"))
async def ytdl(_, message: Message):

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage:\n/ytdlleech youtube_link"
        )

    url = message.command[1]

    msg = await message.reply_text("🔍 Fetching qualities...")

    try:

        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = info.get("formats", [])

        buttons = []
        added = set()

        for f in formats:

            height = f.get("height")
            fmt = f.get("format_id")

            if not height:
                continue

            text = f"{height}p"

            if text in added:
                continue

            added.add(text)

            key = f"{message.from_user.id}_{fmt}"

            quality_cache[key] = {
                "url": url,
                "format": fmt
            }

            buttons.append([
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"yt_{key}"
                )
            ])

        await msg.edit(
            "🎬 اختر الجودة:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await msg.edit(str(e))


@app.on_callback_query(filters.regex("^yt_"))
async def quality_download(_, query: CallbackQuery):

    key = query.data.replace("yt_", "")

    if key not in quality_cache:
        return await query.answer("Expired")

    data = quality_cache[key]

    url = data["url"]
    fmt = data["format"]

    await query.message.edit("📥 Downloading quality...")

    output = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"

    cmd = (
        f'yt-dlp -f {fmt} '
        f'-o "{output}" "{url}"'
    )

    process = await asyncio.create_subprocess_shell(cmd)
    await process.communicate()

    files = os.listdir(DOWNLOAD_DIR)

    if not files:
        return await query.message.edit("❌ Failed")

    filepath = f"{DOWNLOAD_DIR}/{files[0]}"

    await query.message.edit("📤 Uploading...")

    await query.message.reply_video(filepath)

    os.remove(filepath)

    await query.message.delete()


# ======================
# QB TORRENT
# ======================

@app.on_message(filters.command("qb"))
async def qb(_, message: Message):

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage:\n/qb magnet_link"
        )

    magnet = message.command[1]

    await message.reply_text(
        "🧲 qBittorrent task added\n\n"
        f"{magnet[:100]}"
    )
