import os
import json
import html
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, Request, Header, HTTPException

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

app = FastAPI()

MESSAGES_FILE = "messages.json"
CONNECTIONS_FILE = "connections.json"
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)


def load_json(path: str):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


saved_messages = load_json(MESSAGES_FILE)
saved_connections = load_json(CONNECTIONS_FILE)


@app.get("/")
async def root():
    return {"ok": True, "service": "telegram-business-user-notifier"}


@app.get("/health")
async def health():
    return {"ok": True}


def escape_text(value) -> str:
    return html.escape(str(value or "—"))


def quote_box(text: str) -> str:
    text = str(text or "—").strip()
    lines = text.split("\n")
    return "\n".join([f"┃ <b>{escape_text(line)}</b>" for line in lines])


def tg_api(method: str, data=None, files=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    response = requests.post(url, data=data, files=files, timeout=120)
    try:
        return response.json()
    except Exception:
        return {"ok": False, "status_code": response.status_code, "text": response.text}


def send_message(chat_id: int, text: str):
    return tg_api("sendMessage", data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })


def send_photo(chat_id: int, photo_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML"
    }
    with open(photo_path, "rb") as f:
        response = requests.post(url, data=data, files={"photo": f}, timeout=120)
    try:
        return response.json()
    except Exception:
        return {"ok": False, "status_code": response.status_code, "text": response.text}


def send_video(chat_id: int, video_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML"
    }
    with open(video_path, "rb") as f:
        response = requests.post(url, data=data, files={"video": f}, timeout=120)
    try:
        return response.json()
    except Exception:
        return {"ok": False, "status_code": response.status_code, "text": response.text}


def send_document(chat_id: int, file_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML"
    }
    with open(file_path, "rb") as f:
        response = requests.post(url, data=data, files={"document": f}, timeout=120)
    try:
        return response.json()
    except Exception:
        return {"ok": False, "status_code": response.status_code, "text": response.text}


def get_file(file_id: str):
    response = tg_api("getFile", data={"file_id": file_id})
    if response.get("ok"):
        return response.get("result")
    return None


def download_file(file_id: str, prefix: str, unique_id: str):
    try:
        file_info = get_file(file_id)
        if not file_info:
            return None

        remote_path = file_info.get("file_path")
        if not remote_path:
            return None

        ext = Path(remote_path).suffix or ".bin"
        local_path = MEDIA_DIR / f"{prefix}_{unique_id}{ext}"

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{remote_path}"
        response = requests.get(file_url, timeout=120)
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(response.content)
            return str(local_path)
    except Exception as e:
        print("DOWNLOAD ERROR:", str(e))

    return None


def message_key(chat_id, message_id) -> str:
    return f"{chat_id}:{message_id}"


def get_user_label(user) -> str:
    if not user:
        return "Неизвестный пользователь"

    username = user.get("username")
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    full_name = " ".join(filter(None, [first_name, last_name])).strip()

    if full_name and username:
        return f"{full_name} (@{username})"
    if username:
        return f"@{username}"
    if full_name:
        return full_name
    return str(user.get("id", "unknown"))


def store_connection(business_connection_id: str, user_chat_id: Optional[int], user_obj=None):
    if not business_connection_id:
        return

    item = saved_connections.get(business_connection_id, {})
    if user_chat_id is not None:
        item["user_chat_id"] = user_chat_id
    if user_obj is not None:
        item["user"] = user_obj

    saved_connections[business_connection_id] = item
    save_json(CONNECTIONS_FILE, saved_connections)


def get_owner_chat_id(business_connection_id: Optional[str], fallback_chat_id=None):
    if business_connection_id and business_connection_id in saved_connections:
        user_chat_id = saved_connections[business_connection_id].get("user_chat_id")
        if user_chat_id:
            return user_chat_id
    return fallback_chat_id


def safe_notify_owner(business_connection_id: Optional[str], text: str, fallback_chat_id=None):
    owner_chat_id = get_owner_chat_id(business_connection_id, fallback_chat_id=fallback_chat_id)
    if not owner_chat_id:
        print("NO OWNER CHAT:", {"business_connection_id": business_connection_id, "fallback_chat_id": fallback_chat_id})
        return None
    result = send_message(owner_chat_id, text)
    print("SEND RESULT:", result)
    return result


def safe_notify_owner_photo(business_connection_id: Optional[str], photo_path: str, caption: str = "", fallback_chat_id=None):
    owner_chat_id = get_owner_chat_id(business_connection_id, fallback_chat_id=fallback_chat_id)
    if not owner_chat_id:
        print("NO OWNER CHAT:", {"business_connection_id": business_connection_id, "fallback_chat_id": fallback_chat_id})
        return None
    result = send_photo(owner_chat_id, photo_path, caption=caption)
    print("SEND PHOTO RESULT:", result)
    return result


def safe_notify_owner_video(business_connection_id: Optional[str], video_path: str, caption: str = "", fallback_chat_id=None):
    owner_chat_id = get_owner_chat_id(business_connection_id, fallback_chat_id=fallback_chat_id)
    if not owner_chat_id:
        print("NO OWNER CHAT:", {"business_connection_id": business_connection_id, "fallback_chat_id": fallback_chat_id})
        return None
    result = send_video(owner_chat_id, video_path, caption=caption)
    print("SEND VIDEO RESULT:", result)
    return result


def safe_notify_owner_document(business_connection_id: Optional[str], file_path: str, caption: str = "", fallback_chat_id=None):
    owner_chat_id = get_owner_chat_id(business_connection_id, fallback_chat_id=fallback_chat_id)
    if not owner_chat_id:
        print("NO OWNER CHAT:", {"business_connection_id": business_connection_id, "fallback_chat_id": fallback_chat_id})
        return None
    result = send_document(owner_chat_id, file_path, caption=caption)
    print("SEND DOCUMENT RESULT:", result)
    return result


def get_reply_preview(reply_to):
    if not reply_to:
        return None
    if reply_to.get("text"):
        return reply_to["text"]
    if reply_to.get("caption"):
        return reply_to["caption"]
    if reply_to.get("photo"):
        return "[photo]"
    if reply_to.get("video"):
        return "[video]"
    if reply_to.get("document"):
        return "[document]"
    if reply_to.get("voice"):
        return "[voice]"
    return None


def extract_reply_media(reply_to):
    if not reply_to:
        return None

    if reply_to.get("photo"):
        largest = reply_to["photo"][-1]
        return {
            "message_type": "photo",
            "file_id": largest.get("file_id"),
            "file_unique_id": largest.get("file_unique_id"),
            "caption": reply_to.get("caption", "")
        }

    if reply_to.get("video"):
        video = reply_to["video"]
        return {
            "message_type": "video",
            "file_id": video.get("file_id"),
            "file_unique_id": video.get("file_unique_id"),
            "caption": reply_to.get("caption", "")
        }

    if reply_to.get("document"):
        doc = reply_to["document"]
        return {
            "message_type": "document",
            "file_id": doc.get("file_id"),
            "file_unique_id": doc.get("file_unique_id"),
            "caption": reply_to.get("caption", "")
        }

    return None


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
        "reply_to_preview": None,
    }

    if msg.get("reply_to_message"):
        result["reply_to_preview"] = get_reply_preview(msg.get("reply_to_message"))

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

    elif msg.get("document"):
        doc = msg["document"]
        result["message_type"] = "document"
        result["file_id"] = doc.get("file_id")
        result["file_unique_id"] = doc.get("file_unique_id")
        result["file_name"] = doc.get("file_name")
        result["mime_type"] = doc.get("mime_type")

    elif msg.get("voice"):
        voice = msg["voice"]
        result["message_type"] = "voice"
        result["file_id"] = voice.get("file_id")
        result["file_unique_id"] = voice.get("file_unique_id")
        result["duration"] = voice.get("duration")
        result["mime_type"] = voice.get("mime_type")

    return result


def build_message_preview(item) -> str:
    if not item:
        return "—"

    mtype = item.get("message_type")
    if mtype == "text":
        return item.get("text") or "—"
    if mtype == "photo":
        return f"Фото\nПодпись: {item.get('caption') or '—'}"
    if mtype == "video":
        return f"Видео\nПодпись: {item.get('caption') or '—'}"
    if mtype == "document":
        return f"Документ\nИмя: {item.get('file_name') or '—'}\nПодпись: {item.get('caption') or '—'}"
    if mtype == "voice":
        return f"Голосовое\nДлительность: {item.get('duration') or '—'} сек"
    return item.get("text") or item.get("caption") or "—"


def build_deleted_text_message(user_label: str, preview: str) -> str:
    return (
        f"🗑 <b>{escape_text(user_label)}</b> <b>УДАЛИЛ(А) СООБЩЕНИЕ</b>\n\n"
        f"{quote_box(preview or '—')}"
    )


def build_deleted_caption(user_label: str) -> str:
    return f"🗑 <b>{escape_text(user_label)}</b> <b>УДАЛИЛ(А) СООБЩЕНИЕ</b>"


def build_edited_text_message(user_label: str, old_text: str, new_text: str) -> str:
    return (
        f"✏️ <b>{escape_text(user_label)}</b> <b>ИЗМЕНИЛ(А) СООБЩЕНИЕ</b>\n\n"
        f"<b>OLD:</b>\n"
        f"{quote_box(old_text or '—')}\n\n"
        f"<b>NEW:</b>\n"
        f"{quote_box(new_text or '—')}"
    )


def build_edited_media_message(user_label: str, old_preview: str, new_preview: str) -> str:
    return (
        f"✏️ <b>{escape_text(user_label)}</b> <b>ИЗМЕНИЛ(А) СООБЩЕНИЕ</b>\n\n"
        f"<b>OLD:</b>\n"
        f"{quote_box(old_preview or '—')}\n\n"
        f"<b>NEW:</b>\n"
        f"{quote_box(new_preview or '—')}"
    )


def build_reply_saved_caption(user_label: str, caption: str) -> str:
    return (
        f"💾 <b>{escape_text(user_label)}</b> <b>ОТВЕТИЛ(А) НА REPLY-МЕДИА</b>\n\n"
        f"<b>СОХРАНЕНО АВТОМАТИЧЕСКИ</b>\n"
        f"{quote_box(caption or 'Без подписи')}"
    )


def auto_forward_reply_media_to_owner(business_connection_id: Optional[str], fallback_chat_id, user_label: str, reply_to):
    reply_media = extract_reply_media(reply_to)
    if not reply_media:
        return False

    file_id = reply_media.get("file_id")
    file_unique_id = reply_media.get("file_unique_id")
    message_type = reply_media.get("message_type")
    caption = reply_media.get("caption") or ""

    if not file_id or not file_unique_id:
        return False

    stored_path = download_file(file_id, f"reply_{message_type}", file_unique_id)
    if not stored_path or not os.path.exists(stored_path):
        return False

    notify_caption = build_reply_saved_caption(user_label, caption)

    if message_type == "photo":
        safe_notify_owner_photo(business_connection_id, stored_path, caption=notify_caption, fallback_chat_id=fallback_chat_id)
        return True

    if message_type == "video":
        safe_notify_owner_video(business_connection_id, stored_path, caption=notify_caption, fallback_chat_id=fallback_chat_id)
        return True

    if message_type == "document":
        safe_notify_owner_document(business_connection_id, stored_path, caption=notify_caption, fallback_chat_id=fallback_chat_id)
        return True

    return False


@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None)
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    try:
        update = await request.json()
        print("UPDATE:", update)

        if "business_connection" in update:
            bc = update["business_connection"]
            bc_id = bc.get("id")
            user_chat_id = bc.get("user_chat_id")
            user_obj = bc.get("user")

            if bc_id:
                store_connection(bc_id, user_chat_id, user_obj)

            if bc.get("is_enabled") and user_chat_id:
                send_message(
                    user_chat_id,
                    "✅ <b>Бот подключён.</b>\n\n"
                    "Теперь удалённые, изменённые сообщения и сохранённые reply-медиа "
                    "будут приходить сюда, в этот чат с ботом."
                )

        elif "business_message" in update:
            msg = update["business_message"]
            bc_id = msg.get("business_connection_id")
            chat_id = (msg.get("chat") or {}).get("id")
            message_id = msg.get("message_id")
            user_label = get_user_label(msg.get("from"))

            if bc_id:
                owner_chat_id = get_owner_chat_id(bc_id, fallback_chat_id=chat_id)
                store_connection(bc_id, owner_chat_id, msg.get("from"))

            media_info = extract_media_info(msg)

            if media_info["file_id"] and media_info["file_unique_id"]:
                media_info["stored_path"] = download_file(
                    media_info["file_id"],
                    media_info["message_type"],
                    media_info["file_unique_id"]
                )

            saved_messages[message_key(chat_id, message_id)] = {
                "business_connection_id": bc_id,
                "owner_chat_id": get_owner_chat_id(bc_id, fallback_chat_id=chat_id),
                "chat_id": chat_id,
                "message_id": message_id,
                "user_label": user_label,
                **media_info
            }
            save_json(MESSAGES_FILE, saved_messages)

            reply_to = msg.get("reply_to_message")
            if reply_to:
                auto_forward_reply_media_to_owner(
                    bc_id,
                    get_owner_chat_id(bc_id, fallback_chat_id=chat_id),
                    user_label,
                    reply_to
                )

        elif "edited_business_message" in update:
            msg = update["edited_business_message"]
            bc_id = msg.get("business_connection_id")
            chat_id = (msg.get("chat") or {}).get("id")
            message_id = msg.get("message_id")
            key = message_key(chat_id, message_id)

            old = saved_messages.get(key)
            user_label = get_user_label(msg.get("from"))
            media_info = extract_media_info(msg)

            if media_info["file_id"] and media_info["file_unique_id"]:
                media_info["stored_path"] = download_file(
                    media_info["file_id"],
                    media_info["message_type"],
                    media_info["file_unique_id"]
                )

            old_text = ""
            old_preview = "Не было сохранено"

            if old:
                old_text = old.get("text") or old.get("caption") or ""
                old_preview = build_message_preview(old)

            new_text = media_info.get("text") or media_info.get("caption") or ""
            new_preview = build_message_preview(media_info)

            saved_messages[key] = {
                "business_connection_id": bc_id,
                "owner_chat_id": get_owner_chat_id(bc_id, fallback_chat_id=chat_id),
                "chat_id": chat_id,
                "message_id": message_id,
                "user_label": user_label,
                **media_info
            }
            save_json(MESSAGES_FILE, saved_messages)

            if old and old.get("message_type") == "text" and media_info.get("message_type") == "text":
                safe_notify_owner(
                    bc_id,
                    build_edited_text_message(user_label, old_text, new_text),
                    fallback_chat_id=get_owner_chat_id(bc_id, fallback_chat_id=chat_id)
                )
            else:
                safe_notify_owner(
                    bc_id,
                    build_edited_media_message(user_label, old_preview, new_preview),
                    fallback_chat_id=get_owner_chat_id(bc_id, fallback_chat_id=chat_id)
                )

        elif "deleted_business_messages" in update:
            deleted = update["deleted_business_messages"]
            bc_id = deleted.get("business_connection_id")
            chat_id = (deleted.get("chat") or {}).get("id")
            owner_chat_id = get_owner_chat_id(bc_id, fallback_chat_id=chat_id)

            for mid in deleted.get("message_ids", []):
                key = message_key(chat_id, mid)
                old = saved_messages.get(key)

                if not old:
                    print("DELETE MISS:", {"chat_id": chat_id, "message_id": mid, "business_connection_id": bc_id})
                    continue

                user_label = old.get("user_label", "Пользователь")
                message_type = old.get("message_type")
                stored_path = old.get("stored_path")
                caption = build_deleted_caption(user_label)

                if message_type == "photo" and stored_path and os.path.exists(stored_path):
                    safe_notify_owner_photo(bc_id, stored_path, caption=caption, fallback_chat_id=owner_chat_id)

                elif message_type == "video" and stored_path and os.path.exists(stored_path):
                    safe_notify_owner_video(bc_id, stored_path, caption=caption, fallback_chat_id=owner_chat_id)

                elif message_type in ["document", "voice"] and stored_path and os.path.exists(stored_path):
                    safe_notify_owner_document(bc_id, stored_path, caption=caption, fallback_chat_id=owner_chat_id)

                else:
                    safe_notify_owner(
                        bc_id,
                        build_deleted_text_message(user_label, build_message_preview(old)),
                        fallback_chat_id=owner_chat_id
                    )

        elif "message" in update:
            msg = update["message"]
            chat_id = (msg.get("chat") or {}).get("id")
            text = (msg.get("text") or "").strip().lower()

            if text == "/start" and chat_id:
                send_message(
                    chat_id,
                    "✅ <b>Бот работает.</b>\n\n"
                    "Подключи его через Telegram Business → Chatbots.\n"
                    "После подключения все изменения по сообщениям будут приходить сюда."
                )

            elif text == "/help" and chat_id:
                send_message(
                    chat_id,
                    "Команды:\n"
                    "• /start — запуск\n"
                    "• /help — помощь"
                )

        return {"ok": True}

    except Exception as e:
        print("WEBHOOK ERROR:", str(e))
        if ADMIN_CHAT_ID:
            try:
                send_message(
                    int(ADMIN_CHAT_ID),
                    f"❌ <b>Webhook error</b>\n<pre>{escape_text(str(e))}</pre>"
                )
            except Exception:
                pass
        return {"ok": True, "error": str(e)}
