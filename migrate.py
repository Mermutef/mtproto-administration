#!/usr/bin/env python3
import sqlite3
import asyncio
import re
from app.config import DB_PATH, TOKEN
from app.proxy_manager import load_users, rename_user
from telegram import Bot


async def main():
    bot = Bot(token=TOKEN)
    users = load_users()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Список логинов, которые нужно попробовать исправить
    target_usernames = ["u_937383965_398697", "u_301750870_440051"]

    for old_name in target_usernames:
        if old_name not in users:
            print(f"❌ Пользователь {old_name} не найден в конфиге прокси.")
            continue

        # Пытаемся определить Telegram ID по структуре имени
        match = re.search(r'u_(\d+)_\d+', old_name)
        if not match:
            print(f"❌ Не удалось извлечь Telegram ID из имени {old_name}.")
            continue

        tid = match.group(1)

        try:
            chat = await bot.get_chat(int(tid))
            base_name = chat.username or chat.first_name or f"user{tid}"
        except Exception as e:
            print(f"⚠️ Не удалось получить данные для Telegram ID {tid}: {e}")
            continue

        base_name = re.sub(r'[^a-zA-Z0-9_]', '_', base_name)
        new_name = f"{base_name}_{tid}"

        if new_name == old_name:
            print(f"✓ {old_name} уже имеет правильное имя.")
            continue

        # Проверяем, не занято ли новое имя
        c.execute("SELECT 1 FROM users WHERE username = ?", (new_name,))
        if c.fetchone():
            print(f"⚠️ Имя {new_name} уже занято, пробуем добавить суффикс.")
            counter = 1
            while True:
                candidate = f"{new_name}_{counter}"
                c.execute("SELECT 1 FROM users WHERE username = ?", (candidate,))
                if not c.fetchone():
                    new_name = candidate
                    break
                counter += 1

        print(f"🔄 Переименовываем {old_name} -> {new_name}")
        if rename_user(old_name, new_name):
            print(f"   ✅ Успешно")
        else:
            print(f"   ❌ Ошибка переименования {old_name}")

    conn.close()
    print("🎉 Операция завершена.")


if __name__ == "__main__":
    asyncio.run(main())