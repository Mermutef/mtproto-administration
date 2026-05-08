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

XRAY_INBOUND_ID = int(os.getenv("XRAY_INBOUND_ID", "1"))
XRAY_SUB_URL_BASE = os.getenv("XRAY_SUB_URL_BASE", f"{XUI_BASE_URL}/sub/")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
