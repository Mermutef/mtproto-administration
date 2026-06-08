"""Trojan service — 3x-ui managed.

Re-exports ``ThreeXUIService`` with Trojan-specific settings.

Exports:
    trojan_service: Singleton TrojanService instance.
"""

from typing import Dict, Any
from app.config import TROJAN_INBOUND_ID, TROJAN_SUB_URL_BASE, TROJAN_ENABLED
from app.services.threexui_base import ThreeXUIService


class TrojanService(ThreeXUIService):
    """Trojan client management via 3x-ui API."""

    protocol_name = "trojan"
    display_name = "Trojan"
    emoji = "🐴"

    @property
    def enabled(self) -> bool:
        return TROJAN_ENABLED

    @property
    def inbound_id(self) -> int:
        return TROJAN_INBOUND_ID

    @property
    def sub_url_base(self) -> str:
        return TROJAN_SUB_URL_BASE



# Singleton
trojan_service = TrojanService()
