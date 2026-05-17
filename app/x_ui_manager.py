import requests
import json
import uuid
import time
import secrets
from typing import Optional, List, Dict, Any
from app.config import XUI_BASE_URL, XUI_USERNAME, XUI_PASSWORD


class XUIClient:
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

        self._login()
        self._authenticated = True

    def _login(self) -> bool:
        self.session.cookies.clear()

        login_url = f"{self.base_url}{self.API_LOGIN}"

        resp = self._do_login_request(login_url)

        if not resp or not resp.ok:
            alt_url = f"{self.base_url}{self.API_LOGIN_ALT}"
            if alt_url != login_url:
                resp = self._do_login_request(alt_url)

        if not resp or not resp.ok:
            body = resp.text[:300] if resp else "No response"
            raise Exception(f"Не удалось авторизоваться в 3x-ui (status {resp.status_code if resp else 'N/A'})")

        session_cookie = self._get_session_cookie()
        if not session_cookie:
            time.sleep(1)
            self.session.cookies.clear()
            resp = self._do_login_request(login_url)
            if not resp or not resp.ok or not self._get_session_cookie():
                raise Exception("Не удалось установить сессию после повторной попытки")

        self._authenticated = True
        return True

    def _do_login_request(self, url: str) -> Optional[requests.Response]:
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
        for name in ['session', '3x-ui', 'x-ui', 'JSESSIONID']:
            value = self.session.cookies.get(name)
            if value:
                return value
        return None

    def _ensure_authenticated(self) -> bool:
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

        raise last_error or Exception("Неизвестная ошибка запроса")

    def _request_json(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        resp = self._request(method, path, **kwargs)

        if resp.status_code == 200 and not resp.text.strip():
            self._login()
            resp = self._request(method, path, **kwargs)

        try:
            return resp.json() if resp.text.strip() else {}
        except json.JSONDecodeError as e:
            raise Exception(f"Невалидный JSON от сервера: {e}")

    def get_client_sub_id(self, inbound_id: int, email: str) -> str:
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
                   flow: str = "xtls-rprx-vision") -> Dict[str, str]:
        self._ensure_authenticated()

        if not uuid_str:
            uuid_str = str(uuid.uuid4())

        sub_id = secrets.token_urlsafe(self.SUB_ID_LEN)

        settings = {
            "clients": [{
                "email": email,
                "id": uuid_str,
                "flow": flow,
                "enable": True,
                "subId": sub_id
            }]
        }

        resp_data = self._request_json(
            "POST",
            self.API_INBOUND_ADD_CLIENT,
            json={"id": inbound_id, "settings": json.dumps(settings, ensure_ascii=False)}
        )

        if not resp_data.get("success"):
            raise Exception(resp_data.get("msg", "Ошибка при добавлении клиента"))

        return {"uuid": uuid_str, "sub_id": sub_id}

    def remove_client(self, inbound_id: int, email: str) -> bool:
        self._ensure_authenticated()

        clients = self.get_clients(inbound_id)
        client_to_delete = next((c for c in clients if c.get("email") == email), None)

        if not client_to_delete:
            raise Exception(f"Клиент с email {email} не найден в inbound {inbound_id}")

        client_id = client_to_delete.get("id")
        path = self.API_INBOUND_DEL_CLIENT.format(inbound_id=inbound_id, client_id=client_id)

        resp = self._request("POST", path)

        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("success"):
                    return True
                raise Exception(data.get("msg", "Неизвестная ошибка при удалении"))
            except json.JSONDecodeError:
                return True
        else:
            try:
                err = resp.json()
                raise Exception(err.get("msg", f"HTTP {resp.status_code}"))
            except json.JSONDecodeError:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:100]}")

    def get_clients(self, inbound_id: int) -> List[Dict[str, Any]]:
        self._ensure_authenticated()

        path = self.API_INBOUND_GET.format(inbound_id=inbound_id)
        resp_data = self._request_json("GET", path)

        if not resp_data.get("success"):
            raise Exception(resp_data.get("msg", "Ошибка получения клиентов"))

        inbound = resp_data["obj"]
        settings = json.loads(inbound["settings"])
        return settings.get("clients", [])

    def get_inbounds(self) -> List[Dict[str, Any]]:
        self._ensure_authenticated()

        resp_data = self._request_json("GET", self.API_INBOUNDS_LIST)

        if resp_data.get("success"):
            return resp_data["obj"]
        return []

    def update_client(self, inbound_id: int, client_uuid: str, new_email: str,
                      **extra_fields) -> bool:
        self._ensure_authenticated()

        path = self.API_INBOUND_GET.format(inbound_id=inbound_id)
        resp_data = self._request_json("GET", path)

        if not resp_data.get("success"):
            raise Exception("Не удалось получить данные inbound")

        inbound = resp_data["obj"]
        settings = json.loads(inbound["settings"])

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
            raise Exception(f"Клиент с UUID {client_uuid} не найден в inbound {inbound_id}")

        inbound["settings"] = json.dumps(settings, ensure_ascii=False)

        resp_data = self._request_json(
            "POST",
            self.API_INBOUND_UPDATE.format(inbound_id=inbound_id),
            json=inbound
        )

        if resp_data.get("success"):
            return True

        raise Exception(resp_data.get("msg", "Ошибка обновления inbound"))

    def get_traffic(self, inbound_id: int, email: str) -> Dict[str, Any]:
        self._ensure_authenticated()

        clients = self.get_clients(inbound_id)
        client = next((c for c in clients if c.get("email") == email), None)

        if not client:
            raise Exception(f"Клиент {email} не найден")

        return {
            "email": client.get("email"),
            "up": client.get("up", 0),
            "down": client.get("down", 0),
            "total": client.get("total", 0),
            "expiry_time": client.get("expiry_time"),
            "enable": client.get("enable", True)
        }

    def close(self):
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
