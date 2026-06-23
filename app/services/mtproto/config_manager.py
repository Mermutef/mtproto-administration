"""Low-level MTProto proxy configuration file manager.

Handles reading and writing the MTProto proxy's Python configuration
file (``config.py``), managing the user dictionary inside it, and
signalling the Docker container to reload.
"""

import os
import re
import ast
import json
import subprocess
import sqlite3
from datetime import datetime
from app.config import CONFIG_PATH, DOMAIN, PORT, SERVER, CONTAINER_NAME, DB_PATH, DOCKER_PORT

TEMPLATE_HEAD = '''# MTProto Proxy configuration
PORT = {port}
MODES = {{
    "classic": False,
    "secure": False,
    "tls": True
}}
TLS_DOMAIN = "{tls_domain}"
'''


def _read_config():
    """Read the USERS dictionary from the proxy config file.

    Returns:
        A dict mapping username -> secret, or empty dict on error.
    """
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'USERS\s*=\s*(\{.*?\n\})', content, re.DOTALL)
    if not match:
        return {}
    try:
        users_dict = ast.literal_eval(match.group(1))
        return users_dict if isinstance(users_dict, dict) else {}
    except:
        return {}


def _write_config(users_dict):
    """Write the USERS dictionary back to the proxy config file.

    Args:
        users_dict: Mapping of username -> secret.
    """
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
    """Load all MTProto proxy users.

    Returns:
        A dict of username -> secret.
    """
    return _read_config()


def save_users(users_dict):
    """Persist the user dict and reload the proxy container.

    Args:
        users_dict: Mapping of username -> secret.
    """
    _write_config(users_dict)
    try:
        subprocess.run(["docker", "exec", CONTAINER_NAME, "kill", "-USR2", "1"], check=True)
    except subprocess.CalledProcessError:
        subprocess.run(["docker", "restart", CONTAINER_NAME], capture_output=True)


def add_user(username, secret):
    """Add a user to the MTProto proxy.

    Args:
        username: Login name.
        secret: Proxy secret hex string.

    Returns:
        True if added, False if the username already exists.
    """
    users = load_users()
    if username in users:
        return False
    users[username] = secret
    save_users(users)
    return True


def remove_user(username):
    """Remove a user from the MTProto proxy.

    Args:
        username: The user to remove.

    Returns:
        True if removed, False if not found.
    """
    users = load_users()
    if username not in users:
        return False
    del users[username]
    save_users(users)
    return True


def rename_user(old_name, new_name):
    """Rename a user in proxy config, local DB, and 3x-ui panel.

    Updates the username across ALL protocols (mtproto, xray, trojan,
    hysteria2) that belong to this user, and syncs the change to the
    3x-ui panel so the web interface reflects the new name.

    Args:
        old_name: Current username.
        new_name: New username.

    Returns:
        True on success, False if old_name is missing or new_name taken.
    """
    users = load_users()
    if old_name not in users:
        return False
    if new_name in users:
        return False

    # 1. Rename in MTProto config
    new_users = {new_name if k == old_name else k: v for k, v in users.items()}
    save_users(new_users)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 2. Find the user id
    c.execute("SELECT id FROM users WHERE username = ?", (old_name,))
    row = c.fetchone()
    if not row:
        conn.close()
        return True
    user_id = row[0]

    # 3. Rename in users table
    c.execute("UPDATE users SET username = ? WHERE id = ?", (new_name, user_id))

    # 4. Update key_data for ALL protocols — replace email in JSON
    for proto in ('mtproto', 'xray', 'trojan', 'hysteria2'):
        c.execute(
            "UPDATE keys SET key_data = json_set(key_data, '$.email', ?) "
            "WHERE user_id = ? AND protocol = ? AND json_extract(key_data, '$.email') = ?",
            (new_name, user_id, proto, old_name),
        )
        # Also update '$.username' for mtproto keys that use that field
        c.execute(
            "UPDATE keys SET key_data = json_set(key_data, '$.username', ?) "
            "WHERE user_id = ? AND protocol = ? AND json_extract(key_data, '$.username') = ?",
            (new_name, user_id, proto, old_name),
        )

    conn.commit()
    conn.close()

    # 5. Update email on 3x-ui panel (best effort — ignore failures)
    try:
        from app.x_ui_manager import XuiApi
        api = XuiApi()
        # Try to find and update on each 3x-ui protocol inbound
        for inbound_id in (1, 2, 3):  # xray=1, trojan=2, hysteria2=3
            try:
                client = api.get_client(old_name)
                if client:
                    client["email"] = new_name
                    api.update_client(old_name, client)
            except Exception:
                pass
    except Exception:
        pass

    return True


def generate_unique_username(base: str) -> str:
    """Generate a unique username that doesn't exist in the config.

    Args:
        base: Preferred base name.

    Returns:
        A unique username string.
    """
    users = load_users()
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
    """Build a Telegram proxy link from a secret.

    Args:
        secret: The proxy secret hex string.

    Returns:
        A ``tg://proxy`` URL.
    """
    domain_hex = DOMAIN.encode().hex()
    full_secret = f"ee{secret}{domain_hex}"
    return f"tg://proxy?server={SERVER}&port={PORT}&secret={full_secret}"


def sync_all_users():
    """Synchronise the database with the proxy config file.

    Creates missing database records for users present in the config,
    and adds users from the database back to the config if missing.
    """
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
