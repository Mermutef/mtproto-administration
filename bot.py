"""Telegram bot entry point.

Initialises the database, synchronises MTProto proxy users,
registers command and callback handlers, and starts polling.
"""

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from app.config import TOKEN, ADMIN_GROUP_ID
import app.db as db
from app.services.mtproto import mtproto_service
from app.handlers import (
    start, request_key, status_command, cancel_command,
    start_admin, adduser_command, users_command, revoke_command,
    button_callback, unknown, mykeys_command
)
from app.handlers.admin_handlers import broadcast_command, sendto_command, cache_message_handler, resend_keys_command, \
    info_command


def main():
    """Initialise and start the Telegram bot."""
    db.init_db()
    db.migrate_v1_to_v2()
    mtproto_service.sync_all_users()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("request", request_key, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("status", status_command, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("cancel", cancel_command, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("mykeys", mykeys_command, filters=filters.ChatType.PRIVATE))

    app.add_handler(CommandHandler("start", start_admin, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("adduser", adduser_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("users", users_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("revoke", revoke_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("broadcast", broadcast_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("sendto", sendto_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("resend_keys", resend_keys_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("info", info_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))

    app.add_handler(CallbackQueryHandler(button_callback))

    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    app.add_handler(MessageHandler(filters.Chat(chat_id=ADMIN_GROUP_ID) & filters.ALL, cache_message_handler), group=0)

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
