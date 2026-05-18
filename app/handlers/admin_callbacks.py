import sqlite3
import app.db as db
import app.proxy_manager as proxy_manager
from app.config import DB_PATH, get_active_protocols
from app.handlers.admin_handlers import _revoke_key_by_protocol, users_show_page, user_info_callback
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
                    text=MESSAGES["mtp_key_granted"].format(username=escape_html(proxy_username), link=link),
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
        await context.bot.send_message(chat_id=int(uid),
                                       text=MESSAGES["request_rejected_notification"].format(req_id=req_id))
    except:
        pass
    await query.edit_message_text(MESSAGES["reject_request_success"].format(req_id=req_id))


async def handle_revoke_mtproto(query, data, context):
    # data format: revoke_mtproto_<username>
    username = data.split("_", 2)[2]
    await _revoke_key_by_protocol(username, 'mtproto', query, context)


async def handle_revoke_xray(query, data, context):
    # data format: revoke_xray_<email>
    email = data.split("_", 2)[2]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT u.username FROM users u JOIN keys k ON u.id = k.user_id WHERE k.protocol='xray' AND json_extract(k.key_data, '$.email') = ?",
        (email,))
    row = c.fetchone()
    conn.close()
    if row:
        username = row[0]
        await _revoke_key_by_protocol(username, 'xray', query, context, email=email)
    else:
        await query.edit_message_text(MESSAGES["revoke_user_not_found"].format(identifier=email))


async def handle_revoke_cancel(query, data, context):
    await query.edit_message_text(MESSAGES["revoke_canceled"])


async def handle_add_key(query, data, context):
    parts = data.split('_', 2)
    if len(parts) != 3:
        await query.edit_message_text(MESSAGES["invalid_callback_format"])
        return
    _, protocol, identifier = parts
    if protocol not in get_active_protocols():
        await query.edit_message_text(MESSAGES[f"{protocol}_not_supported"])
        return

    if identifier.startswith('@'):
        username = identifier[1:]
        try:
            chat = await context.bot.get_chat(f"@{username}")
            user_id = chat.id
        except:
            await query.edit_message_text(MESSAGES["user_not_found"].format(username=username))
            return

        if protocol == "mtproto":
            existing = db.get_user_by_telegram_id(user_id)
            if existing:
                await query.edit_message_text(
                    MESSAGES["user_already_has_key"].format(tg_username=username, username=escape_html(existing)),
                    parse_mode="HTML"
                )
                return
            success, (proxy_username, link), error = create_mtproto_key(user_id, username)
            if success:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=MESSAGES["mtp_key_granted"].format(username=escape_html(proxy_username), link=link),
                    parse_mode="HTML"
                )
                await query.edit_message_text(MESSAGES["mtp_key_created_sent"].format(username=username))
            else:
                await query.edit_message_text(MESSAGES["key_created_error"].format(error=error))

        elif protocol == "xray":
            keys = db.get_user_active_keys(user_id, 'xray')
            if keys:
                await query.edit_message_text(MESSAGES["xray_already_has_key"].format(username=username))
                return
            success, (email, subscribe_url), error = create_xray_key(user_id, username)
            if success:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=MESSAGES["xray_key_granted"].format(email=escape_html(email), subscribe_url=subscribe_url),
                    parse_mode="HTML"
                )
                await query.edit_message_text(MESSAGES["xray_key_created_sent"].format(username=username))
            else:
                await query.edit_message_text(MESSAGES["key_created_error"].format(error=error))

    else:
        proxy_username = identifier.strip()
        if not proxy_username:
            await query.edit_message_text(MESSAGES["empty_username"])
            return
        if protocol == "mtproto":
            if proxy_username in proxy_manager.load_users():
                await query.edit_message_text(MESSAGES["mtproto_user_already_exists"].format(username=proxy_username))
                return
            success, link = proxy_manager.create_user(proxy_username, telegram_id="web")
            if success:
                await query.edit_message_text(
                    MESSAGES["mtproto_user_created"].format(username=proxy_username, link=link))
            else:
                await query.edit_message_text(MESSAGES["key_created_error"].format(error=link))
        elif protocol == "xray":
            success, (email, subscribe_url), error = create_xray_key("web", proxy_username)
            if success:
                await query.edit_message_text(
                    MESSAGES["xray_client_added"].format(email=email, subscribe_url=subscribe_url))
            else:
                await query.edit_message_text(MESSAGES["key_created_error"].format(error=error))


async def handle_users_page(query, context, protocol, page):
    await users_show_page(query, context, protocol, page)


async def handle_user_info(query, context, username):
    await user_info_callback(query, context, username)
