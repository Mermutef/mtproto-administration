import sqlite3
from datetime import datetime
from config import DB_PATH


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, telegram_id TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS requests
                 (request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT, user_name TEXT, status TEXT, created_at TEXT)''')
    conn.commit()
    conn.close()


def add_user_to_db(username, telegram_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (username, telegram_id, created_at) VALUES (?, ?, ?)",
              (username, str(telegram_id), datetime.now().isoformat()))
    conn.commit()
    conn.close()


def remove_user_from_db(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def get_user_by_telegram_id(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE telegram_id = ?", (str(telegram_id),))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, telegram_id, created_at FROM users")
    users = c.fetchall()
    conn.close()
    return users


def add_request(user_id, user_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO requests (user_id, user_name, status, created_at) VALUES (?, ?, ?, ?)",
              (str(user_id), user_name, 'pending', datetime.now().isoformat()))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    return request_id


def get_request(request_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, user_name, status FROM requests WHERE request_id = ?", (request_id,))
    result = c.fetchone()
    conn.close()
    return result


def update_request_status(request_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE requests SET status = ? WHERE request_id = ?", (status, request_id))
    conn.commit()
    conn.close()


def get_user_requests(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT request_id, status, created_at FROM requests WHERE user_id = ? ORDER BY created_at DESC",
              (str(user_id),))
    rows = c.fetchall()
    conn.close()
    return rows


def sync_db_with_proxy(proxy_users):
    """
    proxy_users: dict {username: secret}
    Добавляет в БД всех пользователей, которые есть в прокси, но отсутствуют в БД.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for username in proxy_users:
        c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        if not c.fetchone():
            c.execute("INSERT INTO users (username, telegram_id, created_at) VALUES (?, ?, ?)",
                      (username, 'unknown', datetime.now().isoformat()))
    conn.commit()
    conn.close()
