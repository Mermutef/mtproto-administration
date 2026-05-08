import sqlite3
import asyncio
import traceback

from telegram import Update
from telegram.ext import ContextTypes
import app.db as db
import app.proxy_manager as proxy_manager
from app.config import ADMIN_GROUP_ID, ADMIN_IDS, DB_PATH, XRAY_SUB_URL_BASE
from app.db import get_user_active_keys
from app.utils import escape_html
from app.locales.ru import MESSAGES
from app.services.key_service import create_mtproto_key, create_xray_key
from app.services.broadcast_service import get_user_ids_by_protocol
from app.services.key_service import get_or_update_sub_id


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
    protocol = context.args[1].lower() if len(context.args) > 1 else "mtproto"
    if protocol not in ("mtproto", "xray", "hysteria2"):
        await update.message.reply_text("❌ Неизвестный протокол. Используйте: mtproto, xray, hysteria2.")
        return

    if arg.startswith('@'):
        username = arg.lstrip('@')
        try:
            chat = await context.bot.get_chat(f"@{username}")
            user_id = chat.id
        except:
            await update.message.reply_text(MESSAGES["user_not_found"].format(username=username))
            return

        # Проверим, нет ли уже такого ключа
        if protocol == "mtproto":
            existing = db.get_user_by_telegram_id(user_id)
            if existing:
                await update.message.reply_text(
                    MESSAGES["user_already_has_key"].format(tg_username=username, username=escape_html(existing)),
                    parse_mode="HTML"
                )
                return
            success, (proxy_username, link), error = create_mtproto_key(user_id, username)
        elif protocol == "xray":
            keys = db.get_user_active_keys(user_id, 'xray')
            if keys:
                await update.message.reply_text(f"⚠️ У @{username} уже есть активный ключ Xray.")
                return
            success, (email, subscribe_url), error = create_xray_key(user_id, username)
        elif protocol == "hysteria2":
            await update.message.reply_text("Hysteria2 пока не поддерживается.")
            return

        if success:
            if protocol == "mtproto":
                await context.bot.send_message(
                    chat_id=user_id,
                    text=MESSAGES["admin_key_granted"].format(username=escape_html(proxy_username), link=link),
                    parse_mode="HTML"
                )
                await update.message.reply_text(MESSAGES["mtp_key_created_sent"].format(username=username))
            elif protocol == "xray":
                await context.bot.send_message(
                    chat_id=user_id,
                    text=MESSAGES["xray_key_granted"].format(email=escape_html(email), subscribe_url=subscribe_url),
                    parse_mode="HTML"
                )
                await update.message.reply_text(f"✅ Xray-ключ для @{username} создан и отправлен.")
        else:
            await update.message.reply_text(MESSAGES["key_created_error"].format(error=error))
    else:
        if protocol != "mtproto":
            await update.message.reply_text("❌ При указании логина доступен только протокол mtproto.")
            return
        proxy_username = arg.strip()
        if not proxy_username:
            await update.message.reply_text("❌ Логин не может быть пустым.")
            return
        if proxy_username in proxy_manager.load_users():
            await update.message.reply_text(f"❌ Логин '{proxy_username}' уже существует.")
            return
        success, link = proxy_manager.create_user(proxy_username, telegram_id="web")
        if success:
            await update.message.reply_text(f"✅ Пользователь '{proxy_username}' добавлен.\nСсылка: {link}")
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


async def cache_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        traceback.print_exc()
        return False


async def sendto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    source_chat_id = update.effective_chat.id
    success = await _copy_to_user(int(tid), source_chat_id,
                                  update.message.reply_to_message, context)
    if success:
        await update.message.reply_text(f"✅ Сообщение отправлено пользователю '{target}'.")
    else:
        await update.message.reply_text(f"❌ Не удалось отправить сообщение пользователю '{target}'.")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "ℹ️ Ответьте на сообщение командой /broadcast [фильтр: all, mtproto, xray, hysteria2]")
        return

    filter_protocol = context.args[0].lower() if context.args else "all"
    if filter_protocol not in ("all", "mtproto", "xray", "hysteria2"):
        await update.message.reply_text("Фильтр должен быть all, mtproto, xray или hysteria2")
        return

    if filter_protocol == "all":
        unique_ids = db.get_unique_telegram_ids()
    else:
        unique_ids = get_user_ids_by_protocol(filter_protocol)

    if not unique_ids:
        await update.message.reply_text("📭 Нет пользователей для рассылки.")
        return

    total = len(unique_ids)
    status_msg = await update.message.reply_text(f"⏳ Рассылка начата ({filter_protocol}). Получателей: {total}...")
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
        f"✅ Рассылка завершена ({filter_protocol}).\n"
        f"Успешно: {success}\n"
        f"Ошибок: {failed}"
    )


async def resend_keys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return

    if not context.args:
        await update.message.reply_text(MESSAGES["resend_keys_usage"])
        return

    filter_protocol = context.args[0].lower()
    allowed = ("all", "mtproto", "xray", "hysteria2")
    if filter_protocol not in allowed:
        await update.message.reply_text(MESSAGES["resend_keys_usage"])
        return

    if filter_protocol == "hysteria2":
        await update.message.reply_text(MESSAGES["resend_keys_hysteria2_not_supported"])
        return

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
                for proto in ("mtproto", "xray"):
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
            print(f"Ошибка при отправке ключа пользователю {uid}: {e}")
        await asyncio.sleep(0.15)

    await status_msg.edit_text(
        MESSAGES["resend_keys_done"].format(success=success, failed=failed)
    )


async def send_existing_key(chat_id: int, protocol: str, key_data: dict, context) -> bool:
    try:
        if protocol == "mtproto":
            secret = key_data.get("secret")
            if not secret:
                return False
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "SELECT username FROM users WHERE id = (SELECT user_id FROM keys WHERE protocol='mtproto' AND json_extract(key_data, '$.secret') = ?)",
                (secret,))
            row = c.fetchone()
            conn.close()
            if not row:
                return False
            username = row[0]
            link = proxy_manager.get_proxy_link(secret)
            text = MESSAGES["admin_key_granted"].format(username=escape_html(username), link=link)
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            return True
        elif protocol == "xray":
            email = key_data.get("email")
            if not email:
                return False
            sub_id = key_data.get("sub_id")
            if not sub_id:
                sub_id = get_or_update_sub_id(email)  # подстрахуемся
            subscribe_url = f"{XRAY_SUB_URL_BASE}{sub_id}" if sub_id else ""
            text = MESSAGES["xray_key_granted"].format(email=escape_html(email), subscribe_url=subscribe_url)
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            return True
        else:
            return False
    except Exception as e:
        print(f"Ошибка отправки ключа {protocol} пользователю {chat_id}: {e}")
        return False
