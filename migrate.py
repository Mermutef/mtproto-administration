#!/usr/bin/env python3
import sqlite3
import requests
import time
import sys
from pathlib import Path

# Добавляем путь к проекту для импорта из app.config
sys.path.insert(0, str(Path(__file__).parent))

from app.config import TOKEN, DB_PATH, DOMAIN, SERVER, PORT

DOMAIN_HEX = DOMAIN.encode().hex()


def get_all_users_with_secret():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT username, telegram_id, secret 
        FROM users 
        WHERE telegram_id NOT IN ('unknown', 'web', '—') 
          AND secret IS NOT NULL
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.ok
    except Exception as e:
        print(f"❌ Ошибка отправки для {chat_id}: {e}")
        return False


def main():
    users = get_all_users_with_secret()
    total = len(users)
    print(f"Найдено пользователей: {total}")
    success = 0

    for username, tid, secret in users:
        full_secret = f"ee{secret}{DOMAIN_HEX}"
        link = f"tg://proxy?server={SERVER}&port={PORT}&secret={full_secret}"

        message = (
            f"🔐 <b>Обновление подключения к Telegram</b>\n\n"
            f"Уважаемые пользователи!\n\n"
            f"В связи с усилением блокировок был обновлен прокси-сервер. "
            f"Новая конфигурация должна обеспечивать более стабильную работу и лучшую защиту от ограничений.\n\n"
            f"<b>Для перехода на новое подключение:</b>\n"
            f"1. Нажмите на ссылку ниже:\n"
            f"{link}\n"
            f"2. В открывшемся окне Telegram нажмите «Подключить прокси» (или «Connect proxy»).\n"
            f"3. Готово — новое соединение активируется автоматически.\n\n"
            f"Если возникнут вопросы — просто свяжитесь с тем, кто изначально предоставил вам доступ к сервису."
        )

        if send_message(tid, message):
            success += 1
            print(f"✅ {username} ({tid})")
        else:
            print(f"⚠️ Не отправлено: {username} ({tid})")

        time.sleep(0.1)

    print(f"\n🎉 Готово. Отправлено {success} из {total}.")


if __name__ == "__main__":
    main()
