"""Unified Panel Blueprint — single API for all protocols.

Replaces the per-protocol Blueprints with a single set of RESTful
endpoints.  Old endpoints (``/api/{proto}/users``) are kept for
backward compatibility.

Endpoints:
    GET    /api/panel/summary              — dashboard stats
    GET    /api/panel/{proto}/users        — list (paginated)
    POST   /api/panel/{proto}/users        — create user
    DELETE /api/panel/{proto}/users        — delete user
    PATCH  /api/panel/{proto}/users        — rename user
"""

from flask import Blueprint, jsonify, request
from app.services.registry import registry
from app.config import get_active_protocols, DB_PATH
from app.locales.ru import MESSAGES
import sqlite3
import json

bp = Blueprint("panel_api", __name__, url_prefix="/api/panel")


# ── helpers ────────────────────────────────────────────────────────

def _get_svc(protocol):
    svc = registry.get(protocol)
    if not svc:
        return None
    return svc


def _error(msg, code=400):
    return jsonify({"error": msg}), code


# ── All users (merged across protocols) ──────────────────────────

@bp.route("/users/all")
def all_users():
    """Return one row per user with a protocol map."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.username, u.telegram_id, u.created_at,
               k.protocol, k.status, k.key_data
        FROM users u
        LEFT JOIN keys k ON u.id = k.user_id
    """)
    rows = c.fetchall()
    conn.close()

    users = {}
    for uid, uname, tid, created, proto, status, key_data in rows:
        if uid not in users:
            users[uid] = {
                "id": uid,
                "username": uname,
                "email": uname,
                "telegram_id": tid or "unknown",
                "created_at": created or "—",
                "protocols": {},
            }
        if proto:
            users[uid]["protocols"][proto] = {
                "status": status,
                "key_data": json.loads(key_data) if key_data else {},
            }

    return jsonify(list(users.values()))


# ── Toggle user protocol ─────────────────────────────────────────

@bp.route("/<proto>/toggle", methods=["POST"])
def toggle_protocol(proto):
    svc = _get_svc(proto)
    if not svc:
        return _error("Protocol not found", 404)

    data = request.json or {}
    username = data.get("username", "").strip()
    enable = data.get("enable", True)

    if not username:
        return _error("username required")

    if not enable:
        svc.delete_user(username)
    else:
        # Try to create — if email in use, attach
        try:
            svc.create_user(username, telegram_id="web")
        except Exception as e:
            return _error(str(e))

    return jsonify({"success": True, "message": f"{proto}: {'enabled' if enable else 'disabled'}"})


# ── Summary ────────────────────────────────────────────────────────

@bp.route("/summary")
def summary():
    """Return aggregate counts across all protocols."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_keys = c.execute("SELECT COUNT(*) FROM keys WHERE status='active'").fetchone()[0]
    protocols = {}
    for proto in get_active_protocols():
        users = c.execute(
            "SELECT COUNT(DISTINCT user_id) FROM keys WHERE protocol=?", (proto,)
        ).fetchone()[0]
        active = c.execute(
            "SELECT COUNT(*) FROM keys WHERE protocol=? AND status='active'", (proto,)
        ).fetchone()[0]
        protocols[proto] = {"users": users, "active": active}
    conn.close()
    return jsonify({
        "total_users": total_users,
        "active_keys": active_keys,
        "protocols": protocols,
    })


# ── List users ─────────────────────────────────────────────────────

@bp.route("/<proto>/users", methods=["GET"])
def list_users(proto):
    svc = _get_svc(proto)
    if not svc:
        return _error(f"Protocol '{proto}' not found", 404)
    try:
        users = svc.get_users()
    except Exception as e:
        return _error(str(e), 500)

    # Search filter
    search = request.args.get("search", "").strip().lower()
    if search:
        users = [u for u in users if search in u.get("username", "").lower()
                 or search in u.get("email", "").lower()
                 or search in str(u.get("telegram_id", ""))]

    # Sort
    sort = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")
    reverse = order == "desc"
    if sort in ("username", "email", "created_at", "telegram_id"):
        users.sort(key=lambda u: u.get(sort) or "", reverse=reverse)

    # Pagination
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    total = len(users)
    start = (page - 1) * per_page
    page_users = users[start:start + per_page]

    return jsonify({
        "users": page_users,
        "total": total,
        "page": page,
        "per_page": per_page,
    })


# ── Create user ────────────────────────────────────────────────────

@bp.route("/<proto>/users", methods=["POST"])
def add_user(proto):
    svc = _get_svc(proto)
    if not svc:
        return _error(f"Protocol '{proto}' not found", 404)

    identifier = (request.json or {}).get("identifier", "").strip()
    if not identifier:
        return _error("identifier is required")

    success, result = svc.create_user(identifier, telegram_id="web")
    if success:
        return jsonify({"success": True, "message": "User added", "link": result})
    return _error(result)


# ── Delete user ────────────────────────────────────────────────────

@bp.route("/<proto>/users", methods=["DELETE"])
def delete_user(proto):
    svc = _get_svc(proto)
    if not svc:
        return _error(f"Protocol '{proto}' not found", 404)

    identifier = (request.json or {}).get("identifier", "").strip()
    if not identifier:
        return _error("identifier is required")

    if svc.delete_user(identifier):
        return jsonify({"success": True, "message": "User deleted"})
    return _error("User not found", 404)


# ── Rename user ────────────────────────────────────────────────────

@bp.route("/<proto>/users", methods=["PATCH"])
def rename_user(proto):
    svc = _get_svc(proto)
    if not svc:
        return _error(f"Protocol '{proto}' not found", 404)

    data = request.json or {}
    identifier = data.get("identifier", "").strip()
    new_identifier = data.get("new_identifier", "").strip()
    if not identifier or not new_identifier:
        return _error("identifier and new_identifier are required")

    success, msg = svc.rename_user(identifier, new_identifier)
    if success:
        return jsonify({"success": True, "message": msg})
    return _error(msg)
