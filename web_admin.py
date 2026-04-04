#!/usr/bin/env python3
import secrets
import sqlite3
from flask import Flask, request, render_template_string, redirect, url_for, flash
from config import ADMIN_PASSWORD, FLASK_PORT, SERVER_IP, PORT, DB_PATH
import proxy_manager
import db

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# При старте синхронизируем БД с конфигом прокси
proxy_manager.sync_all_users()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>MTProto Proxy Admin</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .link { font-family: monospace; word-break: break-all; }
        .add-form { margin-bottom: 30px; background: #f9f9f9; padding: 20px; border-radius: 8px; }
        input, button { padding: 8px; font-size: 16px; }
        .flash { padding: 10px; background: #d4edda; color: #155724; border-radius: 4px; margin-bottom: 20px; }
        .error { background: #f8d7da; color: #721c24; }
        .delete-btn { color: red; cursor: pointer; text-decoration: underline; margin-left: 10px; }
        .badge { background: #e9ecef; padding: 2px 6px; border-radius: 12px; font-size: 12px; }
    </style>
</head>
<body>
    <h1>Управление пользователями MTProto прокси</h1>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
            <div class="flash {% if category == 'error' %}error{% endif %}">{{ message }}</div>
        {% endfor %}
    {% endwith %}

    <div class="add-form">
        <h3>➕ Добавить пользователя</h3>
        <form method="post">
            <input type="text" name="username" placeholder="Логин" required>
            <button type="submit">Создать</button>
        </form>
    </div>

    <h3>📋 Список пользователей</h3>
    <table>
        <tr>
            <th>Логин</th>
            <th>Секрет (32 hex)</th>
            <th>Telegram ID</th>
            <th>Ссылка для Telegram</th>
            <th>Действие</th>
        </tr>
        {% for username, secret in users.items() %}
        <tr>
            <td>{{ username }}</td>
            <td><code>{{ secret }}</code></td>
            <td>
                {% set tg_id = user_tg_ids.get(username, '—') %}
                {% if tg_id != 'unknown' and tg_id != 'web' %}
                    {{ tg_id }}
                {% else %}
                    <span class="badge">{{ tg_id }}</span>
                {% endif %}
            </td>
            <td class="link">
                <a href="{{ make_link(secret) }}">{{ make_link(secret) }}</a>
            </td>
            <td>
                <a href="{{ url_for('delete_user', username=username) }}" class="delete-btn" onclick="return confirm('Удалить {{ username }}?')">Удалить</a>
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""


def make_link(secret):
    return proxy_manager.get_proxy_link(secret)


@app.route("/", methods=["GET", "POST"])
def admin():
    auth = request.authorization
    if not auth or auth.username != "admin" or auth.password != ADMIN_PASSWORD:
        return "Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            flash("Логин не может быть пустым", "error")
            return redirect(url_for("admin"))
        if username in proxy_manager.load_users():
            flash(f"Пользователь '{username}' уже существует", "error")
            return redirect(url_for("admin"))
        success, result = proxy_manager.create_user(username, telegram_id="web")
        if success:
            flash(f"Пользователь '{username}' добавлен. Ссылка: {result}")
        else:
            flash(f"Ошибка: {result}", "error")
        return redirect(url_for("admin"))

    users = proxy_manager.load_users()
    user_tg_ids = {}
    for uname in users:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT telegram_id FROM users WHERE username = ?", (uname,))
        row = c.fetchone()
        conn.close()
        user_tg_ids[uname] = row[0] if row else "—"

    return render_template_string(
        HTML_TEMPLATE,
        users=users,
        user_tg_ids=user_tg_ids,
        make_link=make_link
    )


@app.route("/delete/<username>")
def delete_user(username):
    auth = request.authorization
    if not auth or auth.password != ADMIN_PASSWORD:
        return "Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}

    if proxy_manager.delete_user(username):
        flash(f"Пользователь '{username}' удалён")
    else:
        flash(f"Пользователь '{username}' не найден", "error")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    print("=" * 50)
    print(f"Proxy config: {proxy_manager.CONFIG_PATH}")
    print(f"Container: {proxy_manager.CONTAINER_NAME}")
    print(f"Domain: {proxy_manager.DOMAIN}, Port: {proxy_manager.PORT}, IP: {proxy_manager.SERVER_IP}")
    print(f"Admin password: {ADMIN_PASSWORD}")
    print(f"Starting web admin on http://0.0.0.0:{FLASK_PORT}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)
