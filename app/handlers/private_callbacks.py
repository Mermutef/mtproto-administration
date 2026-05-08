from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import app.db as db
import app.proxy_manager as proxy_manager
from app.config import ADMIN_GROUP_ID, XRAY_SUB_URL_BASE
from app.locales.ru import MESSAGES
from app.services.key_service import get_or_update_sub_id


async def handle_cancel_req(query, data, user_id, context):
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
    await query.edit_message_text(MESSAGES["request_cancelled"].format(req_id=req_id))
    await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=MESSAGES["user_cancelled_request"].format(user_id=user_id, req_id=req_id)
    )


async def handle_req_service(query, data, user_id, user_name, context):
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
                email = key.get('email')
                sub_id = get_or_update_sub_id(email)
                subscribe_url = f"{XRAY_SUB_URL_BASE}{sub_id}" if sub_id else ""
                msg += f"\n\nEmail: <code>{email}</code>\nСсылка: {subscribe_url}"
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
                user_name=user_name, user_id=user_id,
                req_id=request_id, protocol=protocol.upper()),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка отправки в группу: {e}")
