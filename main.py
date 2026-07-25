import os
from fastapi import FastAPI, Request, Header, HTTPException
from aiogram import Bot
from aiogram.types import Update

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")

app = FastAPI()
bot = Bot(token=BOT_TOKEN)

saved_messages = {}

def make_key(connection_id, chat_id, message_id):
    return f"{connection_id}:{chat_id}:{message_id}"

def get_user_label(user):
    if not user:
        return "Неизвестный пользователь"
    if user.username:
        return f"@{user.username}"
    full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip()
    return full_name or str(user.id)

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
        saved_messages[key] = {
            "connection_id": msg.business_connection_id,
            "chat_id": msg.chat.id,
            "message_id": msg.message_id,
            "text": msg.text or msg.caption or "",
            "user_label": get_user_label(msg.from_user),
        }

    elif update.edited_business_message:
        msg = update.edited_business_message
        key = make_key(msg.business_connection_id, msg.chat.id, msg.message_id)
        old = saved_messages.get(key)

        old_text = old["text"] if old else "Не было сохранено"
        new_text = msg.text or msg.caption or ""
        user_label = get_user_label(msg.from_user)

        saved_messages[key] = {
            "connection_id": msg.business_connection_id,
            "chat_id": msg.chat.id,
            "message_id": msg.message_id,
            "text": new_text,
            "user_label": user_label,
        }

        if ADMIN_CHAT_ID:
            await bot.send_message(
                ADMIN_CHAT_ID,
                f"✏️ {user_label} изменил сообщение\n\nБыло:\n{old_text}\n\nСтало:\n{new_text or '—'}"
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
                        f"🗑 {old['user_label']} удалил сообщение\n\n{old['text'] or '—'}"
                    )
                else:
                    await bot.send_message(
                        ADMIN_CHAT_ID,
                        f"🗑 Удалено сообщение ID {message_id}, но текст не был сохранён заранее."
                    )

    return {"ok": True}
