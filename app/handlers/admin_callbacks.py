import sqlite3
import app.db as db
import app.proxy_manager as proxy_manager
from app.config import DB_PATH
from app.utils import escape_html
from app.locales.ru import MESSAGES
from app.services.key_service import create_mtproto_key, create_xray_key


async def handle_approve(query, data, context):
    req_id = int(data.split("_")[1])
    req = db.get_request(req_id)
    if not req or req[3] != "pending":
        await query.edit_message_text(MESSAGES["request_already_processed"])
        return
    uid, user_name, protocol, _ = req

    if protocol == "mtproto":
        success, (proxy_username, link), error = create_mtproto_key(uid, user_name)
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
            await query.edit_message_text(MESSAGES["approve_request_error"].format(error=error))

    elif protocol == "xray":
        success, (email, subscribe_url), error = create_xray_key(uid, user_name)
        if success:
            db.update_request_status(req_id, "approved")
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=MESSAGES["xray_key_granted"].format(email=escape_html(email), subscribe_url=subscribe_url),
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {uid}: {e}")
            await query.edit_message_text(MESSAGES["approve_request_success"].format(req_id=req_id))
        else:
            await query.edit_message_text(MESSAGES["approve_request_error"].format(error=error))


async def handle_reject(query, data, context):
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


async def handle_revoke(query, data, context):
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
