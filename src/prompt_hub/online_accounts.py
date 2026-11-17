"""Danbooru account and remote favorite operations used by the online gallery."""

from __future__ import annotations

import base64
import json
import re
from http import HTTPStatus
from threading import RLock
from typing import IO, TYPE_CHECKING, override
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from prompt_hub.studio_store import StudioError, write_json

if TYPE_CHECKING:
    from pathlib import Path

ACCOUNT_URL = "https://danbooru.donmai.us"
MAX_RESPONSE_BYTES = 4_000_000
MAX_USERNAME_LENGTH = 160
MAX_API_KEY_LENGTH = 12000


class NoAccountRedirect(HTTPRedirectHandler):
    @override
    def redirect_request(
        self, req: Request, fp: IO[bytes], code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


class OnlineAccountStore:
    def __init__(self, library_root: Path) -> None:
        self.path = library_root / "private" / "online-gallery-account.json"
        self.lock = RLock()

    def read(self) -> dict[str, str]:
        if not self.path.is_file():
            return {"username": "", "api_key": ""}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            message = "畫廊帳號設定無法讀取"
            raise StudioError(message) from error

    def public(self) -> dict[str, object]:
        account = self.read()
        return {"username": account["username"], "has_api_key": bool(account["api_key"])}

    def save(self, values: dict[str, str]) -> dict[str, object]:
        with self.lock:
            existing = self.read()
            username = self.username(values.get("username", ""))
            key = str(values.get("api_key") or "").strip()
            if not key and username != existing["username"]:
                message = "帳號已變更，請填寫對應的 API Key"
                raise StudioError(message)
            key = key or existing["api_key"]
            if not key or len(key) > MAX_API_KEY_LENGTH:
                message = "請填寫有效的 Danbooru API Key"
                raise StudioError(message)
            account = {"username": username, "api_key": key}
            profile = self.request("/profile.json", account=account)
            if not isinstance(profile, dict) or not profile.get("id"):
                message = "Danbooru 帳號驗證未返回有效的使用者"
                raise StudioError(message)
            write_json(self.path, account)
            return self.public()

    def clear(self) -> dict[str, object]:
        with self.lock:
            write_json(self.path, {"username": "", "api_key": ""})
            return self.public()

    @staticmethod
    def username(value: str) -> str:
        username = str(value).strip()
        if not username or len(username) > MAX_USERNAME_LENGTH or re.search(r'[\s:"\\]', username):
            message = "請填寫 Danbooru 使用者名稱或數字 ID"
            raise StudioError(message)
        return username

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        values: dict[str, object] | None = None,
        account: dict[str, str] | None = None,
    ) -> object:
        credentials = self.read() if account is None else account
        headers = {"User-Agent": "NAI-Launcher/1.0", "Accept": "application/json"}
        if credentials["api_key"]:
            token = base64.b64encode(
                (credentials["username"] + ":" + credentials["api_key"]).encode()
            ).decode()
            headers["Authorization"] = "Basic " + token
        body = None
        if values is not None:
            body = urlencode(values).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(ACCOUNT_URL + path, data=body, headers=headers, method=method)  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
        try:
            with build_opener(NoAccountRedirect()).open(request, timeout=35) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                message = "遠端收藏回應超過大小限制"
                raise StudioError(message)
            return json.loads(raw) if raw else {}
        except HTTPError as error:
            # Deleting a missing favorite is idempotent. A 422 on creation can
            # also mean an invalid post or a quota error and must remain visible.
            if method == "DELETE" and error.code == HTTPStatus.NOT_FOUND:
                return {}
            message = f"Danbooru 帳號請求失敗，HTTP {error.code}"
            raise StudioError(message) from error
        except (URLError, TimeoutError, OSError, ValueError) as error:
            message = "Danbooru 帳號連線失敗，請稍後重試"
            raise StudioError(message) from error

    def favorites(self, username: str, page: int, *, general_only: bool = False) -> list[dict]:
        user = self.username(username or self.read()["username"])
        tags = "ordfav:" + user + (" rating:g" if general_only else "")
        result = self.request("/posts.json?" + urlencode({"tags": tags, "page": page, "limit": 36}))
        if not isinstance(result, list):
            message = "遠端收藏沒有返回圖片清單"
            raise StudioError(message)
        return result

    def favorite(self, post_id: str, *, selected: bool | None = None) -> bool:
        if not str(post_id).isdigit():
            message = "遠端收藏圖片 ID 無效"
            raise StudioError(message)
        if not self.read()["api_key"]:
            message = "請先設定 Danbooru 帳號與 API Key"
            raise StudioError(message)
        if selected is None:
            result = self.request(
                "/favorites.json?" + urlencode({"search[post_id]": post_id, "limit": 1})
            )
            return isinstance(result, list) and bool(result)
        if selected:
            self.request("/favorites.json", method="POST", values={"post_id": post_id})
        else:
            self.request("/favorites/" + post_id + ".json", method="DELETE")
        return selected
