"""3x-ui (Xray) panel API client — powered by ``py3xui``.

Replaces the old hand-rolled HTTP client with the mature ``py3xui``
library which handles authentication, session management, CSRF tokens,
and client/inbound CRUD correctly for 3x-ui 3.x.

Exports:
    get_xui: Thread-local :class:`py3xui.Api` singleton factory.
"""

import threading
import logging
from typing import Optional

from py3xui import Api, Client

from app.config import XUI_BASE_URL, XUI_USERNAME, XUI_PASSWORD, XUI_API_TOKEN


_xui_per_thread = threading.local()


def get_xui() -> Optional[Api]:
    """Get a thread-local :class:`py3xui.Api` singleton.

    Authenticates once per thread; subsequent calls return the cached
    instance.  If initialisation fails, ``None`` is returned.

    Returns:
        An :class:`py3xui.Api` instance, or ``None``.
    """
    client = getattr(_xui_per_thread, 'client', None)
    if client is None:
        try:
            client = Api(
                host=XUI_BASE_URL,
                username=XUI_USERNAME if not XUI_API_TOKEN else None,
                password=XUI_PASSWORD if not XUI_API_TOKEN else None,
                token=XUI_API_TOKEN,
                use_tls_verify=True,
            )
            if not XUI_API_TOKEN:
                client.login()
            logging.info(f"XUI client initialised (token_auth={bool(XUI_API_TOKEN)})")
        except Exception as e:
            logging.error(f"Failed to initialise XUI client: {e}")
            _xui_per_thread.client = False
            return None
        _xui_per_thread.client = client
    return client if client is not False else None


def make_client(
    email: str,
    enable: bool = True,
    flow: str = "",
    tg_id: str = "",
    total_gb: int = 0,
    **extra,
) -> Client:
    """Build a :class:`py3xui.Client` with the given parameters.

    Args:
        email: Client email (used as identifier).
        enable: Whether the client is enabled.
        flow: Xray flow setting (e.g. ``xtls-rprx-vision`` for VLESS).
        tg_id: Telegram ID (left empty for new clients).
        total_gb: Total traffic limit in GB (0 = unlimited).
        **extra: Any additional fields forwarded to the Client model.

    Returns:
        A :class:`py3xui.Client` instance.
    """
    return Client(
        email=email,
        enable=enable,
        flow=flow,
        tg_id=tg_id,
        total_gb=total_gb,
        **extra,
    )
