"""Abstract base for all 3x-ui-managed VPN protocols.

Uses the ``py3xui`` library to communicate with the 3x-ui panel API.
Each subclass only needs to provide metadata and a protocol-specific
``_flow`` property if needed.

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

from py3xui import Client

from app.config import DB_PATH
from app.services.base import BaseVpnService
from app.x_ui_manager import get_xui, make_client


class ThreeXUIService(BaseVpnService):
    """Service base for protocols managed through the 3x-ui panel API.

    Subclasses **must** define:
    - :attr:`protocol_name`, :attr:`display_name`, :attr:`emoji`
    - :meth:`enabled`
    - :meth:`inbound_id` (property)
    - :meth:`sub_url_base` (property)
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

    @property
    def _flow(self) -> str:
        """Xray ``flow`` setting (e.g. ``xtls-rprx-vision`` for VLESS)."""
        return ""

    # ── 3x-ui helpers ────────────────────────────────────────────

    def _get_api(self):
        """Get a thread-local py3xui.Api instance."""
        return get_xui()

    # ── CRUD ──────────────────────────────────────────────────────

    def create_user(self, username: str, telegram_id: str = "unknown") -> Tuple[bool, str]:
        """Create a client via the 3x-ui API.

        In 3x-ui 3.2.9 email uniqueness is enforced globally across all
        inbounds.  If a client with the given email already exists (e.g.
        in the Xray inbound), we re-use its UUID and attach it to *this*
        inbound instead of creating a duplicate.

        Args:
            username: Base name used to generate the email.
            telegram_id: Telegram user ID.

        Returns:
            (True, subscribe_url) on success,
            (False, error_message) on failure.
        """
        api = self._get_api()
        if not api:
            return False, "No connection to 3x-ui"

        base_name = re.sub(r'[^a-zA-Z0-9_]', '_', username)
        email = f"{base_name}_{telegram_id}"

        # Check if client already exists globally (in any inbound)
        existing_client = None
        try:
            existing_client = api.client.get_by_email(email)
        except Exception:
            pass

        if existing_client:
            # Client already exists globally — attach to *this* inbound
            # by updating the inbound's settings (how GUI "Attached inbounds" works).
            uuid_str = existing_client.uuid or ""
            sub_id = existing_client.sub_id or ""

            try:
                inbound = api.inbound.get_by_id(self.inbound_id)
                if inbound.settings is None:
                    return False, "Inbound has no settings"

                # Add the existing client to this inbound's client list
                new_client = Client(
                    email=email,
                    enable=True,
                    flow=self._flow,
                    id=uuid_str,
                    total_gb=0,
                )
                inbound.settings.clients.append(new_client)
                api.inbound.update(self.inbound_id, inbound)
            except Exception as e:
                return False, str(e)
        else:
            # Fresh client — check this inbound specifically for duplicates
            try:
                inbound = api.inbound.get_by_id(self.inbound_id)
                existing = inbound.settings.clients if inbound.settings else []
                for c in existing:
                    if c.email == email:
                        return False, f"Client with email '{email}' already exists in this inbound"
            except Exception as e:
                return False, f"Error checking existing clients: {e}"

            client = make_client(
                email=email,
                enable=True,
                flow=self._flow,
                total_gb=0,
            )

            try:
                api.client.add(self.inbound_id, [client])
            except Exception as e:
                return False, str(e)

            # Fetch back to get uuid and sub_id
            created = None
            try:
                created = api.client.get_by_email(email)
            except Exception:
                pass
            uuid_str = created.id if created else ""
            sub_id = created.sub_id if created else ""

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

    def delete_user(self, username: str) -> bool:
        """Delete a client from the 3x-ui panel.

        Args:
            username: The client email to delete.

        Returns:
            True if the client was removed.
        """
        api = self._get_api()
        if not api:
            return False
        email = username
        try:
            client = api.client.get_by_email(email)
            if not client or not client.id:
                return False
            api.client.delete(self.inbound_id, client.id)
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
        api = self._get_api()
        if not api:
            return []
        try:
            inbound = api.inbound.get_by_id(self.inbound_id)
            clients = inbound.settings.clients if inbound.settings else []
        except Exception:
            return []

        emails = [c.email for c in clients if c.email]
        db_map = {}
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
            email = c.email or ""
            uuid_str = c.id or ""
            enable = c.enable

            db_row = db_map.get(email)
            if db_row:
                telegram_id, created_at_db, sub_id = db_row
            else:
                telegram_id, created_at_db, sub_id = "—", None, None

            if not sub_id and c.sub_id:
                sub_id = c.sub_id
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
            created_at = created_at_db or "—"

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
        """Rename a client in both 3x-ui and the database."""
        api = self._get_api()
        if not api:
            return False, "3x-ui unavailable"

        try:
            client = api.client.get_by_email(old_username)
        except Exception as e:
            return False, f"Failed to fetch clients: {e}"
        if not client:
            return False, f"Client {old_username} not found"

        client.email = new_username
        try:
            api.client.update(client.id, client)
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
        return key_data.get('email', '')

    def get_link_for_key(self, key_data: Dict[str, Any]) -> str:
        sub_id = key_data.get('sub_id', '')
        if not sub_id:
            email = key_data.get('email', '')
            sub_id = self._get_sub_id_from_db(email)
        return f"{self.sub_url_base}{sub_id}" if sub_id else ""

    def format_user_key_message(self, key_data: Dict[str, Any]) -> Tuple[str, str]:
        from app.locales.ru import MESSAGES
        from app.utils import escape_html
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
        return len(identifier.strip()) > 0

    # ── internal helpers ──────────────────────────────────────────

    def _get_sub_id_from_db(self, email: str) -> str:
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
