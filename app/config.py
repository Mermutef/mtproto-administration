import os
import ast
from dotenv import load_dotenv


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, str(default)).strip().lower()
    return val in ("1", "true", "yes", "y")


def get_active_protocols():
    active = []
    if MTP_ENABLED:
        active.append("mtproto")
    if XRAY_ENABLED:
        active.append("xray")
    if HYSTERIA2_ENABLED:
        active.append("hysteria2")
    return active


load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))
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

XRAY_INBOUND_ID = int(os.getenv("XRAY_INBOUND_ID", "1"))
XRAY_SUB_URL_BASE = os.getenv("XRAY_SUB_URL_BASE", f"{XUI_BASE_URL}/sub/")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))

MTP_ENABLED = _env_bool("MTP_ENABLED", True)
XRAY_ENABLED = _env_bool("XRAY_ENABLED", False) and XRAY_INBOUND_ID > 0
HYSTERIA2_ENABLED = _env_bool("HYSTERIA2_ENABLED", False)
