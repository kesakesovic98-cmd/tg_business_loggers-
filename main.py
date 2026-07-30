import os
import json
import html
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://tg-business-loggers.onrender.com").strip()

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
    except Exception as e:
        print(f"LOAD_JSON ERROR {path}: {e}")
        return {}


def save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"SAVE_JSON ERROR {path}: {e}")


saved_messages = load_json(MESSAGES_FILE)
saved_connections = load_json(CONNECTIONS_FILE)


@app.get("/")
async def root():
    return {"ok": True, "service": "snapsaveguard-bot"}


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/healthz")
async def healthz():
    return {"status": "OK"}


@app.get("/set_webhook")
async def set_webhook():
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    payload = {
        "url": webhook_url,
        "allowed_updates": [
            "message",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages"
        ]
    }

    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json=payload,
        timeout=30
    )

    try:
        result = response.json()
    except Exception:
        result = {
            "ok": False,
            "status_code": response.status_code,
            "text": response.text
        }

    print("SET_WEBHOOK RESULT:", result)
    return result


@app.get("/get_webhook_info")
async def get_webhook_info():
    response = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo",
        timeout=30
    )
    try:
        result = response.json()
    except Exception:
        result = {
            "ok": False,
            "status_code": response.status_code,
            "text": response.text
        }

    print("GET_WEBHOOK_INFO RESULT:", result)
    return result


def escape_text(value) -> str:
    return html.escape(str(value or "—"))


def quote_box(text: str) -> str:
    text = str(text or "—").strip()
    lines = text.split("\n")
    return "\n".join([f"┃ <b>{escape_text(line)}</b>" for line in lines])


def tg_api(method: str, data=None, files=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        response = requests.post(url, data=data, files=files, timeout=120)
        try:
            result = response.json()
        except Exception:
            result = {
                "ok": False,
                "status_code": response.status_code,
                "text": response.text
            }
        print(f"TG_API {method}:", result)
        return result
    except Exception as e:
        result = {"ok": False, "error": str(e)}
        print(f"TG_API {method} EXCEPTION:", result)
        return result


def send_message(chat_id: int, text: str):
    result = tg_api("sendMessage", data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })
    print("SEND_MESSAGE RESULT:", result)
    return result


def send_message_with_buttons(chat_id: int, text: str, buttons):
    result = tg_api("sendMessage", data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps({"inline_keyboard": buttons}, ensure_ascii=False)
    })
    print("SEND_MESSAGE_WITH_BUTTONS RESULT:", result)
    return result


def send_photo(chat_id: int, photo_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        with open(photo_path, "rb") as f:
            response = requests.post(url, data=data, files={"photo": f}, timeout=120)
        try:
            result = response.json()
        except Exception:
            result = {"ok": False, "status_code": response.status_code, "text": response.text}
        print("SEND_PHOTO RESULT:", result)
        return result
    except Exception as e:
        result = {"ok": False, "error": str(e)}
        print("SEND_PHOTO EXCEPTION:", result)
        return result


def send_photo_with_buttons(chat_id: int, photo_path: str, caption: str = "", buttons=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML"
    }
    if buttons:
        data["reply_markup"] = json.dumps({"inline_keyboard": buttons}, ensure_ascii=False)

    try:
        with open(photo_path, "rb") as f:
            response = requests.post(url, data=data, files={"photo": f}, timeout=120)

        try:
            result = response.json()
        except Exception:
            result = {"ok": False, "status_code": response.status_code, "text": response.text}

        print("SEND_PHOTO_WITH_BUTTONS RESULT:", result)
        return result
    except Exception as e:
        result = {"ok": False, "error": str(e)}
        print("SEND_PHOTO_WITH_BUTTONS EXCEPTION:", result)
        return result


def send_video(chat_id: int, video_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        with open(video_path, "rb") as f:
            response = requests.post(url, data=data, files={"video": f}, timeout=120)
        try:
            result = response.json()
        except Exception:
            result = {"ok": False, "status_code": response.status_code, "text": response.text}
        print("SEND_VIDEO RESULT:", result)
        return result
    except Exception as e:
        result = {"ok": False, "error": str(e)}
        print("SEND_VIDEO EXCEPTION:", result)
        return result


def send_video_note(chat_id: int, video_note_path: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideoNote"
    data = {"chat_id": chat_id}
    try:
        with open(video_note_path, "rb") as f:
            response = requests.post(url, data=data, files={"video_note": f}, timeout=120)
        try:
            result = response.json()
        except Exception:
            result = {"ok": False, "status_code": response.status_code, "text": response.text}
        print("SEND_VIDEO_NOTE RESULT:", result)
        return result
    except Exception as e:
        result = {"ok": False, "error": str(e)}
        print("SEND_VIDEO_NOTE EXCEPTION:", result)
        return result


def send_document(chat_id: int, file_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        with open(file_path, "rb") as f:
            response = requests.post(url, data=data, files={"document": f}, timeout=120)
        try:
            result = response.json()
        except Exception:
            result = {"ok": False, "status_code": response.status_code, "text": response.text}
        print("SEND_DOCUMENT RESULT:", result)
        return result
    except Exception as e:
        result = {"ok": False, "error": str(e)}
        print("SEND_DOCUMENT EXCEPTION:", result)
        return result


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
            print("DOWNLOADED FILE:", str(local_path))
            return str(local_path)

        print("DOWNLOAD FAILED STATUS:", response.status_code)
    except Exception as e:
        print("DOWNLOAD ERROR:", str(e))

    return None


def make_message_key(business_connection_id, chat_id, message_id) -> str:
    return f"{business_connection_id}:{chat_id}:{message_id}"


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


def store_connection(business_connection_id: str, user_chat_id=None, user_obj=None, is_enabled=None):
    if not business_connection_id:
        return

    item = saved_connections.get(business_connection_id, {})
    if user_chat_id is not None:
        item["user_chat_id"] = user_chat_id
    if user_obj is not None:
        item["user"] = user_obj
    if is_enabled is not None:
        item["is_enabled"] = is_enabled

    saved_connections[business_connection_id] = item
    save_json(CONNECTIONS_FILE, saved_connections)


def get_connection(business_connection_id: Optional[str]):
    if not business_connection_id:
        return {}
    return saved_connections.get(business_connection_id, {})


def get_user_chat_id(business_connection_id: Optional[str]):
    conn = get_connection(business_connection_id)
    return conn.get("user_chat_id")


def notify_user_text(business_connection_id: str, text: str):
    user_chat_id = get_user_chat_id(business_connection_id)
    if not user_chat_id:
        print("NO USER CHAT:", {"business_connection_id": business_connection_id})
        return None
    return send_message(user_chat_id, text)


def notify_user_photo(business_connection_id: str, photo_path: str, caption: str = ""):
    user_chat_id = get_user_chat_id(business_connection_id)
    if not user_chat_id:
        print("NO USER CHAT:", {"business_connection_id": business_connection_id})
        return None
    return send_photo(user_chat_id, photo_path, caption=caption)


def notify_user_video(business_connection_id: str, video_path: str, caption: str = ""):
    user_chat_id = get_user_chat_id(business_connection_id)
    if not user_chat_id:
        print("NO USER CHAT:", {"business_connection_id": business_connection_id})
        return None
    return send_video(user_chat_id, video_path, caption=caption)


def notify_user_video_note(business_connection_id: str, video_note_path: str):
    user_chat_id = get_user_chat_id(business_connection_id)
    if not user_chat_id:
        print("NO USER CHAT:", {"business_connection_id": business_connection_id})
        return None
    return send_video_note(user_chat_id, video_note_path)


def notify_user_document(business_connection_id: str, file_path: str, caption: str = ""):
    user_chat_id = get_user_chat_id(business_connection_id)
    if not user_chat_id:
        print("NO USER CHAT:", {"business_connection_id": business_connection_id})
        return None
    return send_document(user_chat_id, file_path, caption=caption)


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
    if reply_to.get("video_note"):
        return "[video_note]"
    if reply_to.get("document"):
        return "[document]"
    if reply_to.get("voice"):
        return "[voice]"
    return None


def is_disappearing_message(msg) -> bool:
    if not msg:
        return False

    return bool(
        msg.get("ttl_seconds")
        or msg.get("self_destructs_in")
        or msg.get("is_temporal")
        or msg.get("is_ephemeral")
        or msg.get("has_protected_content")
    )


def extract_reply_media(reply_to):
    if not reply_to:
        return None

    if reply_to.get("video_note"):
        video_note = reply_to["video_note"]
        return {
            "message_type": "video_note",
            "file_id": video_note.get("file_id"),
            "file_unique_id": video_note.get("file_unique_id"),
            "caption": ""
        }

    if reply_to.get("photo") and is_disappearing_message(reply_to):
        largest = reply_to["photo"][-1]
        return {
            "message_type": "photo",
            "file_id": largest.get("file_id"),
            "file_unique_id": largest.get("file_unique_id"),
            "caption": reply_to.get("caption", "")
        }

    if reply_to.get("video") and is_disappearing_message(reply_to):
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
        "ttl_seconds": msg.get("ttl_seconds"),
        "is_disappearing": is_disappearing_message(msg),
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

    elif msg.get("video_note"):
        video_note = msg["video_note"]
        result["message_type"] = "video_note"
        result["file_id"] = video_note.get("file_id")
        result["file_unique_id"] = video_note.get("file_unique_id")
        result["duration"] = video_note.get("duration")
        result["mime_type"] = video_note.get("mime_type")

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


def should_store_main_message(media_info: dict) -> bool:
    message_type = media_info.get("message_type")

    if message_type == "text":
        return True

    if message_type == "video_note":
        return True

    if message_type in ["photo", "video"]:
        return bool(media_info.get("is_disappearing"))

    if message_type in ["document", "voice"]:
        return True

    return False


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
    if mtype == "video_note":
        return f"Кружок\nДлительность: {item.get('duration') or '—'} сек"
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


def auto_forward_reply_media(business_connection_id: str, user_label: str, reply_to):
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
        notify_user_photo(business_connection_id, stored_path, caption=notify_caption)
        return True

    if message_type == "video":
        notify_user_video(business_connection_id, stored_path, caption=notify_caption)
        return True

    if message_type == "video_note":
        notify_user_video_note(business_connection_id, stored_path)
        notify_user_text(
            business_connection_id,
            f"💾 <b>{escape_text(user_label)}</b> <b>ОТВЕТИЛ(А) НА REPLY-КРУЖОК</b>\n\n<b>СОХРАНЕНО АВТОМАТИЧЕСКИ</b>"
        )
        return True

    if message_type == "document":
        notify_user_document(business_connection_id, stored_path, caption=notify_caption)
        return True

    return False


def process_update(update: dict):
    try:
        print("UPDATE RAW:", update)

        if "business_connection" in update:
            print("BUSINESS_CONNECTION HIT")
            bc = update["business_connection"]
            bc_id = bc.get("id")
            user_chat_id = bc.get("user_chat_id")
            user_obj = bc.get("user")
            is_enabled = bc.get("is_enabled")

            if bc_id:
                store_connection(
                    business_connection_id=bc_id,
                    user_chat_id=user_chat_id,
                    user_obj=user_obj,
                    is_enabled=is_enabled
                )

            if bc_id and user_chat_id and is_enabled:
                notify_user_text(
                    bc_id,
                    "✅ <b>Бот подключён.</b>\n\n"
                    "Теперь уведомления об удалённых, изменённых сообщениях и сохранённых reply-медиа будут приходить сюда."
                )

        elif "business_message" in update:
            print("BUSINESS_MESSAGE HIT")
            msg = update["business_message"]
            bc_id = msg.get("business_connection_id")
            chat_id = (msg.get("chat") or {}).get("id")
            message_id = msg.get("message_id")
            user_label = get_user_label(msg.get("from"))

            media_info = extract_media_info(msg)

            if should_store_main_message(media_info):
                if media_info["file_id"] and media_info["file_unique_id"]:
                    media_info["stored_path"] = download_file(
                        media_info["file_id"],
                        media_info["message_type"],
                        media_info["file_unique_id"]
                    )

                key = make_message_key(bc_id, chat_id, message_id)
                saved_messages[key] = {
                    "business_connection_id": bc_id,
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "user_label": user_label,
                    **media_info
                }
                save_json(MESSAGES_FILE, saved_messages)
            else:
                print("SKIP STORE MAIN MESSAGE:", {
                    "message_id": message_id,
                    "message_type": media_info.get("message_type"),
                    "is_disappearing": media_info.get("is_disappearing")
                })

            reply_to = msg.get("reply_to_message")
            if reply_to and bc_id:
                auto_forward_reply_media(bc_id, user_label, reply_to)

        elif "edited_business_message" in update:
            print("EDITED_BUSINESS_MESSAGE HIT")
            msg = update["edited_business_message"]
            bc_id = msg.get("business_connection_id")
            chat_id = (msg.get("chat") or {}).get("id")
            message_id = msg.get("message_id")
            user_label = get_user_label(msg.get("from"))

            key = make_message_key(bc_id, chat_id, message_id)
            old = saved_messages.get(key)
            media_info = extract_media_info(msg)

            if should_store_main_message(media_info):
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
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "user_label": user_label,
                    **media_info
                }
                save_json(MESSAGES_FILE, saved_messages)

                if bc_id:
                    if old and old.get("message_type") == "text" and media_info.get("message_type") == "text":
                        notify_user_text(bc_id, build_edited_text_message(user_label, old_text, new_text))
                    else:
                        notify_user_text(bc_id, build_edited_media_message(user_label, old_preview, new_preview))
            else:
                print("SKIP STORE EDITED MESSAGE:", {
                    "message_id": message_id,
                    "message_type": media_info.get("message_type"),
                    "is_disappearing": media_info.get("is_disappearing")
                })

        elif "deleted_business_messages" in update:
            print("DELETED_BUSINESS_MESSAGES HIT")
            deleted = update["deleted_business_messages"]
            bc_id = deleted.get("business_connection_id")
            chat_id = (deleted.get("chat") or {}).get("id")

            for mid in deleted.get("message_ids", []):
                key = make_message_key(bc_id, chat_id, mid)
                old = saved_messages.get(key)

                if not old:
                    print("DELETE MISS:", {
                        "business_connection_id": bc_id,
                        "chat_id": chat_id,
                        "message_id": mid
                    })
                    continue

                user_label = old.get("user_label", "Пользователь")
                message_type = old.get("message_type")
                stored_path = old.get("stored_path")
                caption = build_deleted_caption(user_label)

                if bc_id:
                    if message_type == "photo" and stored_path and os.path.exists(stored_path):
                        notify_user_photo(bc_id, stored_path, caption=caption)
                    elif message_type == "video" and stored_path and os.path.exists(stored_path):
                        notify_user_video(bc_id, stored_path, caption=caption)
                    elif message_type == "video_note" and stored_path and os.path.exists(stored_path):
                        notify_user_video_note(bc_id, stored_path)
                        notify_user_text(bc_id, caption)
                    elif message_type in ["document", "voice"] and stored_path and os.path.exists(stored_path):
                        notify_user_document(bc_id, stored_path, caption=caption)
                    else:
                        notify_user_text(
                            bc_id,
                            build_deleted_text_message(user_label, build_message_preview(old))
                        )

        elif "message" in update:
            print("MESSAGE UPDATE HIT")
            msg = update["message"]
            chat_id = (msg.get("chat") or {}).get("id")
            text = (msg.get("text") or "").strip()
            text_lower = text.lower()

            print("CHAT_ID:", chat_id)
            print("TEXT:", text)

            if text_lower == "/start" and chat_id:
                print("START COMMAND HIT")
                guide_path = "start_guide.png"

                start_caption = (
                    "Привет! Это <b>SnapSaveGuard</b>.\n\n"
                    "Бот помогает отслеживать изменения в переписке и сохранять важные медиа.\n\n"
                    "<b>Что умеет:</b>\n"
                    "• Уведомляет об удалённых и изменённых сообщениях.\n"
                    "• Сохраняет reply-медиа и файлы с таймером.\n\n"
                    "<b>Как подключить:</b>\n"
                    "1. Нажмите «Подключить».\n"
                    "2. Откройте Telegram Business → Чат-боты.\n"
                    "3. Введите <code>@snapsaveguard_bot</code>."
                )

                buttons = [
                    [{"text": "🟢 Подключить", "url": "https://t.me/snapsaveguard_bot"}],
                    [{"text": "🎥 Демонстрация работы", "url": "https://t.me/snapsaveguard_bot"}]
                ]

                send_result = None

                if os.path.exists(guide_path):
                    print("START IMAGE FOUND")
                    send_result = send_photo_with_buttons(
                        chat_id,
                        guide_path,
                        caption=start_caption,
                        buttons=buttons
                    )
                    if not send_result or not send_result.get("ok"):
                        print("PHOTO SEND FAILED, FALLBACK TO TEXT")
                        send_result = send_message_with_buttons(chat_id, start_caption, buttons)
                else:
                    print("START IMAGE NOT FOUND")
                    send_result = send_message_with_buttons(chat_id, start_caption, buttons)

                print("FINAL START SEND RESULT:", send_result)

            elif text_lower == "/help" and chat_id:
                print("HELP COMMAND HIT")
                result = send_message(
                    chat_id,
                    "Команды:\n"
                    "• /start — запуск\n"
                    "• /help — помощь"
                )
                print("HELP SEND RESULT:", result)

            else:
                print("UNKNOWN USER MESSAGE:", text)

        else:
            print("UNKNOWN UPDATE TYPE")

    except Exception as e:
        print("PROCESS_UPDATE ERROR:", str(e))
        if ADMIN_CHAT_ID:
            try:
                send_message(
                    int(ADMIN_CHAT_ID),
                    f"❌ <b>Webhook error</b>\n<pre>{escape_text(str(e))}</pre>"
                )
            except Exception:
                pass


@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None)
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        print("INVALID SECRET TOKEN:", x_telegram_bot_api_secret_token)
        raise HTTPException(status_code=403, detail="Invalid secret token")

    update = await request.json()
    background_tasks.add_task(process_update, update)
    return {"ok": True}
