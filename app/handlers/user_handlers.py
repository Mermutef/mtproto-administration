"""User-facing Telegram command handlers.

Provides commands available to regular users in private chat:
``/start``, ``/request``, ``/status``, ``/cancel``, ``/mykeys``.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import app.db as db
from app.locales.ru import MESSAGES
from app.config import ADMIN_GROUP_ID, get_active_protocols
from app.services.registry import registry


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — show welcome message with supported protocols."""
    if update.effective_chat.type != "private":
        return
    protocols_str = ", ".join(p.upper() for p in get_active_protocols())
    await update.message.reply_text(MESSAGES["start"].format(protocols=protocols_str), parse_mode="HTML")


async def request_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /request — show protocol selection buttons."""
    if update.effective_chat.type != "private":
        await update.message.reply_text(MESSAGES["not_in_private"])
        return

    buttons = []
    active = get_active_protocols()
    for proto in active:
        svc = registry.get(proto)
        if svc:
            buttons.append([InlineKeyboardButton(f"{svc.emoji} {svc.display_name}", callback_data=f"req_service_{proto}")])

    if not buttons:
        await update.message.reply_text(MESSAGES["no_available_protocols"])
        return

    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(MESSAGES["choose_protocol"], reply_markup=keyboard)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status — show the latest access request status."""
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    requests = db.get_user_requests(user_id)
    if not requests:
        await update.message.reply_text(MESSAGES["no_requests"])
        return
    req_id, status, created, _ = requests[0]
    status_map = {
        "pending": MESSAGES["status_pending"],
        "approved": MESSAGES["status_approved"],
        "rejected": MESSAGES["status_rejected"],
        "revoked": MESSAGES["status_revoked"]
    }
    status_text = status_map.get(status, status)
    await update.message.reply_text(
        MESSAGES["last_request_status"].format(
            req_id=req_id, status_text=status_text, created=created[:19]),
        parse_mode="HTML"
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel — cancel one or more pending access requests."""
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    requests = db.get_user_requests(user_id)
    pending = [(r[0], r[2], r[3]) for r in requests if r[1] == "pending"]
    if not pending:
        await update.message.reply_text(MESSAGES["no_pending_requests"])
        return

    if len(pending) == 1:
        req_id, created, protocol = pending[0]
        db.update_request_status(req_id, "rejected")
        await update.message.reply_text(MESSAGES["request_cancelled"].format(req_id=req_id))
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=MESSAGES["user_cancelled_request"].format(user_id=user_id, req_id=req_id)
        )
        return

    keyboard = []
    for req_id, created, protocol in pending:
        label = f"❌ #{req_id} ({protocol.upper()}) от {created[:10]}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"cancel_req_{req_id}")])

    keyboard.append([InlineKeyboardButton("« Назад", callback_data="cancel_req_cancel")])
    await update.message.reply_text(
        MESSAGES["multiple_pending_requests"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def mykeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mykeys — display all active keys for the user."""
    if update.effective_chat.type != "private":
        await update.message.reply_text(MESSAGES["not_in_private"])
        return
    user_id = update.effective_user.id
    msg = MESSAGES["my_keys_header"]
    found = False

    # Freshly fetch all keys from the panel for 3x-ui protocols
    # and merge them into the local DB to fix stale sub_id / missing logins.
    for proto in get_active_protocols():
        svc = registry.get(proto)
        if not svc:
            continue
        if hasattr(svc, 'inbound_id') and svc.inbound_id:
            try:
                # Refresh local keys from panel (fixes stale sub_id, missing uuid)
                svc.get_users()
            except Exception:
                pass

    for proto in get_active_protocols():
        svc = registry.get(proto)
        if not svc:
            continue
        keys = db.get_user_active_keys(user_id, proto)
        for key in keys:
            found = True
            login = svc.get_identifier(key)
            link = svc.get_link_for_key(key)
            # Fix empty login for MTProto
            if not login and proto == "mtproto":
                login = key.get('username', '—')
            msg += MESSAGES["my_keys_key"].format(protocol=proto.upper(), login=login, link=link)
    if not found:
        msg = MESSAGES["my_keys_no_keys"]
    await update.message.reply_text(msg, parse_mode="HTML")
