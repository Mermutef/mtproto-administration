"""Telegram bot command and callback handlers.

This package contains all handlers for the Telegram bot, organised
by domain:

* ``user_handlers`` — commands usable by regular users in private chat.
* ``admin_handlers`` — admin-only commands for the admin group.
* ``callback_handlers`` — dispatcher for inline button callbacks.
* ``admin_callbacks`` — admin callback actions (approve, reject, revoke).
* ``private_callbacks`` — user callback actions (cancel request, request key).
"""

from app.handlers.user_handlers import start, request_key, status_command, cancel_command, mykeys_command
from app.handlers.admin_handlers import start_admin, adduser_command, users_command, revoke_command, info_command
from app.handlers.callback_handlers import button_callback, unknown
