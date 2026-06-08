"""Admin callback handlers for inline button actions.

Handles callbacks triggered by administrators in the admin group:
approve/reject requests, revoke keys, add keys for users, and
paginate through user lists.
"""

import logging
import sqlite3
import app.db as db
from app.config import DB_PATH, get_active_protocols
from app.handlers.admin_handlers import _revoke_key_by_protocol, users_show_page, user_info_callback, _create_key_for_identifier, _send_key_to_user
from app.utils import escape_html
from app.locales.ru import MESSAGES
from app.services.registry import registry


async def handle_approve(query, data, context):
    """Approve a pending access request.

    Creates a VPN key for the user and notifies them in private chat.

    Args:
        query: The callback query.
        data: Callback data (``approve_<request_id>``).
        context: Bot context.
    """
    req_id = int(data.split("_")[1])
    req = db.get_request(req_id)
    if not req or req[3] != "pending":
        await query.edit_message_text(MESSAGES["request_already_processed"])
        return
    uid, user_name, protocol, _ = req

    svc = registry.get(protocol)
    if not svc:
        await query.edit_message_text(MESSAGES["key_created_error"].format(error="Protocol not supported"))
        return

    success, result = svc.create_user(user_name, telegram_id=str(uid))
    if success:
        db.update_request_status(req_id, "approved")
        await _send_key_to_user(context, int(uid), protocol, user_name, result)
        await query.edit_message_text(MESSAGES["approve_request_success"].format(req_id=req_id))
    else:
        await query.edit_message_text(MESSAGES["approve_request_error"].format(error=result))


async def handle_reject(query, data, context):
    """Reject a pending access request.

    Updates the request status and notifies the user.

    Args:
        query: The callback query.
        data: Callback data (``reject_<request_id>``).
        context: Bot context.
    """
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
    """Revoke an MTProto key.

    Args:
        query: The callback query.
        data: Callback data (``revoke_mtproto_<username>``).
        context: Bot context.
    """
    username = data.split("_", 2)[2]
    await _revoke_key_by_protocol(username, 'mtproto', query, context)


async def handle_revoke_xray(query, data, context):
    """Revoke an Xray key.

    Args:
        query: The callback query.
        data: Callback data (``revoke_xray_<email>``).
        context: Bot context.
    """
    parts = data.split("_", 2)
    protocol = parts[0].replace("revoke_", "")
    email = parts[2]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT u.username FROM users u JOIN keys k ON u.id = k.user_id WHERE k.protocol=? AND json_extract(k.key_data, '$.email') = ?",
        (protocol, email))
    row = c.fetchone()
    conn.close()
    if row:
        username = row[0]
        await _revoke_key_by_protocol(username, protocol, query, context, email=email)
    else:
        await query.edit_message_text(MESSAGES["revoke_user_not_found"].format(identifier=email))


async def handle_revoke_cancel(query, data, context):
    """Cancel a revoke operation.

    Args:
        query: The callback query.
        data: Callback data.
        context: Bot context.
    """
    await query.edit_message_text(MESSAGES["revoke_canceled"])


async def handle_add_key(query, data, context):
    """Handle the 'add key' admin callback.

    Creates a VPN key for a user (either by @username or by literal
    proxy username). Delegates to :func:`_create_key_for_identifier`.

    Args:
        query: The callback query.
        data: Callback data (``add_<protocol>_<identifier>``).
        context: Bot context.
    """
    parts = data.split('_', 2)
    if len(parts) != 3:
        await query.edit_message_text(MESSAGES["invalid_callback_format"])
        return
    _, protocol, identifier = parts
    if protocol not in get_active_protocols():
        await query.edit_message_text(MESSAGES[f"{protocol}_not_supported"])
        return

    await _create_key_for_identifier(query, context, identifier, protocol, is_callback=True)


async def handle_users_page(query, context, protocol, page):
    """Handle pagination through the users list.

    Args:
        query: The callback query.
        context: Bot context.
        protocol: Protocol filter (or ``'all'``).
        page: The page number to display.
    """
    await users_show_page(query, context, protocol, page)


async def handle_user_info(query, context, username):
    """Show detailed information about a specific user.

    Args:
        query: The callback query.
        context: Bot context.
        username: The username to display info for.
    """
    await user_info_callback(query, context, username)
