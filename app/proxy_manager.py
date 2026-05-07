import os
import secrets
import sqlite3
import subprocess
import re
from datetime import datetime

from flask import json

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


def generate_unique_username(base: str) -> str:
    """Генерирует уникальное имя пользователя на основе base."""
    users = load_users()
    # Очищаем base от недопустимых символов
    base = re.sub(r'[^a-zA-Z0-9_]', '_', base)
    if not base:
        base = "user"
    if base not in users:
        return base
    i = 1
    while True:
        candidate = f"{base}_{i}"
        if candidate not in users:
            return candidate
        i += 1


def get_proxy_link(secret):
    domain_hex = DOMAIN.encode().hex()
    full_secret = f"ee{secret}{domain_hex}"
    return f"tg://proxy?server={SERVER}&port={PORT}&secret={full_secret}"


def create_user(username: str, telegram_id="unknown"):
    """
    Создаёт пользователя MTProto.
    Если username уже существует, возвращает ошибку.
    """
    if username in load_users():
        return False, "User already exists"
    secret = secrets.token_hex(16)
    if add_user(username, secret):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (username, telegram_id, created_at) VALUES (?, ?, ?)",
                  (username, str(telegram_id), datetime.now().isoformat()))
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_id = c.fetchone()[0]
        key_data = json.dumps({"secret": secret})
        c.execute("INSERT INTO keys (user_id, protocol, key_data, created_at) VALUES (?, 'mtproto', ?, ?)",
                  (user_id, key_data, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        link = get_proxy_link(secret)
        return True, link
    return False, "Failed to add user to proxy config"


def delete_user(username):
    if remove_user(username):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, telegram_id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if row:
            user_id, telegram_id = row
            if telegram_id not in ('unknown', 'web', '—'):
                db.revoke_user_requests(telegram_id)
            c.execute("DELETE FROM keys WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    return False


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


def sync_all_users():
    proxy_users = load_users()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for username, secret in proxy_users.items():
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO users (username, telegram_id, created_at) VALUES (?, 'unknown', ?)",
                      (username, datetime.now().isoformat()))
            user_id = c.lastrowid
        else:
            user_id = row[0]
        c.execute("SELECT id FROM keys WHERE user_id = ? AND protocol = 'mtproto'", (user_id,))
        if not c.fetchone():
            key_data = json.dumps({"secret": secret})
            c.execute("INSERT INTO keys (user_id, protocol, key_data, created_at) VALUES (?, 'mtproto', ?, ?)",
                      (user_id, key_data, datetime.now().isoformat()))

    c.execute("""
        SELECT u.username, json_extract(k.key_data, '$.secret') as secret
        FROM keys k
        JOIN users u ON k.user_id = u.id
        WHERE k.protocol = 'mtproto' AND k.status = 'active'
          AND u.username NOT IN (SELECT value FROM json_each(?))
    """, (json.dumps(list(proxy_users.keys())),))
    missing = c.fetchall()
    if missing:
        new_users = proxy_users.copy()
        for username, secret in missing:
            if secret:
                new_users[username] = secret
        save_users(new_users)

    conn.commit()
    conn.close()
