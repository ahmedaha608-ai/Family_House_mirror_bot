FROM python:3.11-slim

WORKDIR /app

# نسخ كل ملفات المشروع للمجلد الرئيسي /app
COPY . .

# تثبيت قفل التورنت وحزم النظام المطلوبة
RUN apt-get update && apt-get install -y \
    qbittorrent-nox \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# تثبيت المكتبات (Pyrogram, yt-dlp, وغيرها)
RUN pip install --no-cache-dir -r requirements.txt

# تشغيل البوت من الملف الرئيسي مباشرة (بدون الحاجة لـ start.sh)
CMD ["python", "__init__.py"]
