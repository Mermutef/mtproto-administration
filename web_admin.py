#!/usr/bin/env python3
import secrets
import sqlite3
import threading
import time
import requests
import subprocess
import json
import traceback
from datetime import datetime
from flask import Flask, request, render_template, jsonify
from werkzeug.exceptions import HTTPException
from app.config import (
    DOMAIN, PORT, SERVER, ADMIN_PASSWORD, FLASK_PORT, DB_PATH, TOKEN,
    CONTAINER_NAME, XRAY_INBOUND_ID, generate_xray_link
)
import app.proxy_manager as proxy_manager
import app.db as db

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.secret_key = secrets.token_hex(16)

NOISY_PATHS = {'/robots.txt', '/favicon.ico', '/.well-known/change-password'}

_xui_per_thread = threading.local()


def get_xui_client():
    """Возвращает потокобезопасный экземпляр XUIClient (по одному на поток)."""
    client = getattr(_xui_per_thread, 'client', None)
    if client is None:
        try:
            from app.x_ui_manager import XUIClient
            _xui_per_thread.client = XUIClient()
        except Exception as e:
            print(f"⚠️ Не удалось подключиться к 3x-ui API: {e}")
            _xui_per_thread.client = False
        client = _xui_per_thread.client
    return client if client is not False else None


def check_auth():
    auth = request.authorization
    if not auth or auth.username != "admin" or auth.password != ADMIN_PASSWORD:
        return False
    return True


def unauthorized():
    return "Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}


@app.errorhandler(HTTPException)
def handle_http_exception(e):
    if e.code == 401:
        return "Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}
    return jsonify({"error": e.description}), e.code


@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return handle_http_exception(e)
    tb = traceback.format_exc()
    app.logger.error(f"Unhandled Exception: {tb}")
    return jsonify({"error": "Internal Server Error"}), 500


@app.before_request
def filter_noisy():
    if request.path in NOISY_PATHS:
        return "", 200


# ---------- Главная страница ----------
@app.route("/")
def index():
    if not check_auth():
        return "", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}
    return render_template("index.html")


# ---------- MTProto API ----------
@app.route("/api/mtproto/users")
def api_mtproto_users():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    users = proxy_manager.load_users()
    data = []
    for username, secret in users.items():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT created_at, telegram_id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        created_at = row[0] if row else None
        telegram_id = row[1] if row else "—"
        c.execute("""
            SELECT status FROM requests 
            WHERE user_id = (SELECT id FROM users WHERE username = ?)
            ORDER BY created_at DESC LIMIT 1
        """, (username,))
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


@app.route("/api/mtproto/add_user", methods=["POST"])
def api_mtproto_add_user():
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


@app.route("/api/mtproto/delete_user", methods=["POST"])
def api_mtproto_delete_user():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    username = request.json.get("username", "").strip()
    if not username:
        return jsonify({"error": "Логин не указан"}), 400
    if proxy_manager.delete_user(username):
        return jsonify({"success": True, "message": f"Пользователь '{username}' удалён"})
    else:
        return jsonify({"error": f"Пользователь '{username}' не найден"}), 404


@app.route("/api/mtproto/rename_user", methods=["POST"])
def api_mtproto_rename_user():
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


# ---------- Xray API ----------
@app.route("/api/xray/users")
def api_xray_users():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    client = get_xui_client()
    if client is None:
        return jsonify({"error": "API 3x-ui недоступно"}), 503
    try:
        clients = client.get_clients(XRAY_INBOUND_ID)
    except Exception as e:
        return jsonify({"error": f"Ошибка получения клиентов: {e}"}), 500
    data = []
    for c in clients:
        email = c.get("email", "")
        uuid_str = c.get("id", "")
        enable = c.get("enable", True)
        link = generate_xray_link(uuid_str)
        conn = sqlite3.connect(DB_PATH)
        c_db = conn.cursor()
        c_db.execute('''
            SELECT u.telegram_id, k.created_at FROM keys k
            JOIN users u ON k.user_id = u.id
            WHERE k.protocol='xray' AND json_extract(k.key_data, '$.email') = ?
        ''', (email,))
        row = c_db.fetchone()
        conn.close()
        telegram_id = row[0] if row else "—"
        created_at_db = row[1] if row and row[1] else None
        if created_at_db:
            created_at = created_at_db
        elif c.get('created_at'):
            created_at = datetime.fromtimestamp(c.get('created_at') / 1000).isoformat()
        else:
            created_at = "—"
        data.append({
            "email": email,
            "uuid": uuid_str,
            "telegram_id": telegram_id,
            "created_at": created_at,
            "enable": enable,
            "link": link
        })
    return jsonify(data)


@app.route("/api/xray/add_user", methods=["POST"])
def api_xray_add_user():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    email = request.json.get("email", "").strip()
    if not email:
        return jsonify({"error": "Email обязателен"}), 400
    client = get_xui_client()
    if client is None:
        return jsonify({"error": "API 3x-ui недоступно"}), 503
    try:
        uuid_str = client.add_client(XRAY_INBOUND_ID, email)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT OR IGNORE INTO users (username, telegram_id, created_at) VALUES (?, 'web', ?)",
              (email, now))
    c.execute("SELECT id FROM users WHERE username = ?", (email,))
    user_id = c.fetchone()[0]
    key_data = json.dumps({"email": email, "uuid": uuid_str})
    c.execute("INSERT INTO keys (user_id, protocol, key_data, created_at) VALUES (?, 'xray', ?, ?)",
              (user_id, key_data, now))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Клиент {email} добавлен", "uuid": uuid_str})


@app.route("/api/xray/delete_user", methods=["POST"])
def api_xray_delete_user():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    email = request.json.get("email")
    if not email:
        return jsonify({"error": "Email не указан"}), 400
    client = get_xui_client()
    if client is None:
        return jsonify({"error": "API 3x-ui недоступно"}), 503
    try:
        success = client.remove_client(XRAY_INBOUND_ID, email)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if success:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE keys SET status='revoked' WHERE protocol='xray' AND json_extract(key_data, '$.email') = ?",
                  (email,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Клиент {email} удалён"})
    else:
        return jsonify({"error": "Не удалось удалить клиента"}), 400


@app.route("/api/xray/rename_user", methods=["POST"])
def api_xray_rename_user():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    old_email = request.json.get("old_email", "").strip()
    new_email = request.json.get("new_email", "").strip()
    if not old_email or not new_email:
        return jsonify({"error": "Старый и новый email обязательны"}), 400
    client = get_xui_client()
    if client is None:
        return jsonify({"error": "API 3x-ui недоступно"}), 503
    try:
        clients = client.get_clients(XRAY_INBOUND_ID)
    except Exception as e:
        return jsonify({"error": f"Не удалось получить список клиентов: {e}"}), 500
    client_to_update = None
    for c in clients:
        if c.get("email") == old_email:
            client_to_update = c
            break
    if not client_to_update:
        return jsonify({"error": f"Клиент {old_email} не найден"}), 404
    try:
        client.update_client(XRAY_INBOUND_ID, client_to_update['id'], new_email)
    except Exception as e:
        return jsonify({"error": f"Ошибка при обновлении: {e}"}), 500
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET username = ? WHERE username = ?", (new_email, old_email))
    c.execute(
        "UPDATE keys SET key_data = json_set(key_data, '$.email', ?) WHERE protocol='xray' AND json_extract(key_data, '$.email') = ?",
        (new_email, old_email))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Клиент переименован в {new_email}"})


# ---------- Заглушка для Hysteria2 API (чтобы не было 500) ----------
@app.route("/api/hysteria2/users")
def api_hysteria2_users():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify([])  # пока нет данных


# ---------- Общие API ----------
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
        resp = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                             data={"chat_id": tid, "text": f"✉️ Администратор: {message}"}, timeout=5)
        if resp.status_code == 200:
            return jsonify({"success": True, "message": f"Сообщение отправлено пользователю '{username}'"})
        else:
            return jsonify({"error": f"Ошибка Telegram: {resp.text}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/restart_server", methods=["POST"])
def api_restart_server():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    subprocess.run(["reboot"], capture_output=True)
    return jsonify({"success": True, "message": "Сервер перезагружается..."})


# ---------- Страницы протоколов ----------
@app.route("/mtproto")
def mtproto_panel():
    if not check_auth():
        return "", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}
    return render_template("mtproto.html")


@app.route("/xray")
def xray_panel():
    if not check_auth():
        return "", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}
    return render_template("xray.html")


@app.route("/hysteria2")
def hysteria2_panel():
    if not check_auth():
        return "", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}
    return render_template("hysteria2.html")


if __name__ == "__main__":
    print("=" * 50)
    print(f"Container name: {CONTAINER_NAME}")
    print(f"Domain: {DOMAIN}, Port: {PORT}, IP: {SERVER}")
    print(f"Starting web admin on http://0.0.0.0:{FLASK_PORT}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)
