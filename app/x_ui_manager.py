"""3x-ui (Xray) panel API client — powered by ``py3xui``.

Replaces the old hand-rolled HTTP client with the mature ``py3xui``
library which handles authentication, session management, CSRF tokens,
and client/inbound CRUD correctly for 3x-ui 3.x.

Exports:
    get_xui: Thread-local :class:`py3xui.Api` singleton factory.
    attach_client_to_inbound: Raw-JSON helper that preserves subId for all clients.
"""

import json
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


def attach_client_to_inbound(api: Api, inbound_id: int, client_dict: dict) -> None:
    """Attach a client to an inbound via raw JSON to preserve subId for existing clients.

    py3xui's Pydantic models can lose ``subId`` during serialisation because
    the field alias is ``subId`` (camelCase) but the Python attribute is
    ``sub_id`` (snake_case).  This function bypasses Pydantic entirely:
    it fetches the inbound as a raw dict, appends the new client, and posts
    the complete dict back using the same ``requests.Session`` that py3xui
    configured (with Bearer token / cookie).

    Args:
        api: An authenticated :class:`py3xui.Api` instance.
        inbound_id: The inbound to attach the client to.
        client_dict: A plain Python dict representing the client (keys
            must use the API's camelCase naming, e.g. ``id``, ``email``,
            ``subId``).

    Raises:
        Exception: If any API call fails.
    """
    import requests as _requests

    base = XUI_BASE_URL.rstrip("/")
    session = getattr(api, "_session", None) or _requests.Session()

    # 1. Fetch inbound as raw JSON
    get_url = f"{base}/panel/api/inbounds/get/{inbound_id}"
    resp = session.get(get_url, timeout=30, allow_redirects=True)
    if resp.status_code == 200 and not resp.text.strip():
        # possibly a re-login redirect — let the session handle it
        resp = session.get(get_url, timeout=30, allow_redirects=True)
    if resp.status_code != 200:
        raise Exception(f"GET inbound failed: {resp.status_code}")
    data = resp.json()
    if not data.get("success"):
        raise Exception(data.get("msg", "Error fetching inbound data"))

    inbound_dict = data["obj"]
    settings = inbound_dict.get("settings", {})
    if isinstance(settings, str):
        settings = json.loads(settings)

    clients = settings.setdefault("clients", [])
    clients.append(client_dict)
    settings["clients"] = clients
    inbound_dict["settings"] = json.dumps(settings, ensure_ascii=False)

    # 2. Update inbound with the full, merged client list
    update_url = f"{base}/panel/api/inbounds/update/{inbound_id}"
    resp = session.post(update_url, json=inbound_dict, timeout=30, allow_redirects=True)
    if resp.status_code != 200:
        raise Exception(f"Update inbound failed: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if not data.get("success"):
        raise Exception(data.get("msg", "Error updating inbound"))
