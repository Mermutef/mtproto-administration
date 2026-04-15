import os
import ast
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))
ADMIN_IDS = ast.literal_eval(os.getenv("ADMIN_IDS", "[]"))

MTPROXYMAX_SERVICE = os.getenv("MTPROXYMAX_SERVICE", "mtproxymax")
SECRETS_FILE = os.getenv("SECRETS_FILE", "/opt/mtproxymax/secrets.conf")

DOMAIN = os.getenv("DOMAIN", "www.google.com")
PORT = int(os.getenv("PORT", 443))
SERVER_IP = os.getenv("SERVER_IP")
DB_PATH = os.getenv("DB_PATH", "/root/mtproto_bot.db")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))