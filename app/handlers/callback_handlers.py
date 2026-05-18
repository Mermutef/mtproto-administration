from telegram import Update
from telegram.ext import ContextTypes
from .private_callbacks import handle_cancel_req, handle_req_service
from .admin_callbacks import handle_approve, handle_reject, handle_add_key
from app.config import ADMIN_GROUP_ID, ADMIN_IDS
from app.locales.ru import MESSAGES


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data
    is_private = update.effective_chat.type == "private"
    is_admin_group = update.effective_chat.id == ADMIN_GROUP_ID

    if is_private:
        if data.startswith("cancel_req_"):
            await handle_cancel_req(query, data, user.id, context)
            return
        if data.startswith("req_service_"):
            await handle_req_service(query, data, user.id, user.username or user.first_name, context)
            return
        return

    if not is_admin_group:
        await query.edit_message_text(MESSAGES["button_only_in_group"])
        return
    if ADMIN_IDS and user.id not in ADMIN_IDS:
        await query.edit_message_text(MESSAGES["no_permission"])
        return

    if data.startswith("revoke_mtproto_"):
        from .admin_callbacks import handle_revoke_mtproto
        await handle_revoke_mtproto(query, data, context)
        return
    if data.startswith("revoke_xray_"):
        from .admin_callbacks import handle_revoke_xray
        await handle_revoke_xray(query, data, context)
        return
    if data == "revoke_cancel":
        from .admin_callbacks import handle_revoke_cancel
        await handle_revoke_cancel(query, data, context)
        return

    if data.startswith("add_"):
        await handle_add_key(query, data, context)
    elif data.startswith("approve_"):
        await handle_approve(query, data, context)
    elif data.startswith("reject_"):
        await handle_reject(query, data, context)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(MESSAGES["unknown_command"])
    elif update.effective_chat.id == ADMIN_GROUP_ID:
        await update.message.reply_text(MESSAGES["unknown_admin_command"])
