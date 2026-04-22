from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import app.db as db
from app.locales.ru import MESSAGES
from app.config import ADMIN_GROUP_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    await update.message.reply_text(MESSAGES["start"], parse_mode="HTML")


async def request_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text(MESSAGES["not_in_private"])
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡️ MTProto", callback_data="req_service_mtproto")],
        [InlineKeyboardButton("🌐 Xray", callback_data="req_service_xray")],
        [InlineKeyboardButton("⚡ Hysteria2", callback_data="req_service_hysteria2")]
    ])
    await update.message.reply_text("Выберите протокол для получения ключа:", reply_markup=keyboard)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    """Показывает список активных заявок с кнопками для отмены."""
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
        await update.message.reply_text(
            MESSAGES["request_cancelled"].format(req_id=req_id)
        )
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
