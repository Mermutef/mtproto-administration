"""MTProto web API Blueprint.

Provides REST endpoints for managing MTProto proxy users.

Endpoints:
    GET    /api/mtproto/users       — list all users
    POST   /api/mtproto/add_user    — create a user
    POST   /api/mtproto/delete_user — delete a user
    POST   /api/mtproto/rename_user — rename a user
"""

from flask import Blueprint, jsonify, request
from app.services.mtproto import mtproto_service
from app.locales.ru import MESSAGES

bp = Blueprint("mtproto_api", __name__, url_prefix="/api/mtproto")


@bp.route("/users")
def list_users():
    return jsonify(mtproto_service.get_users())


@bp.route("/add_user", methods=["POST"])
def add_user():
    username = request.json.get("username", "").strip()
    if not username:
        return jsonify({"error": MESSAGES["web_login_empty"]}), 400
    success, result = mtproto_service.create_user(username, telegram_id="web")
    if success:
        return jsonify({"success": True, "message": MESSAGES["web_user_added"].format(username=username), "link": result})
    return jsonify({"error": result}), 400


@bp.route("/delete_user", methods=["POST"])
def delete_user():
    username = request.json.get("username", "").strip()
    if not username:
        return jsonify({"error": MESSAGES["web_identifier_required"]}), 400
    if mtproto_service.delete_user(username):
        return jsonify({"success": True, "message": MESSAGES["web_user_deleted"].format(username=username)})
    return jsonify({"error": MESSAGES["web_user_not_found"].format(username=username)}), 404


@bp.route("/rename_user", methods=["POST"])
def rename_user():
    old_name = request.json.get("old_name", "").strip()
    new_name = request.json.get("new_name", "").strip()
    if not old_name or not new_name:
        return jsonify({"error": MESSAGES["web_old_new_required"]}), 400
    success, msg = mtproto_service.rename_user(old_name, new_name)
    if success:
        return jsonify({"success": True, "message": msg})
    return jsonify({"error": msg}), 400
