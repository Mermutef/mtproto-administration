"""Database access layer for the VPN administration bot.

Uses SQLite for persistent storage of users, keys, access requests,
and message caching. All functions take care of opening and closing
connections, so callers don't need to manage database lifecycle.
"""

import sqlite3
import json
import time
from datetime import datetime
from app.config import DB_PATH


def init_db():
    """Initialize the database schema.

    Creates the following tables if they don't exist:
        - users: Registered users with Telegram IDs.
        - keys: VPN protocol keys associated with users.
        - requests: Access requests requiring admin approval.
        - message_cache: Cached media group messages for forwarding.

    Also creates indexes on message_cache for performance.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  telegram_id TEXT,
                  created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keys
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  protocol TEXT NOT NULL,
                  key_data TEXT NOT NULL,
                  status TEXT DEFAULT 'active',
                  created_at TEXT,
                  expires_at TEXT,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS requests
                 (request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  user_name TEXT,
                  protocol TEXT DEFAULT 'mtproto',
                  status TEXT,
                  created_at TEXT,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS message_cache
                     (media_group_id TEXT NOT NULL,
                      message_id INTEGER NOT NULL,
                      chat_id INTEGER NOT NULL,
                      date REAL NOT NULL,
                      PRIMARY KEY (chat_id, message_id))''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_cache_group ON message_cache(media_group_id, chat_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_cache_date ON message_cache(date)')
    conn.commit()
    conn.close()


def get_user_by_telegram_id(telegram_id):
    """Look up a username by Telegram ID.

    Args:
        telegram_id: The Telegram user ID.

    Returns:
        The username string, or None if not found.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE telegram_id = ?", (str(telegram_id),))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def get_all_users():
    """Return all registered users.

    Returns:
        A list of (username, telegram_id, created_at) tuples.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, telegram_id, created_at FROM users")
    users = c.fetchall()
    conn.close()
    return users


def add_request(user_id, user_name, protocol='mtproto'):
    """Create a new access request for a user.

    If the user doesn't exist yet, they are created first.

    Args:
        user_id: Telegram user ID.
        user_name: Display name or username.
        protocol: Requested VPN protocol.

    Returns:
        The new request ID.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE telegram_id = ?", (str(user_id),))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (username, telegram_id, created_at) VALUES (?, ?, ?)",
                  (user_name, str(user_id), datetime.now().isoformat()))
        user_db_id = c.lastrowid
    else:
        user_db_id = row[0]
    c.execute("INSERT INTO requests (user_id, user_name, protocol, status, created_at) VALUES (?, ?, ?, ?, ?)",
              (user_db_id, user_name, protocol, 'pending', datetime.now().isoformat()))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    return request_id


def get_request(request_id):
    """Retrieve a request by its ID.

    Args:
        request_id: The request identifier.

    Returns:
        A tuple (telegram_id, user_name, protocol, status) or None.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT u.telegram_id, r.user_name, r.protocol, r.status
                 FROM requests r JOIN users u ON r.user_id = u.id
                 WHERE r.request_id = ?''', (request_id,))
    result = c.fetchone()
    conn.close()
    return result


def update_request_status(request_id, status):
    """Update the status of a request.

    Args:
        request_id: The request identifier.
        status: New status (e.g. 'approved', 'rejected', 'revoked').
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE requests SET status = ? WHERE request_id = ?", (status, request_id))
    conn.commit()
    conn.close()


def get_user_requests(telegram_id):
    """Get all requests made by a specific user.

    Args:
        telegram_id: The Telegram user ID.

    Returns:
        A list of (request_id, status, created_at, protocol) tuples,
        ordered by creation date descending.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT r.request_id, r.status, r.created_at, r.protocol
                 FROM requests r JOIN users u ON r.user_id = u.id
                 WHERE u.telegram_id = ? ORDER BY r.created_at DESC''',
              (str(telegram_id),))
    rows = c.fetchall()
    conn.close()
    return rows


def revoke_user_requests(telegram_id):
    """Revoke all approved requests for a user.

    Args:
        telegram_id: The Telegram user ID.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''UPDATE requests SET status = 'revoked'
                 WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?)
                 AND status = 'approved' ''', (str(telegram_id),))
    conn.commit()
    conn.close()


def get_all_users_with_telegram():
    """Get users who have a valid, known Telegram ID.

    Returns:
        A list of (username, telegram_id) tuples.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT username, telegram_id FROM users WHERE telegram_id NOT IN ('unknown', 'web', '—') AND telegram_id IS NOT NULL")
    rows = c.fetchall()
    conn.close()
    return rows


def get_mtproto_secret(username):
    """Get the MTProto secret for a given username.

    Args:
        username: The user's login name.

    Returns:
        The secret string, or None.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT json_extract(key_data, '$.secret') FROM keys
                 WHERE user_id = (SELECT id FROM users WHERE username = ?)
                 AND protocol = 'mtproto' ''', (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_user_active_keys(telegram_id, protocol=None):
    """Get all active keys for a user, optionally filtered by protocol.

    Args:
        telegram_id: The Telegram user ID.
        protocol: Optional protocol name filter (e.g. 'mtproto', 'xray').

    Returns:
        A list of parsed key_data dicts.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if protocol:
        c.execute('''
            SELECT k.key_data
            FROM keys k
            JOIN users u ON k.user_id = u.id
            WHERE u.telegram_id = ? AND k.protocol = ? AND k.status = 'active'
        ''', (str(telegram_id), protocol))
    else:
        c.execute('''
            SELECT k.key_data
            FROM keys k
            JOIN users u ON k.user_id = u.id
            WHERE u.telegram_id = ? AND k.status = 'active'
        ''', (str(telegram_id),))
    rows = c.fetchall()
    conn.close()
    keys = []
    for row in rows:
        key_data = json.loads(row[0])
        keys.append(key_data)
    return keys


def get_unique_telegram_ids():
    """Get all distinct, valid Telegram user IDs.

    Returns:
        A list of Telegram ID strings.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT telegram_id
        FROM users
        WHERE telegram_id NOT IN ('web', 'unknown', '') AND telegram_id IS NOT NULL
    """)
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]


def cache_message(chat_id: int, message_id: int, media_group_id: str, date: float):
    """Cache a media group message for later batch forwarding.

    Old entries older than 7 days are pruned.

    Args:
        chat_id: Chat where the message was sent.
        message_id: Unique message ID.
        media_group_id: Group identifier for album messages.
        date: Unix timestamp of the message.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff = time.time() - 7 * 24 * 3600
    c.execute("DELETE FROM message_cache WHERE date < ?", (cutoff,))
    c.execute("INSERT OR REPLACE INTO message_cache (media_group_id, message_id, chat_id, date) VALUES (?,?,?,?)",
              (media_group_id, message_id, chat_id, date))
    conn.commit()
    conn.close()


def get_media_group_message_ids(chat_id: int, media_group_id: str) -> list[int]:
    """Get all cached message IDs for a media group.

    Args:
        chat_id: The source chat.
        media_group_id: The media group identifier.

    Returns:
        Sorted list of message IDs.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT message_id FROM message_cache WHERE chat_id = ? AND media_group_id = ? ORDER BY message_id",
              (chat_id, media_group_id))
    ids = [row[0] for row in c.fetchall()]
    conn.close()
    return ids


def get_users_with_active_keys():
    """Get all users who have at least one active key.

    Returns:
        A list of (username, telegram_id, created_at) tuples.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT u.username, u.telegram_id, u.created_at
        FROM users u
        JOIN keys k ON u.id = k.user_id
        WHERE k.status = 'active'
        ORDER BY u.created_at DESC
    """)
    users = c.fetchall()
    conn.close()
    return users


def get_users_with_active_keys_for_protocol(protocol):
    """Get all users who have an active key for a specific protocol.

    Args:
        protocol: The protocol name to filter by.

    Returns:
        A list of (username, telegram_id, created_at) tuples.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT u.username, u.telegram_id, u.created_at
        FROM users u
        JOIN keys k ON u.id = k.user_id
        WHERE k.status = 'active' AND k.protocol = ?
        ORDER BY u.created_at DESC
    """, (protocol,))
    users = c.fetchall()
    conn.close()
    return users
