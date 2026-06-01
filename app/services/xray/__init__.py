"""Xray (VLESS Reality) service implementation.

Manages Xray clients through the 3x-ui panel API.
Each client is identified by an ``email`` field (used as ``username``
in the generic service interface).

Exports:
    xray_service: Singleton XrayService instance.
"""

import json
import sqlite3
import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from app.config import DB_PATH, XRAY_INBOUND_ID, XRAY_SUB_URL_BASE, XRAY_ENABLED
from app.services.base import BaseVpnService
from app.x_ui_manager import XUIClient, get_xui_client
import logging


class XrayService(BaseVpnService):
    """Xray (VLESS Reality) client management via 3x-ui API.

    Communicates with the 3x-ui panel to create, list, update,
    delete clients and manage their subscription links.
    """

    protocol_name = "xray"
    display_name = "Xray"
    emoji = "🌐"

    @property
    def enabled(self) -> bool:
        """Whether Xray is enabled via the ``XRAY_ENABLED`` env var."""
        return XRAY_ENABLED

    def _get_xui(self) -> Optional[XUIClient]:
        """Get a thread-local 3x-ui API client."""
        return get_xui_client()

    def create_user(self, username: str, telegram_id: str = "unknown") -> Tuple[bool, str]:
        """Create an Xray client via the 3x-ui API.

        Args:
            username: Base name used to generate the email.
            telegram_id: Telegram user ID.

        Returns:
            (True, subscribe_url) on success,
            (False, error_message) on failure.
        """
        xui = self._get_xui()
        if not xui:
            return False, "No connection to 3x-ui"

        base_name = re.sub(r'[^a-zA-Z0-9_]', '_', username)
        email = f"{base_name}_{telegram_id}"

        try:
            existing = xui.get_clients(XRAY_INBOUND_ID)
            for c in existing:
                if c.get("email") == email:
                    return False, f"Client with email '{email}' already exists"
        except Exception as e:
            return False, f"Error checking existing clients: {e}"

        try:
            result = xui.add_client(XRAY_INBOUND_ID, email)
            uuid_str = result["uuid"]
            sub_id = result["sub_id"]
        except Exception as e:
            return False, str(e)

        user_id = self._ensure_user_in_db(email, telegram_id)
        key_data = {"email": email, "uuid": uuid_str, "sub_id": sub_id}
        now = datetime.now().isoformat()

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO keys (user_id, protocol, key_data, created_at) VALUES (?, ?, ?, ?)",
            (user_id, self.protocol_name, json.dumps(key_data), now),
        )
        conn.commit()
        conn.close()

        subscribe_url = f"{XRAY_SUB_URL_BASE}{sub_id}" if sub_id else ""
        return True, subscribe_url

    def delete_user(self, username: str) -> bool:
        """Delete an Xray client from the 3x-ui panel.

        Args:
            username: The client email to delete.

        Returns:
            True if the client was removed.
        """
        xui = self._get_xui()
        if not xui:
            return False
        email = username
        try:
            xui.remove_client(XRAY_INBOUND_ID, email)
        except Exception as e:
            logging.error(f"Error removing Xray client {email}: {e}")
            return False
        self._revoke_keys(email)
        return True

    def get_users(self) -> List[Dict[str, Any]]:
        """List all Xray clients from the 3x-ui panel with DB metadata.

        Returns:
            A list of user dicts with ``username``, ``email``, ``uuid``,
            ``telegram_id``, ``created_at``, ``enable``, ``link``, and ``protocol``.
        """
        xui = self._get_xui()
        if not xui:
            return []
        try:
            clients = xui.get_clients(XRAY_INBOUND_ID)
        except Exception:
            return []

        # Single batch query to gather DB metadata for all clients
        emails = [c.get("email", "") for c in clients if c.get("email")]
        db_map = {}  # email -> (telegram_id, created_at, sub_id)
        if emails:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            placeholders = ",".join("?" for _ in emails)
            try:
                c.execute(f'''
                    SELECT u.telegram_id, k.created_at,
                           json_extract(k.key_data, '$.sub_id') as sub_id,
                           json_extract(k.key_data, '$.email') as email
                    FROM keys k
                    JOIN users u ON k.user_id = u.id
                    WHERE k.protocol='xray'
                      AND json_extract(k.key_data, '$.email') IN ({placeholders})
                ''', emails)
                for row in c.fetchall():
                    db_map[row[3]] = (row[0], row[1], row[2])
            finally:
                conn.close()

        data = []
        for c in clients:
            email = c.get("email", "")
            uuid_str = c.get("id", "")
            enable = c.get("enable", True)

            db_row = db_map.get(email)
            if db_row:
                telegram_id, created_at_db, sub_id = db_row
            else:
                telegram_id, created_at_db, sub_id = "—", None, None

            if not sub_id:
                sub_id = self._get_sub_id_from_api(email)
                if sub_id:
                    # Persist the fetched sub_id
                    conn = sqlite3.connect(DB_PATH)
                    try:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE keys SET key_data = json_set(key_data, '$.sub_id', ?) "
                            "WHERE protocol='xray' AND json_extract(key_data, '$.email') = ?",
                            (sub_id, email)
                        )
                        conn.commit()
                    finally:
                        conn.close()

            link = f"{XRAY_SUB_URL_BASE}{sub_id}" if sub_id else ""

            if created_at_db:
                created_at = created_at_db
            elif c.get('created_at'):
                created_at = datetime.fromtimestamp(c['created_at'] / 1000).isoformat()
            else:
                created_at = "—"

            data.append({
                "username": email,
                "email": email,
                "uuid": uuid_str,
                "telegram_id": telegram_id,
                "created_at": created_at,
                "enable": enable,
                "link": link,
                "protocol": self.protocol_name,
            })
        return data

    def rename_user(self, old_username: str, new_username: str) -> Tuple[bool, str]:
        """Rename an Xray client in both 3x-ui and the database.

        Args:
            old_username: Current email.
            new_username: New email.

        Returns:
            (True, message) or (False, error).
        """
        xui = self._get_xui()
        if not xui:
            return False, "3x-ui unavailable"
        try:
            clients = xui.get_clients(XRAY_INBOUND_ID)
        except Exception as e:
            return False, f"Failed to fetch clients: {e}"

        client_to_update = next((c for c in clients if c.get("email") == old_username), None)
        if not client_to_update:
            return False, f"Client {old_username} not found"

        try:
            xui.update_client(XRAY_INBOUND_ID, client_to_update['id'], new_username)
        except Exception as e:
            return False, f"Update error: {e}"

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, old_username))
        c.execute(
            "UPDATE keys SET key_data = json_set(key_data, '$.email', ?) "
            "WHERE protocol='xray' AND json_extract(key_data, '$.email') = ?",
            (new_username, old_username),
        )
        conn.commit()
        conn.close()
        return True, f"Client renamed to {new_username}"

    def get_identifier(self, key_data: Dict[str, Any]) -> str:
        """Extract the email from Xray key data."""
        return key_data.get('email', '')

    def get_link_for_key(self, key_data: Dict[str, Any]) -> str:
        """Build the subscription link from key data.

        Falls back to fetching the sub_id from the API if not cached.
        """
        sub_id = key_data.get('sub_id', '')
        if not sub_id:
            email = key_data.get('email', '')
            sub_id = self._get_sub_id_from_db(email)
        return f"{XRAY_SUB_URL_BASE}{sub_id}" if sub_id else ""

    def format_user_key_message(self, key_data: Dict[str, Any]) -> Tuple[str, str]:
        """Send the standard Xray grant message to the user."""
        from app.locales.ru import MESSAGES
        from app.utils import escape_html
        email = key_data.get('email', '')
        link = key_data.get('_link_override') or self.get_link_for_key(key_data)
        text = MESSAGES["xray_key_granted"].format(email=escape_html(email), subscribe_url=link)
        return text, "HTML"

    def format_admin_created_message(self, identifier: str) -> str:
        from app.locales.ru import MESSAGES
        return MESSAGES["xray_key_created_sent"].format(username=identifier)

    def format_admin_direct_message(self, identifier: str, link: str) -> str:
        from app.locales.ru import MESSAGES
        return MESSAGES["xray_client_added"].format(email=identifier, subscribe_url=link)

    def validate_identifier(self, identifier: str) -> bool:
        """Accept any non-empty identifier for Xray."""
        return len(identifier.strip()) > 0

    def _get_sub_id_from_db(self, email: str) -> str:
        """Look up cached sub_id from the local database."""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT json_extract(key_data, '$.sub_id') FROM keys "
            "WHERE protocol='xray' AND json_extract(key_data, '$.email') = ?",
            (email,),
        )
        row = c.fetchone()
        conn.close()
        return row[0] if row and row[0] else ""

    def _get_sub_id_from_api(self, email: str) -> str:
        """Fetch sub_id directly from the 3x-ui API."""
        xui = self._get_xui()
        if not xui:
            return ""
        try:
            return xui.get_client_sub_id(XRAY_INBOUND_ID, email)
        except Exception:
            return ""


# Singleton
xray_service = XrayService()
