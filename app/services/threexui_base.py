"""Abstract base for all 3x-ui-managed VPN protocols.

Uses the official 3x-ui REST API via :class:`XuiApi` (pure ``requests``,
no external SDKs).

Each subclass only needs to provide metadata.

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

from app.config import DB_PATH, XUI_SUB_URL_BASE
from app.services.base import BaseVpnService
from app.x_ui_manager import XuiApi, XuiError
from app.utils import sanitize_username


class ThreeXUIService(BaseVpnService):
    """Service base for protocols managed through the 3x-ui panel API.

    Subclasses **must** define:
    - :attr:`protocol_name`, :attr:`display_name`, :attr:`emoji`
    - :meth:`enabled`
    - :meth:`inbound_id` (property)
    """

    @staticmethod
    def _guess_existing_email(base_name: str, telegram_id: str) -> str:
        """Try to find an existing user in DB whose username matches.

        If the *base_name* ends with the *telegram_id* (i.e. was
        previously stored as ``name_telegramID_telegramID``), return
        the stored username from the database.
        """
        if not telegram_id or telegram_id in ('unknown', 'web', '—'):
            return ""
        # Check if there's a user whose username starts with base_name
        # and ends with _telegramId → name_tgid_tgid (double suffix)
        # or name_tgid (single suffix)
        cand = f"{base_name}_{telegram_id}"
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Check if email as name_tgid already exists
        c.execute("SELECT username FROM users WHERE username = ?", (cand,))
        row = c.fetchone()
        conn.close()
        if row:
            return row[0]
        return ""

    # ── abstract / subclass-supplied ──────────────────────────────

    @property
    @abstractmethod
    def inbound_id(self) -> int:
        """3x-ui inbound ID for this protocol."""

    # All 3x-ui protocols share the same subscription system —
    # one sub_id covers every inbound the client is attached to.
    sub_url_base: str = XUI_SUB_URL_BASE

    @property
    def _flow(self) -> str:
        """Xray flow setting (e.g. xtls-rprx-vision for VLESS)."""
        return ""

    @property
    def _total_gb(self) -> int:
        """Default traffic limit in GB (0 = unlimited)."""
        return 0

    # ── 3x-ui helpers ────────────────────────────────────────────

    def _get_api(self) -> XuiApi:
        """Get a thread-local XuiApi instance."""
        return XuiApi()

    # ── CRUD ──────────────────────────────────────────────────────

    def create_user(self, username: str, telegram_id: str = "unknown") -> Tuple[bool, str]:
        """Create a client via the 3x-ui API.

        In 3x-ui 3.2.9, the ``/panel/api/clients/add`` endpoint lets us
        specify multiple inbound IDs.  If the email already exists, we
        attach it to *this* inbound via ``/panel/api/clients/{email}/attach``.

        Args:
            username: Base name used to generate the email.
            telegram_id: Telegram user ID.

        Returns:
            (True, subscribe_url) on success,
            (False, error_message) on failure.
        """
        api = self._get_api()
        base_name = sanitize_username(username)
        if email := self._guess_existing_email(base_name, telegram_id):
            pass  # use guessed email
        else:
            email = f"{base_name}_{telegram_id}"

        # Try to create the client (happens on first-time creation)
        try:
            api.create_client(
                email=email,
                inbound_ids=[self.inbound_id],
                flow=self._flow,
                total_gb=self._total_gb,
            )
        except XuiError as e:
            # If email already exists, attach to this inbound instead
            if "email" in str(e).lower() and "in use" in str(e).lower():
                try:
                    api.attach_client(email, [self.inbound_id])
                except XuiError as attach_err:
                    return False, str(attach_err)
            else:
                return False, str(e)

        # Fetch client to get uuid and sub_id
        client_data = api.get_client(email)
        uuid_str = (client_data or {}).get("id", "") or ""
        sub_id = (client_data or {}).get("subId", "") or ""

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
        """Delete a client **only** from this inbound via detach.

        Uses ``POST /panel/api/clients/{email}/detach`` so the client
        stays alive in other inbounds.

        Args:
            username: The client email to delete.

        Returns:
            True if the client was removed.
        """
        api = self._get_api()
        email = username
        try:
            api.detach_client(email, [self.inbound_id])
        except XuiError as e:
            logging.error(f"Error detaching {self.protocol_name} client {email}: {e}")
            return False
        self._revoke_keys(email)
        return True

    def _get_client_uuid(self, email: str) -> str:
        """Fetch the real UUID from the panel client record.

        Uses the ``uuid`` field (not ``id``, which is the internal
        auto-increment integer).  Falls back to empty string if not
        available.
        """
        try:
            api = self._get_api()
            client = api.get_client(email)
            if client:
                return client.get("uuid") or ""
        except Exception:
            pass
        return ""

    def get_users(self) -> List[Dict[str, Any]]:
        """List all clients in this inbound with DB metadata.

        Returns:
            A list of user dicts.
        """
        api = self._get_api()
        try:
            inbound = api.get_inbound(self.inbound_id)
        except XuiError:
            return []

        # Parse settings (may be str or dict)
        settings = inbound.get("settings", {})
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except json.JSONDecodeError:
                return []
        clients = settings.get("clients", [])

        emails = [c.get("email", "") for c in clients if c.get("email")]
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
            email = c.get("email", "")
            uuid_str = c.get("id", "")
            enable = c.get("enable", True)

            db_row = db_map.get(email)
            if db_row:
                telegram_id, created_at_db, sub_id = db_row
                # Sync panel uuid if missing (Trojan / Hysteria2 inbound
                # settings don't always include the ``id`` field).
                if not uuid_str:
                    uuid_str = self._get_client_uuid(email)
                    if uuid_str:
                        # Persist fetched uuid to DB so /mykeys, /info etc. work
                        conn_uuid = sqlite3.connect(DB_PATH)
                        try:
                            cur_uuid = conn_uuid.cursor()
                            cur_uuid.execute(
                                "UPDATE keys SET key_data = json_set(key_data, '$.uuid', ?) "
                                "WHERE protocol=? AND json_extract(key_data, '$.email') = ?",
                                (uuid_str, self.protocol_name, email)
                            )
                            conn_uuid.commit()
                        finally:
                            conn_uuid.close()

                # Sync panel sub_id if different (fixes stale per-protocol sub_id)
                panel_sub_id = c.get("subId") or ""
                if sub_id and panel_sub_id and sub_id != panel_sub_id:
                    conn_sync = sqlite3.connect(DB_PATH)
                    try:
                        cur_sync = conn_sync.cursor()
                        cur_sync.execute(
                            "UPDATE keys SET key_data = json_set(key_data, '$.sub_id', ?) "
                            "WHERE protocol=? AND json_extract(key_data, '$.email') = ?",
                            (panel_sub_id, self.protocol_name, email)
                        )
                        conn_sync.commit()
                    finally:
                        conn_sync.close()
                    sub_id = panel_sub_id
            else:
                # Client exists on the panel but not in our DB
                # (e.g. added via panel GUI, not through bot).
                # Auto-sync: create a key record so /mykeys works.
                telegram_id, created_at_db, sub_id = "—", None, None
                sub_id = c.get("subId") or ""
                if not uuid_str:
                    uuid_str = self._get_client_uuid(email)
                    if uuid_str:
                        conn_uuid = sqlite3.connect(DB_PATH)
                        try:
                            cur_uuid = conn_uuid.cursor()
                            cur_uuid.execute(
                                "UPDATE keys SET key_data = json_set(key_data, '$.uuid', ?) "
                                "WHERE protocol=? AND json_extract(key_data, '$.email') = ?",
                                (uuid_str, self.protocol_name, email)
                            )
                            conn_uuid.commit()
                        finally:
                            conn_uuid.close()
                try:
                    conn2 = sqlite3.connect(DB_PATH)
                    cur2 = conn2.cursor()
                    cur2.execute("SELECT id FROM users WHERE username = ?", (email,))
                    user_row = cur2.fetchone()
                    if user_row:
                        user_id_sync = user_row[0]
                    else:
                        cur2.execute(
                            "INSERT INTO users (username, telegram_id, created_at) VALUES (?, ?, ?)",
                            (email, "—", datetime.now().isoformat()),
                        )
                        user_id_sync = cur2.lastrowid
                    key_data_sync = {"email": email, "uuid": uuid_str, "sub_id": sub_id}
                    cur2.execute(
                        "INSERT OR IGNORE INTO keys (user_id, protocol, key_data, created_at) VALUES (?, ?, ?, ?)",
                        (user_id_sync, self.protocol_name, json.dumps(key_data_sync), datetime.now().isoformat()),
                    )
                    conn2.commit()
                    conn2.close()
                except Exception:
                    pass

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
        try:
            client = api.get_client(old_username)
        except XuiError as e:
            return False, f"Failed to fetch client: {e}"

        if not client:
            return False, f"Client {old_username} not found"

        # Build a clean payload — remove fields that trip up the Go JSON decoder
        upd = {"email": new_username, "enable": True}
        if client.get("flow"):
            upd["flow"] = client["flow"]
        if client.get("subId"):
            upd["subId"] = client["subId"]
        if client.get("totalGB"):
            upd["totalGB"] = client["totalGB"]

        try:
            api.update_client(old_username, upd)
        except XuiError as e:
            return False, f"Update error: {e}"

        # Update DB
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
