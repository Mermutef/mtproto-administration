"""Admin-only Telegram command handlers.

Provides administrative commands for the admin group chat:
``/start``, ``/adduser``, ``/users``, ``/revoke``, ``/info``,
``/broadcast``, ``/sendto``, ``/resend_keys``, and helpers for
cache and pagination.
"""

import json
import logging
import sqlite3
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import app.db as db
from app.config import ADMIN_GROUP_ID, ADMIN_IDS, DB_PATH, XUI_SUB_URL_BASE, get_active_protocols, \
    USERS_PER_PAGE
from app.db import get_user_active_keys
from app.utils import escape_html
from app.locales.ru import MESSAGES
from app.services.registry import registry


def _svc(protocol):
    """Get a VPN service instance by protocol name.

    Args:
        protocol: Protocol identifier (e.g. ``'mtproto'``, ``'xray'``).

    Returns:
        The service instance, or ``None`` if not found.
    """
    return registry.get(protocol)


async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start in the admin group.

    Displays the admin welcome message with supported protocols.

    Args:
        update: The update object.
        context: The bot context.
    """
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(MESSAGES["no_permission"])
        return
    protocols_str = ", ".join(p.upper() for p in get_active_protocols())
    await update.message.reply_text(MESSAGES["admin_start"].format(protocols=protocols_str), parse_mode="HTML")


async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /adduser — start the add-user flow with protocol selection.

    Usage: ``/adduser <username_or_@telegram_username>``

    Args:
        update: The update object.
        context: The bot context.
    """
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(MESSAGES["no_permission"])
        return
    if not context.args:
        await update.message.reply_text(MESSAGES["adduser_usage"])
        return

    arg = context.args[0]

    buttons = []
    active = get_active_protocols()
    for proto in active:
        svc = _svc(proto)
        if svc:
            buttons.append([InlineKeyboardButton(f"{svc.emoji} {svc.display_name}", callback_data=f"add_{proto}_{arg}")])

    if not buttons:
        await update.message.reply_text(MESSAGES["no_available_protocols"])
        return

    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        MESSAGES["adduser_choose_protocol"].format(user=escape_html(arg)),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def _create_key_for_identifier(
    send_or_edit,
    context: ContextTypes.DEFAULT_TYPE,
    identifier: str,
    protocol: str,
    *,
    is_callback: bool = False,
):
    """Create a VPN key for a user, handling both @mention and direct name flows.

    This is the single shared entry point used by ``process_adduser_direct``
    and ``handle_add_key``, eliminating duplicate protocol-specific logic.

    Args:
        send_or_edit: Either an ``Update`` (for message-based commands) or
            a callback ``Query`` (for inline button handlers).
        context: Bot context.
        identifier: The ``@username`` or literal proxy name.
        protocol: Protocol name (e.g. ``'mtproto'``, ``'xray'``).
        is_callback: If ``True``, uses ``edit_message_text``; otherwise
            ``reply_text``.

    Returns:
        ``True`` if the key was created and sent successfully.
    """
    svc = _svc(protocol)
    if not svc or not svc.enabled:
        await _reply(send_or_edit, MESSAGES[f"{protocol}_not_supported"], is_callback=is_callback)
        return False

    async def _reply_safe(msg, **kwargs):
        await _reply(send_or_edit, msg, is_callback=is_callback, **kwargs)

    if identifier.startswith('@'):
        username = identifier.lstrip('@')
        try:
            chat = await context.bot.get_chat(f"@{username}")
            user_id = chat.id
        except Exception:
            await _reply_safe(MESSAGES["user_not_found"].format(username=username))
            return False

        keys = db.get_user_active_keys(user_id, protocol)
        if keys:
            await _reply_safe(
                MESSAGES["user_already_has_key"].format(tg_username=username, username=escape_html(username)),
                parse_mode="HTML"
            )
            return False

        success, link = svc.create_user(username, telegram_id=str(user_id))
        if success:
            await _send_key_to_user(context, int(user_id), protocol, username, link)
            admin_msg = svc.format_admin_created_message(username)
            await _reply_safe(admin_msg)
            return True
        else:
            await _reply_safe(MESSAGES["key_created_error"].format(error=link))
            return False
    else:
        proxy_username = identifier.strip()
        if not proxy_username:
            await _reply_safe(MESSAGES["empty_username"])
            return False

        # Try to find existing user in DB to preserve telegram_id
        tid = "web"
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT telegram_id FROM users WHERE username = ?", (proxy_username,))
        row = c.fetchone()
        conn.close()
        if row and row[0] not in ('unknown', 'web', '—', None):
            tid = row[0]

        success, link = svc.create_user(proxy_username, telegram_id=tid)
        if success:
            admin_msg = svc.format_admin_direct_message(proxy_username, link)
            await _reply_safe(admin_msg)
            return True
        else:
            await _reply_safe(MESSAGES["key_created_error"].format(error=link))
            return False


async def _send_key_to_user(context, chat_id: int, protocol: str, identifier: str, link: str):
    """Send a newly-created key to a user in private chat.

    Delegates to the service's ``format_user_key_message`` so each
    protocol produces its own localised message without branching here.

    Args:
        context: Bot context.
        chat_id: Target user chat ID.
        protocol: Protocol name.
        identifier: The username or email.
        link: The connection link returned by the service (used directly).
    """
    svc = _svc(protocol)
    if not svc:
        return
    # Build minimal key_data embedding the real link so the formatter
    # can produce the correct message without requiring stored secrets.
    # All 3x-ui-managed protocols (xray, trojan, hysteria2) use "email".
    if protocol == "mtproto":
        key_data = {"username": identifier, "secret": "", "_link_override": link}
    elif hasattr(svc, 'inbound_id') and svc.inbound_id:
        # 3x-ui protocols — use email as the identifier field
        key_data = {"email": identifier, "sub_id": "", "uuid": "", "_link_override": link}
    else:
        key_data = {"username": identifier, "_link_override": link}
    text, parse_mode = svc.format_user_key_message(key_data)
    if not text:
        return
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
    except Exception as e:
        logging.error(f"Failed to send key to user {chat_id}: {e}")


async def _reply(send_or_edit, text, is_callback=False, **kwargs):
    """Send or edit a message depending on the source type."""
    if is_callback:
        try:
            await send_or_edit.edit_message_text(text, **kwargs)
        except Exception:
            await send_or_edit.message.reply_text(text, **kwargs)
    else:
        await send_or_edit.message.reply_text(text, **kwargs)


async def process_adduser_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, arg: str, protocol: str):
    """Create a user directly (without callback) for a given protocol.

    Delegates to :func:`_create_key_for_identifier`.
    """
    await _create_key_for_identifier(update, context, arg, protocol, is_callback=False)


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /users — show protocol selection for listing users.

    Args:
        update: The update object.
        context: The bot context.
    """
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(MESSAGES["no_permission"])
        return

    buttons = []
    active = get_active_protocols()
    for proto in active:
        svc = _svc(proto)
        if svc:
            buttons.append([InlineKeyboardButton(f"{svc.emoji} {svc.display_name}", callback_data=f"users_list_{proto}_0")])

    if not buttons:
        await update.message.reply_text(MESSAGES["no_available_protocols"])
        return

    buttons.append([InlineKeyboardButton("👥 All", callback_data="users_list_all_0")])
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(MESSAGES["users_choose_protocol"],
                                    reply_markup=keyboard)


async def users_show_page(update_or_query, context: ContextTypes.DEFAULT_TYPE, protocol: str, page: int):
    """Display a paginated list of users with active keys.

    Args:
        update_or_query: The update or callback query object.
        context: The bot context.
        protocol: Protocol filter (or ``'all'``).
        page: The page number to show (0-indexed).
    """
    if protocol == "all":
        users = db.get_users_with_active_keys()
    else:
        users = db.get_users_with_active_keys_for_protocol(protocol)

    if not users:
        await update_or_query.edit_message_text(MESSAGES["users_no_users"])
        return

    total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * USERS_PER_PAGE
    page_users = users[start:start + USERS_PER_PAGE]

    buttons = []
    for uname, tid, created in page_users:
        buttons.append([InlineKeyboardButton(uname, callback_data=f"user_info_{uname}")])

    # Navigation row: always show both prev and next when applicable
    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton(
            MESSAGES["pagination_prev"],
            callback_data=f"users_page_{protocol}_{page - 1}",
        ))
    if page < total_pages - 1:
        nav_btns.append(InlineKeyboardButton(
            MESSAGES["pagination_next"],
            callback_data=f"users_page_{protocol}_{page + 1}",
        ))
    if nav_btns:
        buttons.append(nav_btns)

    text = MESSAGES["users_page"].format(protocol=protocol.upper(), page=page + 1, total_pages=total_pages)
    await update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /info — show user info by username.

    Usage: ``/info <username>``

    Args:
        update: The update object.
        context: The bot context.
    """
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(MESSAGES["no_permission"])
        return
    if not context.args:
        await update.message.reply_text(MESSAGES["info_usage"])
        return
    username = context.args[0].lstrip('@')
    await user_info_direct(update, context, username)


async def _build_user_info_message(username: str) -> str:
    """Build a formatted user info message string.

    Args:
        username: The username to build info for.

    Returns:
        A formatted HTML message string, or empty string if the user
        was not found.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT telegram_id, created_at FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return ""
    telegram_id, created = row
    created_str = _format_date(created)

    c.execute(
        "SELECT protocol, key_data, status, created_at FROM keys WHERE user_id = (SELECT id FROM users WHERE username = ?)",
        (username,))
    keys = c.fetchall()
    conn.close()

    msg = MESSAGES["user_info_profile"].format(username=escape_html(username), telegram_id=telegram_id,
                                               created=created_str)
    if not keys:
        msg += "\n" + MESSAGES["user_info_no_keys"]
    else:
        for protocol, key_data_str, status, created_key in keys:
            key_data = json.loads(key_data_str)
            svc = _svc(protocol)
            login = svc.get_identifier(key_data) if svc else '—'
            link = svc.get_link_for_key(key_data) if svc else "—"
            created_key_str = _format_date(created_key)
            msg += MESSAGES["user_info_key"].format(
                protocol=protocol.upper(),
                login=login,
                status=status,
                created=created_key_str,
                link=link
            )
    return msg


async def user_info_callback(query, context, username):
    """Display detailed user info (keys, Telegram ID, timestamps).

    Args:
        query: The callback query.
        context: The bot context.
        username: The username to display.
    """
    msg = await _build_user_info_message(username)
    if not msg:
        await query.edit_message_text(MESSAGES["user_not_found"])
        return
    await query.edit_message_text(msg, parse_mode="HTML")


async def user_info_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
    """Display detailed user info directly (non-callback path).

    Args:
        update: The update object.
        context: The bot context.
        username: The username to display.
    """
    msg = await _build_user_info_message(username)
    if not msg:
        await update.message.reply_text(MESSAGES["user_not_found"])
        return
    await update.message.reply_text(msg, parse_mode="HTML")


def _format_date(iso_string):
    """Format an ISO datetime string to ``DD.MM.YYYY HH:MM``.

    Args:
        iso_string: An ISO-8601 datetime string.

    Returns:
        The formatted date string, or the original string on error.
    """
    if not iso_string:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime('%d.%m.%Y %H:%M')
    except:
        return iso_string


async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /revoke — show a keyboard to select which key to revoke.

    Usage: ``/revoke <username_or_telegram_id>``

    Args:
        update: The update object.
        context: The bot context.
    """
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(MESSAGES["no_permission"])
        return
    if not context.args:
        await update.message.reply_text(MESSAGES["revoke_usage"])
        return

    identifier = context.args[0].lstrip('@')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE telegram_id = ? OR username = ?", (identifier, identifier))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(MESSAGES["revoke_user_not_found"].format(identifier=identifier))
        return

    username = row[0]
    await _show_revoke_keyboard(update, username)


async def _show_revoke_keyboard(update: Update, username: str):
    """Display a keyboard with active keys for a user to revoke.

    Args:
        update: The update object.
        username: The user whose keys to list.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT k.protocol, json_extract(k.key_data, '$.email') as email, k.key_data
        FROM keys k
        JOIN users u ON k.user_id = u.id
        WHERE u.username = ? AND k.status = 'active'
    """, (username,))
    active_keys = c.fetchall()
    conn.close()

    if not active_keys:
        await update.message.reply_text(MESSAGES["revoke_no_active_keys"].format(identifier=username))
        return

    keyboard_buttons = []
    for protocol, email, key_data_str in active_keys:
        svc = _svc(protocol)
        if not svc:
            continue
        identifier = email if email else username
        label = f"{svc.emoji} {svc.display_name}: {identifier}"
        callback_data = f"revoke_{protocol}_{identifier}"
        keyboard_buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])

    keyboard_buttons.append([InlineKeyboardButton(MESSAGES["revoke_cancel_btn"], callback_data="revoke_cancel")])

    await update.message.reply_text(
        MESSAGES["revoke_select_key"].format(user=escape_html(username)),
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
        parse_mode="HTML"
    )


async def _revoke_key_by_protocol(username: str, protocol: str, update_or_query, context, email: str = None):
    """Revoke a key for a given protocol and notify the user.

    Uses the service registry to obtain the protocol-specific
    implementation, eliminating per-protocol branching.

    Args:
        username: The canonical username.
        protocol: The protocol identifier (e.g. ``'mtproto'``, ``'xray'``).
        update_or_query: Update or callback query for editing the message.
        context: Bot context.
        email: Protocol-specific identifier override (e.g. Xray email).
    """
    svc = _svc(protocol)
    if not svc:
        await update_or_query.edit_message_text(MESSAGES["revoke_error"])
        return

    identifier = email if email else username
    if svc.delete_user(identifier):
        if protocol == "mtproto":
            success_text = MESSAGES["revoke_mtproto_success"].format(username=escape_html(identifier))
        elif protocol == "xray":
            success_text = MESSAGES["revoke_xray_success"].format(email=escape_html(identifier))
        else:
            success_text = MESSAGES["revoke_success"].format(identifier=escape_html(identifier))
        await update_or_query.edit_message_text(
            success_text,
            parse_mode="HTML"
        )
        tid = svc.get_telegram_id(username)
        if tid and tid not in ('unknown', 'web', '—'):
            try:
                await context.bot.send_message(chat_id=int(tid), text=MESSAGES["key_revoked_notification"])
            except:
                pass
    else:
        await update_or_query.edit_message_text(MESSAGES["revoke_error"])


async def cache_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cache a media group message for later batch forwarding.

    Args:
        update: The update object.
        context: The bot context.
    """
    msg = update.effective_message
    if msg and msg.media_group_id and msg.date:
        db.cache_message(
            chat_id=msg.chat_id,
            message_id=msg.message_id,
            media_group_id=msg.media_group_id,
            date=msg.date.timestamp()
        )


async def _copy_to_user(chat_id: int, source_chat_id: int,
                        reply_message, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Copy a message (or album) from the admin group to a user.

    Args:
        chat_id: Target user chat ID.
        source_chat_id: Source chat (admin group) ID.
        reply_message: The message to copy.
        context: Bot context.

    Returns:
        True if the copy succeeded, False otherwise.
    """
    try:
        if reply_message.media_group_id:
            album_ids = db.get_media_group_message_ids(source_chat_id, reply_message.media_group_id)
            if album_ids:
                await context.bot.copy_messages(
                    chat_id=chat_id,
                    from_chat_id=source_chat_id,
                    message_ids=album_ids
                )
                return True
            else:
                await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=source_chat_id,
                    message_id=reply_message.message_id
                )
                return True
        else:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source_chat_id,
                message_id=reply_message.message_id
            )
            return True
    except Exception as e:
        return False


async def sendto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sendto — forward a message to a specific user.

    Usage: ``/sendto <username>`` (reply to the message to forward)

    Args:
        update: The update object.
        context: The bot context.
    """
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(MESSAGES["no_permission"])
        return

    if not context.args:
        await update.message.reply_text(MESSAGES["sendto_usage"])
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(MESSAGES["sendto_reply_prompt"])
        return

    target = context.args[0].lstrip('@')

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE username = ? OR telegram_id = ?", (target, target))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(MESSAGES["sendto_user_not_found"].format(target=target))
        return

    tid = row[0]
    if tid in ('unknown', 'web', '—'):
        await update.message.reply_text(MESSAGES["sendto_no_telegram_id"].format(target=target))
        return

    source_chat_id = update.effective_chat.id
    success = await _copy_to_user(int(tid), source_chat_id,
                                  update.message.reply_to_message, context)
    if success:
        await update.message.reply_text(MESSAGES["sendto_success"].format(target=target))
    else:
        await update.message.reply_text(MESSAGES["sendto_error"].format(target=target))


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast — forward a message to all users.

    Usage: ``/broadcast [protocol]`` (reply to the message to forward)

    Args:
        update: The update object.
        context: The bot context.
    """
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(MESSAGES["no_permission"])
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(MESSAGES["broadcast_usage"])
        return

    filter_protocol = context.args[0].lower() if context.args else "all"
    allowed = ["all"] + get_active_protocols()
    if filter_protocol not in allowed:
        await update.message.reply_text(MESSAGES["invalid_broadcast_filter"])
        return

    if filter_protocol == "all":
        unique_ids = db.get_unique_telegram_ids()
    else:
        from app.services.broadcast_service import get_user_ids_by_protocol
        unique_ids = get_user_ids_by_protocol(filter_protocol)

    if not unique_ids:
        await update.message.reply_text(MESSAGES["broadcast_no_users"])
        return

    total = len(unique_ids)
    status_msg = await update.message.reply_text(
        MESSAGES["broadcast_started"].format(filter_protocol=filter_protocol, total=total))
    source_chat_id = update.effective_chat.id
    original = update.message.reply_to_message

    success = 0
    failed = 0
    for tid in unique_ids:
        ok = await _copy_to_user(int(tid), source_chat_id, original, context)
        if ok:
            success += 1
        else:
            failed += 1
        await asyncio.sleep(0.15)

    await status_msg.edit_text(
        MESSAGES["broadcast_done"].format(filter_protocol=filter_protocol, success=success, failed=failed))


async def resend_keys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /resend_keys — resend VPN keys to users.

    Usage: ``/resend_keys [protocol]``

    Args:
        update: The update object.
        context: The bot context.
    """
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(MESSAGES["no_permission"])
        return

    if not context.args:
        await update.message.reply_text(MESSAGES["resend_keys_usage"])
        return

    filter_protocol = context.args[0].lower() if context.args else "all"
    allowed = ["all"] + get_active_protocols()
    if filter_protocol not in allowed:
        await update.message.reply_text(MESSAGES[f"{filter_protocol}_not_supported"])
        return

    from app.services.broadcast_service import get_user_ids_by_protocol
    if filter_protocol == "all":
        user_ids = get_user_ids_by_protocol(None)
    else:
        user_ids = get_user_ids_by_protocol(filter_protocol)

    if not user_ids:
        await update.message.reply_text(MESSAGES["resend_keys_no_users"])
        return

    total_users = len(user_ids)
    status_msg = await update.message.reply_text(
        MESSAGES["resend_keys_started"].format(filter_protocol=filter_protocol, total=total_users)
    )

    success = 0
    failed = 0

    for uid in user_ids:
        try:
            uid = int(uid)
            if filter_protocol == "all":
                for proto in get_active_protocols():
                    keys = get_user_active_keys(uid, proto)
                    for key in keys:
                        await send_existing_key(uid, proto, key, context)
                success += 1
            else:
                keys = get_user_active_keys(uid, filter_protocol)
                for key in keys:
                    if await send_existing_key(uid, filter_protocol, key, context):
                        success += 1
                    else:
                        failed += 1
        except Exception as e:
            failed += 1
            logging.error(f"Error sending key to user {uid}: {e}")
        await asyncio.sleep(0.15)

    await status_msg.edit_text(
        MESSAGES["resend_keys_done"].format(success=success, failed=failed)
    )


async def send_existing_key(chat_id: int, protocol: str, key_data: dict, context) -> bool:
    """Send an existing VPN key to a user by protocol.

    Uses the service's ``format_user_key_message`` to build the
    protocol-specific message text, eliminating per-protocol branching.

    Args:
        chat_id: The target chat ID.
        protocol: The protocol name (e.g. ``'mtproto'``, ``'xray'``).
        key_data: The key data dict from the database.
        context: Bot context.

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    try:
        svc = _svc(protocol)
        if not svc:
            return False
        text, parse_mode = svc.format_user_key_message(key_data)
        if not text:
            return False
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return True
    except Exception as e:
        logging.error(f"Error sending {protocol} key to {chat_id}: {e}")
        return False
