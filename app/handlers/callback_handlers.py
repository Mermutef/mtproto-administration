import sqlite3
from telegram import Update
from telegram.ext import ContextTypes
import app.db as db
import app.proxy_manager as proxy_manager
from app.config import ADMIN_GROUP_ID, ADMIN_IDS, DB_PATH
from app.utils import escape_html
from app.locales.ru import MESSAGES


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_chat.id != ADMIN_GROUP_ID:
        await query.edit_message_text(MESSAGES["button_only_in_group"])
        return
    user_id = query.from_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await query.edit_message_text(MESSAGES["no_permission"])
        return

    data = query.data
    if data.startswith("approve_"):
        req_id = int(data.split("_")[1])
        req = db.get_request(req_id)
        if not req or req[2] != "pending":
            await query.edit_message_text(MESSAGES["request_already_processed"])
            return
        uid, user_name, _ = req
        proxy_username = proxy_manager.generate_unique_username(f"u_{uid}")
        success, link = proxy_manager.create_user(proxy_username, telegram_id=uid)
        if success:
            db.update_request_status(req_id, "approved")
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=MESSAGES["admin_key_granted"].format(
                        username=escape_html(proxy_username), link=link),
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {uid}: {e}")
            await query.edit_message_text(MESSAGES["approve_request_success"].format(req_id=req_id))
        else:
            await query.edit_message_text(MESSAGES["approve_request_error"].format(error=link))
    elif data.startswith("reject_"):
        req_id = int(data.split("_")[1])
        req = db.get_request(req_id)
        if not req or req[2] != "pending":
            await query.edit_message_text(MESSAGES["request_already_processed"])
            return
        uid, user_name, _ = req
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
