"""MTProto proxy service implementation.

Provides user management for the MTProto proxy running in a Docker
container. Uses ``config_manager`` to read/write the proxy's config
file and reload the container on changes.

Exports:
    mtproto_service: Singleton MtprotoService instance.
"""

import secrets
import json
import sqlite3
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime
from app.config import DB_PATH, MTP_ENABLED
from app.services.base import BaseVpnService
from app.services.mtproto.config_manager import (
    load_users, add_user, remove_user, rename_user,
    generate_unique_username, get_proxy_link,
)
import app.db as db


class MtprotoService(BaseVpnService):
    """MTProto proxy user management service.

    Communicates with the MTProto proxy Docker container by writing
    its Python configuration file and sending a SIGHUP signal (or
    restarting the container) to apply changes.
    """

    protocol_name = "mtproto"
    display_name = "MTProto"
    emoji = "🛡️"

    @property
    def enabled(self) -> bool:
        """Whether MTProto is enabled via the ``MTP_ENABLED`` env var."""
        return MTP_ENABLED

    def create_user(self, username: str, telegram_id: str = "unknown") -> Tuple[bool, str]:
        """Create an MTProto proxy user.

        Args:
            username: Desired login name.
            telegram_id: Telegram user ID.

        Returns:
            (True, proxy_link) on success,
            (False, error_string) on failure.
        """
        secret = secrets.token_hex(16)
        username = generate_unique_username(username)

        if not add_user(username, secret):
            return False, "Failed to add user to proxy config"

        user_id = self._ensure_user_in_db(username, telegram_id)
        key_data = {"secret": secret, "username": username}
        now = datetime.now().isoformat()

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO keys (user_id, protocol, key_data, created_at) VALUES (?, ?, ?, ?)",
            (user_id, self.protocol_name, json.dumps(key_data), now),
        )
        conn.commit()
        conn.close()

        link = get_proxy_link(secret)
        return True, link

    def delete_user(self, username: str) -> bool:
        """Delete an MTProto user and revoke their requests.

        Args:
            username: The user to delete.

        Returns:
            True if the user was found and removed.
        """
        if not remove_user(username):
            return False

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, telegram_id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if row:
            user_id, telegram_id = row
            if telegram_id not in ('unknown', 'web', '—'):
                db.revoke_user_requests(telegram_id)
            c.execute("DELETE FROM keys WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True

    def get_users(self) -> List[Dict[str, Any]]:
        """List all MTProto users with their keys and metadata.

        Returns:
            A list of user dicts containing ``username``, ``secret``,
            ``telegram_id``, ``created_at``, ``request_status``,
            ``link``, and ``protocol``.
        """
        users = load_users()
        result = []
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

            link = get_proxy_link(secret)
            result.append({
                "username": username,
                "secret": secret,
                "telegram_id": telegram_id,
                "created_at": created_at if created_at else "—",
                "request_status": request_status,
                "link": link,
                "protocol": self.protocol_name,
            })
        return result

    def rename_user(self, old_username: str, new_username: str) -> Tuple[bool, str]:
        """Rename a user in both the proxy config and the database.

        Args:
            old_username: Current username.
            new_username: New username.

        Returns:
            (True, message) or (False, error).
        """
        if rename_user(old_username, new_username):
            return True, f"User renamed to '{new_username}'"
        return False, "Error during rename"

    def get_identifier(self, key_data: Dict[str, Any]) -> str:
        return key_data.get('username', '')

    def get_link_for_key(self, key_data: Dict[str, Any]) -> str:
        secret = key_data.get('secret', '')
        return get_proxy_link(secret) if secret else ""

    def format_user_key_message(self, key_data: Dict[str, Any]) -> Tuple[str, str]:
        """Send the standard MTProto grant message to the user."""
        from app.locales.ru import MESSAGES
        from app.utils import escape_html
        username = key_data.get('username', '')
        link = key_data.get('_link_override') or self.get_link_for_key(key_data)
        text = MESSAGES["mtp_key_granted"].format(username=escape_html(username), link=link)
        return text, "HTML"

    def format_admin_created_message(self, identifier: str) -> str:
        from app.locales.ru import MESSAGES
        return MESSAGES["mtp_key_created_sent"].format(username=identifier)

    def format_admin_direct_message(self, identifier: str, link: str) -> str:
        from app.locales.ru import MESSAGES
        return MESSAGES["mtproto_user_created"].format(username=identifier, link=link)

    def validate_identifier(self, identifier: str) -> bool:
        return bool(re.match(r'^[a-zA-Z0-9_]+$', identifier))

    # -- helpers used directly by bot handlers -----------------------

    def generate_unique_username(self, base: str) -> str:
        """Generate a unique username from a base name.

        Args:
            base: Preferred name.

        Returns:
            A username that doesn't exist in the proxy config yet.
        """
        return generate_unique_username(base)

    def user_exists(self, username: str) -> bool:
        """Check if a username is already taken.

        Args:
            username: The candidate name.

        Returns:
            True if the name is in use.
        """
        return username in load_users()

    def sync_all_users(self) -> None:
        """Synchronise the database with the proxy config file.

        Creates missing users and keys, and adds missing users from
        the database back to the proxy config.
        """
        from app.services.mtproto.config_manager import sync_all_users
        sync_all_users()


# Singleton
mtproto_service = MtprotoService()
