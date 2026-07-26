@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None)
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

            if bc_id and user_chat_id:
                store_connection_info(
                    business_connection_id=bc_id,
                    user_chat_id=user_chat_id,
                    user_obj=user_obj
                )

                if bc.get("is_enabled"):
                    send_message(
                        user_chat_id,
                        "✅ <b>SnapSave Bot подключён.</b>\n\n"
                        "Теперь уведомления будут приходить сюда.",
                        business_connection_id=bc_id
                    )

        elif "business_message" in update:
            msg = update["business_message"]
            bc_id = msg.get("business_connection_id")
            chat_id = msg.get("chat", {}).get("id")
            if bc_id and chat_id:
                store_connection_info(bc_id, chat_id, msg.get("from"))

            key = make_key(bc_id, chat_id, msg.get("message_id"))
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
                "message_id": msg.get("message_id"),
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

        elif "edited_business_message" in update:
            msg = update["edited_business_message"]
            bc_id = msg.get("business_connection_id")
            chat_id = msg.get("chat", {}).get("id")
            if bc_id and chat_id:
                store_connection_info(bc_id, chat_id, msg.get("from"))

            key = make_key(bc_id, chat_id, msg.get("message_id"))
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

            old_text = old.get("text") if old else ""
            old_preview = build_message_preview(old) if old else "Не было сохранено"
            new_text = media_info.get("text") or media_info.get("caption") or ""
            new_preview = build_message_preview(media_info)

            saved_messages[key] = {
                "connection_id": bc_id,
                "chat_id": chat_id,
                "message_id": msg.get("message_id"),
                "user_label": user_label,
                "previous_text": old_text,
                **media_info
            }
            save_json(DATA_FILE, saved_messages)

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
            chat_id = deleted.get("chat", {}).get("id")
            if bc_id and chat_id:
                store_connection_info(bc_id, chat_id)

            for message_id in deleted.get("message_ids", []):
                key = make_key(bc_id, chat_id, message_id)
                old = saved_messages.get(key)
                if not old:
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
                    send_to_business_owner_text(route_obj, f"🗑 <b>{escape_text(user_label)}</b> <b>УДАЛИЛ(А) КРУЖОК</b>")
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
            chat_id = msg.get("chat", {}).get("id")
            text = (msg.get("text") or "").strip().lower()

            if text == "/start" and chat_id:
                send_message(chat_id, "✅ <b>SnapSave Bot работает.</b>")
            elif text == "/help" and chat_id:
                send_message(chat_id, "Напишите /start для проверки работы бота.")

        return {"ok": True}

    except Exception as e:
        print("WEBHOOK ERROR:", str(e))
        if ADMIN_CHAT_ID:
            try:
                send_message(ADMIN_CHAT_ID, f"❌ <b>Webhook error:</b>\n<pre>{escape_text(str(e))}</pre>")
            except Exception:
                pass
        return {"ok": True, "error": str(e)}
