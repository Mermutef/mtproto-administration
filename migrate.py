import sqlite3
import re
import asyncio
from app.config import TOKEN, DB_PATH
from telegram import Bot


# Функция для формирования имени как при первой регистрации
async def get_proper_username(bot, telegram_id):
    try:
        chat = await bot.get_chat(int(telegram_id))
        base = chat.username or chat.first_name or f"user{telegram_id}"
        base = re.sub(r'[^a-zA-Z0-9_]', '_', base)
        return f"{base}_{telegram_id}"
    except Exception as e:
        print(f"  ⚠️ Не удалось получить имя для {telegram_id}: {e}")
        return f"user_{telegram_id}"


async def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    bot = Bot(token=TOKEN)

    # Удаляем старые бэкап-таблицы
    c.execute("DROP TABLE IF EXISTS users_old_backup")
    c.execute("DROP TABLE IF EXISTS requests_old_backup")
    print("Удалены таблицы users_old_backup, requests_old_backup")

    # Шаг 1: Приводим telegram_id в порядок (заменяем NULL, unknown, '—' на 'web')
    c.execute("UPDATE users SET telegram_id = 'web' WHERE telegram_id IS NULL OR telegram_id IN ('', 'unknown', '—')")
    print("Пустые telegram_id заменены на 'web'")

    # Шаг 2: Группируем дубликаты по telegram_id (исключаем 'web')
    dup_rows = c.execute("""
        SELECT telegram_id, COUNT(*) as cnt
        FROM users
        WHERE telegram_id != 'web'
        GROUP BY telegram_id
        HAVING cnt > 1
    """).fetchall()

    if not dup_rows:
        print("Дубликатов пользователей не найдено.")
    else:
        print(f"Найдено {len(dup_rows)} telegram_id с дубликатами.")

    for row in dup_rows:
        tg_id = row['telegram_id']
        # Получаем все записи с этим telegram_id
        users = c.execute("SELECT id, username, telegram_id, created_at FROM users WHERE telegram_id = ?",
                          (tg_id,)).fetchall()
        print(f"\nОбработка telegram_id={tg_id}, записей: {len(users)}")

        # Определяем основного пользователя: предпочитаем того, у кого имя не начинается с 'u_' и не состоит из множества '_'
        main_user = None
        for u in users:
            name = u['username']
            if not name.startswith('u_') and not name.startswith('_____'):
                if main_user is None or u['id'] > main_user['id']:
                    main_user = u
        if main_user is None:
            # Берём первую запись
            main_user = users[0]

        # Переименовываем основного пользователя по правилам "как при первой регистрации"
        new_name = await get_proper_username(bot, tg_id)
        print(
            f"  Основной пользователь: id={main_user['id']}, старое имя={main_user['username']}, новое имя={new_name}")
        c.execute("UPDATE users SET username = ? WHERE id = ?", (new_name, main_user['id']))

        # Переносим ключи и заявки с дубликатов на основного
        for u in users:
            if u['id'] == main_user['id']:
                continue
            print(f"  Удаляем дубликат id={u['id']}, username={u['username']}")
            # Переносим ключи
            c.execute("UPDATE keys SET user_id = ? WHERE user_id = ?", (main_user['id'], u['id']))
            # Переносим заявки
            c.execute("UPDATE requests SET user_id = ? WHERE user_id = ?", (main_user['id'], u['id']))
            # Удаляем дубликат
            c.execute("DELETE FROM users WHERE id = ?", (u['id'],))

    # Шаг 3: Удаляем дублирующиеся ключи одного протокола (оставляем последний активный)
    # Сначала найдём пользователей с несколькими ключами одного протокола
    dup_keys = c.execute("""
        SELECT user_id, protocol, COUNT(*) as cnt
        FROM keys
        WHERE status = 'active'
        GROUP BY user_id, protocol
        HAVING cnt > 1
    """).fetchall()

    for dk in dup_keys:
        user_id = dk['user_id']
        protocol = dk['protocol']
        # Получаем все активные ключи этого протокола у пользователя
        keys = c.execute("""
            SELECT id, key_data, created_at FROM keys
            WHERE user_id = ? AND protocol = ? AND status = 'active'
            ORDER BY id DESC
        """, (user_id, protocol)).fetchall()
        print(
            f"Пользователь {user_id}, протокол {protocol}: найдено {len(keys)} активных ключей, оставляем последний (id={keys[0]['id']})")
        # Оставляем первый (самый последний), остальные помечаем revoked
        for k in keys[1:]:
            c.execute("UPDATE keys SET status = 'revoked' WHERE id = ?", (k['id'],))

    # Шаг 4: Удаляем все отклонённые заявки и заявки, по которым нет ни одного ключа
    # а) Удаляем заявки со статусом 'rejected'
    c.execute("DELETE FROM requests WHERE status = 'rejected'")
    print("Удалены все rejected заявки.")
    # б) Удаляем заявки со статусом 'pending', у которых нет ключей (но оставим те, что могут быть в процессе? По задаче - все заявки без ключей)
    # Найдём request_id, для которых не существует ключей с таким же user_id и протоколом
    c.execute("""
        DELETE FROM requests
        WHERE request_id IN (
            SELECT r.request_id
            FROM requests r
            LEFT JOIN keys k ON r.user_id = k.user_id AND r.protocol = k.protocol
            WHERE k.id IS NULL
        )
    """)
    print("Удалены заявки, по которым не выдано ни одного ключа.")

    # Шаг 5: Делаем поле telegram_id NOT NULL (SQLite не позволяет ALTER COLUMN, поэтому пересоздадим таблицу)
    # Сохраняем данные users
    c.execute("SELECT id, username, telegram_id, created_at FROM users")
    users_data = c.fetchall()
    c.execute("DROP TABLE IF EXISTS users_new")
    c.execute("""
        CREATE TABLE users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            telegram_id TEXT NOT NULL DEFAULT 'web',
            created_at TEXT
        )
    """)
    for u in users_data:
        c.execute("INSERT INTO users_new (id, username, telegram_id, created_at) VALUES (?, ?, ?, ?)",
                  (u['id'], u['username'], u['telegram_id'], u['created_at']))
    c.execute("DROP TABLE users")
    c.execute("ALTER TABLE users_new RENAME TO users")
    print("Таблица users пересоздана с NOT NULL на telegram_id.")

    # Сохраняем изменения
    conn.commit()
    conn.close()
    print("\n✅ Миграция завершена. База данных обновлена.")


if __name__ == '__main__':
    asyncio.run(main())
