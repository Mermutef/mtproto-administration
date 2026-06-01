"""Modular web handler registration for VPN protocol services.

This package provides a factory function that automatically creates
Flask Blueprints for each enabled service and registers them with
the application.

Each service can optionally have a dedicated module at
``app.web.{protocol_name}.py`` exporting a ``bp`` Blueprint object.
If no such module exists, a generic Blueprint with standard CRUD
endpoints is created automatically.
"""

from flask import Blueprint
from app.services.registry import registry


def register_all_blueprints(app, auth_decorator=None):
    """Register Blueprints for all enabled services in the registry.

    For each enabled service, the function first tries to import
    ``app.web.<protocol>`` and use its ``bp`` Blueprint. If that
    fails, a generic Blueprint is created via
    :func:`_create_generic_blueprint`.

    If ``auth_decorator`` is provided, every view function in the
    Blueprint is wrapped with it.

    Args:
        app: The Flask application instance.
        auth_decorator: Optional decorator (callable) to apply to
            every view function. Typically used for HTTP Basic Auth.
    """
    import importlib

    for protocol_name, service in registry.get_all().items():
        if not service.enabled:
            continue

        module_name = f"app.web.{protocol_name}"
        try:
            mod = importlib.import_module(module_name)
            bp = getattr(mod, "bp", None)
            if bp is None:
                bp = _create_generic_blueprint(service)
        except (ImportError, ModuleNotFoundError):
            bp = _create_generic_blueprint(service)

        if auth_decorator:
            AUTH_WRAPPED_ATTR = "_auth_wrapped"
            for name, func in list(bp.view_functions.items()):
                if not getattr(func, AUTH_WRAPPED_ATTR, False):
                    wrapped = auth_decorator(func)
                    setattr(wrapped, AUTH_WRAPPED_ATTR, True)
                    bp.view_functions[name] = wrapped

        app.register_blueprint(bp)


def _create_generic_blueprint(service):
    """Create a generic CRUD Blueprint for a service without a dedicated module.

    The generated endpoints match the frontend's expected API contract:

    * ``GET    /api/{protocol}/users``       — list users
    * ``POST   /api/{protocol}/add_user``    — create user
    * ``POST   /api/{protocol}/delete_user`` — delete user
    * ``POST   /api/{protocol}/rename_user`` — rename user

    Args:
        service: A :class:`~app.services.base.BaseVpnService` instance.

    Returns:
        A configured :class:`flask.Blueprint` object.
    """
    from flask import jsonify, request
    from app.locales.ru import MESSAGES

    bp = Blueprint(
        f"{service.protocol_name}_api",
        __name__,
        url_prefix=f"/api/{service.protocol_name}",
    )

    @bp.route("/users")
    def list_users():
        return jsonify(service.get_users())

    @bp.route("/add_user", methods=["POST"])
    def add_user():
        username = request.json.get("username", "").strip()
        if not username:
            return jsonify({"error": MESSAGES["web_login_empty"]}), 400
        if not service.validate_identifier(username):
            return jsonify({"error": MESSAGES["web_invalid_identifier"].format(identifier=username)}), 400
        success, result = service.create_user(username, telegram_id="web")
        if success:
            return jsonify({
                "success": True,
                "message": MESSAGES["web_user_added"].format(username=username),
                "link": result
            })
        return jsonify({"error": result}), 400

    @bp.route("/delete_user", methods=["POST"])
    def delete_user():
        username = request.json.get("username", "").strip()
        if not username:
            return jsonify({"error": MESSAGES["web_identifier_required"]}), 400
        if service.delete_user(username):
            return jsonify({
                "success": True,
                "message": MESSAGES["web_user_deleted"].format(username=username)
            })
        return jsonify({"error": MESSAGES["web_user_not_found"].format(username=username)}), 404

    @bp.route("/rename_user", methods=["POST"])
    def rename_user():
        old_name = request.json.get("old_name", "").strip()
        new_name = request.json.get("new_name", "").strip()
        if not old_name or not new_name:
            return jsonify({"error": MESSAGES["web_old_new_required"]}), 400
        success, msg = service.rename_user(old_name, new_name)
        if success:
            return jsonify({"success": True, "message": msg})
        return jsonify({"error": msg}), 400

    return bp
