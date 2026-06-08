"""Abstract base for all 3x-ui-managed VPN protocols.

Shared logic for Xray, Trojan, Hysteria2 (and any future 3x-ui
protocol).  Each subclass only needs to provide metadata and a
protocol-specific ``_build_client_payload`` method.

Exports:
    ThreeXUIService: Abstract base class.
"""

import json
import sqlite3
import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from abc import abstractmethod

from app.config import DB_PATH
from app.services.base import BaseVpnService
from app.x_ui_manager import get_xui_client, XUIClient


class ThreeXUIService(BaseVpnService):
    """Service base for protocols managed through the 3x-ui panel API.

    Subclasses **must** define:

    - :attr:`protocol_name`, :attr:`display_name`, :attr:`emoji`
    - :meth:`enabled`
    - :meth:`inbound_id` (property)
    - :meth:`sub_url_base` (property)
    - :meth:`_build_client_payload` — the client dict sent to ``addClient``
    """

    # ── abstract / subclass-supplied ──────────────────────────────

    @property
    @abstractmethod
    def inbound_id(self) -> int:
        """3x-ui inbound ID for this protocol."""

    @property
    @abstractmethod
    def sub_url_base(self) -> str:
        """Base URL for subscription links."""

    @abstractmethod
    def _build_client_payload(self, email: str, uuid_str: str, sub_id: str) -> dict:
        """Build the per-client payload dict for ``addClient``.

        Must include at least ``email``, ``id``, ``enable``, ``subId``.
        """

    # ── 3x-ui client helper ──────────────────────────────────────

    def _get_xui(self) -> Optional[XUIClient]:
        """Get a thread-local 3x-ui API client."""
        return get_xui_client()

    # ── CRUD ──────────────────────────────────────────────────────

    def create_user(self, username: str, telegram_id: str = "unknown") -> Tuple[bool, str]:
        """Create a client via the 3x-ui API.

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
            existing = xui.get_clients(self.inbound_id)
            for c in existing:
                if c.get("email") == email:
                    return False, f"Client with email '{email}' already exists"
        except Exception as e:
            return False, f"Error checking existing clients: {e}"

        try:
            uuid_str, sub_id = self._create_and_get_ids(xui, email)
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

        subscribe_url = f"{self.sub_url_base}{sub_id}" if sub_id else ""
        return True, subscribe_url

    def _create_and_get_ids(self, xui: XUIClient, email: str) -> Tuple[str, str]:
        """Call add_client and return (uuid, sub_id)."""
        result = xui.add_client(self.inbound_id, email)
        return result["uuid"], result["sub_id"]

    def delete_user(self, username: str) -> bool:
        """Delete a client from the 3x-ui panel.

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
            xui.remove_client(self.inbound_id, email)
        except Exception as e:
            logging.error(f"Error removing {self.protocol_name} client {email}: {e}")
            return False
        self._revoke_keys(email)
        return True

    def get_users(self) -> List[Dict[str, Any]]:
        """List all clients from the 3x-ui panel with DB metadata.

        Returns:
            A list of user dicts.
        """
        xui = self._get_xui()
        if not xui:
            return []
        try:
            clients = xui.get_clients(self.inbound_id)
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
                    WHERE k.protocol=?
                      AND json_extract(k.key_data, '$.email') IN ({placeholders})
                ''', [self.protocol_name] + emails)
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
                            "WHERE protocol=? AND json_extract(key_data, '$.email') = ?",
                            (sub_id, self.protocol_name, email)
                        )
                        conn.commit()
                    finally:
                        conn.close()

            link = f"{self.sub_url_base}{sub_id}" if sub_id else ""

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
        """Rename a client in both 3x-ui and the database.

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
            clients = xui.get_clients(self.inbound_id)
        except Exception as e:
            return False, f"Failed to fetch clients: {e}"

        client_to_update = next((c for c in clients if c.get("email") == old_username), None)
        if not client_to_update:
            return False, f"Client {old_username} not found"

        try:
            xui.update_client(self.inbound_id, client_to_update['id'], new_username)
        except Exception as e:
            return False, f"Update error: {e}"

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, old_username))
        c.execute(
            "UPDATE keys SET key_data = json_set(key_data, '$.email', ?) "
            "WHERE protocol=? AND json_extract(key_data, '$.email') = ?",
            (new_username, self.protocol_name, old_username),
        )
        conn.commit()
        conn.close()
        return True, f"Client renamed to {new_username}"

    # ── auxiliary ────────────────────────────────────────────────

    def get_identifier(self, key_data: Dict[str, Any]) -> str:
        """Extract the email from key data."""
        return key_data.get('email', '')

    def get_link_for_key(self, key_data: Dict[str, Any]) -> str:
        """Build the subscription link from key data."""
        sub_id = key_data.get('sub_id', '')
        if not sub_id:
            email = key_data.get('email', '')
            sub_id = self._get_sub_id_from_db(email)
        return f"{self.sub_url_base}{sub_id}" if sub_id else ""

    def format_user_key_message(self, key_data: Dict[str, Any]) -> Tuple[str, str]:
        """Send the standard key-granted message to the user."""
        from app.locales.ru import MESSAGES
        from app.utils import escape_html
        protocol_upper = self.protocol_name.upper()
        msg_key = f"{self.protocol_name}_key_granted"
        email = key_data.get('email', '')
        link = key_data.get('_link_override') or self.get_link_for_key(key_data)
        text = MESSAGES.get(msg_key, "").format(email=escape_html(email), subscribe_url=link)
        return text, "HTML"

    def format_admin_created_message(self, identifier: str) -> str:
        from app.locales.ru import MESSAGES
        return MESSAGES.get(f"{self.protocol_name}_key_created_sent", "").format(username=identifier)

    def format_admin_direct_message(self, identifier: str, link: str) -> str:
        from app.locales.ru import MESSAGES
        return MESSAGES.get(f"{self.protocol_name}_client_added", "").format(email=identifier, subscribe_url=link)

    def validate_identifier(self, identifier: str) -> bool:
        """Accept any non-empty identifier."""
        return len(identifier.strip()) > 0

    # ── internal helpers ──────────────────────────────────────────

    def _get_sub_id_from_db(self, email: str) -> str:
        """Look up cached sub_id from the local database."""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT json_extract(key_data, '$.sub_id') FROM keys "
            "WHERE protocol=? AND json_extract(key_data, '$.email') = ?",
            (self.protocol_name, email),
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
            return xui.get_client_sub_id(self.inbound_id, email)
        except Exception:
            return ""
