import secrets
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import db
import proxy_manager
from config import ADMIN_GROUP_ID, ADMIN_IDS, DB_PATH
from utils import escape_html


# ---------- Пользовательские команды (ЛС) ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    await update.message.reply_text(
        "🚀 <b>MTProxy Bot</b>\n\n"
        "Этот бот выдаёт ключи для доступа к MTProto прокси.\n\n"
        "Команды:\n"
        "/request — подать заявку на получение ключа\n"
        "/status — проверить статус последней заявки\n"
        "/cancel — отменить текущую заявку\n\n"
        "После одобрения администратором ключ придёт в этот чат.",
        parse_mode="HTML"
    )


async def request_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("Пожалуйста, пишите мне в личные сообщения.")
        return
    user = update.effective_user
    user_id = user.id
    user_name = user.username or user.first_name

    existing = db.get_user_by_telegram_id(user_id)
    if existing:
        await update.message.reply_text(
            f"⚠️ У вас уже есть активный ключ (логин: <code>{escape_html(existing)}</code>).\n"
            "Если вы забыли ссылку, обратитесь к администратору.",
            parse_mode="HTML"
        )
        return

    requests = db.get_user_requests(user_id)
    for req_id, status, _ in requests:
        if status == "pending":
            await update.message.reply_text(
                f"⏳ У вас уже есть активная заявка #{req_id}. Ожидайте решения администратора.")
            return

    request_id = db.add_request(user_id, user_name)
    await update.message.reply_text(f"✅ Заявка #{request_id} создана! Администратор рассмотрит её в ближайшее время.")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{request_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")]
    ])
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=(
                f"🆕 <b>Новая заявка на ключ!</b>\n"
                f"От: {escape_html(user_name)} (ID: <code>{user_id}</code>)\n"
                f"Заявка #{request_id}"
            ),
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
        await update.message.reply_text("У вас нет ни одной заявки. Используйте /request, чтобы создать.")
        return
    last = requests[0]
    req_id, status, created = last
    status_text = {
        "pending": "⏳ Ожидает рассмотрения",
        "approved": "✅ Одобрена (ключ уже должен был прийти)",
        "rejected": "❌ Отклонена"
    }.get(status, status)
    await update.message.reply_text(
        f"📋 <b>Ваша последняя заявка</b>\n"
        f"Номер: #{req_id}\n"
        f"Статус: {status_text}\n"
        f"Создана: {created[:19]}",
        parse_mode="HTML"
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    requests = db.get_user_requests(user_id)
    pending = [(rid, stat) for rid, stat, _ in requests if stat == "pending"]
    if not pending:
        await update.message.reply_text("У вас нет ожидающих заявок.")
        return
    req_id = pending[0][0]
    db.update_request_status(req_id, "rejected")
    await update.message.reply_text(f"Заявка #{req_id} отменена.")
    await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=f"ℹ️ Пользователь {user_id} отменил заявку #{req_id}."
    )


# ---------- Административные команды (только в группе) ----------
async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    await update.message.reply_text(
        "👑 <b>Административная панель</b>\n\n"
        "Доступные команды:\n"
        "/users — список пользователей с кнопками отзыва\n"
        "/adduser @username — выдать ключ пользователю\n"
        "/revoke @username — отозвать ключ\n\n"
        "Заявки приходят с кнопками Одобрить/Отклонить.",
        parse_mode="HTML"
    )


async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    if not context.args:
        await update.message.reply_text("❌ Использование: /adduser @username")
        return
    username = context.args[0].lstrip('@')
    try:
        chat = await context.bot.get_chat(f"@{username}")
        user_id = chat.id
    except:
        await update.message.reply_text(f"❌ Не найден @{username}. Убедитесь, что пользователь начал диалог с ботом.")
        return
    existing = db.get_user_by_telegram_id(user_id)
    if existing:
        await update.message.reply_text(f"⚠️ У @{username} уже есть ключ: <code>{escape_html(existing)}</code>",
                                        parse_mode="HTML")
        return
    proxy_username = proxy_manager.generate_unique_username(f"u_{user_id}")
    success, link = proxy_manager.create_user(proxy_username, telegram_id=str(user_id))
    if success:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ Администратор выдал вам ключ!\n"
                f"Логин: <code>{escape_html(proxy_username)}</code>\n"
                f"🔗 {link}"
            ),
            parse_mode="HTML"
        )
        await update.message.reply_text(f"✅ Ключ для @{username} создан и отправлен.")
    else:
        await update.message.reply_text(f"❌ Ошибка при создании ключа: {link}")


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    users = db.get_all_users()
    if not users:
        await update.message.reply_text("📭 Список пользователей пуст.")
        return

    message_lines = ["<b>📋 Список пользователей:</b>\n"]
    keyboard_buttons = []
    for uname, tid, created in users:
        if tid != 'unknown':
            try:
                chat = await context.bot.get_chat(int(tid))
                tg_uname = f"@{chat.username}" if chat.username else tid
            except:
                tg_uname = tid
        else:
            tg_uname = "unknown"
        message_lines.append(f"• <code>{escape_html(uname)}</code> — {escape_html(str(tg_uname))} (с {created[:10]})")
        keyboard_buttons.append([InlineKeyboardButton(f"❌ Отозвать {uname}", callback_data=f"revoke_{uname}")])

    message_text = "\n".join(message_lines)
    keyboard = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None
    await update.message.reply_text(message_text, parse_mode="HTML", reply_markup=keyboard)


async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    if not context.args:
        await update.message.reply_text("❌ Использование: /revoke @username")
        return
    identifier = context.args[0].lstrip('@')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE telegram_id = ? OR username = ?", (identifier, identifier))
    row = c.fetchone()
    conn.close()
    if not row:
        await update.message.reply_text(f"❌ Пользователь @{identifier} не найден.")
        return
    proxy_username = row[0]
    if proxy_manager.delete_user(proxy_username):
        await update.message.reply_text(f"✅ Ключ для @{identifier} отозван.")
        # уведомление пользователю, если знаем его ID
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT telegram_id FROM users WHERE username = ?", (proxy_username,))
        row2 = c.fetchone()
        conn.close()
        if row2 and row2[0] != 'unknown':
            try:
                await context.bot.send_message(chat_id=int(row2[0]), text="⚠️ Ваш ключ отозван администратором.")
            except:
                pass
    else:
        await update.message.reply_text("❌ Ошибка при отзыве.")


# ---------- Callback кнопок ----------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_chat.id != ADMIN_GROUP_ID:
        await query.edit_message_text("⛔ Эта кнопка работает только в админской группе.")
        return
    user_id = query.from_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ У вас нет прав для обработки заявок.")
        return

    data = query.data
    if data.startswith("approve_"):
        req_id = int(data.split("_")[1])
        req = db.get_request(req_id)
        if not req or req[2] != "pending":
            await query.edit_message_text("❌ Заявка уже обработана или не существует.")
            return
        uid, user_name, _ = req
        proxy_username = proxy_manager.generate_unique_username(f"u_{uid}")
        success, link = proxy_manager.create_user(proxy_username, telegram_id=uid)
        if success:
            db.update_request_status(req_id, "approved")
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=(
                        f"✅ Ваша заявка одобрена!\n"
                        f"Логин: <code>{escape_html(proxy_username)}</code>\n"
                        f"🔗 {link}"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {uid}: {e}")
            await query.edit_message_text(f"✅ Заявка #{req_id} одобрена. Ключ отправлен пользователю.")
        else:
            await query.edit_message_text(f"❌ Ошибка создания ключа: {link}")
    elif data.startswith("reject_"):
        req_id = int(data.split("_")[1])
        req = db.get_request(req_id)
        if not req or req[2] != "pending":
            await query.edit_message_text("❌ Заявка уже обработана.")
            return
        uid, user_name, _ = req
        db.update_request_status(req_id, "rejected")
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"❌ Ваша заявка #{req_id} отклонена.")
        except:
            pass
        await query.edit_message_text(f"❌ Заявка #{req_id} отклонена.")
    elif data.startswith("revoke_"):
        proxy_username = data.split("_")[1]
        if proxy_manager.delete_user(proxy_username):
            await query.edit_message_text(f"✅ Ключ <code>{escape_html(proxy_username)}</code> отозван.",
                                          parse_mode="HTML")
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT telegram_id FROM users WHERE username = ?", (proxy_username,))
            row = c.fetchone()
            conn.close()
            if row and row[0] != 'unknown':
                try:
                    await context.bot.send_message(chat_id=int(row[0]),
                                                   text=f"⚠️ Ваш ключ <code>{escape_html(proxy_username)}</code> отозван администратором.",
                                                   parse_mode="HTML")
                except:
                    pass
        else:
            await query.edit_message_text("❌ Ошибка при отзыве ключа.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("❓ Неизвестная команда. Используйте /start")
    elif update.effective_chat.id == ADMIN_GROUP_ID:
        await update.message.reply_text("❓ Неизвестная команда. Доступно: /start, /adduser, /users, /revoke")
