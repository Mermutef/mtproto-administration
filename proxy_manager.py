import os
import secrets
import subprocess
import re
import time

from config import CONFIG_PATH, DOMAIN, PORT, SERVER_IP, CONTAINER_NAME
import db

TEMPLATE_HEAD = '''# MTProto Proxy configuration
PORT = {port}
MODES = {{
    "classic": False,
    "secure": False,
    "tls": True
}}
TLS_DOMAIN = "{tls_domain}"
# AD_TAG = "your_tag_from_bot"
'''


def _read_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, 'r') as f:
        content = f.read()
    match = re.search(r'USERS\s*=\s*(\{.*?\n\})', content, re.DOTALL)
    if not match:
        return {}
    try:
        users_dict = eval(match.group(1))
        return users_dict if isinstance(users_dict, dict) else {}
    except:
        return {}


def _write_config(users_dict):
    port = PORT
    tls_domain = DOMAIN
    header = TEMPLATE_HEAD.format(port=port, tls_domain=tls_domain)
    users_str = "USERS = {\n"
    for name, secret in users_dict.items():
        users_str += f'    "{name}": "{secret}",\n'
    users_str += "}\n"
    with open(CONFIG_PATH, 'w') as f:
        f.write(header + "\n" + users_str)


def load_users():
    return _read_config()


def save_users(users_dict):
    _write_config(users_dict)
    try:
        subprocess.run(
            ["docker", "exec", CONTAINER_NAME, "kill", "-USR2", "1"],
            capture_output=True,
            check=True
        )
        time.sleep(1)
    except subprocess.CalledProcessError as e:
        subprocess.run(["docker", "restart", CONTAINER_NAME], capture_output=True)


def add_user(username, secret):
    users = load_users()
    if username in users:
        return False
    users[username] = secret
    save_users(users)
    return True


def remove_user(username):
    users = load_users()
    if username not in users:
        return False
    del users[username]
    save_users(users)
    return True


def generate_unique_username(base="user"):
    users = load_users()
    while True:
        num = secrets.randbelow(1000000)
        username = f"{base}_{num}"
        if username not in users:
            return username


def get_proxy_link(secret):
    domain_hex = DOMAIN.encode().hex()
    full_secret = f"ee{secret}{domain_hex}"
    return f"tg://proxy?server={SERVER_IP}&port={PORT}&secret={full_secret}"


def create_user(username, telegram_id="unknown"):
    """Создаёт пользователя: добавляет в конфиг и в БД. Возвращает (success, link_or_error)"""
    if username in load_users():
        return False, "User already exists"
    secret = secrets.token_hex(16)
    if add_user(username, secret):
        db.add_user_to_db(username, telegram_id)
        link = get_proxy_link(secret)
        return True, link
    return False, "Failed to add user to proxy config"


def delete_user(username):
    """Удаляет пользователя: из конфига и из БД"""
    if remove_user(username):
        db.remove_user_from_db(username)
        return True
    return False


def sync_all_users():
    """Синхронизирует БД с конфигом прокси"""
    proxy_users = load_users()
    db.sync_db_with_proxy(proxy_users)
