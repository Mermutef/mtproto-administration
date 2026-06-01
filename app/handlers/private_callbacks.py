"""Private-chat callback handlers.

Handles inline button actions initiated by regular users in their
private chat with the bot — cancelling requests and requesting
a new key for a specific protocol.
"""

import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import app.db as db
from app.config import ADMIN_GROUP_ID, get_active_protocols
from app.locales.ru import MESSAGES
from app.services.registry import registry


async def handle_cancel_req(query, data, user_id, context):
    """Handle /cancel callback: reject a specific pending request.

    Args:
        query: The callback query.
        data: Callback data (cancel_req_<id> or cancel_req_cancel).
        user_id: Telegram user ID.
        context: Bot context.
    """
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
    """Handle protocol selection: create an access request.

    Checks for existing keys and pending requests before creating
    a new one.

    Args:
        query: The callback query.
        data: Callback data (req_service_<protocol>).
        user_id: Telegram user ID.
        user_name: Display name.
        context: Bot context.
    """
    protocol = data.split("_")[2]
    if protocol not in get_active_protocols():
        await query.edit_message_text(MESSAGES[f"{protocol}_not_supported"])
        return

    svc = registry.get(protocol)

    existing_keys = db.get_user_active_keys(user_id, protocol)
    if existing_keys:
        msg = MESSAGES["already_has_keys"].format(protocol=protocol.upper())
        for key in existing_keys:
            identifier = svc.get_identifier(key) if svc else key.get('username', '—')
            link = svc.get_link_for_key(key) if svc else ""
            msg += f"\n\nЛогин: <code>{identifier}</code>\nСсылка: {link}"
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
        logging.error(f"Error sending message to admin group: {e}")
