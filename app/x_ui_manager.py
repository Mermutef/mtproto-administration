"""3x-ui (Xray) panel API client — pure ``requests`` with Bearer auth.

Based on the official 3x-ui 3.2.9 API endpoints found in the Go source
(``web/controller/client.go``, ``web/controller/api.go``).

Exports:
    XuiApi — Thread-safe API wrapper exposing the operations we need.
"""

import json
import threading
import logging
import secrets
from typing import Optional, List, Dict, Any

import requests

from app.config import XUI_BASE_URL, XUI_API_TOKEN


logger = logging.getLogger(__name__)


class XuiApi:
    """Thin wrapper around the 3x-ui REST API.

    Authentication is done via Bearer token (``XUI_API_TOKEN``).  The
    token is generated once in the panel GUI (Settings → API Keys) and
    stored in the ``.env`` file.

    Every public method raises :class:`XuiError` on failure.
    """

    def __init__(self, max_retries: int = 2, timeout: int = 30):
        self.base_url = XUI_BASE_URL.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {XUI_API_TOKEN}",
            "Accept": "application/json",
        })
        logger.info("XuiApi initialised (token auth)")

    # ── low-level helpers ──────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Send an HTTP request and return the parsed JSON body.

        Raises:
            XuiError: On non-200 status or ``success: false`` response.
        """
        url = self._url(path)
        kwargs.setdefault("timeout", self.timeout)

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(method, url, **kwargs)
                if resp.status_code == 401:
                    raise XuiError("Authentication failed — check XUI_API_TOKEN")
                if resp.status_code == 404:
                    raise XuiError(f"Resource not found: {path}")
                if resp.status_code != 200:
                    raise XuiError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                data = resp.json() if resp.text.strip() else {}
                if not data.get("success"):
                    msg = data.get("msg", "Unknown error")
                    raise XuiError(msg)
                return data
            except (requests.RequestException, XuiError) as e:
                last_error = e
                if attempt < self.max_retries:
                    logger.warning("API call failed, retrying (%d/%d): %s",
                                   attempt + 1, self.max_retries, e)
                    import time
                    time.sleep(2 ** attempt)
                    continue
                raise XuiError(str(last_error)) from last_error

        raise XuiError(str(last_error or "Unknown error"))

    def _get(self, path: str) -> dict:
        return self._request("GET", path)

    def _post(self, path: str, json_body: dict = None) -> dict:
        return self._request("POST", path, json=json_body or {})

    # ── Client API ─────────────────────────────────────────────────

    def create_client(self, email: str, inbound_ids: List[int],
                      enable: bool = True,
                      flow: str = "",
                      total_gb: int = 0,
                      tg_id: str = "") -> Dict[str, Any]:
        """Create a new client via ``POST /panel/api/clients/add``.

        The panel auto-generates ``id`` (UUID), ``subId``, and protocol-
        specific fields (``password`` for Trojan, ``auth`` for Hysteria).

        Returns:
            The response object with ``msg`` and ``obj`` keys.
        """
        client = {
            "email": email,
            "enable": enable,
            "totalGB": total_gb,
            "tgId": tg_id,
        }
        if flow:
            client["flow"] = flow

        payload = {
            "client": client,
            "inboundIds": inbound_ids,
        }
        return self._post("/panel/api/clients/add", payload)

    def attach_client(self, email: str, inbound_ids: List[int]) -> Dict[str, Any]:
        """Attach an existing client to additional inbounds.

        ``POST /panel/api/clients/{email}/attach``
        """
        return self._post(f"/panel/api/clients/{email}/attach",
                          {"inboundIds": inbound_ids})

    def detach_client(self, email: str, inbound_ids: List[int]) -> Dict[str, Any]:
        """Detach a client from specific inbounds (keep in others).

        ``POST /panel/api/clients/{email}/detach``
        """
        return self._post(f"/panel/api/clients/{email}/detach",
                          {"inboundIds": inbound_ids})

    def delete_client(self, email: str, keep_traffic: bool = False) -> Dict[str, Any]:
        """Delete a client globally (from all inbounds).

        ``POST /panel/api/clients/del/{email}``
        """
        qs = "?keepTraffic=1" if keep_traffic else ""
        return self._post(f"/panel/api/clients/del/{email}{qs}")

    def update_client(self, email: str, client_data: dict,
                      inbound_ids: List[int] = None) -> Dict[str, Any]:
        """Update a client's properties by email.

        ``POST /panel/api/clients/update/{email}``
        """
        qs = ""
        if inbound_ids:
            qs = "?inboundIds=" + ",".join(str(i) for i in inbound_ids)
        return self._post(f"/panel/api/clients/update/{email}{qs}", client_data)

    def get_client(self, email: str) -> Optional[Dict[str, Any]]:
        """Get client details by email.

        ``GET /panel/api/clients/get/{email}``

        Returns the ``client`` dict (with keys like ``id``, ``email``,
        ``subId``, ``enable``, etc.), or ``None`` if not found.
        """
        try:
            data = self._get(f"/panel/api/clients/get/{email}")
            obj = data.get("obj", {})
            return obj.get("client") or obj
        except XuiError as e:
            if "not found" in str(e).lower() or "no such" in str(e).lower():
                return None
            raise

    def get_clients_list(self) -> List[Dict[str, Any]]:
        """List all clients panel-wide.

        ``GET /panel/api/clients/list``
        """
        data = self._get("/panel/api/clients/list")
        return data.get("obj", [])

    # ── Inbound API (read-only — needed by get_users) ──────────────

    def get_inbound(self, inbound_id: int) -> Dict[str, Any]:
        """Get full inbound data including ``settings.clients``.

        ``GET /panel/api/inbounds/get/{id}``
        """
        data = self._get(f"/panel/api/inbounds/get/{inbound_id}")
        return data["obj"]

    def get_inbounds_list(self) -> List[Dict[str, Any]]:
        """List all inbounds (used for diagnostics).

        ``GET /panel/api/inbounds/list``
        """
        data = self._get("/panel/api/inbounds/list")
        return data.get("obj", [])

    # ── helpers ────────────────────────────────────────────────────

    def ensure_client_attached(self, email: str, inbound_id: int) -> None:
        """Check if a client exists and attach to *inbound_id* if needed.

        If the client does not exist at all, callers should create it
        first via :meth:`create_client`.  This method only *attaches*
        an existing client to an additional inbound (idempotent — safe
        to call even if already attached).
        """
        # A 404 or "not found" here means the client doesn't exist yet.
        client = self.get_client(email)
        if client is None:
            raise XuiError(f"Client '{email}' not found — create it first")
        # Attach (idempotent; no error if already attached)
        self.attach_client(email, [inbound_id])


class XuiError(Exception):
    """Raised when the 3x-ui API returns an error."""
