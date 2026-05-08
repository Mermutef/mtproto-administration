import sqlite3
from app.config import DB_PATH

def get_user_ids_by_protocol(protocol=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if protocol:
        c.execute("""
            SELECT DISTINCT u.telegram_id
            FROM users u
            JOIN keys k ON u.id = k.user_id
            WHERE k.protocol = ? AND k.status = 'active'
              AND u.telegram_id NOT IN ('web', 'unknown', '') AND u.telegram_id IS NOT NULL
        """, (protocol,))
    else:
        c.execute("""
            SELECT DISTINCT telegram_id
            FROM users
            WHERE telegram_id NOT IN ('web', 'unknown', '') AND telegram_id IS NOT NULL
        """)
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]