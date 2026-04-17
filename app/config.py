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
SERVER_IP = os.getenv("SERVER_IP")
DB_PATH = os.getenv("DB_PATH", "mtproto_bot.db")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))