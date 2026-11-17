from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from http import HTTPStatus
from threading import RLock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from prompt_hub.studio_providers import NOVELAI_CLIENT_HEADERS, ImageProviderStore
from prompt_hub.studio_store import StudioError

OFFICIAL_API = "https://api.novelai.net"
OFFICIAL_IMAGE_API = "https://image.novelai.net"
# NAI Launcher NaiApiEndpointConfig.userUrl routes official user APIs to the image host.
OFFICIAL_USER_API = OFFICIAL_IMAGE_API


MAX_ACCOUNT_VALUE_CHARS = 12000


class NovelAIAuthenticationError(StudioError):
    pass


def derive_access_key(email: str, password: str) -> str:
    # Match NAI Launcher v4.3.1 NAICryptoService and NovelAI's client derivation.
    prefix = password.encode("utf-16-le")[:12].decode("utf-16-le", errors="replace")
    salt = hashlib.blake2b(
        (prefix + email + "novelai_data_access_key").encode(), digest_size=16
    ).digest()
    key = Argon2id(salt=salt, length=64, iterations=2, lanes=1, memory_cost=1953).derive(
        password.encode()
    )
    return base64.urlsafe_b64encode(key).decode().rstrip("=")[:64]


def request_account(url: str, *, token: str = "", key: str = "") -> dict[str, Any]:  # noqa: C901 - protocol validation and dispatch stay together
    headers = {
        **NOVELAI_CLIENT_HEADERS,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, data=json.dumps({"key": key}).encode() if key else None)  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            msg = "NovelAI 帳號回應超過大小限制"
            raise StudioError(msg)
        value = json.loads(raw)
    except HTTPError as error:
        if error.code in {400, 401} or (
            error.code == HTTPStatus.FORBIDDEN
            and "application/json" in error.headers.get("Content-Type", "")
        ):
            msg = "NovelAI 登入失敗，請檢查帳號密碼或 Token 是否有效"
            raise NovelAIAuthenticationError(msg) from None
        if error.code == HTTPStatus.FORBIDDEN:
            msg = "NovelAI 返回存取驗證頁，請檢查網路或稍後重試"
            raise StudioError(msg) from None
        if error.code == HTTPStatus.TOO_MANY_REQUESTS:
            msg = "NovelAI 請求過於頻繁，請稍後重試"
            raise StudioError(msg) from None
        if error.code in {404, 405}:
            msg = "此服務未提供 NovelAI 帳號查詢，請使用圖片服務連線設定"
            raise StudioError(msg) from None
        msg = f"NovelAI 帳號服務暫時無法使用，HTTP {error.code}"
        raise StudioError(msg) from None
    except (URLError, TimeoutError, OSError):
        msg = "NovelAI 帳號連線逾時或中斷，請檢查網路後重試"
        raise StudioError(msg) from None
    except (ValueError, UnicodeError):
        msg = "NovelAI 帳號服務未返回有效資料"
        raise StudioError(msg) from None
    if not isinstance(value, dict):
        msg = "NovelAI 帳號服務未返回有效資料"
        raise StudioError(msg)
    return value


def subscription_summary(value: dict[str, Any]) -> dict[str, Any]:
    def number(item: Any) -> int | float:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
        return item if isinstance(item, (int, float)) and math.isfinite(item) else 0

    credit = value.get("trainingStepsLeft", {})
    if isinstance(credit, (int, float)):
        credit = {"fixedTrainingStepsLeft": credit}
    if not isinstance(credit, dict):
        credit = {}
    tiers = {"0": "Paper", "1": "Tablet", "2": "Scroll", "3": "Opus"}
    usage = value.get("usage")
    return {
        "tier": tiers.get(str(value.get("tier", 0)), "Unknown"),
        "active": bool(value.get("active")),
        "expires_at": number(value.get("expiresAt")) or None,
        "fixed_anlas": number(credit.get("fixedTrainingStepsLeft")),
        "purchased_anlas": number(credit.get("purchasedTrainingSteps")),
        "usage": {
            "percent": number(usage.get("percent")),
            "isNegative": bool(usage.get("isNegative")),
        }
        if isinstance(usage, dict)
        else None,
        "checked_at": datetime.now(UTC).isoformat(),
    }


class NovelAIAccounts:
    def __init__(self, providers: ImageProviderStore) -> None:
        self.providers = providers
        self._lock = RLock()

    def login(self, values: dict[str, Any]) -> dict[str, Any]:
        mode = values.get("mode", "token")
        email = values.get("email", "")
        password = values.get("password", "")
        token = values.get("token", "")
        label = values.get("label", "")
        identifier = values.get("provider_id", "")
        if (
            not isinstance(mode, str)
            or mode not in {"token", "credentials"}
            or any(
                not isinstance(item, str) or len(item) > MAX_ACCOUNT_VALUE_CHARS
                for item in (email, password, token, label, identifier)
            )
        ):
            msg = "NovelAI 登入欄位格式有誤"
            raise StudioError(msg)
        with self._lock:
            if identifier:
                existing = self._provider(identifier)
                if existing["base_url"] not in {OFFICIAL_API, OFFICIAL_IMAGE_API}:
                    msg = "第三方服務請使用圖片服務連線設定"
                    raise StudioError(msg)
            if mode == "credentials":
                email = email.strip()
                if "@" not in email or not password:
                    msg = "請填寫 NovelAI 電子郵件與密碼"
                    raise StudioError(msg)
                login = request_account(
                    OFFICIAL_USER_API + "/user/login", key=derive_access_key(email, password)
                )
                token = login.get("accessToken", "")
                label = label.strip() or email.split("@")[0]
            else:
                token = token.strip().strip("\"'")
                while re.match(r"(?i)^Bearer\s+", token):
                    token = re.sub(r"(?i)^Bearer\s+", "", token).strip()
                token = re.sub(r"\s+", "", token)
            if not isinstance(token, str) or not token or len(token) > MAX_ACCOUNT_VALUE_CHARS:
                msg = "請填寫有效的 NovelAI Token"
                raise StudioError(msg)
            subscription = request_account(OFFICIAL_USER_API + "/user/subscription", token=token)
            account = subscription_summary(subscription) | {"mode": mode}
            config = self.providers.save(
                {
                    "provider": {
                        "id": identifier,
                        "kind": "novelai",
                        "label": label.strip() or "NovelAI",
                        "base_url": OFFICIAL_IMAGE_API,
                        "model": existing["model"] if identifier else "nai-diffusion-4-5-full",
                        "api_key": token,
                    }
                },
                novelai_account=account,
            )
            provider = next(
                item
                for item in reversed(config["providers"])
                if item["kind"] == "novelai" and item.get("novelai_account") == account
            )
            return {"provider": provider, "subscription": account, "authenticated": True}

    def session(self, identifier: str, *, refresh: bool = False) -> dict[str, Any]:
        if not identifier:
            return {"authenticated": False, "provider": None}
        with self._lock:
            provider = self._provider(identifier)
            public = next(p for p in self.providers.public()["providers"] if p["id"] == identifier)
            official = provider["base_url"] in {OFFICIAL_API, OFFICIAL_IMAGE_API}
            if not provider.get("api_key") or not official:
                return {"authenticated": False, "provider": public, "official": official}
            account = provider.get("novelai_account")
            if refresh:
                try:
                    account = subscription_summary(
                        request_account(
                            OFFICIAL_USER_API + "/user/subscription", token=provider["api_key"]
                        )
                    ) | {"mode": (account or {}).get("mode", "token")}
                except NovelAIAuthenticationError:
                    account = {**(account or {}), "authentication_status": "invalid"}
                    public = self.providers.update_novelai_account(identifier, account)
                    return {
                        "authenticated": False,
                        "provider": public,
                        "subscription": None,
                        "official": official,
                        "error": "NovelAI 憑證已失效，請重新登入",
                    }
                public = self.providers.update_novelai_account(identifier, account)
            authenticated = bool(account) and account.get("authentication_status") != "invalid"
            return {
                "authenticated": authenticated,
                "provider": public,
                "subscription": account if authenticated else None,
                "official": official,
                **(
                    {"error": "NovelAI 憑證已失效，請重新登入"}
                    if account and not authenticated
                    else {}
                ),
            }

    def logout(self, identifier: str) -> dict[str, Any]:
        with self._lock:
            self.providers.disconnect_novelai(identifier)
            return {"authenticated": False}

    def _provider(self, identifier: str) -> dict[str, Any]:
        provider = self.providers.get_provider(identifier)
        if not provider or provider["kind"] != "novelai":
            msg = "NovelAI 帳號連線不存在"
            raise StudioError(msg)
        return provider
