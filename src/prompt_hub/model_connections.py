from __future__ import annotations

import ipaddress
import json
import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING, Literal, override
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

if TYPE_CHECKING:
    from http.client import HTTPMessage

    from prompt_hub.config import Settings

MODEL_CONNECTION_FORMAT = "soda-prompt-hub-model-connections-v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_DISCOVERED_MODELS = 500
MAX_API_KEY_CHARS = 12000
CONNECTION_ID_PATTERN = re.compile(r"^external-[a-f0-9]{16}$")
Provider = Literal["openai_compatible"]
ModelFetcher = Callable[[str, str], list[str]]


class ModelConnectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ModelConnection:
    connection_id: str
    label: str
    provider: Provider
    base_url: str
    api_key: str
    model_name: str
    supports_vision: bool

    def public(self) -> dict[str, object]:
        return {
            "id": self.connection_id,
            "label": self.label,
            "provider": self.provider,
            "base_url": self.base_url,
            "model_name": self.model_name,
            "supports_vision": self.supports_vision,
            "has_api_key": bool(self.api_key),
        }

    def model_option(self) -> dict[str, object]:
        return {
            "id": self.connection_id,
            "name": self.label,
            "loaded": False,
            "vision": self.supports_vision,
            "params": "外部 API",
            "provider": self.provider,
            "source": "external",
        }

    def stored(self) -> dict[str, object]:
        return {
            "id": self.connection_id,
            "label": self.label,
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "model_name": self.model_name,
            "supports_vision": self.supports_vision,
        }


class ModelConnectionStore:
    def __init__(self, settings: Settings, *, fetcher: ModelFetcher | None = None) -> None:
        self.path = settings.library_root / "private" / "model-connections.json"
        self._fetcher = fetcher or _fetch_openai_models

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_connections(self) -> list[ModelConnection]:
        connections = [_connection_from_mapping(item) for item in self._read_items()]
        return sorted(connections, key=lambda item: (item.label.casefold(), item.connection_id))

    def list_public(self) -> list[dict[str, object]]:
        return [connection.public() for connection in self.list_connections()]

    def list_model_options(self) -> list[dict[str, object]]:
        return [connection.model_option() for connection in self.list_connections()]

    def resolve(self, connection_id: str) -> ModelConnection | None:
        return next(
            (
                connection
                for connection in self.list_connections()
                if connection.connection_id == connection_id
            ),
            None,
        )

    def discover(self, base_url: str, api_key: str) -> list[str]:
        normalized_url = validate_model_base_url(base_url)
        clean_key = api_key.strip()
        if len(clean_key) > MAX_API_KEY_CHARS:
            message = "API Key 过长"
            raise ModelConnectionError(message)
        return self._fetcher(normalized_url, clean_key)

    def save(self, values: Mapping[str, object]) -> dict[str, object]:
        connections = self.list_connections()
        connection_id = _clean_string(values.get("connection_id"), 80)
        provider = _clean_string(values.get("provider"), 40) or "openai_compatible"
        if provider != "openai_compatible":
            message = "首版只支持 OpenAI-compatible 接口"
            raise ModelConnectionError(message)
        base_url = validate_model_base_url(_clean_string(values.get("base_url"), 2048))
        model_name = _clean_string(values.get("model_name"), 300)
        if not model_name:
            message = "请填写上游服务使用的模型名称"
            raise ModelConnectionError(message)
        label = _clean_string(values.get("label"), 160) or model_name
        api_key = _clean_string(values.get("api_key"), MAX_API_KEY_CHARS)
        supports_vision = bool(values.get("supports_vision", False))

        current = None
        if connection_id:
            if not CONNECTION_ID_PATTERN.fullmatch(connection_id):
                message = "外部模型连接 ID 无效"
                raise ModelConnectionError(message)
            current = next(
                (item for item in connections if item.connection_id == connection_id),
                None,
            )
            if current is None:
                message = "外部模型连接不存在"
                raise ModelConnectionError(message)
        else:
            current = next(
                (
                    item
                    for item in connections
                    if item.base_url == base_url and item.model_name == model_name
                ),
                None,
            )
            connection_id = current.connection_id if current else f"external-{secrets.token_hex(8)}"
        if not api_key and current is not None:
            api_key = current.api_key

        connection = ModelConnection(
            connection_id=connection_id,
            label=label,
            provider="openai_compatible",
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            supports_vision=supports_vision,
        )
        retained = [item for item in connections if item.connection_id != connection_id]
        self._write([*retained, connection])
        return connection.public()

    def delete(self, connection_id: str) -> dict[str, object]:
        if not CONNECTION_ID_PATTERN.fullmatch(connection_id):
            message = "外部模型连接 ID 无效"
            raise ModelConnectionError(message)
        connections = self.list_connections()
        retained = [item for item in connections if item.connection_id != connection_id]
        if len(retained) == len(connections):
            message = "外部模型连接不存在"
            raise ModelConnectionError(message)
        self._write(retained)
        return {"deleted": connection_id}

    def _read_items(self) -> list[Mapping[str, object]]:
        if not self.path.is_file():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            message = "外部模型配置无法读取"
            raise ModelConnectionError(message) from error
        if not isinstance(payload, dict) or payload.get("format") != MODEL_CONNECTION_FORMAT:
            message = "外部模型配置格式无效"
            raise ModelConnectionError(message)
        items = payload.get("connections", [])
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            message = "外部模型配置内容无效"
            raise ModelConnectionError(message)
        return items

    def _write(self, connections: list[ModelConnection]) -> None:
        self.initialize()
        temporary = self.path.with_name(f".{self.path.name}.{secrets.token_hex(8)}.tmp")
        payload = {
            "format": MODEL_CONNECTION_FORMAT,
            "connections": [connection.stored() for connection in connections],
        }
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(self.path)
        self.path.chmod(0o600)


def validate_model_base_url(value: str) -> str:
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        _ = parsed.port
    except ValueError as error:
        message = "模型服务地址无效"
        raise ModelConnectionError(message) from error
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or scheme not in {"http", "https"}:
        message = "模型服务地址必须使用 HTTP 或 HTTPS"
        raise ModelConnectionError(message)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        message = "模型服务地址不能包含账号、查询参数或片段"
        raise ModelConnectionError(message)
    if scheme == "http" and not _is_loopback(host):
        message = "远程模型服务必须使用 HTTPS。HTTP 只允许本机地址"
        raise ModelConnectionError(message)
    path = (parsed.path or "").rstrip("/")
    return urlunsplit((scheme, parsed.netloc.lower(), path, "", ""))


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _clean_string(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _connection_from_mapping(value: Mapping[str, object]) -> ModelConnection:
    connection_id = _clean_string(value.get("id"), 80)
    if not CONNECTION_ID_PATTERN.fullmatch(connection_id):
        message = "外部模型配置包含无效 ID"
        raise ModelConnectionError(message)
    provider = _clean_string(value.get("provider"), 40)
    if provider != "openai_compatible":
        message = "外部模型配置包含不支持的接口协议"
        raise ModelConnectionError(message)
    model_name = _clean_string(value.get("model_name"), 300)
    if not model_name:
        message = "外部模型配置缺少模型名称"
        raise ModelConnectionError(message)
    return ModelConnection(
        connection_id=connection_id,
        label=_clean_string(value.get("label"), 160) or model_name,
        provider="openai_compatible",
        base_url=validate_model_base_url(_clean_string(value.get("base_url"), 2048)),
        api_key=_clean_string(value.get("api_key"), MAX_API_KEY_CHARS),
        model_name=model_name,
        supports_vision=bool(value.get("supports_vision", False)),
    )


class _NoRedirect(HTTPRedirectHandler):
    @override
    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> None:
        return None


def _fetch_openai_models(base_url: str, api_key: str) -> list[str]:
    headers = {"Accept": "application/json", "User-Agent": "SodaPromptHub/0.1 model-discovery"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(f"{base_url}/models", headers=headers)  # noqa: S310
    try:
        with build_opener(_NoRedirect).open(request, timeout=20) as response:
            declared = response.headers.get("Content-Length", "")
            if declared.isdigit() and int(declared) > MAX_RESPONSE_BYTES:
                message = "模型列表响应过大"
                raise ModelConnectionError(message)
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        message = f"模型列表读取失败: 服务返回 HTTP {error.code}"
        raise ModelConnectionError(message) from error
    except (URLError, TimeoutError) as error:
        message = "无法连接模型服务"
        raise ModelConnectionError(message) from error
    if len(body) > MAX_RESPONSE_BYTES:
        message = "模型列表响应过大"
        raise ModelConnectionError(message)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        message = "模型服务没有返回有效 JSON"
        raise ModelConnectionError(message) from error
    if not isinstance(payload, dict):
        message = "模型列表格式无效"
        raise ModelConnectionError(message)
    raw_models = payload.get("data", payload.get("models", []))
    if not isinstance(raw_models, list):
        message = "模型列表格式无效"
        raise ModelConnectionError(message)
    return _parse_model_names(raw_models)


def _parse_model_names(raw_models: list[object]) -> list[str]:
    models: list[str] = []
    for item in raw_models:
        name = ""
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = _clean_string(item.get("id") or item.get("name"), 300)
        if name and name not in models:
            models.append(name)
        if len(models) >= MAX_DISCOVERED_MODELS:
            break
    return models
