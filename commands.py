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

from config import app

# =========================================================
# ⚙️ إعدادات البوت
# =========================================================

ADMIN_ID = 7030252495

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

user_video_format = {}
user_compress_res = {}
user_backgrounds = {}
quality_cache = {}
active_tasks = {}

# =========================================================
# 🔍 Kraken Engine
# =========================================================

def bypass_and_get_clean_title(url):

    default_title = ""
    target_url = url

    if "krakenfiles.com" in url:

        try:

            url = url.replace("/download/", "/view/")

            parsed_url = urllib.parse.urlparse(url)

            conn = http.client.HTTPSConnection(
                parsed_url.netloc,
                timeout=15
            )

            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                'Accept': (
                    'text/html,application/xhtml+xml,application/xml;'
                    'q=0.9,image/webp,*/*;q=0.8'
                ),
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': url
            }

            conn.request(
                "GET",
                parsed_url.path,
                headers=headers
            )

            response = conn.getresponse()

            html_content = response.read().decode(
                'utf-8',
                errors='ignore'
            )

            conn.close()

            title_match = re.search(
                r'<title>(.*?)</title>',
                html_content,
                re.IGNORECASE
            )

            if title_match:

                raw_page_title = title_match.group(1)

                raw_page_title = re.sub(
                    r'(?i)-\s*KrakenFiles\.com',
                    '',
                    raw_page_title
                )

                raw_page_title = re.sub(
                    r'(?i)Free\s*File\s*Sharing',
                    '',
                    raw_page_title
                )

                default_title = raw_page_title.strip()

            if not default_title:

                meta_title = re.search(
                    r'property="og:title"\s+content="(.*?)"',
                    html_content
                )

                if meta_title:
                    default_title = meta_title.group(1)

            stream_url_match = re.search(
                r'data-url=["\']([^"\']+?)["\']',
                html_content
            )

            if stream_url_match:

                token_url = stream_url_match.group(1)

                if token_url.startswith("//"):
                    token_url = "https:" + token_url

                target_url = token_url

            else:

                matches = re.findall(
                    r'https://[^"\']+?\.mp4[^"\']*?',
                    html_content
                )

                if matches:
                    target_url = matches[0]

                else:

                    file_id = (
                        url.split('/')[-2]
                        if url.endswith('/')
                        else url.split('/')[-1]
                    )

                    if file_id != "file.html":

                        target_url = (
                            f"https://krakenfiles.com/download/{file_id}"
                        )

        except Exception as e:
            print(f"Kraken Engine Error: {e}")

    return target_url, default_title

# =========================================================
# 🧹 تنظيف الأسماء
# =========================================================

def clean_filename_title(raw_title):

    if not raw_title:
        return "مقطع مرئي"

    for ext in [
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".flv",
        ".webm",
        ".html",
        ".htm"
    ]:
        raw_title = re.sub(
            re.escape(ext),
            "",
            raw_title,
            flags=re.IGNORECASE
        )

    junk_patterns = [
        r'\[.*?\]',
        r'\(.*?\)',
        r'\{.*?\}',
        r'(?i)arabseed',
        r'(?i)tuktukcima',
        r'(?i)cima',
        r'(?i)egybest',
        r'(?i)wecima',
        r'(?i)mycima',
        r'(?i)vod',
        r'عرب\s*سيد',
        r'توك\s*توك\s*سيما',
        r'ماي\s*سيما',
        r'ايجي\s*بست',
        r'موقع',
        r'تحميل',
        r'مشاهدة',
        r'فيلم',
        r'كامل',
        r'مترجم'
    ]

    for pattern in junk_patterns:
        raw_title = re.sub(pattern, "", raw_title)

    raw_title = (
        raw_title
        .replace(".", " ")
        .replace("-", " ")
        .replace("_", " ")
        .replace("+", " ")
    )

    clean_title = re.sub(
        r'\s+',
        ' ',
        raw_title
    ).strip()

    return clean_title if clean_title else "مقطع مرئي"

# =========================================================
# 📊 حالة السيرفر
# =========================================================

def get_server_status():

    total, used, free = shutil.disk_usage("/")

    disk_p = (used / total) * 100

    try:

        with open('/proc/loadavg', 'r') as f:

            load = f.read().split()[0]

            cpu_p = min(float(load) * 100 / 2, 100.0)

    except:
        cpu_p = 20.0

    return (
        f"⚙️ CPU: {cpu_p:.1f}%\n"
        f"💾 التخزين: {disk_p:.1f}%"
    )

# =========================================================
# 📊 Progress Bar
# =========================================================

async def progress_bar(
    current,
    total,
    reply_msg,
    start_time,
    task_key,
    mode="رفع 📤"
):

    if active_tasks.get(task_key) == "cancelled":
        raise Exception("TASK_CANCELLED")

    now = time.time()

    diff = now - start_time

    if round(diff % 4.0) == 0 or current == total:

        percentage = (
            (current / total) * 100
            if total > 0 else 0
        )

        speed = current / diff if diff > 0 else 0

        speed_kb = speed / 1024
        speed_mb = speed_kb / 1024

        speed_text = (
            f"{speed_mb:.1f} MB/s"
            if speed_mb > 1
            else f"{speed_kb:.1f} KB/s"
        )

        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)

        blocks = int(percentage // 10)

        bar = (
            "■" * blocks
            + "□" * (10 - blocks)
        )

        status = get_server_status()

        progress_text = (
            f"⚡ {mode}\n\n"
            f"📊 [{bar}] {percentage:.1f}%\n"
            f"📦 {current_mb:.1f} MB / {total_mb:.1f} MB\n"
            f"🚀 {speed_text}\n\n"
            f"{status}"
        )

        buttons = [[
            InlineKeyboardButton(
                "❌ إلغاء",
                callback_data=f"cancel_{task_key}"
            )
        ]]

        try:

            await reply_msg.edit_text(
                progress_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except:
            pass

# =========================================================
# 🔄 Safe Progress Hook
# =========================================================

def safe_progress(
    current,
    total,
    reply_msg,
    start_time,
    task_key,
    mode
):

    try:

        loop = asyncio.get_running_loop()

        loop.create_task(
            progress_bar(
                current,
                total,
                reply_msg,
                start_time,
                task_key,
                mode
            )
        )

    except:
        pass

# =========================================================
# 📥 Download Engine
# =========================================================

async def download_direct_mp4_with_progress(
    url,
    output_path,
    reply_msg,
    task_key
):

    start_time = time.time()

    def hook(d):

        if active_tasks.get(task_key) == "cancelled":
            raise Exception("TASK_CANCELLED")

        if d['status'] == 'downloading':

            current = d.get('downloaded_bytes', 0)

            total = (
                d.get('total_bytes')
                or d.get('total_bytes_estimate', 0)
            )

            if total > 0:

                safe_progress(
                    current,
                    total,
                    reply_msg,
                    start_time,
                    task_key,
                    "تنزيل ⚡📥"
                )

    ydl_opts_aria = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'progress_hooks': [hook],
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'retries': 10,
        'fragment_retries': 10,
        'user_agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'external_downloader': 'aria2c',
        'external_downloader_args': [
            '-j', '16',
            '-x', '16',
            '-s', '16',
            '-k', '1M',
            '--allow-overwrite=true'
        ]
    }

    try:

        await asyncio.to_thread(
            yt_dlp.YoutubeDL(ydl_opts_aria).download,
            [url]
        )

        if (
            os.path.exists(output_path)
            and os.path.getsize(output_path) > 1048576
        ):
            return True

    except:
        pass

    ydl_opts_native = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'progress_hooks': [hook],
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'retries': 10,
        'fragment_retries': 10,
        'user_agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
    }

    try:

        await asyncio.to_thread(
            yt_dlp.YoutubeDL(ydl_opts_native).download,
            [url]
        )

        if (
            os.path.exists(output_path)
            and os.path.getsize(output_path) > 1048576
        ):
            return True

    except:
        pass

    return False
