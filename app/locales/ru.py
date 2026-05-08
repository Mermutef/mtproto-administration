MESSAGES = {
    "start": (
        "🚀 <b>VPN Bot</b>\n\n"
        "Этот бот выдаёт ключи для доступа к прокси и VPN.\n\n"
        "<b>Доступные команды:</b>\n"
        "/request — подать заявку на получение ключа\n"
        "/status — проверить статус последней заявки\n"
        "/cancel — отменить текущую заявку\n\n"
        "После одобрения администратором ключ придёт в этот чат.\n\n"
        "<i>Поддерживаемые протоколы: MTProto (прокси Telegram), Xray (VLESS Reality), "
        "Hysteria2 (скоро будет).</i>"
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
    "status_approved": "✅ Одобрена (ключ уже должен быть у вас)",
    "status_rejected": "❌ Отклонена",
    "status_revoked": "🚫 Отозвана",
    "no_pending_requests": "У вас нет ожидающих заявок.",
    "request_cancelled": "Заявка #{req_id} отменена.",
    "user_cancelled_request": "ℹ️ Пользователь {user_id} отменил заявку #{req_id}.",
    "not_in_private": "Пожалуйста, пишите мне в личные сообщения.",
    "unknown_command": "❓ Неизвестная команда. Используйте /start",
    "admin_start": (
        "👑 <b>Административная панель</b>\n\n"
        "<b>Команды:</b>\n"
        "/users — список пользователей\n"
        "/adduser @username [протокол] — выдать ключ (по умолчанию MTProto)\n"
        "/revoke @username — отозвать ключ\n"
        "/sendto @username — переслать сообщение пользователю\n"
        "/broadcast [фильтр] — рассылка сообщения всем/по протоколам\n"
        "       Фильтры: all, mtproto, xray, hysteria2\n"
        "/resend_keys [фильтр] — повторно отправить существующие ключи\n\n"
        "Заявки приходят с кнопками ✅Одобрить / ❌Отклонить."
    ),
    "adduser_usage": "❌ Использование: /adduser @username [mtproto|xray|hysteria2] или /adduser логин",
    "user_not_found": "❌ Не найден @{username}. Убедитесь, что пользователь начал диалог с ботом.",
    "user_already_has_key": "⚠️ У @{tg_username} уже есть ключ: <code>{username}</code>",
    "mtp_key_created_sent": "✅ MTProto-ключ для @{username} создан и отправлен.",
    "xray_key_created_sent": "✅ Xray-ключ для @{username} создан и отправлен.",
    "key_created_error": "❌ Ошибка при создании ключа: {error}",
    "admin_key_granted": (
        "✅ Администратор выдал вам ключ MTProto!\n"
        "Логин: <code>{username}</code>\n"
        "Ссылка для подключения (нажмите): {link}\n\n"
        "<b>Инструкция:</b>\n"
        "1. Нажмите на ссылку выше — откроется системный диалог Telegram.\n"
        "2. Подтвердите подключение прокси.\n"
        "3. Прокси будет активирован автоматически.\n\n"
        "Если ссылка не открывается, добавьте прокси вручную в Настройки → Данные и диск → Прокси."
    ),
    "xray_key_granted": (
        "✅ Администратор выдал вам ключ Xray!\n"
        "Логин: <code>{email}</code>\n"
        "Ссылка на подписку: {subscribe_url}\n\n"
        "<b>Как подключиться:</b>\n"
        "1. Скачайте и установите Hiddify:\n"
        "   • Официальный сайт: https://hiddify.com\n"
        "   • AppStore: https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532\n"
        "   • Google Play: https://play.google.com/store/apps/details?id=app.hiddify.com\n"
        "2. Скопируйте ссылку на подписку выше.\n"
        "3. Откройте Hiddify, нажмите «+» в правом верхнем углу.\n"
        "4. Вставьте скопированную ссылку (кнопка «Буфер обмена») и подтвердите.\n"
        "5. После импорта выберите появившуюся конфигурацию и подключитесь.\n\n"
        "Приятного использования!\n\n"
        "P.S. Вы также можете открыть ссылку на подписку в браузере, чтобы получить ключ для других приложений."
    ),
    "users_list_empty": "📭 Список пользователей пуст.",
    "users_list_header": "<b>📋 Список пользователей:</b>\n",
    "users_list_item": "• <code>{username}</code> — {tg_info} (с {created})",
    "users_list_footer": "\n\n<i>Чтобы отозвать ключ, используйте команду:</i>\n<code>/revoke u_name</code>\nНапример: <code>/revoke u_111111111_000000</code>",
    "revoke_usage": "❌ Использование: /revoke @username",
    "revoke_user_not_found": "❌ Пользователь @{identifier} не найден.",
    "revoke_success": "✅ Ключ для @{identifier} отозван.",
    "revoke_error": "❌ Ошибка при отзыве.",
    "key_revoked_notification": "⚠️ Ваш ключ был отозван администратором.",
    "approve_request_success": "✅ Заявка #{req_id} одобрена. Ключ отправлен пользователю.",
    "approve_request_error": "❌ Ошибка создания ключа: {error}",
    "reject_request_success": "❌ Заявка #{req_id} отклонена.",
    "request_already_processed": "❌ Заявка уже обработана.",
    "key_revoked_callback": "✅ Ключ <code>{username}</code> отозван.",
    "key_revoked_callback_notification": "⚠️ Ваш ключ <code>{username}</code> был отозван администратором.",
    "button_only_in_group": "⛔ Эта кнопка работает только в админской группе.",
    "no_permission": "⛔ У вас нет прав для обработки заявок.",
    "multiple_pending_requests": "У вас несколько активных заявок. Выберите, какую отменить:",
    "cancel_selection_cancelled": "❎ Отмена отмены.",
    "cancel_request_not_found": "❌ Эта заявка уже обработана или не существует.",
    "cancel_request_invalid": "❓ Неверный номер заявки.",
    "resend_keys_usage": "ℹ️ Использование: /resend_keys [all|mtproto|xray|hysteria2]",
    "resend_keys_started": "⏳ Повторная рассылка ключей ({filter_protocol}) начата. Получателей: {total}...",
    "resend_keys_done": "✅ Повторная рассылка завершена.\nУспешно: {success}\nОшибок: {failed}",
    "resend_keys_no_users": "📭 Нет пользователей с активными ключами.",
    "resend_keys_hysteria2_not_supported": "⚡ Hysteria2 пока не поддерживается.",
}
