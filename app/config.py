"""Application configuration loaded from environment variables.

This module reads configuration from a .env file using python-dotenv.
All settings are exposed as module-level constants for easy import.

Attributes:
    TOKEN: Telegram bot API token.
    ADMIN_GROUP_ID: Telegram group ID for admin commands.
    ADMIN_IDS: List of allowed admin user IDs.
    CONFIG_PATH: Path to MTProto proxy configuration file.
    CONTAINER_NAME: Docker container name for MTProto proxy.
    DOMAIN: Domain used for proxy links.
    PORT: External proxy port.
    DOCKER_PORT: Internal Docker port mapping.
    SERVER: Server IP or domain for proxy links.
    DB_PATH: Path to the SQLite database file.
    XUI_BASE_URL: Base URL for 3x-ui panel API.
    XUI_USERNAME: Username for 3x-ui authentication (ignored if ``XUI_API_TOKEN`` is set).
    XUI_PASSWORD: Password for 3x-ui authentication (ignored if ``XUI_API_TOKEN`` is set).
    XUI_API_TOKEN: Optional API token for 3x-ui 3.x+ (bypasses login/password).
    XRAY_INBOUND_ID: 3x-ui inbound ID for Xray clients.
    XUI_SUB_URL_BASE: Base URL for 3x-ui subscription links.
    ADMIN_PASSWORD: Password for web admin panel Basic Auth.
    FLASK_PORT: Port for the Flask web server.
    MTP_ENABLED: Whether MTProto proxy is enabled.
    XRAY_ENABLED: Whether Xray (3x-ui) is enabled.
    HYSTERIA2_ENABLED: Whether Hysteria2 is enabled.
    USERS_PER_PAGE: Number of users per paginated page.
"""

import os
import ast
from dotenv import load_dotenv


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse an environment variable as a boolean.

    Args:
        name: The environment variable name.
        default: Default value if the variable is not set.

    Returns:
        True if the value is '1', 'true', 'yes', or 'y'; False otherwise.
    """
    val = os.getenv(name, str(default)).strip().lower()
    return val in ("1", "true", "yes", "y")


def get_active_protocols():
    """Return a list of currently enabled protocol names.

    Returns:
        A list of strings, e.g. ['mtproto', 'xray', 'hysteria2'].
        Only protocols whose corresponding *_ENABLED flag is True
        are included.
    """
    active = []
    if MTP_ENABLED:
        active.append("mtproto")
    if XRAY_ENABLED:
        active.append("xray")
    if TROJAN_ENABLED:
        active.append("trojan")
    if HYSTERIA2_ENABLED:
        active.append("hysteria2")
    return active


load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN environment variable is required")

ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID")
if not ADMIN_GROUP_ID:
    raise ValueError("ADMIN_GROUP_ID environment variable is required")
ADMIN_GROUP_ID = int(ADMIN_GROUP_ID)

ADMIN_IDS = ast.literal_eval(os.getenv("ADMIN_IDS", "[]"))

CONFIG_PATH = os.getenv("CONFIG_PATH", "mtprotoproxy/config.py")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "mtproto-proxy")

DOMAIN = os.getenv("DOMAIN", "ya.ru")
PORT = int(os.getenv("PORT", 443))
DOCKER_PORT = int(os.getenv("DOCKER_PORT", 4443))
SERVER = os.getenv("SERVER")
DB_PATH = os.getenv("DB_PATH", "mtproto_bot.db")

XUI_BASE_URL = os.getenv("XUI_BASE_URL", "https://mysite.ru")
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD = os.getenv("XUI_PASSWORD")
XUI_API_TOKEN = os.getenv("XUI_API_TOKEN")
XUI_SUB_URL_BASE = os.getenv("XUI_SUB_URL_BASE", f"{XUI_BASE_URL}/sub/")

XRAY_INBOUND_ID = int(os.getenv("XRAY_INBOUND_ID", "1"))

# All 3x-ui protocols share the same subscription system — one sub_id
# covers all inbounds the client is attached to.
TROJAN_INBOUND_ID = int(os.getenv("TROJAN_INBOUND_ID", "0"))
HYSTERIA2_INBOUND_ID = int(os.getenv("HYSTERIA2_INBOUND_ID", "0"))

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))

MTP_ENABLED = _env_bool("MTP_ENABLED", True)
XRAY_ENABLED = _env_bool("XRAY_ENABLED", False) and XRAY_INBOUND_ID > 0
TROJAN_ENABLED = _env_bool("TROJAN_ENABLED", False) and TROJAN_INBOUND_ID > 0
HYSTERIA2_ENABLED = _env_bool("HYSTERIA2_ENABLED", False) and HYSTERIA2_INBOUND_ID > 0

USERS_PER_PAGE = int(os.getenv("USERS_PER_PAGE", 10))
