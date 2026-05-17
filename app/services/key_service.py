import json
import sqlite3
import re
import threading
import logging
from datetime import datetime
from app.config import DB_PATH, XRAY_INBOUND_ID, XRAY_SUB_URL_BASE
from app.proxy_manager import generate_unique_username, create_user
from app.locales.ru import MESSAGES
from app.x_ui_manager import XUIClient

_xui_per_thread = threading.local()


def get_xui_client():
    client = getattr(_xui_per_thread, 'client', None)
    if client is None:
        try:
            _xui_per_thread.client = XUIClient()
        except Exception as e:
            logging.error(f"❌ Не удалось инициализировать XUIClient: {e}")
            _xui_per_thread.client = False
        client = _xui_per_thread.client
    return client if client is not False else None


def create_mtproto_key(uid, username_hint=None):
    if username_hint:
        base_name = re.sub(r'[^a-zA-Z0-9_]', '_', username_hint)
    else:
        base_name = f"user{uid}"
    proxy_username = generate_unique_username(base_name)
    success, link = create_user(proxy_username, telegram_id=str(uid))
    if success:
        return True, (proxy_username, link), ""
    return False, ("", ""), link


def create_xray_key(uid, username_hint=None):
    xui = get_xui_client()
    if not xui:
        return False, "", MESSAGES["xui_unavailable"]
    if username_hint:
        base_name = re.sub(r'[^a-zA-Z0-9_]', '_', username_hint)
    else:
        base_name = f"user{uid}"
    email = f"{base_name}_{uid}"
    try:
        result = xui.add_client(XRAY_INBOUND_ID, email)
        uuid_str = result["uuid"]
        sub_id = result["sub_id"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute("INSERT OR IGNORE INTO users (username, telegram_id, created_at) VALUES (?, ?, ?)",
                  (email, str(uid), now))
        c.execute("SELECT id FROM users WHERE username = ?", (email,))
        user_db_id = c.fetchone()[0]
        key_data = json.dumps({"email": email, "uuid": uuid_str, "sub_id": sub_id})
        c.execute("INSERT INTO keys (user_id, protocol, key_data, created_at) VALUES (?, 'xray', ?, ?)",
                  (user_db_id, key_data, now))
        conn.commit()
        conn.close()

        subscribe_url = f"{XRAY_SUB_URL_BASE}{sub_id}" if sub_id else ""
        return True, (email, subscribe_url), ""
    except Exception as e:
        return False, "", str(e)


def get_or_update_sub_id(email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT json_extract(key_data, '$.sub_id') FROM keys WHERE protocol='xray' AND json_extract(key_data, '$.email') = ?",
        (email,))
    row = c.fetchone()
    sub_id = row[0] if row and row[0] else None
    if not sub_id:
        xui = get_xui_client()
        if xui:
            sub_id = xui.get_client_sub_id(XRAY_INBOUND_ID, email)
        if sub_id:
            c.execute(
                "UPDATE keys SET key_data = json_set(key_data, '$.sub_id', ?) WHERE protocol='xray' AND json_extract(key_data, '$.email') = ?",
                (sub_id, email))
            conn.commit()
    conn.close()
    return sub_id or ""
