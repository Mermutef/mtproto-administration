"""Hysteria2 service — 3x-ui managed.

Re-exports ``ThreeXUIService`` with Hysteria2-specific settings.
Previously a stub, now a full 3x-ui protocol implementation.

Exports:
    hysteria2_service: Singleton Hysteria2Service instance.
"""

from typing import Dict, Any
from app.config import HYSTERIA2_INBOUND_ID, HYSTERIA2_SUB_URL_BASE, HYSTERIA2_ENABLED
from app.services.threexui_base import ThreeXUIService


class Hysteria2Service(ThreeXUIService):
    """Hysteria2 client management via 3x-ui API."""

    protocol_name = "hysteria2"
    display_name = "Hysteria2"
    emoji = "⚡"

    @property
    def enabled(self) -> bool:
        return HYSTERIA2_ENABLED

    @property
    def inbound_id(self) -> int:
        return HYSTERIA2_INBOUND_ID

    @property
    def sub_url_base(self) -> str:
        return HYSTERIA2_SUB_URL_BASE

    def _build_client_payload(self, email: str, uuid_str: str, sub_id: str) -> dict:
        return {
            "email": email,
            "id": uuid_str,
            "enable": True,
            "subId": sub_id,
            "totalGB": 0,
        }


# Singleton
hysteria2_service = Hysteria2Service()
