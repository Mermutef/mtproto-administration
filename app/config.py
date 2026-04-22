import os
import ast
from dotenv import load_dotenv

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

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))

XRAY_SERVER = os.getenv("XRAY_SERVER")
XRAY_PORT = os.getenv("XRAY_PORT", "443")
XRAY_PUBLIC_KEY = os.getenv("XRAY_PUBLIC_KEY", "")
XRAY_SNI = os.getenv("XRAY_SNI")
XRAY_SID = os.getenv("XRAY_SID", "")
XRAY_SPX = os.getenv("XRAY_SPX", "/")
XRAY_FLOW = os.getenv("XRAY_FLOW", "xtls-rprx-vision")
XRAY_FINGERPRINT = os.getenv("XRAY_FINGERPRINT", "chrome")
XRAY_REMARK = os.getenv("XRAY_REMARK", "Xray")
XRAY_INBOUND_ID = int(os.getenv("XRAY_INBOUND_ID", "1"))


def generate_xray_link(uuid_str: str) -> str:
    """Формирует VLESS-ссылку для подключения к Xray."""
    base = (f"vless://{uuid_str}@{XRAY_SERVER}:{XRAY_PORT}"
            f"?type=tcp&encryption=none&security=reality"
            f"&pbk={XRAY_PUBLIC_KEY}&fp={XRAY_FINGERPRINT}"
            f"&sni={XRAY_SNI}&sid={XRAY_SID}&spx={XRAY_SPX}&flow={XRAY_FLOW}")
    return f"{base}#{XRAY_REMARK}"
