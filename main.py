import os
import json
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
    response = requests.post(url, data=data, files=files, timeout=60)
    return response.json()

def send_message(chat_id, text):
    return tg_api("sendMessage", data={
        "chat_id": chat_id,
        "text": text
    })

def get_file(file_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
    response = requests.post(url, data={"file_id": file_id}, timeout=60).json()
    if response.get("ok"):
        return response["result"]
    return None

def download_file(file_id, message_type, unique_id):
    try:
        file_info = get_file(file_id)
        if not file_info:
            return None

        file_path = file_info.get("file_path")
        if not file_path:
            return None

        ext = Path(file_path).suffix or ".bin"
        local_path = MEDIA_DIR / f"{message_type}_{unique_id}{ext}"

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        response = requests.get(file_url, timeout=120)

        if response.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(response.content)
            return str(local_path)
    except Exception:
        return None

    return None

def make_key(connection_id, chat_id, message_id):
    return f"{connection_id}:{chat_id}:{message_id}"

def get_user_label(user):
    if not user:
        return "Неизвестный пользователь"
    username = user.get("username")
    if username:
        return f"@{username}"
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    full_name = " ".join(filter(None, [first_name, last_name])).strip()
    return full_name or str(user.get("id", "unknown"))

def extract_media_info(msg):
    result = {
        "message_type": "unknown",
        "text": msg.get("text", ""),
        "caption": msg.get("caption", ""),
        "file_id": None,
        "file_unique_id": None,
        "file_name": None,
        "mime_type": None,
        "duration": None,
        "stored_path": None,
    }

    if msg.get("text"):
        result["message_type"] = "text"

    elif msg.get("photo"):
        largest = msg["photo"][-1]
        result["message_type"] = "photo"
        result["file_id"] = largest.get("file_id")
        result["file_unique_id"] = largest.get("file_unique_id")

    elif msg.get("video"):
        video = msg["video"]
        result["message_type"] = "video"
        result["file_id"] = video.get("file_id")
        result["file_unique_id"] = video.get("file_unique_id")
        result["mime_type"] = video.get("mime_type")
        result["duration"] = video.get("duration")

    elif msg.get("video_note"):
        video_note = msg["video_note"]
        result["message_type"] = "video_note"
        result["file_id"] = video_note.get("file_id")
        result["file_unique_id"] = video_note.get("file_unique_id")
        result["duration"] = video_note.get("duration")

    elif msg.get("voice"):
        voice = msg["voice"]
        result["message_type"] = "voice"
        result["file_id"] = voice.get("file_id")
        result["file_unique_id"] = voice.get("file_unique_id")
        result["mime_type"] = voice.get("mime_type")
        result["duration"] = voice.get("duration")

    elif msg.get("audio"):
        audio = msg["audio"]
        result["message_type"] = "audio"
        result["file_id"] = audio.get("file_id")
        result["file_unique_id"] = audio.get("file_unique_id")
        result["mime_type"] = audio.get("mime_type")
        result["duration"] = audio.get("duration")
        result["file_name"] = audio.get("file_name")

    elif msg.get("document"):
        document = msg["document"]
        result["message_type"] = "document"
        result["file_id"] = document.get("file_id")
        result["file_unique_id"] = document.get("file_unique_id")
        result["mime_type"] = document.get("mime_type")
        result["file_name"] = document.get("file_name")

    elif msg.get("animation"):
        animation = msg["animation"]
        result["message_type"] = "animation"
        result["file_id"] = animation.get("file_id")
        result["file_unique_id"] = animation.get("file_unique_id")
        result["mime_type"] = animation.get("mime_type")
        result["file_name"] = animation.get("file_name")
        result["duration"] = animation.get("duration")

    elif msg.get("sticker"):
        sticker = msg["sticker"]
        result["message_type"] = "sticker"
        result["file_id"] = sticker.get("file_id")
        result["file_unique_id"] = sticker.get("file_unique_id")

    return result

def build_message_preview(item):
    mtype = item.get("message_type", "unknown")
    text = item.get("text") or item.get("caption") or ""
    file_name = item.get("file_name") or ""
    stored_path = item.get("stored_path") or ""

    if mtype == "text":
        return f"Текст:\n{text or '—'}"
    if mtype == "video_note":
        return f"Кружок\nДлительность: {item.get('duration') or '—'} сек\nФайл: {stored_path or 'не сохранён'}"
    if mtype == "voice":
        return f"Голосовое\nДлительность: {item.get('duration') or '—'} сек\nФайл: {stored_path or 'не сохранён'}"
    if mtype == "video":
        return f"Видео\nПодпись: {item.get('caption') or '—'}\nФайл: {stored_path or 'не сохранён'}"
    if mtype == "photo":
        return f"Фото\nПодпись: {item.get('caption') or '—'}\nФайл: {stored_path or 'не сохранён'}"
    if mtype == "document":
        return f"Документ\nИмя: {file_name or '—'}\nПодпись: {item.get('caption') or '—'}\nФайл: {stored_path or 'не сохранён'}"
    if mtype == "audio":
        return f"Аудио\nИмя: {file_name or '—'}\nФайл: {stored_path or 'не сохранён'}"
    if mtype == "animation":
        return f"GIF/анимация\nИмя: {file_name or '—'}\nФайл: {stored_path or 'не сохранён'}"
    if mtype == "sticker":
        return f"Стикер\nФайл: {stored_path or 'не сохранён'}"
    return f"Тип: {mtype}\n{text or stored_path or '—'}"

@app.get("/")
async def root():
    return {"ok": True, "service": "telegram-business-logger"}

@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None)
):
    if x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    update = await request.json()

    if update.get("business_message"):
        msg = update["business_message"]
        key = make_key(msg.get("business_connection_id"), msg["chat"]["id"], msg["message_id"])
        user_label = get_user_label(msg.get("from"))

        media_info = extract_media_info(msg)

        if media_info["file_id"] and media_info["file_unique_id"]:
            stored_path = download_file(
                media_info["file_id"],
                media_info["message_type"],
                media_info["file_unique_id"]
            )
            media_info["stored_path"] = stored_path

        saved_messages[key] = {
            "connection_id": msg.get("business_connection_id"),
            "chat_id": msg["chat"]["id"],
            "message_id": msg["message_id"],
            "user_label": user_label,
            **media_info
        }
        save_messages(saved_messages)

    elif update.get("edited_business_message"):
        msg = update["edited_business_message"]
        key = make_key(msg.get("business_connection_id"), msg["chat"]["id"], msg["message_id"])
        old = saved_messages.get(key)

        user_label = get_user_label(msg.get("from"))
        media_info = extract_media_info(msg)

        if media_info["file_id"] and media_info["file_unique_id"]:
            stored_path = download_file(
                media_info["file_id"],
                media_info["message_type"],
                media_info["file_unique_id"]
            )
            media_info["stored_path"] = stored_path

        old_text = ""
        old_preview = "Не было сохранено"
        if old:
            old_text = old.get("text") or old.get("caption") or ""
            old_preview = build_message_preview(old)

        new_text = media_info.get("text") or media_info.get("caption") or ""
        new_preview = build_message_preview(media_info)

        saved_messages[key] = {
            "connection_id": msg.get("business_connection_id"),
            "chat_id": msg["chat"]["id"],
            "message_id": msg["message_id"],
            "user_label": user_label,
            "previous_text": old_text,
            **media_info
        }
        save_messages(saved_messages)

        if ADMIN_CHAT_ID:
            if old and old.get("message_type") == "text" and media_info.get("message_type") == "text":
                send_message(
                    ADMIN_CHAT_ID,
                    f"✏️ {user_label} изменил сообщение\n\nБыло:\n{old_text or '—'}\n\nСтало:\n{new_text or '—'}"
                )
            else:
                send_message(
                    ADMIN_CHAT_ID,
                    f"✏️ {user_label} изменил сообщение\n\nБыло:\n{old_preview}\n\nСтало:\n{new_preview}"
                )

    elif update.get("deleted_business_messages"):
        deleted = update["deleted_business_messages"]
        for message_id in deleted.get("message_ids", []):
            key = make_key(deleted.get("business_connection_id"), deleted["chat"]["id"], message_id)
            old = saved_messages.get(key)

            if ADMIN_CHAT_ID:
                if old:
                    send_message(
                        ADMIN_CHAT_ID,
                        f"🗑 {old['user_label']} удалил сообщение\n\n{build_message_preview(old)}"
                    )
                else:
                    send_message(
                        ADMIN_CHAT_ID,
                        f"🗑 Удалено сообщение ID {message_id}, но оно не было сохранено заранее."
                    )

    return {"ok": True}
