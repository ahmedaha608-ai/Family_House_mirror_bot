#!/bin/bash

echo "Starting Telegram Bot..."

python3 config.py

if [ -f "update.py" ]; then
    python3 update.py
fi

if [ -d "bot" ]; then
    python3 -m bot
else
    echo "Bot source folder not found!"
fi
