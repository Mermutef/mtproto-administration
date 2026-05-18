import sqlite3
import asyncio
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import app.db as db
import app.proxy_manager as proxy_manager
from app.config import ADMIN_GROUP_ID, ADMIN_IDS, DB_PATH, XRAY_SUB_URL_BASE, XRAY_INBOUND_ID, get_active_protocols
from app.db import get_user_active_keys
from app.utils import escape_html
from app.locales.ru import MESSAGES
from app.services.key_service import create_mtproto_key, create_xray_key
from app.services.broadcast_service import get_user_ids_by_protocol
from app.services.key_service import get_or_update_sub_id, get_xui_client


async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return
    protocols_str = ", ".join(p.upper() for p in get_active_protocols())
    await update.message.reply_text(MESSAGES["admin_start"].format(protocols=protocols_str), parse_mode="HTML")


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

    buttons = []
    active = get_active_protocols()
    if "mtproto" in active:
        buttons.append([InlineKeyboardButton("🛡️ MTProto", callback_data=f"add_mtproto_{arg}")])
    if "xray" in active:
        buttons.append([InlineKeyboardButton("🌐 Xray", callback_data=f"add_xray_{arg}")])
    if "hysteria2" in active:
        buttons.append([InlineKeyboardButton("⚡ Hysteria2", callback_data=f"add_hysteria2_{arg}")])

    if not buttons:
        await update.message.reply_text(MESSAGES["no_available_protocols"])
        return

    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        MESSAGES["adduser_choose_protocol"].format(user=escape_html(arg)),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def process_adduser_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, arg: str, protocol: str):
    if protocol == "hysteria2":
        await update.message.reply_text(MESSAGES["hysteria2_not_supported"])
        return

    if arg.startswith('@'):
        username = arg.lstrip('@')
        try:
            chat = await context.bot.get_chat(f"@{username}")
            user_id = chat.id
        except:
            await update.message.reply_text(MESSAGES["user_not_found"].format(username=username))
            return

        if protocol == "mtproto":
            existing = db.get_user_by_telegram_id(user_id)
            if existing:
                await update.message.reply_text(
                    MESSAGES["user_already_has_key"].format(tg_username=username, username=escape_html(existing)),
                    parse_mode="HTML"
                )
                return
            success, (proxy_username, link), error = create_mtproto_key(user_id, username)
            if success:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=MESSAGES["mtp_key_granted"].format(username=escape_html(proxy_username), link=link),
                    parse_mode="HTML"
                )
                await update.message.reply_text(MESSAGES["mtp_key_created_sent"].format(username=username))
            else:
                await update.message.reply_text(MESSAGES["key_created_error"].format(error=error))

        elif protocol == "xray":
            keys = db.get_user_active_keys(user_id, 'xray')
            if keys:
                await update.message.reply_text(MESSAGES["xray_already_has_key"].format(username=username))
                return
            success, (email, subscribe_url), error = create_xray_key(user_id, username)
            if success:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=MESSAGES["xray_key_granted"].format(email=escape_html(email), subscribe_url=subscribe_url),
                    parse_mode="HTML"
                )
                await update.message.reply_text(MESSAGES["xray_key_created_sent"].format(username=username))
            else:
                await update.message.reply_text(MESSAGES["key_created_error"].format(error=error))

    else:
        proxy_username = arg.strip()
        if not proxy_username:
            await update.message.reply_text(MESSAGES["empty_username"])
            return

        if protocol == "mtproto":
            if proxy_username in proxy_manager.load_users():
                await update.message.reply_text(MESSAGES["mtproto_user_already_exists"].format(username=proxy_username))
                return
            success, link = proxy_manager.create_user(proxy_username, telegram_id="web")
            if success:
                await update.message.reply_text(
                    MESSAGES["mtproto_user_created"].format(username=proxy_username, link=link))
            else:
                await update.message.reply_text(MESSAGES["key_created_error"].format(error=link))

        elif protocol == "xray":
            success, (email, subscribe_url), error = create_xray_key("web", proxy_username)
            if success:
                await update.message.reply_text(
                    MESSAGES["xray_client_added"].format(email=email, subscribe_url=subscribe_url))
            else:
                await update.message.reply_text(MESSAGES["key_created_error"].format(error=error))


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
    c.execute("SELECT username FROM users WHERE telegram_id = ? OR username = ?", (identifier, identifier))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(MESSAGES["revoke_user_not_found"].format(identifier=identifier))
        return

    username = row[0]
    await _show_revoke_keyboard(update, username)


async def _show_revoke_keyboard(update: Update, username: str):
    """Показывает клавиатуру с активными ключами пользователя для выборочного отзыва."""
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
        if protocol == 'mtproto':
            label = MESSAGES["revoke_mtproto_btn"].format(username=username)
            callback_data = f"revoke_mtproto_{username}"
        elif protocol == 'xray':
            email_val = email if email else username
            label = MESSAGES["revoke_xray_btn"].format(email=email_val)
            callback_data = f"revoke_xray_{email_val}"
        else:
            continue  # hysteria2 пока нет
        keyboard_buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])

    keyboard_buttons.append([InlineKeyboardButton(MESSAGES["revoke_cancel_btn"], callback_data="revoke_cancel")])

    await update.message.reply_text(
        MESSAGES["revoke_select_key"].format(user=escape_html(username)),
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
        parse_mode="HTML"
    )


async def _revoke_key_by_protocol(username: str, protocol: str, update_or_query, context, email: str = None):
    if protocol == 'mtproto':
        if proxy_manager.delete_user(username):
            await update_or_query.edit_message_text(
                MESSAGES["revoke_mtproto_success"].format(username=escape_html(username)),
                parse_mode="HTML"
            )
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            conn.close()
            if row and row[0] not in ('unknown', 'web', '—'):
                try:
                    await context.bot.send_message(chat_id=int(row[0]), text=MESSAGES["key_revoked_notification"])
                except:
                    pass
        else:
            await update_or_query.edit_message_text(MESSAGES["revoke_error"])

    elif protocol == 'xray':
        xui = get_xui_client()
        if not xui:
            await update_or_query.edit_message_text(MESSAGES["xui_unavailable"])
            return
        try:
            email_to_delete = email if email else username
            xui.remove_client(XRAY_INBOUND_ID, email_to_delete)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "UPDATE keys SET status = 'revoked' WHERE user_id = (SELECT id FROM users WHERE username = ?) AND protocol = 'xray' AND status = 'active'",
                (username,))
            conn.commit()
            conn.close()
            await update_or_query.edit_message_text(
                MESSAGES["revoke_xray_success"].format(email=escape_html(email_to_delete)),
                parse_mode="HTML"
            )
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            conn.close()
            if row and row[0] not in ('unknown', 'web', '—'):
                try:
                    await context.bot.send_message(chat_id=int(row[0]), text=MESSAGES["key_revoked_notification"])
                except:
                    pass
        except Exception as e:
            await update_or_query.edit_message_text(MESSAGES["revoke_error"] + f": {e}")


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
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
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
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return

    if not context.args:
        await update.message.reply_text(MESSAGES["resend_keys_usage"])
        return

    filter_protocol = context.args[0].lower() if context.args else "all"
    allowed = ["all"] + get_active_protocols()
    if filter_protocol not in allowed:
        await update.message.reply_text(MESSAGES[f"{filter_protocol}_not_supported"])
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
            text = MESSAGES["mtp_key_granted"].format(username=escape_html(username), link=link)
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            return True
        elif protocol == "xray":
            email = key_data.get("email")
            if not email:
                return False
            sub_id = key_data.get("sub_id")
            if not sub_id:
                sub_id = get_or_update_sub_id(email)
            subscribe_url = f"{XRAY_SUB_URL_BASE}{sub_id}" if sub_id else ""
            text = MESSAGES["xray_key_granted"].format(email=escape_html(email), subscribe_url=subscribe_url)
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            return True
        else:
            return False
    except Exception as e:
        print(f"Ошибка отправки ключа {protocol} пользователю {chat_id}: {e}")
        return False
