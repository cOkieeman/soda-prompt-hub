from __future__ import annotations

import json
import os
import stat
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.local_model import LocalModelError, analyze_result_image, organize_slots
from prompt_hub.model_connections import (
    ENDPOINT_ID_PATTERN,
    MAX_API_KEY_CHARS,
    MODEL_REF_PATTERN,
    ModelConnectionError,
    ModelConnectionStore,
    _guess_provider,
    _parse_model_names,
    validate_model_base_url,
)

if TYPE_CHECKING:
    from pathlib import Path


def _endpoint_payload(**overrides) -> dict[str, object]:
    return {
        "label": "绘图 API",
        "provider": "openai_compatible",
        "base_url": "https://models.example.test/v1",
        "api_key": "secret-model-key",
        **overrides,
    }


def test_endpoint_store_is_private_and_public_values_are_redacted(settings) -> None:
    store = ModelConnectionStore(settings)
    saved = store.save_endpoint(_endpoint_payload())
    store.save_endpoint_models(
        saved["id"],
        [{"name": "provider/real-model-name", "enabled": True, "supports_vision": False}],
    )

    assert store.path == settings.library_root / "private" / "model-connections.json"
    if os.name != "nt":
        assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert saved["has_api_key"] is True
    assert "api_key" not in saved
    public_json = json.dumps(store.list_public())
    assert "secret-model-key" not in public_json
    assert store.resolve(f"{saved['id']}::provider/real-model-name").api_key == "secret-model-key"


def test_endpoint_update_preserves_secret_when_key_is_blank(settings) -> None:
    store = ModelConnectionStore(settings)
    first = store.save_endpoint(_endpoint_payload())
    updated = store.save_endpoint(
        _endpoint_payload(
            endpoint_id=first["id"],
            label="新的显示名称",
            api_key="",
        )
    )

    assert updated["id"] == first["id"]
    assert updated["label"] == "新的显示名称"
    assert store.get_endpoint(first["id"]).api_key == "secret-model-key"


def test_endpoint_update_requires_new_key_when_base_url_changes(settings) -> None:
    store = ModelConnectionStore(settings)
    first = store.save_endpoint(_endpoint_payload())

    with pytest.raises(ModelConnectionError, match=r"地址.*API Key|重新输入"):
        store.save_endpoint(
            _endpoint_payload(
                endpoint_id=first["id"],
                base_url="https://other.example.test/v1",
                api_key="",
            )
        )

    assert store.get_endpoint(first["id"]).base_url == "https://models.example.test/v1"
    assert store.get_endpoint(first["id"]).api_key == "secret-model-key"


def test_endpoint_update_accepts_new_key_when_base_url_changes(settings) -> None:
    store = ModelConnectionStore(settings)
    first = store.save_endpoint(_endpoint_payload())

    updated = store.save_endpoint(
        _endpoint_payload(
            endpoint_id=first["id"],
            base_url="https://other.example.test/v1",
            api_key="new-secret-key",
        )
    )

    assert updated["base_url"] == "https://other.example.test/v1"
    assert store.get_endpoint(first["id"]).api_key == "new-secret-key"


def test_endpoint_without_saved_key_can_change_base_url_without_key(settings) -> None:
    store = ModelConnectionStore(settings)
    first = store.save_endpoint(_endpoint_payload(api_key=""))

    updated = store.save_endpoint(
        _endpoint_payload(
            endpoint_id=first["id"],
            base_url="http://127.0.0.1:11434/v1",
            api_key="",
        )
    )

    assert updated["base_url"] == "http://127.0.0.1:11434/v1"
    assert store.get_endpoint(first["id"]).api_key == ""


def test_connection_store_reports_damaged_private_config(settings) -> None:
    store = ModelConnectionStore(settings)
    store.initialize()
    store.path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ModelConnectionError, match="外部模型配置无法读取"):
        store.list_connections()


def test_connection_store_rejects_unknown_delete(settings) -> None:
    store = ModelConnectionStore(settings)

    with pytest.raises(ModelConnectionError, match="外部模型连接不存在"):
        store.delete("external-0123456789abcdef")


def test_endpoint_id_pattern_does_not_accept_compound_model_refs() -> None:
    assert ENDPOINT_ID_PATTERN.fullmatch("external-0123456789abcdef")
    assert not ENDPOINT_ID_PATTERN.fullmatch("external-0123456789abcdef::model")
    assert MODEL_REF_PATTERN.fullmatch("external-0123456789abcdef::model")


@pytest.mark.parametrize(
    "value",
    [
        "file:///tmp/models",
        "http://api.example.test/v1",
        "https://user:secret@api.example.test/v1",
        "https://api.example.test/v1?token=secret",
    ],
)
def test_model_base_url_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ModelConnectionError):
        validate_model_base_url(value)


def test_model_base_url_allows_https_and_loopback_http() -> None:
    assert validate_model_base_url("https://api.example.test/v1/") == (
        "https://api.example.test/v1"
    )
    assert validate_model_base_url("http://127.0.0.1:1234/v1") == ("http://127.0.0.1:1234/v1")
    assert validate_model_base_url("http://127.0.0.1:11434/v1") == ("http://127.0.0.1:11434/v1")


def test_v1_config_migrates_to_v2_endpoint_groups(settings) -> None:
    path = settings.library_root / "private" / "model-connections.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "format": "soda-prompt-hub-model-connections-v1",
                "connections": [
                    {
                        "id": "external-1111111111111111",
                        "label": "LM Studio",
                        "provider": "openai_compatible",
                        "base_url": "http://127.0.0.1:1234/v1/",
                        "api_key": "",
                        "model_name": "local-a",
                        "supports_vision": False,
                    },
                    {
                        "id": "external-2222222222222222",
                        "label": "LM Studio second",
                        "provider": "openai_compatible",
                        "base_url": "http://127.0.0.1:1234/v1",
                        "api_key": "saved-key",
                        "model_name": "local-b",
                        "supports_vision": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ModelConnectionStore(settings)
    endpoints = store.list_endpoints()

    assert path.read_text(encoding="utf-8").count("soda-prompt-hub-model-connections-v1") == 1
    assert len(endpoints) == 1
    assert endpoints[0].endpoint_id == "external-1111111111111111"
    assert endpoints[0].provider == "lm_studio"
    assert endpoints[0].api_key == "saved-key"
    assert [
        (model.name, model.enabled, model.supports_vision) for model in endpoints[0].models
    ] == [
        ("local-a", True, False),
        ("local-b", True, True),
    ]
    assert [model.label for model in endpoints[0].models] == ["LM Studio", "LM Studio second"]
    legacy = store.resolve("external-2222222222222222")
    assert legacy is not None
    assert legacy.model_name == "local-b"


def test_legacy_bare_id_does_not_fall_back_to_another_enabled_model(settings) -> None:
    path = settings.library_root / "private" / "model-connections.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "format": "soda-prompt-hub-model-connections-v1",
                "connections": [
                    {
                        "id": "external-1111111111111111",
                        "label": "Model A",
                        "provider": "openai_compatible",
                        "base_url": "https://models.example.test/v1",
                        "api_key": "shared-key",
                        "model_name": "model-a",
                    },
                    {
                        "id": "external-2222222222222222",
                        "label": "Model B",
                        "provider": "openai_compatible",
                        "base_url": "https://models.example.test/v1",
                        "api_key": "shared-key",
                        "model_name": "model-b",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    store = ModelConnectionStore(settings)
    endpoint_id = store.list_endpoints()[0].endpoint_id

    store.save_endpoint_models(
        endpoint_id,
        [
            {"name": "model-a", "enabled": False},
            {"name": "model-b", "enabled": True},
        ],
    )

    assert store.resolve("external-1111111111111111") is None
    assert store.resolve("external-2222222222222222").model_name == "model-b"


def test_v1_migration_keeps_different_keys_as_separate_endpoints(settings) -> None:
    path = settings.library_root / "private" / "model-connections.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "format": "soda-prompt-hub-model-connections-v1",
                "connections": [
                    {
                        "id": "external-1111111111111111",
                        "label": "Account A",
                        "provider": "openai_compatible",
                        "base_url": "https://models.example.test/v1",
                        "api_key": "key-a",
                        "model_name": "model-a",
                    },
                    {
                        "id": "external-2222222222222222",
                        "label": "Account B",
                        "provider": "openai_compatible",
                        "base_url": "https://models.example.test/v1",
                        "api_key": "key-b",
                        "model_name": "model-b",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    endpoints = ModelConnectionStore(settings).list_endpoints()

    assert len(endpoints) == 2
    assert {endpoint.api_key for endpoint in endpoints} == {"key-a", "key-b"}


def test_new_endpoint_with_same_base_url_does_not_overwrite_existing_endpoint(settings) -> None:
    store = ModelConnectionStore(settings)
    company = store.save_endpoint(_endpoint_payload(label="公司账号", api_key="key-COMPANY"))
    store.save_endpoint_models(
        company["id"],
        [{"name": "gpt-4o", "enabled": True, "supports_vision": True}],
    )

    personal = store.save_endpoint(_endpoint_payload(label="个人账号", api_key="key-PERSONAL"))

    endpoints = store.list_endpoints()
    assert company["id"] != personal["id"]
    assert len(endpoints) == 2
    assert {endpoint.label: endpoint.api_key for endpoint in endpoints} == {
        "公司账号": "key-COMPANY",
        "个人账号": "key-PERSONAL",
    }
    assert store.resolve(f"{company['id']}::gpt-4o").api_key == "key-COMPANY"


def test_resolve_accepts_bare_endpoint_and_compound_model_ids(settings) -> None:
    store = ModelConnectionStore(settings)
    endpoint = store.save_endpoint(_endpoint_payload())
    store.save_endpoint_models(
        endpoint["id"],
        [
            {"name": "disabled-model", "enabled": False, "supports_vision": False},
            {"name": "enabled-text", "enabled": True, "supports_vision": False},
            {"name": "enabled-vision", "enabled": True, "supports_vision": True},
        ],
    )

    bare = store.resolve(endpoint["id"])
    compound = store.resolve(f"{endpoint['id']}::enabled-vision")

    assert bare is not None
    assert bare.connection_id == f"{endpoint['id']}::enabled-text"
    assert bare.model_name == "enabled-text"
    assert compound is not None
    assert compound.connection_id == f"{endpoint['id']}::enabled-vision"
    assert compound.supports_vision is True
    store.delete(endpoint["id"])
    assert store.resolve(endpoint["id"]) is None


def test_discovery_uses_backend_fetcher_without_storing_key(settings) -> None:
    captured = {}

    def fetcher(base_url: str, api_key: str) -> list[str]:
        captured.update(base_url=base_url, api_key=api_key)
        return ["model-a", "model-b"]

    store = ModelConnectionStore(settings, fetcher=fetcher)
    assert store.discover("https://models.example.test/v1", "temporary-key") == [
        {"id": "model-a", "name": "model-a", "supports_vision": None},
        {"id": "model-b", "name": "model-b", "supports_vision": None},
    ]
    assert captured == {
        "base_url": "https://models.example.test/v1",
        "api_key": "temporary-key",
    }
    assert not store.path.exists()


def test_discovery_with_saved_key_rejects_request_base_url_mismatch(settings) -> None:
    called = False

    def fetcher(_base_url: str, _api_key: str) -> list[str]:
        nonlocal called
        called = True
        return []

    store = ModelConnectionStore(settings, fetcher=fetcher)
    endpoint = store.save_endpoint(_endpoint_payload())

    with pytest.raises(ModelConnectionError, match="对应的模型服务地址"):
        store.discover("https://evil.example.test/v1", "", endpoint_id=str(endpoint["id"]))

    assert called is False


def test_discovery_with_saved_key_uses_saved_endpoint_url(settings) -> None:
    captured = {}

    def fetcher(base_url: str, api_key: str) -> list[str]:
        captured.update(base_url=base_url, api_key=api_key)
        return ["model-a"]

    store = ModelConnectionStore(settings, fetcher=fetcher)
    endpoint = store.save_endpoint(_endpoint_payload())

    assert store.discover(
        "https://models.example.test/v1",
        "",
        endpoint_id=str(endpoint["id"]),
    ) == [{"id": "model-a", "name": "model-a", "supports_vision": None}]
    assert captured == {
        "base_url": "https://models.example.test/v1",
        "api_key": "secret-model-key",
    }


def test_discovery_rejects_overlong_api_key_before_request(settings) -> None:
    called = False

    def fetcher(_base_url: str, _api_key: str) -> list[str]:
        nonlocal called
        called = True
        return []

    store = ModelConnectionStore(settings, fetcher=fetcher)
    with pytest.raises(ModelConnectionError, match="API Key 过长"):
        store.discover(
            "https://models.example.test/v1",
            "x" * (MAX_API_KEY_CHARS + 1),
        )

    assert called is False


def test_discovered_model_names_are_normalized_deduplicated_and_limited() -> None:
    names = _parse_model_names(
        [
            {"id": "model-a"},
            {"name": "model-a"},
            " model-b ",
            {"id": "", "name": "model-c"},
            None,
        ]
    )

    assert names == ["model-a", "model-b", "model-c"]


def test_model_connection_api_never_returns_secret(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "prompt_hub.model_routes.list_local_models",
        lambda: [
            {
                "id": "local-qwen",
                "name": "Local Qwen",
                "loaded": True,
                "vision": False,
                "params": "14B",
            }
        ],
    )
    with TestClient(create_app(settings)) as client:
        saved = client.post("/api/model-endpoints", json=_endpoint_payload())
        assert saved.status_code == 201
        endpoint_id = saved.json()["id"]
        assert "secret-model-key" not in saved.text
        models_update = client.post(
            f"/api/model-endpoints/{endpoint_id}/models",
            json={
                "models": [
                    {
                        "name": "provider/real-model-name",
                        "label": "Real Model",
                        "enabled": True,
                        "supports_vision": False,
                    },
                    {
                        "name": "disabled-model",
                        "label": "",
                        "enabled": False,
                        "supports_vision": True,
                    },
                ]
            },
        )
        assert models_update.status_code == 200

        listed = client.get("/api/model-endpoints")
        assert listed.status_code == 200
        assert "secret-model-key" not in listed.text
        assert listed.json()[0]["has_api_key"] is True

        models = client.get("/api/models").json()
        assert models["local_available"] is True
        assert [item["id"] for item in models["models"]] == [
            "local-qwen",
            f"{endpoint_id}::provider/real-model-name",
        ]
        assert models["external_count"] == 1

        assert client.get("/api/model-connections").status_code == 404
        missing = client.post(
            "/api/model-endpoints",
            json=_endpoint_payload(endpoint_id="external-ffffffffffffffff"),
        )
        assert missing.status_code == 404
        deleted = client.delete(f"/api/model-endpoints/{endpoint_id}")
        assert deleted.status_code == 200
        assert client.get("/api/model-endpoints").json() == []


def test_external_text_request_uses_real_model_name_and_secret(settings, monkeypatch) -> None:
    store = ModelConnectionStore(settings)
    endpoint = store.save_endpoint(_endpoint_payload())
    store.save_endpoint_models(
        endpoint["id"],
        [{"name": "provider/real-model-name", "enabled": True, "supports_vision": False}],
    )
    model_id = f"{endpoint['id']}::provider/real-model-name"
    captured = {}

    def fake_request(url, **kwargs):
        captured.update(url=url, **kwargs)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"character": "adult artist", "style": "ink illustration"}
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("prompt_hub.local_model._request_json", fake_request)
    result = organize_slots(
        brief="一位成年画师",
        slots={},
        locks={},
        model=model_id,
        target_profile="anima",
        connections=store,
    )

    assert captured["url"] == "https://models.example.test/v1/chat/completions"
    assert captured["payload"]["model"] == "provider/real-model-name"
    assert captured["payload"]["max_tokens"] == 4096
    assert captured["api_key"] == "secret-model-key"
    assert captured["allow_redirects"] is False
    assert captured["response_limit"] == 4 * 1024 * 1024
    assert captured["service_name"] == "外部模型服务"
    assert result["model"] == model_id


def test_external_vision_request_uses_openai_compatible_shape(
    settings,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ModelConnectionStore(settings)
    endpoint = store.save_endpoint(_endpoint_payload())
    store.save_endpoint_models(
        endpoint["id"],
        [{"name": "provider/real-model-name", "enabled": True, "supports_vision": True}],
    )
    model_id = f"{endpoint['id']}::provider/real-model-name"
    image_path = tmp_path / "result.png"
    Image.new("RGB", (64, 64), "teal").save(image_path)
    captured = {}

    def fake_request(url, **kwargs):
        captured.update(url=url, **kwargs)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary_zh": "画面清晰",
                                "observed_slots": {},
                                "strengths": [],
                                "issues": [],
                                "improvements": [],
                                "reconstructed_prompts": {},
                                "safety_warning": "",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("prompt_hub.local_model._request_json", fake_request)
    result = analyze_result_image(
        image_path=image_path,
        project={"brief_zh": "测试"},
        model=model_id,
        connections=store,
    )

    content = captured["payload"]["messages"][1]["content"]
    assert captured["payload"]["model"] == "provider/real-model-name"
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert result["summary_zh"] == "画面清晰"


def test_deleted_external_connection_is_not_sent_to_lm_studio(settings) -> None:
    store = ModelConnectionStore(settings)

    with pytest.raises(LocalModelError, match="外部模型连接不存在或已删除"):
        organize_slots(
            brief="一位成年画师",
            slots={},
            locks={},
            model="external-0123456789abcdef",
            target_profile="anima",
            connections=store,
        )


class TestCaptionAssistSelection:
    """翻译与改写用哪个模型是使用者选的。不是「刚好排第一」。"""

    def _store_with_two_models(self, settings) -> tuple[ModelConnectionStore, str, str]:
        store = ModelConnectionStore(settings)
        saved = store.save_endpoint(_endpoint_payload())
        store.save_endpoint_models(
            saved["id"],
            [
                {"name": "first-model", "enabled": True, "supports_vision": True},
                {"name": "second-model", "enabled": True, "supports_vision": True},
            ],
        )
        return store, f"{saved['id']}::first-model", f"{saved['id']}::second-model"

    def test_unset_falls_back_so_it_keeps_working(self, settings) -> None:
        """没设定过也要能用。强迫先设定不如保持可用。"""
        store, _, _ = self._store_with_two_models(settings)
        assert store.get_caption_assist() is None

    def test_selection_wins_over_the_first_connection(self, settings) -> None:
        store, first, second = self._store_with_two_models(settings)
        store.set_caption_assist(second)

        chosen = store.get_caption_assist()
        assert chosen is not None
        assert chosen.connection_id == second
        assert store.list_connections()[0].connection_id == first

    def test_saving_an_endpoint_does_not_wipe_the_selection(self, settings) -> None:
        """设定跟端点存在同一个档案里。写端点时忘了带上它就会被清掉。"""
        store, _, second = self._store_with_two_models(settings)
        store.set_caption_assist(second)

        store.save_endpoint(_endpoint_payload(label="改个名字"))

        chosen = store.get_caption_assist()
        assert chosen is not None
        assert chosen.connection_id == second

    def test_blank_clears_back_to_automatic(self, settings) -> None:
        store, _, second = self._store_with_two_models(settings)
        store.set_caption_assist(second)
        store.set_caption_assist("")
        assert store.get_caption_assist() is None

    def test_unknown_connection_is_rejected(self, settings) -> None:
        store, _first, _second = self._store_with_two_models(settings)
        with pytest.raises(ModelConnectionError):
            store.set_caption_assist("external-0000000000000000::nope")

    def test_endpoint_exposes_current_choice_and_whether_it_was_chosen(self, settings) -> None:
        _store, first, second = self._store_with_two_models(settings)
        with TestClient(create_app(settings)) as client:
            unset = client.get("/api/caption-assist").json()
            assert unset["configured"] is False
            assert unset["connection_id"] == first

            client.put("/api/caption-assist", json={"connection_id": second})
            after = client.get("/api/caption-assist").json()

        assert after["configured"] is True
        assert after["connection_id"] == second
        assert [option["id"] for option in after["options"]] == [first, second]


class TestLocalNetworkEndpoints:
    """自架模型服务通常在区网里。而且多半只有 HTTP。"""

    def test_private_addresses_may_use_plain_http(self) -> None:
        for url in (
            "http://192.168.1.180:8888/v1",
            "http://10.0.0.5:8000/v1",
            "http://172.16.3.4/v1",
            "http://127.0.0.1:1234/v1",
            "http://localhost:1234/v1",
        ):
            assert validate_model_base_url(url).startswith("http://")

    def test_public_http_is_still_refused(self) -> None:
        """放行的是不路由到网际网路的位址。不是放弃 HTTPS 要求。"""
        for url in ("http://api.example.com/v1", "http://8.8.8.8/v1"):
            with pytest.raises(ModelConnectionError):
                validate_model_base_url(url)

    def test_carrier_grade_nat_is_not_our_lan(self) -> None:
        """100.64/10 会经过电信业者的网路。不属于「自己的区网」。"""
        with pytest.raises(ModelConnectionError):
            validate_model_base_url("http://100.64.1.1/v1")

    def test_hostnames_are_not_trusted_as_local(self) -> None:
        """主机名要经过 DNS 才知道指向哪里。而 DNS 的答案可以被改。"""
        with pytest.raises(ModelConnectionError):
            validate_model_base_url("http://myserver.local/v1")

    def test_lan_lm_studio_and_ollama_are_recognised(self) -> None:
        """跑在别台机器上的 LM Studio 依然是 LM Studio。"""
        assert _guess_provider("http://192.168.1.180:1234/v1") == "lm_studio"
        assert _guess_provider("http://192.168.1.180:11434/v1") == "ollama"
        assert _guess_provider("http://192.168.1.180:8888/v1") == "openai_compatible"
