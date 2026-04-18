#!/usr/bin/env python3
import secrets
import sqlite3
import threading
import time
import requests
import subprocess
from flask import Flask, request, render_template, jsonify
from app.config import DOMAIN, PORT, SERVER, ADMIN_PASSWORD, FLASK_PORT, DB_PATH, TOKEN, \
    CONTAINER_NAME
import app.proxy_manager as proxy_manager
import app.db as db

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.secret_key = secrets.token_hex(16)


def check_auth():
    auth = request.authorization
    if not auth or auth.username != "admin" or auth.password != ADMIN_PASSWORD:
        return False
    return True


def unauthorized():
    return "Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}


@app.route("/")
def index():
    if not check_auth():
        return unauthorized()
    return render_template("admin.html")


@app.route("/api/users")
def api_users():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    users = proxy_manager.load_users()
    data = []
    for username, secret in users.items():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT created_at FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        created_at = row[0] if row else None
        c.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
        row2 = c.fetchone()
        telegram_id = row2[0] if row2 else "—"
        c.execute("""
            SELECT status FROM requests 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 1
        """, (telegram_id,))
        row3 = c.fetchone()
        request_status = row3[0] if row3 else "—"
        conn.close()

        link = proxy_manager.get_proxy_link(secret)
        data.append({
            "username": username,
            "secret": secret,
            "telegram_id": telegram_id,
            "created_at": created_at if created_at else "—",
            "request_status": request_status,
            "link": link
        })
    return jsonify(data)


@app.route("/api/add_user", methods=["POST"])
def api_add_user():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    username = request.json.get("username", "").strip()
    if not username:
        return jsonify({"error": "Логин не может быть пустым"}), 400
    if username in proxy_manager.load_users():
        return jsonify({"error": f"Пользователь '{username}' уже существует"}), 400
    success, result = proxy_manager.create_user(username, telegram_id="web")
    if success:
        return jsonify({"success": True, "message": f"Пользователь '{username}' добавлен", "link": result})
    else:
        return jsonify({"error": result}), 400


@app.route("/api/delete_user", methods=["POST"])
def api_delete_user():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    username = request.json.get("username", "").strip()
    if not username:
        return jsonify({"error": "Логин не указан"}), 400
    if proxy_manager.delete_user(username):
        return jsonify({"success": True, "message": f"Пользователь '{username}' удалён"})
    else:
        return jsonify({"error": f"Пользователь '{username}' не найден"}), 404


@app.route("/api/rename_user", methods=["POST"])
def api_rename_user():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    old_name = request.json.get("old_name", "").strip()
    new_name = request.json.get("new_name", "").strip()
    if not old_name or not new_name:
        return jsonify({"error": "Старое и новое имя обязательны"}), 400
    users = proxy_manager.load_users()
    if new_name in users:
        return jsonify({"error": f"Пользователь '{new_name}' уже существует"}), 400
    if old_name not in users:
        return jsonify({"error": f"Пользователь '{old_name}' не найден"}), 404
    if proxy_manager.rename_user(old_name, new_name):
        return jsonify({"success": True, "message": f"Пользователь переименован в '{new_name}'"})
    else:
        return jsonify({"error": "Ошибка при переименовании"}), 500


@app.route("/api/broadcast", methods=["POST"])
def api_broadcast():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    message = request.json.get("message", "").strip()
    if not message:
        return jsonify({"error": "Сообщение не может быть пустым"}), 400
    users = db.get_all_users_with_telegram()
    if not users:
        return jsonify({"error": "Нет пользователей для рассылки"}), 400

    def send():
        for username, tid in users:
            try:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                              data={"chat_id": tid, "text": f"📢 Администратор: {message}"}, timeout=3)
                time.sleep(0.05)
            except:
                pass

    threading.Thread(target=send).start()
    return jsonify({"success": True, "message": f"Рассылка запущена для {len(users)} пользователей"})


@app.route("/api/send_to", methods=["POST"])
def api_send_to():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    username = request.json.get("username", "").strip()
    message = request.json.get("message", "").strip()
    if not username or not message:
        return jsonify({"error": "Заполните все поля"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if not row or row[0] in ('unknown', 'web', '—'):
        return jsonify({"error": f"Пользователь '{username}' не найден или не имеет telegram_id"}), 404
    tid = row[0]
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      data={"chat_id": tid, "text": f"✉️ Администратор: {message}"}, timeout=5)
        return jsonify({"success": True, "message": f"Сообщение отправлено пользователю '{username}'"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/restart_container", methods=["POST"])
def api_restart_container():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    result = subprocess.run(["docker", "restart", CONTAINER_NAME], capture_output=True, text=True)
    if result.returncode == 0:
        return jsonify({"success": True, "message": f"Контейнер {CONTAINER_NAME} перезапущен"})
    else:
        return jsonify({"error": f"Ошибка перезапуска: {result.stderr}"}), 500


@app.route("/api/restart_server", methods=["POST"])
def api_restart_server():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    subprocess.run(["reboot"], capture_output=True)
    return jsonify({"success": True, "message": "Сервер перезагружается..."})


if __name__ == "__main__":
    print("=" * 50)
    print(f"Container name: {CONTAINER_NAME}")
    print(f"Domain: {DOMAIN}, Port: {PORT}, IP: {SERVER}")
    print(f"Admin password: {ADMIN_PASSWORD}")
    print(f"Starting web admin on http://0.0.0.0:{FLASK_PORT}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)
