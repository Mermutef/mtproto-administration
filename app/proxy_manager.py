import os
import secrets
import sqlite3
import subprocess
import re
from app.config import CONFIG_PATH, DOMAIN, PORT, SERVER, CONTAINER_NAME, DB_PATH, DOCKER_PORT
import app.db as db

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
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
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
    port = DOCKER_PORT
    tls_domain = DOMAIN
    header = TEMPLATE_HEAD.format(port=port, tls_domain=tls_domain)
    users_str = "USERS = {\n"
    for name, secret in users_dict.items():
        users_str += f'    "{name}": "{secret}",\n'
    users_str += "}\n"
    content = header + "\n" + users_str
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        f.write(content)


def load_users():
    return _read_config()


def save_users(users_dict):
    _write_config(users_dict)
    try:
        subprocess.run(["docker", "exec", CONTAINER_NAME, "kill", "-USR2", "1"], check=True)
    except subprocess.CalledProcessError:
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
    return f"tg://proxy?server={SERVER}&port={PORT}&secret={full_secret}"


def create_user(username, telegram_id="unknown"):
    if username in load_users():
        return False, "User already exists"
    secret = secrets.token_hex(16)
    if add_user(username, secret):
        db.add_user_to_db(username, telegram_id, secret)
        link = get_proxy_link(secret)
        return True, link
    return False, "Failed to add user to proxy config"


def delete_user(username):
    if remove_user(username):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        if row and row[0] not in ('unknown', 'web'):
            db.revoke_user_requests(row[0])
        db.remove_user_from_db(username)
        return True
    return False


def sync_all_users():
    proxy_users = load_users()
    db.sync_db_with_proxy(proxy_users)


def rename_user(old_name, new_name):
    users = load_users()
    if old_name not in users:
        return False
    if new_name in users:
        return False
    new_users = {new_name if k == old_name else k: v for k, v in users.items()}
    save_users(new_users)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET username = ? WHERE username = ?", (new_name, old_name))
    conn.commit()
    conn.close()
    return True
