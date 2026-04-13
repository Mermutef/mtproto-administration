from telegram import Update
from telegram.ext import ContextTypes
import app.db as db
from app.utils import escape_html
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
    user = update.effective_user
    user_id = user.id
    user_name = user.username or user.first_name

    existing = db.get_user_by_telegram_id(user_id)
    if existing:
        await update.message.reply_text(
            MESSAGES["already_has_key"].format(username=escape_html(existing)),
            parse_mode="HTML"
        )
        return

    requests = db.get_user_requests(user_id)
    for req_id, status, _ in requests:
        if status == "pending":
            await update.message.reply_text(MESSAGES["pending_request_exists"].format(req_id=req_id))
            return

    request_id = db.add_request(user_id, user_name)
    await update.message.reply_text(MESSAGES["request_created"].format(req_id=request_id))

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{request_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")]
    ])
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=MESSAGES["admin_new_request"].format(
                user_name=escape_html(user_name), user_id=user_id, req_id=request_id),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка отправки в группу: {e}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    requests = db.get_user_requests(user_id)
    if not requests:
        await update.message.reply_text(MESSAGES["no_requests"])
        return
    req_id, status, created = requests[0]
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
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    requests = db.get_user_requests(user_id)
    pending = [(rid, stat) for rid, stat, _ in requests if stat == "pending"]
    if not pending:
        await update.message.reply_text(MESSAGES["no_pending_requests"])
        return
    req_id = pending[0][0]
    db.update_request_status(req_id, "rejected")
    await update.message.reply_text(MESSAGES["request_cancelled"].format(req_id=req_id))
    await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=MESSAGES["user_cancelled_request"].format(user_id=user_id, req_id=req_id)
    )
