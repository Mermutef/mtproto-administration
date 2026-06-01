"""Hysteria2 service placeholder.

Hysteria2 support is not yet implemented. This module provides
a stub service that always reports the protocol as unavailable.

Exports:
    hysteria2_service: Singleton Hysteria2Service instance.
"""

from typing import List, Dict, Any, Tuple
from app.config import HYSTERIA2_ENABLED
from app.services.base import BaseVpnService


class Hysteria2Service(BaseVpnService):
    """Placeholder service for Hysteria2 (not yet implemented).

    All user operations return a "not supported" error.
    """

    protocol_name = "hysteria2"
    display_name = "Hysteria2"
    emoji = "⚡"

    @property
    def enabled(self) -> bool:
        """Whether Hysteria2 is enabled via the ``HYSTERIA2_ENABLED`` env var."""
        return HYSTERIA2_ENABLED

    def create_user(self, username: str, telegram_id: str = "unknown") -> Tuple[bool, str]:
        """Not implemented."""
        return False, "Hysteria2 not supported yet"

    def delete_user(self, username: str) -> bool:
        """Not implemented."""
        return False

    def get_users(self) -> List[Dict[str, Any]]:
        """Not implemented."""
        return []


# Singleton
hysteria2_service = Hysteria2Service()
