"""Flask web panel entry point.

Provides the administrative web interface with Basic Auth protection.
Protocol-specific API endpoints are registered via Blueprints from
``app.web``.

Endpoints:
    GET  /                        — Admin dashboard index
    GET  /mtproto                 — MTProto panel page
    GET  /xray                    — Xray panel page
    GET  /hysteria2               — Hysteria2 panel page
    POST /api/broadcast           — Broadcast a message to all users
    POST /api/send_to             — Send a message to a specific user
    POST /api/restart_server      — Reboot the server
"""

import secrets
import sqlite3
import threading
import time
import logging
import requests
import subprocess
import traceback
from functools import wraps
from datetime import datetime
from flask import Flask, request, render_template, jsonify
from werkzeug.exceptions import HTTPException
from app.config import (
    ADMIN_PASSWORD, FLASK_PORT, DB_PATH, TOKEN,
    get_active_protocols
)
import app.db as db
from app.web import register_all_blueprints

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.secret_key = secrets.token_hex(16)

NOISY_PATHS = {'/robots.txt', '/favicon.ico', '/.well-known/change-password'}


def check_auth():
    """Verify HTTP Basic Auth credentials.

    Returns:
        True if credentials match, False otherwise.
    """
    auth = request.authorization
    if not auth or auth.username != "admin" or auth.password != ADMIN_PASSWORD:
        return False
    return True


def auth_required(func):
    """Decorator that enforces HTTP Basic Authentication.

    On failure returns 401 with a ``WWW-Authenticate`` header and
    logs the attempt.

    Args:
        func: The view function to protect.

    Returns:
        The wrapped function.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not check_auth():
            app.logger.warning(f"Unauthorized access attempt from {request.remote_addr} to {request.path}")
            return "Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}
        return func(*args, **kwargs)
    return wrapper


@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Return a JSON error response for HTTP exceptions.

    Args:
        e: The HTTP exception.

    Returns:
        A tuple ``(json_response, status_code, headers)``.
    """
    if e.code == 401:
        return "Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}
    return jsonify({"error": e.description}), e.code


@app.errorhandler(Exception)
def handle_exception(e):
    """Catch-all handler for unhandled exceptions.

    Logs the traceback and returns a generic 500 error.

    Args:
        e: The exception.
    """
    if isinstance(e, HTTPException):
        return handle_http_exception(e)
    tb = traceback.format_exc()
    app.logger.error(f"Unhandled Exception: {tb}")
    return jsonify({"error": "Internal Server Error"}), 500


@app.before_request
def filter_noisy():
    """Silently return 200 for common crawler paths."""
    if request.path in NOISY_PATHS:
        return "", 200


# ─── register modular Blueprints for all services ───────────────────
register_all_blueprints(app, auth_decorator=auth_required)


# ─── panel pages ────────────────────────────────────────────────────

@app.route("/")
@auth_required
def index():
    """Render the admin dashboard."""
    return render_template("index.html")


@app.route("/mtproto")
@auth_required
def mtproto_panel():
    """Render the MTProto proxy management panel."""
    return render_template("mtproto.html")


@app.route("/xray")
@auth_required
def xray_panel():
    """Render the Xray management panel."""
    return render_template("xray.html")


@app.route("/trojan")
@auth_required
def trojan_panel():
    """Render the Trojan management panel."""
    return render_template("trojan.html")


@app.route("/hysteria2")
@auth_required
def hysteria2_panel():
    """Render the Hysteria2 management panel."""
    return render_template("hysteria2.html")


# ─── common API endpoints ───────────────────────────────────────────

@app.route("/api/broadcast", methods=["POST"])
@auth_required
def api_broadcast():
    """Broadcast a plain-text message to all users with a known Telegram ID.

    Request body::

        {"message": "Hello everyone"}

    Returns:
        JSON with success status and user count.
    """
    message = request.json.get("message", "").strip()
    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400
    users = db.get_all_users_with_telegram()
    if not users:
        return jsonify({"error": "No users to broadcast to"}), 400

    def send():
        for username, tid in users:
            try:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                              data={"chat_id": tid, "text": f"📢 Admin: {message}"}, timeout=3)
                time.sleep(0.05)
            except Exception as e:
                logging.warning(f"Broadcast failed for {username} ({tid}): {e}")

    threading.Thread(target=send).start()
    return jsonify({"success": True, "message": f"Broadcast started for {len(users)} users"})


@app.route("/api/send_to", methods=["POST"])
@auth_required
def api_send_to():
    """Send a private message to a specific user by username.

    Request body::

        {"username": "john", "message": "Hello"}

    Returns:
        JSON with success status or error.
    """
    username = request.json.get("username", "").strip()
    message = request.json.get("message", "").strip()
    if not username or not message:
        return jsonify({"error": "Both fields are required"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if not row or row[0] in ('unknown', 'web', '—'):
        return jsonify({"error": f"User '{username}' not found or has no telegram_id"}), 404
    tid = row[0]
    try:
        resp = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                             data={"chat_id": tid, "text": f"✉️ Admin: {message}"}, timeout=5)
        if resp.status_code == 200:
            return jsonify({"success": True, "message": f"Message sent to '{username}'"})
        else:
            return jsonify({"error": f"Telegram error: {resp.text}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/restart_server", methods=["POST"])
@auth_required
def api_restart_server():
    """Reboot the server immediately.

    Returns:
        JSON confirming the reboot has been triggered.
    """
    subprocess.run(["reboot"], capture_output=True)
    return jsonify({"success": True, "message": "Server is rebooting..."})


@app.context_processor
def inject_active_protocols():
    """Inject the list of active protocol names into all templates.

    Returns:
        A dict with key ``active_protocols``.
    """
    return dict(active_protocols=get_active_protocols())


if __name__ == "__main__":
    from app.config import DOMAIN, PORT, SERVER, CONTAINER_NAME
    print("=" * 50)
    print(f"Container name: {CONTAINER_NAME}")
    print(f"Domain: {DOMAIN}, Port: {PORT}, IP: {SERVER}")
    print(f"Starting web admin on http://0.0.0.0:{FLASK_PORT}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)
