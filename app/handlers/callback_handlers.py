import json
import sqlite3
import re
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import app.db as db
import app.proxy_manager as proxy_manager
from app.config import ADMIN_GROUP_ID, ADMIN_IDS, DB_PATH, XRAY_INBOUND_ID, generate_xray_link
from app.utils import escape_html
from app.locales.ru import MESSAGES

_xui_per_thread = threading.local()


def get_xui_client():
    client = getattr(_xui_per_thread, 'client', None)
    if client is None:
        try:
            from app.x_ui_manager import XUIClient
            _xui_per_thread.client = XUIClient()
        except Exception as e:
            import logging
            logging.error(f"❌ Не удалось инициализировать XUIClient: {e}")
            _xui_per_thread.client = False
        client = _xui_per_thread.client
    return client if client is not False else None


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    user_id = user.id
    user_name = user.username or user.first_name
    data = query.data

    if update.effective_chat.type == "private":
        if data.startswith("cancel_req_"):
            action = data[len("cancel_req_"):]
            if action == "cancel":
                await query.edit_message_text(MESSAGES["cancel_selection_cancelled"])
                return

            try:
                req_id = int(action)
            except ValueError:
                await query.edit_message_text(MESSAGES["cancel_request_invalid"])
                return

            requests = db.get_user_requests(user_id)
            matching = [r for r in requests if r[0] == req_id and r[1] == "pending"]
            if not matching:
                await query.edit_message_text(MESSAGES["cancel_request_not_found"])
                return

            db.update_request_status(req_id, "rejected")
            await query.edit_message_text(
                MESSAGES["request_cancelled"].format(req_id=req_id)
            )
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=MESSAGES["user_cancelled_request"].format(user_id=user_id, req_id=req_id)
            )
            return

        if data.startswith("req_service_"):
            protocol = data.split("_")[2]
            if protocol == "hysteria2":
                await query.edit_message_text("⚡ Hysteria2 пока в разработке. Попробуйте позже.")
                return

            existing_keys = db.get_user_active_keys(user_id, protocol)
            if existing_keys:
                msg = MESSAGES["already_has_keys"].format(protocol=protocol.upper())
                for key in existing_keys:
                    if protocol == 'mtproto':
                        link = proxy_manager.get_proxy_link(key['secret'])
                        msg += f"\n\nЛогин: <code>{key['username']}</code>\nСсылка: {link}"
                    elif protocol == 'xray':
                        link = generate_xray_link(key['uuid'])
                        msg += f"\n\nEmail: <code>{key['email']}</code>\nСсылка: {link}"
                await query.edit_message_text(msg, parse_mode="HTML")
                return

            requests = db.get_user_requests(user_id)
            for req_id, status, _, req_proto in requests:
                if status == "pending" and req_proto == protocol:
                    await query.edit_message_text(MESSAGES["pending_request_exists"].format(req_id=req_id))
                    return

            request_id = db.add_request(user_id, user_name, protocol)
            await query.edit_message_text(MESSAGES["request_created"].format(req_id=request_id))

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{request_id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")]
            ])
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_GROUP_ID,
                    text=MESSAGES["admin_new_request"].format(
                        user_name=escape_html(user_name), user_id=user_id,
                        req_id=request_id, protocol=protocol.upper()),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Ошибка отправки в группу: {e}")
            return

        return

    if update.effective_chat.id != ADMIN_GROUP_ID:
        await query.edit_message_text(MESSAGES["button_only_in_group"])
        return
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await query.edit_message_text(MESSAGES["no_permission"])
        return

    if data.startswith("approve_"):
        req_id = int(data.split("_")[1])
        req = db.get_request(req_id)
        if not req or req[3] != "pending":
            await query.edit_message_text(MESSAGES["request_already_processed"])
            return
        uid, user_name, protocol, _ = req

        # --- MTProto ---
        if protocol == "mtproto":
            try:
                tg_user = await context.bot.get_chat(int(uid))
                base_name = tg_user.username or tg_user.first_name or f"user{uid}"
            except:
                base_name = f"user{uid}"
            base_name = re.sub(r'[^a-zA-Z0-9_]', '_', base_name)
            proxy_username = proxy_manager.generate_unique_username(base_name)
            success, link = proxy_manager.create_user(proxy_username, telegram_id=uid)
            if success:
                db.update_request_status(req_id, "approved")
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=MESSAGES["admin_key_granted"].format(username=escape_html(proxy_username), link=link),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Не удалось отправить сообщение пользователю {uid}: {e}")
                await query.edit_message_text(MESSAGES["approve_request_success"].format(req_id=req_id))
            else:
                await query.edit_message_text(MESSAGES["approve_request_error"].format(error=link))

        # --- Xray ---
        elif protocol == "xray":
            xui = get_xui_client()
            try:
                tg_user = await context.bot.get_chat(int(uid))
                base_name = tg_user.username or tg_user.first_name or f"user{uid}"
            except:
                base_name = f"user{uid}"
            base_name = re.sub(r'[^a-zA-Z0-9_]', '_', base_name)
            email = f"{base_name}_{uid}"
            try:
                uuid_str = xui.add_client(XRAY_INBOUND_ID, email)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                now = db.datetime.now().isoformat()
                c.execute("INSERT OR IGNORE INTO users (username, telegram_id, created_at) VALUES (?, ?, ?)",
                          (email, str(uid), now))
                c.execute("SELECT id FROM users WHERE username = ?", (email,))
                user_db_id = c.fetchone()[0]
                key_data = json.dumps({"email": email, "uuid": uuid_str})
                c.execute("INSERT INTO keys (user_id, protocol, key_data, created_at) VALUES (?, 'xray', ?, ?)",
                          (user_db_id, key_data, now))
                conn.commit()
                conn.close()

                db.update_request_status(req_id, "approved")
                link = generate_xray_link(uuid_str)
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=MESSAGES["admin_key_granted"].format(username=escape_html(email), link=link),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Не удалось отправить сообщение пользователю {uid}: {e}")
                await query.edit_message_text(MESSAGES["approve_request_success"].format(req_id=req_id))
            except Exception as e:
                await query.edit_message_text(MESSAGES["approve_request_error"].format(error=str(e)))

    elif data.startswith("reject_"):
        req_id = int(data.split("_")[1])
        req = db.get_request(req_id)
        if not req or req[3] != "pending":
            await query.edit_message_text(MESSAGES["request_already_processed"])
            return
        uid, user_name, _, _ = req
        db.update_request_status(req_id, "rejected")
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"❌ Ваша заявка #{req_id} отклонена.")
        except:
            pass
        await query.edit_message_text(MESSAGES["reject_request_success"].format(req_id=req_id))

    elif data.startswith("revoke_"):
        proxy_username = data.split("_")[1]
        if proxy_manager.delete_user(proxy_username):
            await query.edit_message_text(
                MESSAGES["key_revoked_callback"].format(username=escape_html(proxy_username)),
                parse_mode="HTML"
            )
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT telegram_id FROM users WHERE username = ?", (proxy_username,))
            row = c.fetchone()
            conn.close()
            if row and row[0] not in ('unknown', 'web'):
                try:
                    await context.bot.send_message(
                        chat_id=int(row[0]),
                        text=MESSAGES["key_revoked_callback_notification"].format(username=escape_html(proxy_username)),
                        parse_mode="HTML"
                    )
                except:
                    pass
        else:
            await query.edit_message_text(MESSAGES["revoke_error"])


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(MESSAGES["unknown_command"])
    elif update.effective_chat.id == ADMIN_GROUP_ID:
        await update.message.reply_text("❓ Неизвестная команда. Доступно: /start, /adduser, /users, /revoke")
