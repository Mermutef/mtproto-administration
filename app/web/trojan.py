"""Trojan web API Blueprint.

Endpoints:
    GET    /api/trojan/users       — list all clients
    POST   /api/trojan/add_user    — create a client
    POST   /api/trojan/delete_user — delete a client
    POST   /api/trojan/rename_user — rename a client
"""

from flask import Blueprint, jsonify, request
from app.services.trojan import trojan_service
from app.locales.ru import MESSAGES

bp = Blueprint("trojan_api", __name__, url_prefix="/api/trojan")


@bp.route("/users")
def list_users():
    return jsonify(trojan_service.get_users())


@bp.route("/add_user", methods=["POST"])
def add_user():
    email = request.json.get("email", "").strip()
    if not email:
        return jsonify({"error": MESSAGES["web_email_empty"]}), 400
    success, result = trojan_service.create_user(email, telegram_id="web")
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
    if trojan_service.delete_user(email):
        return jsonify({"success": True, "message": MESSAGES["web_client_deleted"].format(email=email)})
    return jsonify({"error": MESSAGES["web_client_not_found"].format(email=email)}), 404


@bp.route("/rename_user", methods=["POST"])
def rename_user():
    old_email = request.json.get("old_email", "").strip()
    new_email = request.json.get("new_email", "").strip()
    if not old_email or not new_email:
        return jsonify({"error": MESSAGES["web_old_new_email_required"]}), 400
    success, msg = trojan_service.rename_user(old_email, new_email)
    if success:
        return jsonify({"success": True, "message": msg})
    return jsonify({"error": msg}), 400
