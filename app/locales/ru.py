MESSAGES = {
    # Пользовательские
    "start": (
        "🚀 <b>VPN Bot</b>\n\n"
        "Этот бот выдаёт ключи для доступа к прокси и VPN.\n\n"
        "<b>Команды:</b>\n"
        "/request — подать заявку на получение ключа\n"
        "/mykeys — посмотреть свои ключи\n"
        "/status — проверить статус последней заявки\n"
        "/cancel — отменить текущую заявку\n\n"
        "После одобрения администратором ключ придёт в этот чат.\n\n"
        "<i>Поддерживаемые протоколы: {protocols}</i>"
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
    "choose_protocol": "Выберите протокол для получения ключа:",
    "no_permission": "⛔ У вас нет прав администратора.",

    # Административные
    "admin_start": (
        "👑 <b>Административная панель</b>\n\n"
        "<b>Команды:</b>\n"
        "/users — список пользователей\n"
        "/adduser @username или логин — выдать ключ\n"
        "/revoke @username — отозвать ключ\n"
        "/sendto @username — переслать сообщение пользователю\n"
        "/broadcast [all|mtproto|xray|hysteria2] — рассылка\n"
        "/resend_keys [all|mtproto|xray|hysteria2] — повторная рассылка ключей\n"
        "/info @username — информация о пользователе\n\n"
        "<i>Доступные протоколы: {protocols}</i>"
    ),
    "adduser_usage": "❌ Использование: /adduser @username [mtproto|xray|hysteria2] или /adduser логин",
    "adduser_choose_protocol": "Выберите протокол для выдачи ключа пользователю <code>{user}</code>:",
    "mtproto_not_supported": "🛡️ MTProto пока не поддерживается.",
    "xray_not_supported": "🌐 Xray пока не поддерживается.",
    "trojan_not_supported": "🐴 Trojan пока не поддерживается.",
    "hysteria2_not_supported": "⚡ Hysteria2 пока не поддерживается.",
    "user_not_found": "❌ Не найден @{username}. Убедитесь, что пользователь начал диалог с ботом.",
    "user_already_has_key": "⚠️ У @{tg_username} уже есть ключ: <code>{username}</code>",
    "xray_already_has_key": "⚠️ У @{username} уже есть активный ключ Xray.",
    "mtproto_user_already_exists": "❌ Логин '{username}' уже существует.",
    "mtproto_user_created": "✅ Пользователь '{username}' добавлен.\nСсылка: {link}",
    "empty_username": "❌ Логин не может быть пустым.",
    "mtp_key_created_sent": "✅ MTProto-ключ для @{username} создан и отправлен.",
    "xray_key_created_sent": "✅ Xray-ключ для @{username} создан и отправлен.",
    "trojan_key_created_sent": "✅ Trojan-ключ для @{username} создан и отправлен.",
    "key_created_error": "❌ Ошибка при создании ключа: {error}",
    "mtp_key_granted": (
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

    # Trojan
    "trojan_key_granted": (
        "✅ Администратор выдал вам ключ Trojan!\n"
        "Логин: <code>{email}</code>\n"
        "Ссылка на подписку: {subscribe_url}\n\n"
        "<b>Как подключиться:</b>\n"
        "1. Скачайте и установите Hiddify или любой другой клиент с поддержкой подписок.\n"
        "2. Скопируйте ссылку на подписку выше.\n"
        "3. Откройте приложение, вставьте ссылку и подключитесь."
    ),
    "trojan_client_added": "✅ Trojan-клиент '{email}' добавлен.\nСсылка на подписку: {subscribe_url}",

    # Hysteria2
    "hysteria2_key_granted": (
        "✅ Администратор выдал вам ключ Hysteria2!\n"
        "Логин: <code>{email}</code>\n"
        "Ссылка на подписку: {subscribe_url}\n\n"
        "<b>Как подключиться:</b>\n"
        "1. Скачайте и установите Hiddify или любой другой клиент с поддержкой подписок.\n"
        "2. Скопируйте ссылку на подписку выше.\n"
        "3. Откройте приложение, вставьте ссылку и подключитесь."
    ),
    "hysteria2_key_created_sent": "✅ Hysteria2-ключ для @{username} создан и отправлен.",
    "hysteria2_client_added": "✅ Hysteria2-клиент '{email}' добавлен.\nСсылка на подписку: {subscribe_url}",

    # Веб-API сообщения
    "web_login_empty": "Логин не может быть пустым",
    "web_email_empty": "Email не может быть пустым",
    "web_name_empty": "Имя не может быть пустым",
    "web_invalid_identifier": "Недопустимый идентификатор: '{identifier}'",
    "web_user_added": "Пользователь '{username}' добавлен",
    "web_client_added": "Клиент '{email}' добавлен",
    "web_identifier_required": "Идентификатор не указан",
    "web_user_deleted": "Пользователь '{username}' удалён",
    "web_client_deleted": "Клиент '{email}' удалён",
    "web_user_not_found": "Пользователь '{username}' не найден",
    "web_client_not_found": "Клиент '{email}' не найден",
    "web_old_new_required": "Старое и новое имя обязательны",
    "web_old_new_email_required": "Старый и новый email обязательны",

    # Список пользователей
    "users_choose_protocol": "Выберите протокол для просмотра пользователей:",
    "users_page": "👥 Пользователи ({protocol}) – страница {page}/{total_pages}",
    "users_no_users": "📭 Нет пользователей с активными ключами.",
    "pagination_prev": "⬅️ Назад",
    "pagination_next": "➡️ Вперед",

    # Информация о пользователе
    "info_usage": "ℹ️ Использование: /info @username",
    "user_info_profile": (
        "👤 <b>{username}</b>\n"
        "Telegram ID: <code>{telegram_id}</code>\n"
        "Создан: {created}\n\n"
        "<b>Ключи:</b>"
    ),
    "user_info_no_keys": "🔑 Нет ключей.",

    "user_info_key": (
        "\n<b>{protocol}</b>\n"
        "Логин: <code>{login}</code>\n"
        "Ссылка: {link}\n"
        "Статус: {status}\n"
        "Создан: {created}"
    ),

    # Мои ключи
    "my_keys_header": "🔑 Ваши активные ключи:\n\n",
    "my_keys_no_keys": "У вас нет активных ключей.",
    "my_keys_key": (
        "<b>{protocol}</b>\n"
        "Логин: <code>{login}</code>\n"
        "Ссылка: {link}\n\n"
    ),

    # Остальное
    "users_list_empty": "📭 Список пользователей пуст.",
    "users_list_header": "<b>📋 Список пользователей:</b>\n",
    "users_list_item": "• <code>{username}</code> — {tg_info} (с {created})",
    "users_list_footer": "\n\n<i>Чтобы отозвать ключ, используйте команду:</i>\n<code>/revoke u_name</code>\nНапример: <code>/revoke someuser_12345678</code>",
    "revoke_usage": "❌ Использование: /revoke @username",
    "revoke_user_not_found": "❌ Пользователь @{identifier} не найден.",
    "revoke_success": "✅ Ключ для @{identifier} отозван.",
    "revoke_error": "❌ Ошибка при отзыве.",
    "revoke_select_key": "Выберите ключ для отзыва у пользователя <code>{user}</code>:",
    "revoke_mtproto_btn": "🛡️ MTProto: {username}",
    "revoke_xray_btn": "🌐 Xray: {email}",
    "revoke_cancel_btn": "« Отмена",
    "revoke_no_active_keys": "❌ У пользователя {identifier} нет активных ключей.",
    "revoke_mtproto_success": "✅ MTProto-ключ <code>{username}</code> отозван.",
    "revoke_xray_success": "✅ Xray-ключ <code>{email}</code> отозван.",
    "revoke_canceled": "❎ Отзыв отменён.",
    "key_revoked_notification": "⚠️ Ваш ключ был отозван администратором.",
    "approve_request_success": "✅ Заявка #{req_id} одобрена. Ключ отправлен пользователю.",
    "approve_request_error": "❌ Ошибка создания ключа: {error}",
    "reject_request_success": "❌ Заявка #{req_id} отклонена.",
    "request_already_processed": "❌ Заявка уже обработана.",
    "request_rejected_notification": "❌ Ваша заявка #{req_id} отклонена.",
    "key_revoked_callback": "✅ Ключ <code>{username}</code> отозван.",
    "key_revoked_callback_notification": "⚠️ Ваш ключ <code>{username}</code> был отозван администратором.",
    "button_only_in_group": "⛔ Эта кнопка работает только в админской группе.",
    "multiple_pending_requests": "У вас несколько активных заявок. Выберите, какую отменить:",
    "cancel_selection_cancelled": "❎ Отмена отмены.",
    "cancel_request_not_found": "❌ Эта заявка уже обработана или не существует.",
    "cancel_request_invalid": "❓ Неверный номер заявки.",
    "unknown_admin_command": "❓ Неизвестная команда. Доступно: /start, /adduser, /users, /revoke",

    # sendto
    "sendto_usage": "ℹ️ Использование: /sendto @username (в ответ на сообщение)",
    "sendto_reply_prompt": "ℹ️ Ответьте на сообщение, которое хотите переслать.",
    "sendto_user_not_found": "❌ Пользователь '{target}' не найден.",
    "sendto_no_telegram_id": "❌ У пользователя '{target}' нет Telegram ID.",
    "sendto_success": "✅ Сообщение отправлено пользователю '{target}'.",
    "sendto_error": "❌ Не удалось отправить сообщение пользователю '{target}'.",

    # broadcast
    "broadcast_usage": "ℹ️ Ответьте на сообщение командой /broadcast [all|mtproto|xray|hysteria2]",
    "invalid_broadcast_filter": "❌ Доступны только all, mtproto, xray или hysteria2",
    "broadcast_no_users": "📭 Нет пользователей для рассылки.",
    "broadcast_started": "⏳ Рассылка начата ({filter_protocol}). Получателей: {total}...",
    "broadcast_done": "✅ Рассылка завершена ({filter_protocol}).\nУспешно: {success}\nОшибок: {failed}",

    # resend_keys
    "resend_keys_usage": "ℹ️ Использование: /resend_keys [all|mtproto|xray|hysteria2]",
    "resend_keys_started": "⏳ Повторная рассылка ключей ({filter_protocol}) начата. Получателей: {total}...",
    "resend_keys_done": "✅ Повторная рассылка завершена.\nУспешно: {success}\nОшибок: {failed}",
    "resend_keys_no_users": "📭 Нет пользователей с активными ключами.",

    # Системные
    "xui_unavailable": "❌ Нет подключения к 3x-ui",
    "no_available_protocols": "❌ Нет доступных протоколов.",
    "invalid_callback_format": "❌ Неверный формат команды.",
    "xray_client_added": "✅ Xray-клиент '{email}' добавлен.\nСсылка на подписку: {subscribe_url}",
}
