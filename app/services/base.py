"""Abstract base class for all VPN protocol services.

All VPN protocol implementations must inherit from BaseVpnService
and implement the required abstract methods. The base class provides
common helper methods for database access and key management.

Every service uses ``username`` as the canonical string identifier
for a user, regardless of the underlying protocol's naming conventions
(e.g. MTProto uses ``username``, Xray uses ``email``).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Any, Optional
import json
import sqlite3
from datetime import datetime
from app.config import DB_PATH


class BaseVpnService(ABC):
    """Abstract base class for VPN protocol services.

    Subclasses must define :attr:`protocol_name`, :attr:`display_name`,
    :attr:`emoji`, and the :meth:`enabled` property, plus implement
    all abstract methods.

    Attributes:
        protocol_name: Machine-readable protocol identifier (e.g. 'mtproto').
        display_name: Human-readable name (e.g. 'MTProto').
        emoji: Emoji icon for UI display (e.g. '🛡️').
    """

    protocol_name: str = ""
    display_name: str = ""
    emoji: str = ""

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Whether this service is enabled in the current configuration."""

    @abstractmethod
    def create_user(self, username: str, telegram_id: str = "unknown") -> Tuple[bool, str]:
        """Create a user in the VPN service.

        Args:
            username: Canonical user identifier.
            telegram_id: Telegram user ID or 'unknown'/'web'.

        Returns:
            (True, connection_link) on success,
            (False, error_message) on failure.
        """

    @abstractmethod
    def delete_user(self, username: str) -> bool:
        """Delete a user from the VPN service.

        Args:
            username: The user identifier to delete.

        Returns:
            True if the user was found and deleted, False otherwise.
        """

    @abstractmethod
    def get_users(self) -> List[Dict[str, Any]]:
        """Return all users managed by this service.

        Each entry is a dict with at minimum:
            ``username``, ``telegram_id``, ``created_at``, ``link``, ``protocol``.

        Returns:
            A list of user dicts.
        """

    def rename_user(self, old_username: str, new_username: str) -> Tuple[bool, str]:
        """Rename a user in the service.

        Args:
            old_username: Current user identifier.
            new_username: New user identifier.

        Returns:
            (True, success_message) or (False, error_message).
        """
        return False, "Renaming not supported"

    def get_link_for_key(self, key_data: Dict[str, Any]) -> str:
        """Build a connection link from stored key data.

        Args:
            key_data: Dict with protocol-specific key fields.

        Returns:
            A connection URL string, or empty string.
        """
        return ""

    def get_identifier(self, key_data: Dict[str, Any]) -> str:
        """Extract the canonical username from key data.

        Args:
            key_data: Dict with protocol-specific key fields.

        Returns:
            The username string.
        """
        return key_data.get('username', '')

    def format_user_key_message(self, key_data: Dict[str, Any]) -> Tuple[str, str]:
        """Format the message to send to a user when their key is granted.

        Subclasses should override this to provide protocol-specific
        messaging using their localised strings.

        Args:
            key_data: Dict with protocol-specific key fields.

        Returns:
            A tuple ``(message_text, parse_mode)`` where ``parse_mode``
            is e.g. ``"HTML"`` or ``None``. Returns ``("", "")`` by
            default.
        """
        return ("", "")

    def format_admin_created_message(self, identifier: str) -> str:
        """Format the admin confirmation for a key created via @mention.

        Args:
            identifier: The @username or email of the user.

        Returns:
            A formatted message string.
        """
        return ""

    def format_admin_direct_message(self, identifier: str, link: str) -> str:
        """Format the admin confirmation for a direct name-based user creation.

        Args:
            identifier: The proxy username or email.
            link: The connection link.

        Returns:
            A formatted message string.
        """
        return ""

    def validate_identifier(self, identifier: str) -> bool:
        """Check whether an identifier is valid for this service.

        Args:
            identifier: The candidate username.

        Returns:
            True if the identifier is acceptable.
        """
        return len(identifier.strip()) > 0

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    def _ensure_user_in_db(self, username: str, telegram_id: str = "unknown") -> int:
        """Create a user row in the local database if it doesn't exist.

        Args:
            username: Canonical user identifier.
            telegram_id: Telegram user ID.

        Returns:
            The internal database user ID.
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute(
            "INSERT OR IGNORE INTO users (username, telegram_id, created_at) VALUES (?, ?, ?)",
            (username, str(telegram_id), now),
        )
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_id = c.fetchone()[0]
        conn.commit()
        conn.close()
        return user_id

    def _save_key(self, username: str, telegram_id: str, key_data: Dict) -> int:
        """Persist a protocol key to the database.

        Args:
            username: Canonical user identifier.
            telegram_id: Telegram user ID.
            key_data: Dict of key material to store.

        Returns:
            The new key row ID.
        """
        user_id = self._ensure_user_in_db(username, telegram_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute(
            "INSERT INTO keys (user_id, protocol, key_data, created_at) VALUES (?, ?, ?, ?)",
            (user_id, self.protocol_name, json.dumps(key_data), now),
        )
        key_id = c.lastrowid
        conn.commit()
        conn.close()
        return key_id

    def _revoke_keys(self, username: str) -> None:
        """Mark all active keys for a user as revoked.

        Args:
            username: Canonical user identifier.
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE keys SET status='revoked' "
            "WHERE user_id = (SELECT id FROM users WHERE username = ?) "
            "AND protocol = ? AND status = 'active'",
            (username, self.protocol_name),
        )
        conn.commit()
        conn.close()

    def get_telegram_id(self, username: str) -> Optional[str]:
        """Look up the Telegram ID for a username.

        Args:
            username: Canonical user identifier.

        Returns:
            The Telegram ID string, or None.
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def _get_user_db_id(self, username: str) -> Optional[int]:
        """Look up the internal database user ID.

        Args:
            username: Canonical user identifier.

        Returns:
            The internal user ID, or None.
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
