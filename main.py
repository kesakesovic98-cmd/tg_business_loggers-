import os
import json
import html
from pathlib import Path
from typing import Optional, Tuple

import requests
from fastapi import FastAPI, Request, Header, HTTPException

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

app = FastAPI()

DATA_FILE = "messages.json"
CONNECTIONS_FILE = "connections.json"
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)


@app.get("/")
async def root():
    return {"ok": True, "service": "telegram-business-logger"}


@app.get("/health")
async def health():
    return {"ok": True}


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


saved_messages = load_json(DATA_FILE)
saved_connections = load_json(CONNECTIONS_FILE)


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


def send_message(chat_id, text: str, business_connection_id: Optional[str] = None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if business_connection_id:
        data["business_connection_id"] = business_connection_id
    return tg_api("sendMessage", data=data)


def send_photo(chat_id, photo_path: str, caption: str = "", business_connection_id: Optional[str] = None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if business_connection_id:
        data["business_connection_id"] = business_connection_id

    with open(photo_path, "rb") as photo:
        response = requests.post(url, data=data, files={"photo": photo}, timeout=120)

    try:
        return response.json()
    except Exception:
        return {"ok": False, "status_code": response.status_code, "text": response.text}


def send_video(chat_id, video_path: str, caption: str = "", business_connection_id: Optional[str] = None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if business_connection_id:
        data["business_connection_id"] = business_connection_id

    with open(video_path, "rb") as video:
        response = requests.post(url, data=data, files={"video": video}, timeout=120)

    try:
        return response.json()
    except Exception:
        return {"ok": False, "status_code": response.status_code, "text": response.text}


def send_voice(chat_id, voice_path: str, caption: str = "", business_connection_id: Optional[str] = None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVoice"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if business_connection_id:
        data["business_connection_id"] = business_connection_id

    with open(voice_path, "rb") as voice:
        response = requests.post(url, data=data, files={"voice": voice}, timeout=120)

    try:
        return response.json()
    except Exception:
        return {"ok": False, "status_code": response.status_code, "text": response.text}


def send_document(chat_id, file_path: str, caption: str = "", business_connection_id: Optional[str] = None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if business_connection_id:
        data["business_connection_id"] = business_connection_id

    with open(file_path, "rb") as doc:
        response = requests.post(url, data=data, files={"document": doc}, timeout=120)

    try:
        return response.json()
    except Exception:
        return {"ok": False, "status_code": response.status_code, "text": response.text}


def send_video_note(chat_id, file_path: str, business_connection_id: Optional[str] = None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideoNote"
    data = {"chat_id": chat_id}
    if business_connection_id:
        data["business_connection_id"] = business_connection_id

    with open(file_path, "rb") as video_note:
        response = requests.post(url, data=data, files={"video_note": video_note}, timeout=120)

    try:
        return response.json()
    except Exception:
        return {"ok": False, "status_code": response.status_code, "text": response.text}


def get_file(file_id: str):
    response = tg_api("getFile", data={"file_id": file_id})
    if response.get("ok"):
        return response.get("result")
    return None


def download_file(file_id: str, message_type: str, unique_id: str):
    try:
        file_info = get_file(file_id)
        if not file_info:
            return None

        remote_file_path = file_info.get("file_path")
        if not remote_file_path:
            return None

        ext = Path(remote_file_path).suffix or ".bin"
        local_path = MEDIA_DIR / f"{message_type}_{unique_id}{ext}"

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{remote_file_path}"
        response = requests.get(file_url, timeout=120)

        if response.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(response.content)
            return str(local_path)
    except Exception as e:
        print("DOWNLOAD ERROR:", str(e))

    return None


def make_key(connection_id, chat_id, message_id) -> str:
    return f"{connection_id}:{chat_id}:{message_id}"


def find_saved_message(connection_id, chat_id, message_id):
    exact_key = make_key(connection_id, chat_id, message_id)
    if exact_key in saved_messages:
        return exact_key, saved_messages[exact_key]

    fallback_suffix = f":{chat_id}:{message_id}"
    for k, v in saved_messages.items():
        if k.endswith(fallback_suffix):
            return k, v

    return None, None


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


def store_connection_info(business_connection_id: Optional[str], user_chat_id=None, user_obj=None):
    if not business_connection_id:
        return

    current = saved_connections.get(business_connection_id, {})
    if user_chat_id is not None:
        current["user_chat_id"] = user_chat_id
    if user_obj is not None:
        current["user"] = user_obj

    saved_connections[business_connection_id] = current
    save_json(CONNECTIONS_FILE, saved_connections)


def get_target_chat_and_connection(obj) -> Tuple[Optional[int], Optional[str]]:
    business_connection_id = obj.get("business_connection_id") or obj.get("connection_id")
    chat = obj.get("chat", {}) or {}
    fallback_chat_id = chat.get("id")

    saved_conn = saved_connections.get(business_connection_id, {})
    user_chat_id = saved_conn.get("user_chat_id") or fallback_chat_id

    return user_chat_id, business_connection_id


def send_to_business_owner_text(obj, text: str):
    target_chat_id, business_connection_id = get_target_chat_and_connection(obj)
    if not target_chat_id:
        return None
    return send_message(target_chat_id, text, business_connection_id=business_connection_id)


def send_to_business_owner_photo(obj, photo_path: str, caption: str = ""):
    target_chat_id, business_connection_id = get_target_chat_and_connection(obj)
    if not target_chat_id:
        return None
    return send_photo(target_chat_id, photo_path, caption=caption, business_connection_id=business_connection_id)


def send_to_business_owner_video(obj, video_path: str, caption: str = ""):
    target_chat_id, business_connection_id = get_target_chat_and_connection(obj)
    if not target_chat_id:
        return None
    return send_video(target_chat_id, video_path, caption=caption, business_connection_id=business_connection_id)


def send_to_business_owner_voice(obj, voice_path: str, caption: str = ""):
    target_chat_id, business_connection_id = get_target_chat_and_connection(obj)
    if not target_chat_id:
        return None
    return send_voice(target_chat_id, voice_path, caption=caption, business_connection_id=business_connection_id)


def send_to_business_owner_document(obj, file_path: str, caption: str = ""):
    target_chat_id, business_connection_id = get_target_chat_and_connection(obj)
    if not target_chat_id:
        return None
    return send_document(target_chat_id, file_path, caption=caption, business_connection_id=business_connection_id)


def send_to_business_owner_video_note(obj, file_path: str):
    target_chat_id, business_connection_id = get_target_chat_and_connection(obj)
    if not target_chat_id:
        return None
    return send_video_note(target_chat_id, file_path, business_connection_id=business_connection_id)


def get_reply_preview(reply_to):
    if not reply_to:
        return None

    if reply_to.get("text"):
        return reply_to.get("text")
    if reply_to.get("caption"):
        return reply_to.get("caption")
    if reply_to.get("photo"):
        return "[photo]"
    if reply_to.get("video"):
        return "[video]"
    if reply_to.get("video_note"):
        return "[video_note]"
    if reply_to.get("voice"):
        return "[voice]"
    if reply_to.get("document"):
        return "[document]"
    if reply_to.get("audio"):
        return "[audio]"
    if reply_to.get("animation"):
        return "[animation]"
    if reply_to.get("sticker"):
        return "[sticker]"

    return None


def is_normal_reply_message(reply_to) -> bool:
    if not reply_to:
        return False

    return any([
        reply_to.get("text"),
        reply_to.get("caption"),
        reply_to.get("photo"),
        reply_to.get("video"),
        reply_to.get("video_note"),
        reply_to.get("voice"),
        reply_to.get("document"),
        reply_to.get("audio"),
        reply_to.get("animation"),
        reply_to.get("sticker"),
    ])


def is_probably_disappearing_reply(reply_to) -> bool:
    if not reply_to:
        return False
    if is_normal_reply_message(reply_to):
        return False
    return True


def extract_reply_media(reply_to):
    if not reply_to:
        return None

    if reply_to.get("photo"):
        largest = reply_to["photo"][-1]
        return {
            "message_type": "photo",
            "file_id": largest.get("file_id"),
            "file_unique_id": largest.get("file_unique_id"),
            "caption": reply_to.get("caption", ""),
        }

    if reply_to.get("video"):
        video = reply_to["video"]
        return {
            "message_type": "video",
            "file_id": video.get("file_id"),
            "file_unique_id": video.get("file_unique_id"),
            "caption": reply_to.get("caption", ""),
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
        "reply_to_message_id": None,
        "reply_to_preview": None,
        "reply_is_disappearing": False,
        "reply_debug_raw": None,
    }

    reply_to = msg.get("reply_to_message")
    if reply_to:
        result["reply_to_message_id"] = reply_to.get("message_id")
        result["reply_to_preview"] = get_reply_preview(reply_to)
        result["reply_is_disappearing"] = is_probably_disappearing_reply(reply_to)
        try:
            result["reply_debug_raw"] = json.dumps(reply_to, ensure_ascii=False)
        except Exception:
            result["reply_debug_raw"] = str(reply_to)

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


def build_message_preview(item) -> str:
    if not item:
        return "—"

    mtype = item.get("message_type", "unknown")
    text = item.get("text") or item.get("caption") or ""
    file_name = item.get("file_name") or ""

    if mtype == "text":
        return text or "—"
    if mtype == "photo":
        return f"Фото\nПодпись: {item.get('caption') or '—'}"
    if mtype == "video":
        return f"Видео\nПодпись: {item.get('caption') or '—'}"
    if mtype == "video_note":
        return f"Кружок\nДлительность: {item.get('duration') or '—'} сек"
    if mtype == "voice":
        return f"Голосовое\nДлительность: {item.get('duration') or '—'} сек"
    if mtype == "document":
        return f"Документ\nИмя: {file_name or '—'}\nПодпись: {item.get('caption') or '—'}"
    if mtype == "audio":
        return f"Аудио\nИмя: {file_name or '—'}"
    if mtype == "animation":
        return f"GIF/анимация\nИмя: {file_name or '—'}"
    if mtype == "sticker":
        return "Стикер"
    return text or "—"


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


def build_deleted_text_message(user_label: str, preview: str) -> str:
    return (
        f"🗑 <b>{escape_text(user_label)}</b> <b>УДАЛИЛ(А) СООБЩЕНИЕ</b>\n\n"
        f"{quote_box(preview or '—')}"
    )


def build_deleted_caption(user_label: str) -> str:
    return f"🗑 <b>{escape_text(user_label)}</b> <b>УДАЛИЛ(А) СООБЩЕНИЕ</b>"


def build_disappearing_reply_notice(user_label: str, reply_preview: Optional[str]) -> str:
    return (
        f"👁 <b>{escape_text(user_label)}</b> <b>ОТВЕТИЛ(А) НА ОДНОРАЗОВОЕ / НЕДОСТУПНОЕ СООБЩЕНИЕ</b>\n\n"
        f"{quote_box(reply_preview or 'Содержимое недоступно через Bot API')}"
    )


def build_disappearing_debug_message(user_label: str, raw_reply: Optional[str]) -> str:
    raw_reply = escape_text(raw_reply or "Нет данных")
    if len(raw_reply) > 3000:
        raw_reply = raw_reply[:3000] + "\n...TRUNCATED..."
    return (
        f"🛠 <b>DEBUG reply_to_message для {escape_text(user_label)}</b>\n\n"
        f"<pre>{raw_reply}</pre>"
    )


def auto_forward_reply_media_to_owner(msg_obj, user_label: str, reply_to) -> bool:
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

    notify_caption = (
        f"💾 <b>{escape_text(user_label)}</b> <b>ОТВЕТИЛ(А) НА REPLY-МЕДИА / СООБЩЕНИЕ С ТАЙМЕРОМ</b>\n\n"
        f"<b>СОХРАНЕНО АВТОМАТИЧЕСКИ</b>\n"
        f"{quote_box(caption or 'Без подписи')}"
    )

    if message_type == "photo":
        send_to_business_owner_photo(msg_obj, stored_path, caption=notify_caption)
        return True

    if message_type == "video":
        send_to_business_owner_video(msg_obj, stored_path, caption=notify_caption)
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
                store_connection_info(
                    business_connection_id=bc_id,
                    user_chat_id=user_chat_id,
                    user_obj=user_obj
                )

            if bc.get("is_enabled") and bc_id and user_chat_id:
                send_message(
                    user_chat_id,
                    "✅ <b>SnapSave Bot подключён.</b>\n\n"
                    "Теперь удалённые, изменённые сообщения и сохранённые reply-медиа "
                    "будут приходить именно сюда.",
                    business_connection_id=bc_id
                )

        elif "business_message" in update:
            msg = update["business_message"]
            bc_id = msg.get("business_connection_id")
            chat_id = (msg.get("chat") or {}).get("id")
            message_id = msg.get("message_id")

            if bc_id:
                store_connection_info(
                    business_connection_id=bc_id,
                    user_chat_id=chat_id,
                    user_obj=msg.get("from")
                )

            key = make_key(bc_id, chat_id, message_id)
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
                "connection_id": bc_id,
                "chat_id": chat_id,
                "message_id": message_id,
                "user_label": user_label,
                **media_info
            }
            save_json(DATA_FILE, saved_messages)

            reply_to = msg.get("reply_to_message")
            auto_saved = False

            if reply_to:
                auto_saved = auto_forward_reply_media_to_owner(msg, user_label, reply_to)

            if media_info.get("reply_is_disappearing") and not auto_saved:
                send_to_business_owner_text(
                    msg,
                    build_disappearing_reply_notice(user_label, media_info.get("reply_to_preview"))
                )

                if ADMIN_CHAT_ID and media_info.get("reply_debug_raw"):
                    send_message(
                        ADMIN_CHAT_ID,
                        build_disappearing_debug_message(user_label, media_info.get("reply_debug_raw"))
                    )

        elif "edited_business_message" in update:
            msg = update["edited_business_message"]
            bc_id = msg.get("business_connection_id")
            chat_id = (msg.get("chat") or {}).get("id")
            message_id = msg.get("message_id")

            if bc_id:
                store_connection_info(
                    business_connection_id=bc_id,
                    user_chat_id=chat_id,
                    user_obj=msg.get("from")
                )

            key = make_key(bc_id, chat_id, message_id)
            found_key, old = find_saved_message(bc_id, chat_id, message_id)

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

            saved_messages[key] = {
                "connection_id": bc_id,
                "chat_id": chat_id,
                "message_id": message_id,
                "user_label": user_label,
                "previous_text": old_text,
                **media_info
            }
            save_json(DATA_FILE, saved_messages)

            new_text = media_info.get("text") or media_info.get("caption") or ""
            new_preview = build_message_preview(media_info)

            if old and old.get("message_type") == "text" and media_info.get("message_type") == "text":
                send_to_business_owner_text(
                    msg,
                    build_edited_text_message(user_label, old_text, new_text)
                )
            else:
                send_to_business_owner_text(
                    msg,
                    build_edited_media_message(user_label, old_preview, new_preview)
                )

        elif "deleted_business_messages" in update:
            deleted = update["deleted_business_messages"]
            bc_id = deleted.get("business_connection_id")
            chat_id = (deleted.get("chat") or {}).get("id")

            if bc_id:
                store_connection_info(
                    business_connection_id=bc_id,
                    user_chat_id=chat_id
                )

            for message_id in deleted.get("message_ids", []):
                key = make_key(bc_id, chat_id, message_id)
                found_key, old = find_saved_message(bc_id, chat_id, message_id)

                if not old:
                    print("DELETE MISS:", {"bc_id": bc_id, "chat_id": chat_id, "message_id": message_id})
                    continue

                user_label = old.get("user_label", "Пользователь")
                message_type = old.get("message_type")
                stored_path = old.get("stored_path")
                caption = build_deleted_caption(user_label)

                route_obj = {
                    "business_connection_id": bc_id,
                    "chat": {"id": chat_id}
                }

                if message_type == "photo" and stored_path and os.path.exists(stored_path):
                    send_to_business_owner_photo(route_obj, stored_path, caption=caption)

                elif message_type == "video" and stored_path and os.path.exists(stored_path):
                    send_to_business_owner_video(route_obj, stored_path, caption=caption)

                elif message_type == "voice" and stored_path and os.path.exists(stored_path):
                    send_to_business_owner_voice(route_obj, stored_path, caption=caption)

                elif message_type == "video_note" and stored_path and os.path.exists(stored_path):
                    send_to_business_owner_text(
                        route_obj,
                        f"🗑 <b>{escape_text(user_label)}</b> <b>УДАЛИЛ(А) КРУЖОК</b>"
                    )
                    send_to_business_owner_video_note(route_obj, stored_path)

                elif message_type in ["document", "animation", "audio", "sticker"] and stored_path and os.path.exists(stored_path):
                    send_to_business_owner_document(route_obj, stored_path, caption=caption)

                else:
                    send_to_business_owner_text(
                        route_obj,
                        build_deleted_text_message(user_label, build_message_preview(old))
                    )

        elif "message" in update:
            msg = update["message"]
            chat_id = (msg.get("chat") or {}).get("id")
            text = (msg.get("text") or "").strip().lower()

            if text == "/start" and chat_id:
                send_message(
                    chat_id,
                    "✅ <b>SnapSave Bot работает.</b>\n\n"
                    "Подключи бота через Telegram Business → Chatbots, "
                    "и уведомления о редактировании, удалении и reply-медиа "
                    "будут приходить в этот чат."
                )

            elif text == "/help" and chat_id:
                send_message(
                    chat_id,
                    "Доступно:\n"
                    "• /start — запустить бота\n"
                    "• /help — помощь"
                )

        return {"ok": True}

    except Exception as e:
        print("WEBHOOK ERROR:", str(e))
        if ADMIN_CHAT_ID:
            try:
                send_message(
                    ADMIN_CHAT_ID,
                    f"❌ <b>Webhook error:</b>\n<pre>{escape_text(str(e))}</pre>"
                )
            except Exception:
                pass
        return {"ok": True, "error": str(e)}
