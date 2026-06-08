"""3x-ui (Xray) panel API client.

Provides a thread-safe HTTP client for interacting with the 3x-ui
administration panel to manage Xray (VLESS Reality) inbounds and
clients.

Exports:
    get_xui_client: Thread-local singleton factory.
    XUIClient: Low-level API client class.
"""

import requests
import json
import uuid
import time
import secrets
import threading
import logging
from typing import Optional, List, Dict, Any
from app.config import XUI_BASE_URL, XUI_USERNAME, XUI_PASSWORD, XUI_API_TOKEN


_xui_per_thread = threading.local()


def get_xui_client():
    """Get a thread-local XUIClient singleton.

    Returns:
        An :class:`XUIClient` instance, or ``None`` if initialisation
        failed (e.g. panel unreachable).
    """
    client = getattr(_xui_per_thread, 'client', None)
    if client is None:
        try:
            _xui_per_thread.client = XUIClient()
        except Exception as e:
            logging.error(f"Failed to initialise XUIClient: {e}")
            _xui_per_thread.client = False
        client = _xui_per_thread.client
    return client if client is not False else None


class XUIClient:
    """HTTP client for the 3x-ui panel API.

    Handles authentication, session management, and CRUD operations
    for Xray inbounds and clients.

    Args:
        max_retries: Number of retries on transient errors.
        timeout: Request timeout in seconds.
    """

    API_LOGIN = "/login"
    API_LOGIN_ALT = "/panel/login"
    API_INBOUNDS_LIST = "/panel/api/inbounds/list"
    API_INBOUND_GET = "/panel/api/inbounds/get/{inbound_id}"
    API_INBOUND_ADD_CLIENT = "/panel/api/inbounds/addClient"
    API_INBOUND_DEL_CLIENT = "/panel/api/inbounds/{inbound_id}/delClient/{client_id}"
    API_INBOUND_UPDATE = "/panel/api/inbounds/update/{inbound_id}"
    API_SERVER_STATUS = "/panel/api/server/status"
    SUB_ID_LEN = 16

    def __init__(self, max_retries: int = 2, timeout: int = 30):
        self.base_url = XUI_BASE_URL.rstrip('/')
        self.session = requests.Session()
        self.max_retries = max_retries
        self.timeout = timeout
        self._authenticated = False
        self._token_auth = bool(XUI_API_TOKEN)

        if self._token_auth:
            # 3x-ui 3.2.9+: Bearer token auth — no session cookie needed.
            # See https://github.com/MHSanaei/3x-ui for API docs.
            self.session.headers.update({"Authorization": f"Bearer {XUI_API_TOKEN}"})
            logging.info("Using XUI_API_TOKEN (Bearer) for 3x-ui API authentication")
            self._authenticated = True
            return

        self._login()
        self._authenticated = True

    def _login(self) -> bool:
        """Authenticate with the 3x-ui panel and store the session cookie.

        If ``XUI_API_TOKEN`` is set, Bearer auth is used instead.
        No login request is performed.

        Returns:
            True on success.

        Raises:
            Exception: If login fails after all retries.
        """
        self.session.cookies.clear()

        # Bearer token auth is handled in __init__ — nothing to do here.
        if self._token_auth:
            self._authenticated = True
            return True

        login_url = f"{self.base_url}{self.API_LOGIN}"

        resp = self._do_login_request(login_url)

        if not resp or not resp.ok:
            alt_url = f"{self.base_url}{self.API_LOGIN_ALT}"
            if alt_url != login_url:
                resp = self._do_login_request(alt_url)

        if not resp or not resp.ok:
            body = resp.text[:300] if resp else "No response"
            raise Exception(f"Failed to authenticate with 3x-ui (status {resp.status_code if resp else 'N/A'})")

        session_cookie = self._get_session_cookie()
        if not session_cookie:
            time.sleep(1)
            self.session.cookies.clear()
            resp = self._do_login_request(login_url)
            if not resp or not resp.ok or not self._get_session_cookie():
                raise Exception("Could not establish session after retry")

        self._authenticated = True
        return True

    def _do_login_request(self, url: str) -> Optional[requests.Response]:
        """Send a POST login request.

        Args:
            url: The login endpoint URL.

        Returns:
            The response object, or None on connection error.
        """
        try:
            return self.session.post(
                url,
                data={"username": XUI_USERNAME, "password": XUI_PASSWORD},
                allow_redirects=True,
                timeout=self.timeout
            )
        except requests.exceptions.RequestException as e:
            return None

    def _get_session_cookie(self) -> Optional[str]:
        """Extract the session cookie from the current session.

        Returns:
            The cookie value, or None.
        """
        for name in ['3x-ui', 'session', 'x-ui', 'JSESSIONID', 'xui_session', '3XUI_SESSION']:
            value = self.session.cookies.get(name)
            if value:
                return value
        # Fallback: return the first non-empty cookie
        for cookie in self.session.cookies:
            if cookie.value:
                return cookie.value
        return None

    def _ensure_authenticated(self) -> bool:
        """Verify the session is still valid and re-login if needed.

        For Bearer-token auth, re-authentication is not possible —
        just verify connectivity.

        Returns:
            True after ensuring a valid session.
        """
        if self._token_auth:
            return True

        if self._authenticated:
            try:
                resp = self.session.get(
                    f"{self.base_url}{self.API_SERVER_STATUS}",
                    timeout=10,
                    allow_redirects=True
                )
                if resp.status_code in (401, 403):
                    self._login()
                    return True
                return True
            except requests.exceptions.RequestException as e:
                self._login()
                return True
        else:
            self._login()
            return True

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Perform an HTTP request with automatic retry and re-authentication.

        Args:
            method: HTTP method.
            path: API path (relative to base URL).
            **kwargs: Extra arguments for ``requests.Session.request``.

        Returns:
            The response object.

        Raises:
            Exception: If all retries are exhausted.
        """
        kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('allow_redirects', True)

        last_error = None

        for attempt in range(self.max_retries + 1):
            url = f"{self.base_url}{path}"
            try:
                resp = self.session.request(method, url, **kwargs)

                if resp.status_code in (401, 403):
                    self._login()
                    time.sleep(0.5)
                    continue

                return resp

            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise

        raise last_error or Exception("Unknown request error")

    def _request_json(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Perform an HTTP request and parse the JSON response.

        Args:
            method: HTTP method.
            path: API path.
            **kwargs: Extra arguments for ``_request``.

        Returns:
            Parsed JSON dict.

        Raises:
            Exception: On invalid JSON.
        """
        resp = self._request(method, path, **kwargs)

        if resp.status_code == 200 and not resp.text.strip():
            self._login()
            resp = self._request(method, path, **kwargs)

        try:
            return resp.json() if resp.text.strip() else {}
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON from server: {e}")

    def get_client_sub_id(self, inbound_id: int, email: str) -> str:
        """Get the subscription ID for a client by email.

        Args:
            inbound_id: The inbound configuration ID.
            email: The client email address.

        Returns:
            The subscription ID string, or empty string.
        """
        self._ensure_authenticated()
        try:
            clients = self.get_clients(inbound_id)
            for c in clients:
                if c.get("email") == email:
                    return c.get("subId", "")
        except Exception:
            pass
        return ""

    def add_client(self, inbound_id: int, email: str, uuid_str: Optional[str] = None,
                   flow: str = "xtls-rprx-vision",
                   client_payload: Optional[dict] = None) -> Dict[str, str]:
        """Add a new client to the given inbound.

        Args:
            inbound_id: The inbound ID.
            email: Client email (used as identifier).
            uuid_str: Optional UUID; auto-generated if omitted.
            flow: Xray flow setting (only used when ``client_payload`` is None).
            client_payload: If provided, use this dict as the client settings
                instead of building the default one.  ``uuid_str`` and ``sub_id``
                are still returned; they are injected into the payload if not
                already present.

        Returns:
            A dict with ``uuid`` and ``sub_id`` keys.

        Raises:
            Exception: If the API call fails.
        """
        self._ensure_authenticated()

        if not uuid_str:
            uuid_str = str(uuid.uuid4())

        sub_id = secrets.token_urlsafe(self.SUB_ID_LEN)

        if client_payload is not None:
            # Use the caller-provided payload, inject id/subId if absent or empty
            client_payload["id"] = client_payload.get("id") or uuid_str
            client_payload["subId"] = client_payload.get("subId") or sub_id
        else:
            # Default payload for VLESS / Xray
            client_payload = {
                "email": email,
                "id": uuid_str,
                "flow": flow,
                "enable": True,
                "subId": sub_id,
                "totalGB": 0,
            }

        settings = {"clients": [client_payload]}

        resp_data = self._request_json(
            "POST",
            self.API_INBOUND_ADD_CLIENT,
            json={"id": inbound_id, "settings": json.dumps(settings, ensure_ascii=False)}
        )

        if not resp_data.get("success"):
            raise Exception(resp_data.get("msg", "Error adding client"))

        return {"uuid": uuid_str, "sub_id": sub_id}

    def remove_client(self, inbound_id: int, email: str) -> bool:
        """Remove an Xray client by email.

        Args:
            inbound_id: The inbound ID.
            email: The client email to remove.

        Returns:
            True on success.

        Raises:
            Exception: If the client is not found or removal fails.
        """
        self._ensure_authenticated()

        clients = self.get_clients(inbound_id)
        client_to_delete = next((c for c in clients if c.get("email") == email), None)

        if not client_to_delete:
            raise Exception(f"Client with email {email} not found in inbound {inbound_id}")

        client_id = client_to_delete.get("id")
        path = self.API_INBOUND_DEL_CLIENT.format(inbound_id=inbound_id, client_id=client_id)

        resp = self._request("POST", path)

        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("success"):
                    return True
                raise Exception(data.get("msg", "Unknown error during deletion"))
            except json.JSONDecodeError:
                return True
        else:
            try:
                err = resp.json()
                raise Exception(err.get("msg", f"HTTP {resp.status_code}"))
            except json.JSONDecodeError:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:100]}")

    @staticmethod
    def _parse_settings(settings_value) -> Dict[str, Any]:
        """Parse the inbound ``settings`` value, which may be a JSON string or an already-parsed dict.

        Args:
            settings_value: The ``settings`` field from an inbound object.

        Returns:
            Parsed settings dict.
        """
        if isinstance(settings_value, dict):
            return settings_value
        if isinstance(settings_value, str):
            return json.loads(settings_value)
        return {}

    def get_clients(self, inbound_id: int) -> List[Dict[str, Any]]:
        """List all clients for a given inbound.

        Args:
            inbound_id: The inbound ID.

        Returns:
            A list of client dicts.

        Raises:
            Exception: If the API call fails.
        """
        self._ensure_authenticated()

        path = self.API_INBOUND_GET.format(inbound_id=inbound_id)
        resp_data = self._request_json("GET", path)

        if not resp_data.get("success"):
            raise Exception(resp_data.get("msg", "Error fetching clients"))

        inbound = resp_data["obj"]
        settings = self._parse_settings(inbound["settings"])
        return settings.get("clients", [])

    def get_inbounds(self) -> List[Dict[str, Any]]:
        """List all inbounds from the panel.

        Returns:
            A list of inbound dicts.
        """
        self._ensure_authenticated()

        resp_data = self._request_json("GET", self.API_INBOUNDS_LIST)

        if resp_data.get("success"):
            return resp_data["obj"]
        return []

    def update_client(self, inbound_id: int, client_uuid: str, new_email: str,
                      **extra_fields) -> bool:
        """Update a client's email (rename) and/or extra fields.

        Args:
            inbound_id: The inbound ID.
            client_uuid: The UUID of the client to update.
            new_email: The new email to assign.
            **extra_fields: Additional fields to update on the client.

        Returns:
            True on success.

        Raises:
            Exception: If the update fails.
        """
        self._ensure_authenticated()

        path = self.API_INBOUND_GET.format(inbound_id=inbound_id)
        resp_data = self._request_json("GET", path)

        if not resp_data.get("success"):
            raise Exception("Failed to fetch inbound data")

        inbound = resp_data["obj"]
        settings = self._parse_settings(inbound["settings"])

        # 3x-ui 3.2.9+ validates tgId; strip empty values
        # before writing the whole inbound back.
        for client in settings.get("clients", []):
            if not client.get("tgId"):
                client.pop("tgId", None)

        updated = False
        for client in settings.get("clients", []):
            if client.get("id") == client_uuid:
                client["email"] = new_email
                client["updated_at"] = int(time.time() * 1000)
                for key, value in extra_fields.items():
                    client[key] = value
                updated = True
                break

        if not updated:
            raise Exception(f"Client with UUID {client_uuid} not found in inbound {inbound_id}")

        inbound["settings"] = json.dumps(settings, ensure_ascii=False)

        resp_data = self._request_json(
            "POST",
            self.API_INBOUND_UPDATE.format(inbound_id=inbound_id),
            json=inbound
        )

        if resp_data.get("success"):
            return True

        raise Exception(resp_data.get("msg", "Error updating inbound"))

    def get_traffic(self, inbound_id: int, email: str) -> Dict[str, Any]:
        """Get traffic statistics for a specific client.

        Args:
            inbound_id: The inbound ID.
            email: The client email.

        Returns:
            A dict with ``email``, ``up``, ``down``, ``total``,
            ``expiry_time``, and ``enable`` keys.

        Raises:
            Exception: If the client is not found.
        """
        self._ensure_authenticated()

        clients = self.get_clients(inbound_id)
        client = next((c for c in clients if c.get("email") == email), None)

        if not client:
            raise Exception(f"Client {email} not found")

        return {
            "email": client.get("email"),
            "up": client.get("up", 0),
            "down": client.get("down", 0),
            "total": client.get("total", 0),
            "expiry_time": client.get("expiry_time"),
            "enable": client.get("enable", True)
        }

    def close(self):
        """Close the underlying HTTP session."""
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
