"""Xray web API Blueprint.

Provides REST endpoints for managing Xray clients.

Endpoints:
    GET    /api/xray/users       — list all clients
    POST   /api/xray/add_user    — create a client
    POST   /api/xray/delete_user — delete a client
    POST   /api/xray/rename_user — rename a client

Note: The frontend expects ``email`` as the identifier field in
requests, and responses include ``email``, ``uuid``, ``telegram_id``,
``created_at``, ``enable``, and ``link``.
"""

from flask import Blueprint, jsonify, request
from app.services.xray import xray_service
from app.locales.ru import MESSAGES

bp = Blueprint("xray_api", __name__, url_prefix="/api/xray")


@bp.route("/users")
def list_users():
    return jsonify(xray_service.get_users())


@bp.route("/add_user", methods=["POST"])
def add_user():
    email = request.json.get("email", "").strip()
    if not email:
        return jsonify({"error": MESSAGES["web_email_empty"]}), 400
    success, result = xray_service.create_user(email, telegram_id="web")
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
    if xray_service.delete_user(email):
        return jsonify({"success": True, "message": MESSAGES["web_client_deleted"].format(email=email)})
    return jsonify({"error": MESSAGES["web_client_not_found"].format(email=email)}), 404


@bp.route("/rename_user", methods=["POST"])
def rename_user():
    old_email = request.json.get("old_email", "").strip()
    new_email = request.json.get("new_email", "").strip()
    if not old_email or not new_email:
        return jsonify({"error": MESSAGES["web_old_new_email_required"]}), 400
    success, msg = xray_service.rename_user(old_email, new_email)
    if success:
        return jsonify({"success": True, "message": msg})
    return jsonify({"error": msg}), 400
