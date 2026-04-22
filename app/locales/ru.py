MESSAGES = {
    "start": (
        "🚀 <b>VPN Bot</b>\n\n"
        "Этот бот выдаёт ключи для доступа к прокси и VPN.\n\n"
        "<b>Команды:</b>\n"
        "/request — подать заявку на получение ключа\n"
        "/status — проверить статус последней заявки\n"
        "/cancel — отменить текущую заявку\n\n"
        "После одобрения администратором ключ придёт в этот чат."
    ),
    "already_has_key": "⚠️ У вас уже есть активный ключ для {protocol}.\nЕсли вы забыли ссылку, обратитесь к администратору.",
    "already_has_keys": "⚠️ У вас уже есть активные ключи для {protocol}:",
    "pending_request_exists": "⏳ У вас уже есть активная заявка #{req_id}. Ожидайте решения администратора.",
    "request_created": "✅ Заявка #{req_id} создана! Администратор рассмотрит её в ближайшее время.",
    "admin_new_request": (
        "🆕 <b>Новая заявка на ключ {protocol}!</b>\n"
        "От: {user_name} (ID: <code>{user_id}</code>)\n"
        "Заявка #{req_id}"
    ),
    "no_requests": "У вас нет ни одной заявки. Используйте /request, чтобы создать.",
    "last_request_status": (
        "📋 <b>Ваша последняя заявка</b>\n"
        "Номер: #{req_id}\n"
        "Статус: {status_text}\n"
        "Создана: {created}"
    ),
    "status_pending": "⏳ Ожидает рассмотрения",
    "status_approved": "✅ Одобрена (ключ уже должен был прийти)",
    "status_rejected": "❌ Отклонена",
    "status_revoked": "🚫 Отозвана",
    "no_pending_requests": "У вас нет ожидающих заявок.",
    "request_cancelled": "Заявка #{req_id} отменена.",
    "user_cancelled_request": "ℹ️ Пользователь {user_id} отменил заявку #{req_id}.",
    "not_in_private": "Пожалуйста, пишите мне в личные сообщения.",
    "unknown_command": "❓ Неизвестная команда. Используйте /start",
    "admin_start": (
        "👑 <b>Административная панель</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/users — список пользователей с кнопками отзыва\n"
        "/adduser @username — выдать ключ пользователю (MTProto)\n"
        "/revoke @username — отозвать ключ\n"
        "/sendto @username — переслать сообщение конкретному пользователю\n"
        "/broadcast — рассылка (ответ на сообщение)\n\n"
        "Заявки приходят с кнопками Одобрить/Отклонить."
    ),
    "adduser_usage": "❌ Использование: /adduser @username или /adduser логин",
    "user_not_found": "❌ Не найден @{username}. Убедитесь, что пользователь начал диалог с ботом.",
    "user_already_has_key": "⚠️ У @{tg_username} уже есть ключ: <code>{username}</code>",
    "key_created_sent": "✅ Ключ для @{username} создан и отправлен.",
    "key_created_error": "❌ Ошибка при создании ключа: {error}",
    "admin_key_granted": (
        "✅ Администратор выдал вам ключ!\n"
        "Логин: <code>{username}</code>\n"
        "Ссылка для подключения (нажмите, чтобы скопировать):\n"
        "<code>{link}</code>"
    ),
    "users_list_empty": "📭 Список пользователей пуст.",
    "users_list_header": "<b>📋 Список пользователей:</b>\n",
    "users_list_item": "• <code>{username}</code> — {tg_info} (с {created})",
    "users_list_footer": "\n\n<i>Чтобы отозвать ключ, используйте команду:</i>\n<code>/revoke u_name</code>\nНапример: <code>/revoke u_111111111_000000</code>",
    "revoke_usage": "❌ Использование: /revoke @username",
    "revoke_user_not_found": "❌ Пользователь @{identifier} не найден.",
    "revoke_success": "✅ Ключ для @{identifier} отозван.",
    "revoke_error": "❌ Ошибка при отзыве.",
    "key_revoked_notification": "⚠️ Ваш ключ отозван администратором.",
    "approve_request_success": "✅ Заявка #{req_id} одобрена. Ключ отправлен пользователю.",
    "approve_request_error": "❌ Ошибка создания ключа: {error}",
    "reject_request_success": "❌ Заявка #{req_id} отклонена.",
    "request_already_processed": "❌ Заявка уже обработана.",
    "key_revoked_callback": "✅ Ключ <code>{username}</code> отозван.",
    "key_revoked_callback_notification": "⚠️ Ваш ключ <code>{username}</code> отозван администратором.",
    "button_only_in_group": "⛔ Эта кнопка работает только в админской группе.",
    "no_permission": "⛔ У вас нет прав для обработки заявок.",
    "multiple_pending_requests": "У вас несколько активных заявок. Выберите, какую отменить:",
    "cancel_selection_cancelled": "❎ Отмена отмены.",
    "cancel_request_not_found": "❌ Эта заявка уже обработана или не существует.",
    "cancel_request_invalid": "❓ Неверный номер заявки.",
}
