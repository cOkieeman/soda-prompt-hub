from __future__ import annotations

import ipaddress
import json
import os
import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.client import HTTPException as HTTPClientError
from threading import RLock
from typing import IO, TYPE_CHECKING, Literal, override
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

if TYPE_CHECKING:
    from http.client import HTTPMessage

    from prompt_hub.config import Settings

MODEL_CONNECTION_FORMAT_V1 = "soda-prompt-hub-model-connections-v1"
MODEL_CONNECTION_FORMAT = "soda-prompt-hub-model-connections-v2"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_DISCOVERED_MODELS = 500
MAX_API_KEY_CHARS = 12000
MAX_ENDPOINT_MODELS = 200
MAX_ENDPOINTS = 50
LM_STUDIO_PORT = 1234
OLLAMA_PORT = 11434
ENDPOINT_ID_PATTERN = re.compile(r"^external-[a-f0-9]{16}$")
MODEL_REF_PATTERN = re.compile(r"^external-[a-f0-9]{16}(?:::.{1,300})?$")
Provider = Literal["openai", "lm_studio", "ollama", "openai_compatible"]
ModelFetcher = Callable[[str, str], list[str]]


class ModelConnectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EndpointModel:
    name: str
    label: str = ""
    enabled: bool = False
    supports_vision: bool = False
    legacy_id: str = ""

    def public(self, endpoint_id: str) -> dict[str, object]:
        return {
            "id": _compound_model_id(endpoint_id, self.name),
            "name": self.name,
            "label": self.label,
            "enabled": self.enabled,
            "supports_vision": self.supports_vision,
        }

    def stored(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "label": self.label,
            "legacy_id": self.legacy_id,
            "name": self.name,
            "supports_vision": self.supports_vision,
        }


@dataclass(frozen=True, slots=True)
class ModelEndpoint:
    endpoint_id: str
    label: str
    provider: Provider
    base_url: str
    api_key: str
    models: list[EndpointModel] = field(default_factory=list)

    def public(self) -> dict[str, object]:
        enabled_count = sum(1 for model in self.models if model.enabled)
        return {
            "id": self.endpoint_id,
            "label": self.label,
            "provider": self.provider,
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "enabled_model_count": enabled_count,
            "models": [model.public(self.endpoint_id) for model in self.models],
        }

    def stored(self) -> dict[str, object]:
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "id": self.endpoint_id,
            "label": self.label,
            "models": [model.stored() for model in self.models],
            "provider": self.provider,
        }


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


class ModelConnectionStore:
    def __init__(self, settings: Settings, *, fetcher: ModelFetcher | None = None) -> None:
        self.path = settings.library_root / "private" / "model-connections.json"
        self._fetcher = fetcher or _fetch_openai_models
        self._write_lock = RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_endpoints(self) -> list[ModelEndpoint]:
        return sorted(
            self._read_endpoints(),
            key=lambda item: (item.label.casefold(), item.endpoint_id),
        )

    def list_connections(self) -> list[ModelConnection]:
        connections: list[ModelConnection] = []
        for endpoint in self.list_endpoints():
            connections.extend(
                _connection_for_model(endpoint, model) for model in endpoint.models if model.enabled
            )
        return connections

    def list_public(self) -> list[dict[str, object]]:
        return [endpoint.public() for endpoint in self.list_endpoints()]

    def list_model_options(self) -> list[dict[str, object]]:
        return [connection.model_option() for connection in self.list_connections()]

    def get_endpoint(self, endpoint_id: str) -> ModelEndpoint:
        _validate_endpoint_id(endpoint_id)
        endpoint = next(
            (item for item in self.list_endpoints() if item.endpoint_id == endpoint_id),
            None,
        )
        if endpoint is None:
            message = "外部模型连接不存在"
            raise ModelConnectionError(message)
        return endpoint

    def resolve(self, connection_id: str) -> ModelConnection | None:
        if not MODEL_REF_PATTERN.fullmatch(connection_id):
            return None
        endpoint_id, separator, model_name = connection_id.partition("::")
        endpoint = next(
            (item for item in self.list_endpoints() if item.endpoint_id == endpoint_id),
            None,
        )
        if separator and endpoint is not None:
            model = next(
                (item for item in endpoint.models if item.enabled and item.name == model_name),
                None,
            )
            return _connection_for_model(endpoint, model) if model else None
        if not separator:
            legacy_matches: list[tuple[ModelEndpoint, EndpointModel]] = [
                (candidate, model)
                for candidate in self.list_endpoints()
                for model in candidate.models
                if model.legacy_id == connection_id
            ]
            if legacy_matches:
                match = next(
                    ((candidate, model) for candidate, model in legacy_matches if model.enabled),
                    None,
                )
                if match is None:
                    return None
                return _connection_for_model(match[0], match[1], connection_id=connection_id)
        if endpoint is not None:
            model = next((item for item in endpoint.models if item.enabled), None)
            return _connection_for_model(endpoint, model) if model else None
        return None

    def discover(
        self,
        base_url: str,
        api_key: str = "",
        *,
        endpoint_id: str = "",
    ) -> list[dict[str, object]]:
        clean_key = api_key.strip()
        if len(clean_key) > MAX_API_KEY_CHARS:
            message = "API Key 过长"
            raise ModelConnectionError(message)
        if endpoint_id and not clean_key:
            endpoint = self.get_endpoint(endpoint_id)
            normalized_url = validate_model_base_url(base_url)
            if normalized_url != endpoint.base_url:
                message = "已保存密钥只能用于对应的模型服务地址"
                raise ModelConnectionError(message)
            normalized_url = endpoint.base_url
            clean_key = endpoint.api_key
        else:
            normalized_url = validate_model_base_url(base_url)
        names = self._fetcher(normalized_url, clean_key)
        return [{"id": name, "name": name, "supports_vision": None} for name in names]

    def save_endpoint(self, values: Mapping[str, object]) -> dict[str, object]:
        with self._write_lock:
            return self._save_endpoint(values)

    def _save_endpoint(self, values: Mapping[str, object]) -> dict[str, object]:
        endpoints = self.list_endpoints()
        endpoint_id = _clean_string(values.get("endpoint_id"), 80)
        provider = _provider_from_value(values.get("provider"))
        base_url = validate_model_base_url(_clean_string(values.get("base_url"), 2048))
        label = _clean_string(values.get("label"), 160) or _default_label(provider, base_url)
        api_key = _clean_string(values.get("api_key"), MAX_API_KEY_CHARS)

        current = None
        if endpoint_id:
            _validate_endpoint_id(endpoint_id)
            current = next((item for item in endpoints if item.endpoint_id == endpoint_id), None)
            if current is None:
                message = "外部模型连接不存在"
                raise ModelConnectionError(message)
        else:
            if len(endpoints) >= MAX_ENDPOINTS:
                message = "外部模型端点数量已达上限"
                raise ModelConnectionError(message)
            endpoint_id = f"external-{secrets.token_hex(8)}"
        if not api_key and current is not None:
            if base_url != current.base_url and current.api_key:
                message = "模型服务地址已变化。请重新输入对应的 API Key"
                raise ModelConnectionError(message)
            api_key = current.api_key
        endpoint = ModelEndpoint(
            endpoint_id=endpoint_id,
            label=label,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            models=list(current.models) if current else [],
        )
        retained = [item for item in endpoints if item.endpoint_id != endpoint_id]
        self._write([*retained, endpoint])
        return endpoint.public()

    def save_endpoint_models(
        self,
        endpoint_id: str,
        model_values: list[Mapping[str, object]],
    ) -> dict[str, object]:
        with self._write_lock:
            return self._save_endpoint_models(endpoint_id, model_values)

    def _save_endpoint_models(
        self,
        endpoint_id: str,
        model_values: list[Mapping[str, object]],
    ) -> dict[str, object]:
        endpoint = self.get_endpoint(endpoint_id)
        existing_legacy = {
            model.name: model.legacy_id for model in endpoint.models if model.legacy_id
        }
        models = _models_from_values(model_values, existing_legacy=existing_legacy)
        endpoints = [
            item
            if item.endpoint_id != endpoint_id
            else ModelEndpoint(
                endpoint_id=item.endpoint_id,
                label=item.label,
                provider=item.provider,
                base_url=item.base_url,
                api_key=item.api_key,
                models=models,
            )
            for item in self.list_endpoints()
        ]
        self._write(endpoints)
        return self.get_endpoint(endpoint.endpoint_id).public()

    def delete(self, connection_id: str) -> dict[str, object]:
        with self._write_lock:
            return self._delete(connection_id)

    def _delete(self, connection_id: str) -> dict[str, object]:
        _validate_endpoint_id(connection_id)
        endpoints = self.list_endpoints()
        retained = [item for item in endpoints if item.endpoint_id != connection_id]
        if len(retained) == len(endpoints):
            message = "外部模型连接不存在"
            raise ModelConnectionError(message)
        self._write(retained)
        return {"deleted": connection_id}

    def _read_endpoints(self) -> list[ModelEndpoint]:
        if not self.path.is_file():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            message = "外部模型配置无法读取"
            raise ModelConnectionError(message) from error
        if not isinstance(payload, dict):
            message = "外部模型配置格式无效"
            raise ModelConnectionError(message)
        file_format = payload.get("format")
        if file_format == MODEL_CONNECTION_FORMAT_V1:
            return _migrate_v1(payload)
        if file_format != MODEL_CONNECTION_FORMAT:
            message = "外部模型配置格式无效"
            raise ModelConnectionError(message)
        items = payload.get("endpoints", [])
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            message = "外部模型配置内容无效"
            raise ModelConnectionError(message)
        return [_endpoint_from_mapping(item) for item in items]

    def get_caption_assist(self) -> ModelConnection | None:
        """翻译与改写要用哪个模型。

        没有设定时回传 None。呼叫端会退回「第一个启用的连线」——
        那是设定这个选项之前的行为。保持可用比强迫先设定重要。
        """
        stored = self._read_caption_assist()
        return self.resolve(stored) if stored else None

    def set_caption_assist(self, connection_id: str) -> None:
        """记下选择。空字串代表清除。回到自动挑第一个。"""
        with self._write_lock:
            self._set_caption_assist(connection_id)

    def _set_caption_assist(self, connection_id: str) -> None:
        value = connection_id.strip()
        if value and self.resolve(value) is None:
            message = "选择的模型连接不存在或已停用"
            raise ModelConnectionError(message)
        self._write(self._read_endpoints(), caption_assist=value)

    def _read_caption_assist(self) -> str:
        if not self.path.is_file():
            return ""
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        return str(payload.get("caption_assist", "")) if isinstance(payload, dict) else ""

    def _write(self, endpoints: list[ModelEndpoint], caption_assist: str | None = None) -> None:
        self.initialize()
        temporary = self.path.with_name(f".{self.path.name}.{secrets.token_hex(8)}.tmp")
        # caption_assist 不是 endpoints 的一部分。但存在同一个档案里。
        # None 代表这次不是要改它——沿用既有值。否则每次存端点都会把它清掉。
        keep = self._read_caption_assist() if caption_assist is None else caption_assist
        payload = {
            "endpoints": [endpoint.stored() for endpoint in endpoints],
            "format": MODEL_CONNECTION_FORMAT,
        }
        if keep:
            payload["caption_assist"] = keep
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
                )
            temporary.replace(self.path)
            self.path.chmod(0o600)
        finally:
            temporary.unlink(missing_ok=True)


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
    if scheme == "http" and not _is_local_network(host):
        message = "公网模型服务必须使用 HTTPS。HTTP 只允许本机与内网地址"
        raise ModelConnectionError(message)
    path = (parsed.path or "").rstrip("/")
    return urlunsplit((scheme, parsed.netloc.lower(), path, "", ""))


# 不路由到网际网路的位址。自架模型服务通常就放在这些网段。
# 不用 ipaddress 的 is_private 是因为它也涵盖 100.64.0.0/10 CGNAT——
# 那段流量会经过电信业者的网路。不属于「自己的区网」。
_LOCAL_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _is_local_network(host: str) -> bool:
    """本机或自己的区网。

    只认 IP 字面值。主机名要经过 DNS 才知道指向哪里。
    而 DNS 的答案可以被改——放行 example.local 这类名字等于
    把判断交给一个我们无法验证的来源。需要用区网服务就填 IP。
    """
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    return any(address in network for network in _LOCAL_NETWORKS)


def _clean_string(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _validate_endpoint_id(endpoint_id: str) -> None:
    if not ENDPOINT_ID_PATTERN.fullmatch(endpoint_id):
        message = "外部模型连接 ID 无效"
        raise ModelConnectionError(message)


def _provider_from_value(value: object) -> Provider:
    provider = _clean_string(value, 40) or "openai_compatible"
    if provider in {"openai", "lm_studio", "ollama", "openai_compatible"}:
        return provider
    message = "外部模型端点类型无效"
    raise ModelConnectionError(message)


def _default_label(provider: Provider, base_url: str) -> str:
    labels = {
        "lm_studio": "LM Studio",
        "ollama": "Ollama",
        "openai": "OpenAI",
        "openai_compatible": "自定义模型服务",
    }
    return labels.get(provider) or base_url


def _guess_provider(base_url: str) -> Provider:
    parsed = urlsplit(base_url)
    host = (parsed.hostname or "").lower().rstrip(".")
    port = parsed.port
    if host == "api.openai.com":
        return "openai"
    # 跑在区网另一台机器上的 LM Studio 依然是 LM Studio。
    # provider 只是显示标签。不影响请求行为。猜对了使用者少改一次。
    if _is_local_network(host) and port == LM_STUDIO_PORT:
        return "lm_studio"
    if _is_local_network(host) and port == OLLAMA_PORT:
        return "ollama"
    return "openai_compatible"


def _compound_model_id(endpoint_id: str, model_name: str) -> str:
    return f"{endpoint_id}::{model_name}"


def _connection_for_model(
    endpoint: ModelEndpoint,
    model: EndpointModel,
    *,
    connection_id: str = "",
) -> ModelConnection:
    label = model.label or model.name
    return ModelConnection(
        connection_id=connection_id or _compound_model_id(endpoint.endpoint_id, model.name),
        label=f"{endpoint.label} · {label}",
        provider=endpoint.provider,
        base_url=endpoint.base_url,
        api_key=endpoint.api_key,
        model_name=model.name,
        supports_vision=model.supports_vision,
    )


def _models_from_values(
    model_values: list[Mapping[str, object]],
    *,
    existing_legacy: Mapping[str, str] | None = None,
) -> list[EndpointModel]:
    models: list[EndpointModel] = []
    seen: set[str] = set()
    for value in model_values:
        name = _clean_string(value.get("name"), 300)
        if not name or name in seen:
            continue
        seen.add(name)
        models.append(
            EndpointModel(
                name=name,
                label=_clean_string(value.get("label"), 160),
                enabled=bool(value.get("enabled", False)),
                supports_vision=bool(value.get("supports_vision", False)),
                legacy_id=_clean_string(value.get("legacy_id"), 80)
                or (existing_legacy or {}).get(name, ""),
            )
        )
        if len(models) >= MAX_ENDPOINT_MODELS:
            break
    return models


def _endpoint_from_mapping(value: Mapping[str, object]) -> ModelEndpoint:
    endpoint_id = _clean_string(value.get("id"), 80)
    _validate_endpoint_id(endpoint_id)
    models = value.get("models", [])
    if not isinstance(models, list) or not all(isinstance(item, dict) for item in models):
        message = "外部模型配置内容无效"
        raise ModelConnectionError(message)
    base_url = validate_model_base_url(_clean_string(value.get("base_url"), 2048))
    provider = _provider_from_value(value.get("provider"))
    return ModelEndpoint(
        endpoint_id=endpoint_id,
        label=_clean_string(value.get("label"), 160) or _default_label(provider, base_url),
        provider=provider,
        base_url=base_url,
        api_key=_clean_string(value.get("api_key"), MAX_API_KEY_CHARS),
        models=_models_from_values(models),
    )


def _migrate_v1(payload: Mapping[str, object]) -> list[ModelEndpoint]:
    items = payload.get("connections", [])
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        message = "外部模型配置内容无效"
        raise ModelConnectionError(message)
    endpoints: list[ModelEndpoint] = []
    model_rows: dict[str, list[Mapping[str, object]]] = {}
    for item in items:
        base_url = validate_model_base_url(_clean_string(item.get("base_url"), 2048))
        item_key = _clean_string(item.get("api_key"), MAX_API_KEY_CHARS)
        current_index = next(
            (
                index
                for index, endpoint in enumerate(endpoints)
                if endpoint.base_url == base_url
                and (not endpoint.api_key or not item_key or endpoint.api_key == item_key)
            ),
            -1,
        )
        if current_index < 0:
            endpoint_id = _clean_string(item.get("id"), 80)
            _validate_endpoint_id(endpoint_id)
            provider = _guess_provider(base_url)
            endpoint = ModelEndpoint(
                endpoint_id=endpoint_id,
                label=_default_label(provider, base_url),
                provider=provider,
                base_url=base_url,
                api_key=item_key,
            )
            endpoints.append(endpoint)
            current_index = len(endpoints) - 1
            model_rows[endpoint.endpoint_id] = []
        elif not endpoints[current_index].api_key and item_key:
            endpoint = endpoints[current_index]
            endpoints[current_index] = ModelEndpoint(
                endpoint_id=endpoint.endpoint_id,
                label=endpoint.label,
                provider=endpoint.provider,
                base_url=endpoint.base_url,
                api_key=item_key,
            )
        model_name = _clean_string(item.get("model_name"), 300)
        if model_name:
            model_rows[endpoints[current_index].endpoint_id].append(
                {
                    "enabled": True,
                    "label": _clean_string(item.get("label"), 160),
                    "legacy_id": _clean_string(item.get("id"), 80),
                    "name": model_name,
                    "supports_vision": bool(item.get("supports_vision", False)),
                }
            )
    return [
        ModelEndpoint(
            endpoint_id=endpoint.endpoint_id,
            label=endpoint.label,
            provider=endpoint.provider,
            base_url=endpoint.base_url,
            api_key=endpoint.api_key,
            models=_models_from_values(model_rows[endpoint.endpoint_id]),
        )
        for endpoint in endpoints
    ]


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
    except (HTTPClientError, OSError) as error:
        message = "无法连接模型服务"
        raise ModelConnectionError(message) from error
    if len(body) > MAX_RESPONSE_BYTES:
        message = "模型列表响应过大"
        raise ModelConnectionError(message)
    try:
        payload = json.loads(body)
    except (ValueError, RecursionError) as error:
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
