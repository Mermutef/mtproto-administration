# OurAdmin

[🇬🇧 EN](README.md)

Модульная система администрирования VPN с **Telegram-ботом** для взаимодействия с пользователями и **Flask веб-панелью** для управления администратором. Поддерживает несколько VPN-протоколов через подключаемую архитектуру сервисов.

## Возможности

- **Мультипротокольность**: MTProto Proxy (Telegram), Xray (VLESS Reality) через 3x-ui, Hysteria2 (заглушка)
- **Telegram бот**: Пользователи запрашивают ключи, администраторы одобряют/отзывают через инлайн-кнопки
- **Веб-панель администратора**: Полное CRUD-управление с Bootstrap Table UI
- **Модульная архитектура**: Легко добавлять новые VPN-протоколы через ``BaseVpnService``
- **Рассылка сообщений**: Отправка пользователям с фильтром по протоколу
- **Повторная отправка ключей**: Отправка забытых ключей пользователям
- **Документация**: Автосгенерированная API документация в [docs/](docs/index.html)

## Структура проекта

```
OurAdmin/
├── bot.py                      # Точка входа Telegram бота
├── web.py                      # Точка входа Flask веб-сервера
├── app/
│   ├── __init__.py
│   ├── config.py               # Конфигурация из переменных окружения
│   ├── db.py                   # Слой работы с SQLite
│   ├── utils.py                # Экранирование HTML
│   ├── x_ui_manager.py         # Клиент API 3x-ui + get_xui_client()
│   ├── locales/
│   │   └── ru.py               # Русские строки сообщений
│   ├── handlers/               # Обработчики команд Telegram бота
│   │   ├── __init__.py
│   │   ├── user_handlers.py
│   │   ├── admin_handlers.py
│   │   ├── callback_handlers.py
│   │   ├── admin_callbacks.py
│   │   └── private_callbacks.py
│   ├── services/               # Подключаемые VPN-сервисы
│   │   ├── base.py             # Абстрактный базовый класс (BaseVpnService)
│   │   ├── registry.py         # Центральный реестр сервисов
│   │   ├── broadcast_service.py# Вспомогательные функции рассылки
│   │   ├── mtproto/
│   │   │   ├── __init__.py     # Реализация MtprotoService
│   │   │   └── config_manager.py # Управление конфигом MTProto прокси
│   │   ├── xray/
│   │   │   └── __init__.py     # Реализация XrayService (API 3x-ui)
│   │   └── hysteria2/
│   │       └── __init__.py     # Hysteria2Service (заглушка)
│   ├── web/                    # Flask Blueprint'ы для каждого протокола
│   │   ├── __init__.py         # Фабрика Blueprint'ов и регистрация
│   │   ├── mtproto.py
│   │   ├── xray.py
│   │   └── hysteria2.py
│   ├── static/                 # Фронтенд (CSS, JS, шрифты)
│   └── templates/              # HTML шаблоны Jinja2
├── docs/                       # Автосгенерированная API документация
└── .env.example                # Шаблон переменных окружения
```

## Быстрый старт

### Требования

- Python 3.10+
- Docker (для MTProto прокси)
- Панель 3x-ui (для Xray, опционально)
- Токен Telegram бота от [@BotFather](https://t.me/botfather)

### Установка

```bash
# Клонировать репозиторий
git clone <repo-url>
cd OurAdmin

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Настроить окружение
cp .env.example .env
nano .env  # отредактировать настройки
```

### Запуск

**Flask веб-панель** (порт настраивается через `FLASK_PORT`):
```bash
python web.py
```

**Telegram бот**:
```bash
python bot.py
```

## Конфигурация

Вся конфигурация задаётся через переменные окружения (см. `.env.example`):

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| `TOKEN` | Токен Telegram бота | — |
| `ADMIN_GROUP_ID` | ID группы для админ-команд | — |
| `ADMIN_IDS` | Список ID разрешённых админов (JSON) | `[]` |
| `CONFIG_PATH` | Путь к конфигу MTProto прокси | `mtprotoproxy/config.py` |
| `CONTAINER_NAME` | Имя Docker контейнера MTProto | `mtproto-proxy` |
| `DOMAIN` | Домен для прокси-ссылок | `ya.ru` |
| `PORT` | Внешний порт прокси | `443` |
| `DOCKER_PORT` | Внутренний порт Docker | `4443` |
| `SERVER` | IP/домен сервера для ссылок | — |
| `DB_PATH` | Путь к SQLite базе данных | `mtproto_bot.db` |
| `ADMIN_PASSWORD` | Пароль для Basic Auth веб-панели | `admin` |
| `FLASK_PORT` | Порт Flask сервера | `5000` |
| `MTP_ENABLED` | Включить MTProto прокси | `True` |
| `XRAY_ENABLED` | Включить Xray через 3x-ui | `False` |
| `HYSTERIA2_ENABLED` | Включить Hysteria2 | `False` |
| `XUI_BASE_URL` | Базовый URL панели 3x-ui | `https://mysite.ru` |
| `XUI_USERNAME` | Имя пользователя 3x-ui | `admin` |
| `XUI_PASSWORD` | Пароль 3x-ui | — |
| `XRAY_INBOUND_ID` | ID входящего подключения 3x-ui | `1` |

## Добавление нового VPN-протокола

1. Создать пакет `app/services/newproto/__init__.py` с классом, наследующим [`BaseVpnService`](app/services/base.py)
2. Реализовать обязательные методы: `create_user`, `delete_user`, `get_users`
3. Опционально создать `app/web/newproto.py` с Flask Blueprint'ом
4. Зарегистрировать синглтон в [`registry.py`](app/services/registry.py)
5. Добавить локализованные сообщения в [`app/locales/ru.py`](app/locales/ru.py)
6. Сервис автоматически появится и в боте, и в веб-панели после включения

## Архитектура

### Паттерн сервисов

Все реализации VPN-протоколов следуют единому интерфейсу, описанному в [`BaseVpnService`](app/services/base.py):

```
BaseVpnService (ABC)
├── MtprotoService (app/services/mtproto/)
├── XrayService (app/services/xray/)
└── Hysteria2Service (app/services/hysteria2/)
```

Сервисы регистрируются в [`ServiceRegistry`](app/services/registry.py) и доступны из хендлеров бота и веб-эндпоинтов через `registry.get(protocol)`.

### Регистрация веб-обработчиков

Каждый включённый сервис автоматически получает зарегистрированный Flask Blueprint. Если существует модуль `app/web/{protocol}.py` с переменной `bp`, используется он; иначе генерируется generic CRUD Blueprint.

## Документация

Автосгенерированная API документация доступна в каталоге [docs/](docs/index.html). Для перегенерации:

```bash
pip install pdoc
pdoc --output-dir docs --docformat google app
```

## Лицензия

MIT
