#!/usr/bin/env python3
import sqlite3

DB_PATH = "/root/mtproto_bot.db"
SECRETS_CONF = "/opt/mtproxymax/secrets.conf"


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN secret TEXT")
        print("Added column 'secret'")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Column 'secret' already exists")
        else:
            raise
    secrets = {}
    with open(SECRETS_CONF, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('|')
            if len(parts) >= 2:
                label = parts[0]
                secret = parts[1]
                secrets[label] = secret
    for username, secret in secrets.items():
        c.execute("UPDATE users SET secret = ? WHERE username = ?", (secret, username))
        if c.rowcount == 0:
            c.execute("INSERT INTO users (username, telegram_id, secret, created_at) VALUES (?, ?, ?, ?)",
                      (username, 'unknown', secret, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print("Migration completed")


if __name__ == "__main__":
    from datetime import datetime

    main()
