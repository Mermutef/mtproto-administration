import sqlite3
from telegram import Update
from telegram.ext import ContextTypes
import app.db as db
import app.proxy_manager as proxy_manager
from app.config import ADMIN_GROUP_ID, ADMIN_IDS, DB_PATH
from app.utils import escape_html
from app.locales.ru import MESSAGES

async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    await update.message.reply_text(MESSAGES["admin_start"], parse_mode="HTML")

async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    if not context.args:
        await update.message.reply_text(MESSAGES["adduser_usage"])
        return
    username = context.args[0].lstrip('@')
    try:
        chat = await context.bot.get_chat(f"@{username}")
        user_id = chat.id
    except:
        await update.message.reply_text(MESSAGES["user_not_found"].format(username=username))
        return
    existing = db.get_user_by_telegram_id(user_id)
    if existing:
        await update.message.reply_text(
            MESSAGES["user_already_has_key"].format(tg_username=username, username=escape_html(existing)),
            parse_mode="HTML"
        )
        return
    proxy_username = proxy_manager.generate_unique_username(f"u_{user_id}")
    success, link = proxy_manager.create_user(proxy_username, telegram_id=str(user_id))
    if success:
        await context.bot.send_message(
            chat_id=user_id,
            text=MESSAGES["admin_key_granted"].format(
                username=escape_html(proxy_username), link=link),
            parse_mode="HTML"
        )
        await update.message.reply_text(MESSAGES["key_created_sent"].format(username=username))
    else:
        await update.message.reply_text(MESSAGES["key_created_error"].format(error=link))

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    users = db.get_all_users()
    if not users:
        await update.message.reply_text(MESSAGES["users_list_empty"])
        return
    message_lines = [MESSAGES["users_list_header"]]
    for uname, tid, created in users:
        if tid != 'unknown':
            try:
                chat = await context.bot.get_chat(int(tid))
                tg_uname = f"@{chat.username}" if chat.username else tid
            except:
                tg_uname = tid
        else:
            tg_uname = "unknown"
        message_lines.append(
            MESSAGES["users_list_item"].format(
                username=escape_html(uname),
                tg_info=escape_html(str(tg_uname)),
                created=created[:10]
            )
        )
    message_lines.append(MESSAGES["users_list_footer"])
    message_text = "\n".join(message_lines)
    await update.message.reply_text(message_text, parse_mode="HTML")

async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    if not context.args:
        await update.message.reply_text(MESSAGES["revoke_usage"])
        return
    identifier = context.args[0].lstrip('@')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, telegram_id FROM users WHERE telegram_id = ? OR username = ?", (identifier, identifier))
    row = c.fetchone()
    conn.close()
    if not row:
        await update.message.reply_text(MESSAGES["revoke_user_not_found"].format(identifier=identifier))
        return
    proxy_username, tid = row
    if proxy_manager.delete_user(proxy_username):
        await update.message.reply_text(MESSAGES["revoke_success"].format(identifier=identifier))
        if tid and tid not in ('unknown', 'web'):
            try:
                await context.bot.send_message(chat_id=int(tid), text=MESSAGES["key_revoked_notification"])
            except:
                pass
    else:
        await update.message.reply_text(MESSAGES["revoke_error"])