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
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from config import app

ADMIN_ID = 7030252495  
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

user_video_format = {}    
user_compress_res = {}    
user_backgrounds = {}     
quality_cache = {}
active_tasks = {}         

# =========================================================
# 🔍 المحرك الاحترافي: يدعم Krakenfiles والروابط العامة
# =========================================================
def bypass_and_get_clean_title(url):
    default_title = ""
    target_url = url
    
    if "krakenfiles.com" in url:
        try:
            url = url.replace("/download/", "/view/")
            parsed_url = urllib.parse.urlparse(url)
            conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=15)
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36', 'Referer': url}
            conn.request("GET", parsed_url.path, headers=headers)
            response = conn.getresponse()
            html_content = response.read().decode('utf-8', errors='ignore')
            conn.close()
            
            title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
            if title_match:
                default_title = re.sub(r'(?i)-\s*KrakenFiles\.com', '', title_match.group(1)).strip()
            
            stream_url_match = re.search(r'data-url=["\']([^"\']+?)["\']', html_content)
            if stream_url_match:
                target_url = "https:" + stream_url_match.group(1) if stream_url_match.group(1).startswith("//") else stream_url_match.group(1)
        except Exception as e:
            print(f"Kraken Engine Error: {e}")
    else:
        # لمحاولة الحصول على العنوان للروابط العادية
        default_title = "فيديو_من_رابط_مباشر"
            
    return target_url, default_title

def clean_filename_title(raw_title):
    if not raw_title: return "مقطع مرئي"
    raw_title = raw_title.split('?')[0] # إزالة البارامترات
    junk_patterns = [r'\[.*?\]', r'\(.*?\)', r'(?i)arabseed', r'(?i)egybest', r'(?i)mycima', r'(?i)مشاهدة', r'(?i)فيلم']
    for pattern in junk_patterns: raw_title = re.sub(pattern, "", raw_title)
    return re.sub(r'\s+', ' ', raw_title).strip()

# =========================================================
# 📊 نظام العداد الذكي (محدث لمنع RuntimeWarning)
# =========================================================
async def progress_bar(current, total, reply_msg, start_time, task_key, mode="رفع 📤"):
    if active_tasks.get(task_key) == "cancelled": raise Exception("TASK_CANCELLED")
    
    percentage = (current / total) * 100 if total > 0 else 0
    # تحديث كل 5 ثوانٍ لتقليل عدد الرسائل
    if round(time.time() - start_time) % 5 == 0 or percentage >= 100:
        try:
            await reply_msg.edit_text(f"⚡ {mode}: {percentage:.1f}%")
        except: pass

# =========================================================
# 🔄 محرك التحميل الموحد (تم تحديث الـ hook)
# =========================================================
async def download_direct_mp4_with_progress(url, output_path, reply_msg, task_key):
    start_time = time.time()
    
    def hook(d):
        if active_tasks.get(task_key) == "cancelled": raise Exception("TASK_CANCELLED")
        if d['status'] == 'downloading':
            current = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total > 0:
                # الحل الجذري لمشكلة RuntimeWarning
                asyncio.create_task(progress_bar(current, total, reply_msg, start_time, task_key))

    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'progress_hooks': [hook],
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'referer': url # ضروري جداً للروابط المباشرة
    }
    
    try:
        await asyncio.to_thread(yt_dlp.YoutubeDL(ydl_opts).download, [url])
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1024*1024
    except:
        return False

# =========================================================
# 🚀 الأوامر (Command leech)
# =========================================================
@app.on_message(filters.command(["leech"]) & (filters.private | filters.group))
async def leech(_, message: Message):
    if len(message.command) < 2: return await message.reply("أرسل الرابط مع الأمر")
    raw_url = message.command[1]
    task_key = str(message.id)
    active_tasks[task_key] = "running"
    
    msg = await message.reply("⏳ جاري المعالجة...")
    
    # تحويل الرابط إذا كان كراكن أو استخدامه مباشرة
    url, title = bypass_and_get_clean_title(raw_url)
    real_title = clean_filename_title(title or "video")
    
    filepath = os.path.join(DOWNLOAD_DIR, f"video_{message.id}.mp4")
    
    success = await download_direct_mp4_with_progress(url, filepath, msg, task_key)
    
    if success:
        await msg.edit("📤 جاري الرفع...")
        await message.reply_video(video=filepath, caption=real_title)
        await msg.delete()
    else:
        await msg.edit("❌ فشل التحميل. تأكد من صحة الرابط.")
        
    if os.path.exists(filepath): os.remove(filepath)
    active_tasks.pop(task_key, None)

# إضافة بقية الأوامر (ytdlleech, compress, clean) بنفس المنطق...
