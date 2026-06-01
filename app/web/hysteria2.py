"""Hysteria2 web API Blueprint.

Provides REST endpoints for managing Hysteria2 users.
Currently returns empty results as Hysteria2 is not yet implemented.

Endpoints:
    GET    /api/hysteria2/users       — list all users
    POST   /api/hysteria2/add_user    — create a user
    POST   /api/hysteria2/delete_user — delete a user
"""

from flask import Blueprint, jsonify, request
from app.services.hysteria2 import hysteria2_service
from app.locales.ru import MESSAGES

bp = Blueprint("hysteria2_api", __name__, url_prefix="/api/hysteria2")


@bp.route("/users")
def list_users():
    return jsonify(hysteria2_service.get_users())


@bp.route("/add_user", methods=["POST"])
def add_user():
    username = request.json.get("username", "").strip()
    if not username:
        return jsonify({"error": MESSAGES["web_name_empty"]}), 400
    success, result = hysteria2_service.create_user(username, telegram_id="web")
    if success:
        return jsonify({"success": True, "message": MESSAGES["web_user_added"].format(username=username), "link": result})
    return jsonify({"error": result}), 400


@bp.route("/delete_user", methods=["POST"])
def delete_user():
    username = request.json.get("username", "").strip()
    if not username:
        return jsonify({"error": MESSAGES["web_identifier_required"]}), 400
    if hysteria2_service.delete_user(username):
        return jsonify({"success": True, "message": MESSAGES["web_user_deleted"].format(username=username)})
    return jsonify({"error": MESSAGES["web_user_not_found"].format(username=username)}), 404
