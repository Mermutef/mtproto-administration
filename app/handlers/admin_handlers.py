import sqlite3
from telegram import Update, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
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

    arg = context.args[0]

    if arg.startswith('@'):
        username = arg.lstrip('@')
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

    else:
        proxy_username = arg.strip()
        if not proxy_username:
            await update.message.reply_text("❌ Логин не может быть пустым.")
            return

        if proxy_username in proxy_manager.load_users():
            await update.message.reply_text(f"❌ Логин '{proxy_username}' уже существует.")
            return

        success, link = proxy_manager.create_user(proxy_username, telegram_id="web")
        if success:
            await update.message.reply_text(
                f"✅ Пользователь '{proxy_username}' добавлен.\nСсылка: {link}"
            )
        else:
            await update.message.reply_text(f"❌ Ошибка: {link}")


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


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка сообщения всем пользователям бота."""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "ℹ️ Ответьте на сообщение, которое хотите разослать, командой /broadcast"
        )
        return

    users = db.get_all_users_with_telegram()
    if not users:
        await update.message.reply_text("📭 Нет пользователей для рассылки.")
        return

    original = update.message.reply_to_message
    success = 0
    failed = 0

    status_msg = await update.message.reply_text(f"⏳ Рассылка начата. Всего получателей: {len(users)}...")

    media_group_id = original.media_group_id

    if media_group_id:
        # Собираем все сообщения из этой медиагруппы
        media_messages = []
        async for msg in context.bot.get_chat_history(update.effective_chat.id, limit=50):
            if msg.media_group_id == media_group_id:
                media_messages.append(msg)
        media_messages.sort(key=lambda x: x.message_id)

        input_media_list = []
        for i, msg in enumerate(media_messages):
            caption = msg.caption if i == 0 else None
            if msg.photo:
                input_media_list.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=caption))
            elif msg.video:
                input_media_list.append(InputMediaVideo(media=msg.video.file_id, caption=caption))
            elif msg.document:
                input_media_list.append(InputMediaDocument(media=msg.document.file_id, caption=caption))
            elif msg.audio:
                input_media_list.append(InputMediaAudio(media=msg.audio.file_id, caption=caption))
            else:
                continue

        for username, tid in users:
            try:
                await context.bot.send_media_group(chat_id=int(tid), media=input_media_list)
                success += 1
            except Exception as e:
                failed += 1
                print(f"Ошибка отправки медиагруппы пользователю {tid}: {e}")
    else:
        for username, tid in users:
            try:
                await original.copy(chat_id=int(tid))
                success += 1
            except Exception as e:
                failed += 1
                print(f"Ошибка отправки пользователю {tid}: {e}")

    await status_msg.edit_text(
        f"✅ Рассылка завершена.\n"
        f"Успешно: {success}\n"
        f"Ошибок: {failed}"
    )


async def sendto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересылка сообщения конкретному пользователю."""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return

    if not context.args:
        await update.message.reply_text("ℹ️ Использование: /sendto @username (в ответ на сообщение)")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("ℹ️ Ответьте на сообщение, которое хотите переслать.")
        return

    target = context.args[0].lstrip('@')
    original = update.message.reply_to_message

    # Пытаемся определить получателя
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE username = ? OR telegram_id = ?", (target, target))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(f"❌ Пользователь '{target}' не найден.")
        return

    tid = row[0]
    if tid in ('unknown', 'web', '—'):
        await update.message.reply_text(f"❌ У пользователя '{target}' нет Telegram ID.")
        return

    try:
        media_group_id = original.media_group_id
        if media_group_id:
            # Собираем все сообщения альбома
            media_messages = []
            async for msg in context.bot.get_chat_history(update.effective_chat.id, limit=50):
                if msg.media_group_id == media_group_id:
                    media_messages.append(msg)
            media_messages.sort(key=lambda x: x.message_id)

            input_media_list = []
            for i, msg in enumerate(media_messages):
                caption = msg.caption if i == 0 else None
                if msg.photo:
                    input_media_list.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=caption))
                elif msg.video:
                    input_media_list.append(InputMediaVideo(media=msg.video.file_id, caption=caption))
                elif msg.document:
                    input_media_list.append(InputMediaDocument(media=msg.document.file_id, caption=caption))
                elif msg.audio:
                    input_media_list.append(InputMediaAudio(media=msg.audio.file_id, caption=caption))
                else:
                    continue

            await context.bot.send_media_group(chat_id=int(tid), media=input_media_list)
        else:
            await original.copy(chat_id=int(tid))

        await update.message.reply_text(f"✅ Сообщение отправлено пользователю '{target}'.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отправки: {e}")
