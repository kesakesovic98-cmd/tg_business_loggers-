import os
import json
import html
from pathlib import Path
import requests
from fastapi import FastAPI, Request, Header, HTTPException

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")

app = FastAPI()

DATA_FILE = "messages.json"
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)

def load_messages():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_messages(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

saved_messages = load_messages()

def tg_api(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    response = requests.post(url, data=data, files=files, timeout=120)
    return response.json()

def send_message(chat_id, text):
    return tg_api("sendMessage", data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

def send_photo(chat_id, photo_path, caption=""):
    url 
