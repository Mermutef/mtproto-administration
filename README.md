# OurAdmin

[🇷🇺 RU](README-ru.md)

A modular VPN administration system with a **Telegram bot** for user-facing interactions and a **Flask web panel** for admin management. Supports multiple VPN protocols through a pluggable service architecture.

## Features

- **Multi-protocol support**: MTProto Proxy (Telegram), Xray (VLESS Reality) via 3x-ui, Hysteria2 (placeholder)
- **Telegram bot**: Users request keys, admins approve/revoke via inline buttons
- **Web admin panel**: Full CRUD management with Bootstrap Table UI
- **Modular architecture**: Easy to add new VPN protocols via ``BaseVpnService``
- **Broadcast system**: Send messages to users by protocol filter
- **Key redistribution**: Resend lost keys to users
- **Documentation**: Auto-generated API docs at [docs/](docs/index.html)

## Project Structure

```
OurAdmin/
├── bot.py                      # Telegram bot entry point
├── web.py                      # Flask web server entry point
├── app/
│   ├── __init__.py
│   ├── config.py               # Environment-based configuration
│   ├── db.py                   # SQLite database layer
│   ├── utils.py                # HTML escaping helper
│   ├── x_ui_manager.py         # 3x-ui panel API client + get_xui_client()
│   ├── locales/
│   │   └── ru.py               # Russian message strings
│   ├── handlers/               # Telegram bot command/callback handlers
│   │   ├── __init__.py
│   │   ├── user_handlers.py
│   │   ├── admin_handlers.py
│   │   ├── callback_handlers.py
│   │   ├── admin_callbacks.py
│   │   └── private_callbacks.py
│   ├── services/               # Pluggable VPN protocol services
│   │   ├── base.py             # Abstract base class (BaseVpnService)
│   │   ├── registry.py         # Central service registry
│   │   ├── broadcast_service.py# Broadcast helpers
│   │   ├── mtproto/
│   │   │   ├── __init__.py     # MtprotoService implementation
│   │   │   └── config_manager.py # MTProto proxy config management
│   │   ├── xray/
│   │   │   └── __init__.py     # XrayService (3x-ui API)
│   │   └── hysteria2/
│   │       └── __init__.py     # Hysteria2Service (placeholder)
│   ├── web/                    # Flask Blueprints for each protocol
│   │   ├── __init__.py         # Blueprint factory & registration
│   │   ├── mtproto.py
│   │   ├── xray.py
│   │   └── hysteria2.py
│   ├── static/                 # Frontend assets (CSS, JS, fonts)
│   └── templates/              # Jinja2 HTML templates
├── docs/                       # Auto-generated API documentation
└── .env.example                # Environment variable template
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for MTProto proxy)
- 3x-ui panel (for Xray, optional)
- Telegram bot token from [@BotFather](https://t.me/botfather)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd OurAdmin

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # edit your settings
```

### Running

**Flask web panel** (port configured via `FLASK_PORT`):
```bash
python web.py
```

**Telegram bot**:
```bash
python bot.py
```

## Configuration

All configuration is done via environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `TOKEN` | Telegram bot token | — |
| `ADMIN_GROUP_ID` | Telegram group ID for admin chat | — |
| `ADMIN_IDS` | List of allowed admin user IDs (JSON) | `[]` |
| `CONFIG_PATH` | MTProto proxy config file path | `mtprotoproxy/config.py` |
| `CONTAINER_NAME` | MTProto Docker container name | `mtproto-proxy` |
| `DOMAIN` | Domain for proxy links | `ya.ru` |
| `PORT` | External proxy port | `443` |
| `DOCKER_PORT` | Internal Docker port | `4443` |
| `SERVER` | Server IP/hostname for proxy links | — |
| `DB_PATH` | SQLite database path | `mtproto_bot.db` |
| `ADMIN_PASSWORD` | Web panel Basic Auth password | `admin` |
| `FLASK_PORT` | Flask server port | `5000` |
| `MTP_ENABLED` | Enable MTProto proxy | `True` |
| `XRAY_ENABLED` | Enable Xray via 3x-ui | `False` |
| `HYSTERIA2_ENABLED` | Enable Hysteria2 | `False` |
| `XUI_BASE_URL` | 3x-ui panel base URL | `https://mysite.ru` |
| `XUI_USERNAME` | 3x-ui admin username | `admin` |
| `XUI_PASSWORD` | 3x-ui admin password | — |
| `XRAY_INBOUND_ID` | 3x-ui inbound ID | `1` |

## Adding a New VPN Protocol

1. Create a package `app/services/newproto/__init__.py` with a class inheriting from [`BaseVpnService`](app/services/base.py)
2. Implement the required methods: `create_user`, `delete_user`, `get_users`
3. Optionally create `app/web/newproto.py` with a Flask Blueprint
4. Register the singleton in [`registry.py`](app/services/registry.py)
5. Add localised messages in [`app/locales/ru.py`](app/locales/ru.py)
6. The service automatically appears in the bot and web panel when enabled

## Architecture

### Service Pattern

All VPN protocol implementations follow the same interface defined in [`BaseVpnService`](app/services/base.py):

```
BaseVpnService (ABC)
├── MtprotoService (app/services/mtproto/)
├── XrayService (app/services/xray/)
└── Hysteria2Service (app/services/hysteria2/)
```

Services are registered in [`ServiceRegistry`](app/services/registry.py) and accessed from both bot handlers and web endpoints through `registry.get(protocol)`.

### Web Blueprint Registration

Each enabled service gets a Flask Blueprint registered automatically. If a dedicated module `app/web/{protocol}.py` exists with a `bp` variable, it is used; otherwise, a generic CRUD Blueprint is generated.

## Documentation

Auto-generated API documentation is available in the [docs/](docs/index.html) directory. To regenerate:

```bash
pip install pdoc
pdoc --output-dir docs --docformat google app
```

## License

MIT
