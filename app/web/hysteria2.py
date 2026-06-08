"""Hysteria2 web API Blueprint.

Endpoints:
    GET    /api/hysteria2/users       — list all clients
    POST   /api/hysteria2/add_user    — create a client
    POST   /api/hysteria2/delete_user — delete a client
    POST   /api/hysteria2/rename_user — rename a client
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
    email = request.json.get("email", "").strip()
    if not email:
        return jsonify({"error": MESSAGES["web_email_empty"]}), 400
    success, result = hysteria2_service.create_user(email, telegram_id="web")
    if success:
        return jsonify({
            "success": True,
            "message": MESSAGES["web_client_added"].format(email=email),
            "link": result,
            "subscribe_url": result,
        })
    return jsonify({"error": result}), 400


@bp.route("/delete_user", methods=["POST"])
def delete_user():
    email = request.json.get("email", "").strip()
    if not email:
        return jsonify({"error": MESSAGES["web_identifier_required"]}), 400
    if hysteria2_service.delete_user(email):
        return jsonify({"success": True, "message": MESSAGES["web_client_deleted"].format(email=email)})
    return jsonify({"error": MESSAGES["web_client_not_found"].format(email=email)}), 404


@bp.route("/rename_user", methods=["POST"])
def rename_user():
    old_email = request.json.get("old_email", "").strip()
    new_email = request.json.get("new_email", "").strip()
    if not old_email or not new_email:
        return jsonify({"error": MESSAGES["web_old_new_email_required"]}), 400
    success, msg = hysteria2_service.rename_user(old_email, new_email)
    if success:
        return jsonify({"success": True, "message": msg})
    return jsonify({"error": msg}), 400
