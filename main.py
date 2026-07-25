import os
import json
from pathlib import Path
from fastapi import FastAPI, Request, Header, HTTPException
from aiogram import Bot
from aiogram.types import Update
from aiohttp import ClientSession

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")

app = FastAPI()
bot = Bot(token=BOT_TOKEN)

DATA_FILE = "messages.json"
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)

def load_messages():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_messages(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

saved_messages = load_messages()

def make_key(connection_id, chat_id, message_id):
    return f"{connection_id}:{chat_id}:{message_id}"

def get_user_label(user):
    if not user:
        return "Неизвестный пользователь"
    if user.username:
        return f"@{user.username}"
    full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip()
    return full_name or str(user.id)

def extract_media_info(msg):
    result = {
        "message_type": "unknown",
        "text": msg.text or "",
        "caption": msg.caption or "",
        "file_id": None,
        "file_unique_id": None,
        "file_name": None,
        "mime_type": None,
        "duration": None,
        "stored_path": None,
    }

    if msg.text:
        result["message_type"] = "text"

    elif msg.photo:
        largest = msg.photo[-1]
        result["message_type"] = "photo"
        result["file_id"] = largest.file_id
        result["file_unique_id"] = largest.file_unique_id

    elif msg.video:
        result["message_type"] = "video"
        result["file_id"] = msg.video.file_id
        result["file_unique_id"] = msg.video.file_unique_id
        result["mime_type"] = msg.video.mime_type
        result["duration"] = msg.video.duration

    elif msg.video_note:
        result["message_type"] = "video_note"
        result["file_id"] = msg.video_note.file_id
        result["file_unique_id"] = msg.video_note.file_unique_id
        result["duration"] = msg.video_note.duration

    elif msg.voice:
        result["message_type"] = "voice"
        result["file_id"] = msg.voice.file_id
        result["file_unique_id"] = msg.voice.file_unique_id
        result["mime_type"] = msg.voice.mime_type
        result["duration"] = msg.voice.duration

    elif msg.audio:
        result["message_type"] = "audio"
        result["file_id"] = msg.audio.file_id
        result["file_unique_id"] = msg.audio.file_unique_id
        result["mime_type"] = msg.audio.mime_type
        result["duration"] = msg.audio.duration
        result["file_name"] = msg.audio.file_name

    elif msg.document:
        result["message_type"] = "document"
        result["file_id"] = msg.document.file_id
        result["file_unique_id"] = msg.document.file_unique_id
        result["mime_type"] = msg.document.mime_type
        result["file_name"] = msg.document.file_name

    elif msg.animation:
        result["message_type"] = "animation"
        result["file_id"] = msg.animation.file_id
        result["file_unique_id"] = msg.animation.file_unique_id
        result["mime_type"] = msg.animation.mime_type
        result["file_name"] = msg.animation.file_name
        result["duration"] = msg.animation.duration

    elif msg.sticker:
        result["message_type"] = "sticker"
        result["file_id"] = msg.sticker.file_id
        result["file_unique_id"] = msg.sticker.file_unique_id

    return result

async def download_file(file_id, message_type, unique_id):
    try:
        file = await bot.get_file(file_id)
        file_path = file.file_path
        ext = Path(file_path).suffix or ".bin"
        local_path = MEDIA_DIR / f"{message_type}_{unique_id}{ext}"

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        async with ClientSession() as session:
            async with session.get(file_url) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    with open(local_path, "wb") as f:
                        f.write(content)
                    return str(local_path)
    except Exception:
        return None

    return None

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

    data = await request.json()
    update = Update.model_validate(data)

    if update.business_message:
        msg = update.business_message
        key = make_key(msg.business_connection_id, msg.chat.id, msg.message_id)
        user_label = get_user_label(msg.from_user)

        media_info = extract_media_info(msg)

        if media_info["file_id"] and media_info["file_unique_id"]:
            stored_path = await download_file(
                media_info["file_id"],
                media_info["message_type"],
                media_info["file_unique_id"]
            )
            media_info["stored_path"] = stored_path

        saved_messages[key] = {
            "connection_id": msg.business_connection_id,
            "chat_id": msg.chat.id,
            "message_id": msg.message_id,
            "user_label": user_label,
            **media_info
        }
        save_messages(saved_messages)

    elif update.edited_business_message:
        msg = update.edited_business_message
        key = make_key(msg.business_connection_id, msg.chat.id, msg.message_id)
        old = saved_messages.get(key)

        user_label = get_user_label(msg.from_user)
        media_info = extract_media_info(msg)

        if media_info["file_id"] and media_info["file_unique_id"]:
            stored_path = await download_file(
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
            "connection_id": msg.business_connection_id,
            "chat_id": msg.chat.id,
            "message_id": msg.message_id,
            "user_label": user_label,
            "previous_text": old_text,
            **media_info
        }
        save_messages(saved_messages)

        if ADMIN_CHAT_ID:
            if old and old.get("message_type") == "text" and media_info.get("message_type") == "text":
                await bot.send_message(
                    ADMIN_CHAT_ID,
                    f"✏️ {user_label} изменил сообщение\n\nБыло:\n{old_text or '—'}\n\nСтало:\n{new_text or '—'}"
                )
            else:
                await bot.send_message(
                    ADMIN_CHAT_ID,
                    f"✏️ {user_label} изменил сообщение\n\nБыло:\n{old_preview}\n\nСтало:\n{new_preview}"
                )

    elif update.deleted_business_messages:
        deleted = update.deleted_business_messages
        for message_id in deleted.message_ids:
            key = make_key(deleted.business_connection_id, deleted.chat.id, message_id)
            old = saved_messages.get(key)

            if ADMIN_CHAT_ID:
                if old:
                    await bot.send_message(
                        ADMIN_CHAT_ID,
                        f"🗑 {old['user_label']} удалил сообщение\n\n{build_message_preview(old)}"
                    )
                else:
                    await bot.send_message(
                        ADMIN_CHAT_ID,
                        f"🗑 Удалено сообщение ID {message_id}, но оно не было сохранено заранее."
                    )

    return {"ok": True}
