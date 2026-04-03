from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import TOKEN, ADMIN_GROUP_ID
import db
import proxy_manager
from handlers import (
    start, request_key, status_command, cancel_command,
    start_admin, adduser_command, users_command, revoke_command,
    button_callback, unknown
)


def main():
    db.init_db()
    # Синхронизируем БД с текущими пользователями из конфига прокси
    proxy_manager.sync_all_users()

    app = Application.builder().token(TOKEN).build()

    # Пользовательские команды (только ЛС)
    app.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("request", request_key, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("status", status_command, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("cancel", cancel_command, filters=filters.ChatType.PRIVATE))

    # Административные команды (только группа)
    app.add_handler(CommandHandler("start", start_admin, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("adduser", adduser_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("users", users_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))
    app.add_handler(CommandHandler("revoke", revoke_command, filters=filters.Chat(chat_id=ADMIN_GROUP_ID)))

    # Callback кнопок
    app.add_handler(CallbackQueryHandler(button_callback))

    # Неизвестные команды
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
