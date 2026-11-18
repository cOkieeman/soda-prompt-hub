from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.model_connections import ModelConnectionError, ModelConnectionStore
from prompt_hub.studio_providers import ImageProviderStore
from prompt_hub.studio_store import StudioError


def provider(**values):
    return {
        "kind": "openai",
        "label": "Image service",
        "base_url": "https://images.example/v1",
        "model": "image-model",
        "api_key": "",
        **values,
    }


def test_saving_a_new_connection_returns_its_id_for_subsequent_edits(settings):
    with TestClient(create_app(settings)) as client:
        first = client.put(
            "/api/studio/settings", json={"provider": provider(api_key="saved-test-key")}
        ).json()
        saved_id = first["saved_provider_id"]
        second = client.put(
            "/api/studio/settings", json={"provider": provider(id=saved_id, model="other-image")}
        ).json()
    assert len(second["providers"]) == 1
    assert second["saved_provider_id"] == saved_id
    assert second["providers"][0]["has_api_key"]
    assert "saved-test-key" not in str(second)
    assert (
        ImageProviderStore(settings.library_root).require(saved_id, "openai")["api_key"]
        == "saved-test-key"
    )


@pytest.mark.parametrize(
    ("key", "model"), [("", ""), ("", "image-model"), ("saved-test-key", "image-model")]
)
def test_connection_deletion_does_not_require_credentials_or_model(settings, key, model):
    store = ImageProviderStore(settings.library_root)
    store.save(
        {"comfy_root": "C:/ComfyUI", "caption_worker": {"python": "python.exe", "device": "cpu"}}
    )
    target = store.save({"provider": provider(api_key=key, model=model)})["saved_provider_id"]
    other = store.save({"provider": provider(label="Other service")})["saved_provider_id"]
    with TestClient(create_app(settings)) as client:
        response = client.delete("/api/studio/providers/" + target)
        assert response.status_code == 200
        config = response.json()
        assert [item["id"] for item in config["providers"]] == [other]
        assert config["comfy_root"] == "C:/ComfyUI"
        assert config["caption_worker"]["python"] == "python.exe"
        assert client.delete("/api/studio/providers/" + target).status_code == 422


@pytest.mark.parametrize(
    ("stored", "new", "expected"),
    [
        ("saved-test-key", "", "saved-test-key"),
        ("saved-test-key", "replacement-test-key", "replacement-test-key"),
        ("", "", ""),
    ],
)
def test_model_discovery_uses_the_existing_credentials_and_shared_fetcher(
    settings, stored, new, expected
):
    requests = []
    store = ImageProviderStore(settings.library_root)
    saved_id = store.save({"provider": provider(api_key=stored, model="")})["saved_provider_id"]
    models = ModelConnectionStore(
        settings, fetcher=lambda url, key: requests.append((url, key)) or ["image-a", "image-b"]
    )
    result = store.discover_models(provider(id=saved_id, api_key=new, model=""), models)
    assert requests == [("https://images.example/v1", expected)]
    assert [item["id"] for item in result] == ["image-a", "image-b"]
    assert "api_key" not in str(result)
    assert store.public()["providers"][0]["model"] == ""


def test_discovery_of_an_unsaved_connection_does_not_create_it(settings):
    store = ImageProviderStore(settings.library_root)
    models = ModelConnectionStore(settings, fetcher=lambda *_: ["image-a"])
    assert store.discover_models(provider(), models)[0]["id"] == "image-a"
    assert store.public()["providers"] == []


def test_saved_credentials_cannot_be_forwarded_to_a_different_host(settings):
    store = ImageProviderStore(settings.library_root)
    saved_id = store.save({"provider": provider(api_key="saved-test-key")})["saved_provider_id"]
    models = ModelConnectionStore(settings, fetcher=lambda *_: pytest.fail("No request expected"))
    with pytest.raises(StudioError, match="地址"):
        store.discover_models(provider(id=saved_id, base_url="https://other.example/v1"), models)


def test_discovery_routes_convert_fetch_errors_to_a_user_facing_response(settings, monkeypatch):
    def fail(*_):
        msg = "模型服務沒有返回有效 JSON"
        raise ModelConnectionError(msg)

    monkeypatch.setattr("prompt_hub.model_connections._fetch_openai_models", fail)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/studio/providers/models", json=provider())
    assert response.status_code == 422
    assert "有效 JSON" in response.json()["detail"]
