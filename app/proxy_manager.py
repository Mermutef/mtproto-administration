import secrets
import subprocess
import re
import sqlite3
from app.config import DOMAIN, PORT, SERVER_IP, DB_PATH, SECRETS_FILE
import app.db as db

DOMAIN_HEX = DOMAIN.encode().hex()


def _run_mtproxymax(cmd):
    try:
        proc = subprocess.run(
            ["mtproxymax"] + cmd.split(),
            capture_output=True,
            text=True,
            timeout=30
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    except FileNotFoundError:
        return "", "mtproxymax not found", 127


def load_users():
    users = {}
    try:
        with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if len(parts) >= 2:
                    label = parts[0]
                    secret = parts[1]
                    if re.match(r'^[a-f0-9]{32}$', secret):
                        users[label] = secret
                    else:
                        print(f"Skipping invalid secret for {label}: {secret}")
    except FileNotFoundError:
        print(f"Secrets file {SECRETS_FILE} not found. Make sure mtproxymax is installed and configured.")
    except Exception as e:
        print(f"Error reading secrets file: {e}")
    return users


def generate_unique_username(base="user"):
    users = load_users()
    while True:
        num = secrets.randbelow(1000000)
        username = f"{base}_{num}"
        if username not in users:
            return username


def get_proxy_link(secret):
    full_secret = f"ee{secret}{DOMAIN_HEX}"
    return f"tg://proxy?server={SERVER_IP}&port={PORT}&secret={full_secret}"


def create_user(username, telegram_id="unknown"):
    users = load_users()
    if username in users:
        return False, "User already exists"
    stdout, stderr, rc = _run_mtproxymax(f"secret add {username}")
    if rc != 0:
        return False, f"mtproxymax error: {stderr}"
    users = load_users()
    secret = users.get(username)
    if secret:
        db.add_user_to_db(username, telegram_id, secret)
        link = get_proxy_link(secret)
        return True, link
    else:
        return False, "Failed to retrieve secret after creation"


def delete_user(username):
    users = load_users()
    if username not in users:
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] not in ('unknown', 'web'):
        db.revoke_user_requests(row[0])
    stdout, stderr, rc = _run_mtproxymax(f"secret remove {username}")
    if rc != 0:
        print(f"Failed to remove {username}: {stderr}")
        return False
    db.remove_user_from_db(username)
    return True


def sync_all_users():
    proxy_users = load_users()
    db.sync_db_with_proxy(proxy_users)


def rename_user(old_name, new_name):
    stdout, stderr, rc = _run_mtproxymax(f"secret rename {old_name} {new_name}")
    if rc != 0:
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET username = ? WHERE username = ?", (new_name, old_name))
    conn.commit()
    conn.close()
    return True
