"""Xray (VLESS Reality) service — 3x-ui managed.

Re-exports ``ThreeXUIService`` with Xray-specific settings.

Exports:
    xray_service: Singleton XrayService instance.
"""

from typing import Dict, Any
from app.config import XRAY_INBOUND_ID, XRAY_SUB_URL_BASE, XRAY_ENABLED
from app.services.threexui_base import ThreeXUIService


class XrayService(ThreeXUIService):
    """Xray (VLESS Reality) client management via 3x-ui API."""

    protocol_name = "xray"
    display_name = "Xray"
    emoji = "🌐"

    @property
    def enabled(self) -> bool:
        return XRAY_ENABLED

    @property
    def inbound_id(self) -> int:
        return XRAY_INBOUND_ID

    @property
    def sub_url_base(self) -> str:
        return XRAY_SUB_URL_BASE

    def _build_client_payload(self, email: str, uuid_str: str, sub_id: str) -> dict:
        return {
            "email": email,
            "id": uuid_str,
            "flow": "xtls-rprx-vision",
            "enable": True,
            "subId": sub_id,
            "totalGB": 0,
        }


# Singleton
xray_service = XrayService()
