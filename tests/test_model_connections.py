from __future__ import annotations

import json
import stat
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.local_model import LocalModelError, analyze_result_image, organize_slots
from prompt_hub.model_connections import (
    ModelConnectionError,
    ModelConnectionStore,
    validate_model_base_url,
)

if TYPE_CHECKING:
    from pathlib import Path


def _connection_payload(**overrides) -> dict[str, object]:
    return {
        "label": "绘图 API",
        "provider": "openai_compatible",
        "base_url": "https://models.example.test/v1",
        "api_key": "secret-model-key",
        "model_name": "provider/real-model-name",
        "supports_vision": False,
        **overrides,
    }


def test_connection_store_is_private_and_public_values_are_redacted(settings) -> None:
    store = ModelConnectionStore(settings)
    saved = store.save(_connection_payload())

    assert store.path == settings.library_root / "private" / "model-connections.json"
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert saved["has_api_key"] is True
    assert "api_key" not in saved
    assert "secret-model-key" not in json.dumps(store.list_public())
    assert store.resolve(saved["id"]).api_key == "secret-model-key"


def test_connection_update_preserves_secret_when_key_is_blank(settings) -> None:
    store = ModelConnectionStore(settings)
    first = store.save(_connection_payload())
    updated = store.save(
        _connection_payload(
            connection_id=first["id"],
            label="新的显示名称",
            api_key="",
            supports_vision=True,
        )
    )

    assert updated["id"] == first["id"]
    assert updated["label"] == "新的显示名称"
    assert updated["supports_vision"] is True
    assert store.resolve(first["id"]).api_key == "secret-model-key"


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


def test_discovery_uses_backend_fetcher_without_storing_key(settings) -> None:
    captured = {}

    def fetcher(base_url: str, api_key: str) -> list[str]:
        captured.update(base_url=base_url, api_key=api_key)
        return ["model-a", "model-b"]

    store = ModelConnectionStore(settings, fetcher=fetcher)
    assert store.discover("https://models.example.test/v1", "temporary-key") == [
        "model-a",
        "model-b",
    ]
    assert captured == {
        "base_url": "https://models.example.test/v1",
        "api_key": "temporary-key",
    }
    assert not store.path.exists()


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
        saved = client.post("/api/model-connections", json=_connection_payload())
        assert saved.status_code == 201
        connection_id = saved.json()["id"]
        assert "secret-model-key" not in saved.text

        listed = client.get("/api/model-connections")
        assert listed.status_code == 200
        assert "secret-model-key" not in listed.text
        assert listed.json()[0]["has_api_key"] is True

        models = client.get("/api/models").json()
        assert models["local_available"] is True
        assert [item["id"] for item in models["models"]] == [
            "local-qwen",
            connection_id,
        ]

        deleted = client.delete(f"/api/model-connections/{connection_id}")
        assert deleted.status_code == 200
        assert client.get("/api/model-connections").json() == []


def test_external_text_request_uses_real_model_name_and_secret(settings, monkeypatch) -> None:
    store = ModelConnectionStore(settings)
    saved = store.save(_connection_payload())
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
        model=saved["id"],
        target_profile="anima",
        connections=store,
    )

    assert captured["url"] == "https://models.example.test/v1/chat/completions"
    assert captured["payload"]["model"] == "provider/real-model-name"
    assert captured["api_key"] == "secret-model-key"
    assert captured["allow_redirects"] is False
    assert captured["response_limit"] == 4 * 1024 * 1024
    assert captured["service_name"] == "外部模型服务"
    assert result["model"] == saved["id"]


def test_external_vision_request_uses_openai_compatible_shape(
    settings,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ModelConnectionStore(settings)
    saved = store.save(_connection_payload(supports_vision=True))
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
        model=saved["id"],
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
