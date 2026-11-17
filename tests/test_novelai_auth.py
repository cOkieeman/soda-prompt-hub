from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.novelai_auth import NovelAIAccounts, derive_access_key, subscription_summary
from prompt_hub.studio_providers import ImageProviderStore
from prompt_hub.studio_store import StudioError


@pytest.fixture
def accounts(tmp_path):
    return NovelAIAccounts(ImageProviderStore(tmp_path))


def test_novelai_access_key_uses_launcher_argon2_parameters():
    # Stable test-only values also cover the base64url truncation convention.
    assert derive_access_key("test@example.com", "test-password") == (
        "35kcUNI4AU6Xfo3i8PB-L0Ae91wHwLttBxGDpOPug1agN-9PuHtOQDWRzSTazrka"
    )


def test_login_validates_before_saving_and_redacts_secrets(accounts, monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    calls = []

    def respond(url, **values):
        calls.append((url, values))
        return {
            "tier": 3,
            "active": True,
            "trainingStepsLeft": {
                "fixedTrainingStepsLeft": 1000,
                "purchasedTrainingSteps": 250,
            },
        }

    monkeypatch.setattr(module, "request_account", respond)
    result = accounts.login(
        {"mode": "token", "token": '"Bearer Bearer pst-test-only"', "label": "Example"}
    )
    assert calls == [("https://image.novelai.net/user/subscription", {"token": "pst-test-only"})]
    assert result["subscription"]["tier"] == "Opus"
    assert "pst-test-only" not in json.dumps(result)
    identifier = result["provider"]["id"]
    assert accounts.providers.require(identifier, "novelai")["api_key"] == "pst-test-only"
    restored = NovelAIAccounts(ImageProviderStore(accounts.providers.path.parent.parent))
    assert restored.session(identifier)["authenticated"]
    accounts.logout(identifier)
    assert not restored.session(identifier)["authenticated"]
    assert not restored.session(identifier)["provider"]["has_api_key"]


def test_failed_relogin_preserves_the_existing_account(accounts, monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    monkeypatch.setattr(module, "request_account", lambda *_args, **_kwargs: {"tier": 2})
    previous = accounts.login({"token": "pst-previous-token"})
    identifier = previous["provider"]["id"]

    def fail(*_args, **_kwargs):
        msg = "Login rejected"
        raise StudioError(msg)

    monkeypatch.setattr(module, "request_account", fail)
    with pytest.raises(StudioError):
        accounts.login({"provider_id": identifier, "token": "pst-invalid-token"})
    assert accounts.providers.require(identifier, "novelai")["api_key"] == "pst-previous-token"
    assert accounts.session(identifier)["authenticated"]


def test_credentials_login_sends_derived_key_and_does_not_save_password(accounts, monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    calls = []

    def respond(url, **values):
        calls.append((url, values))
        return {"accessToken": "test-access-token"} if url.endswith("/login") else {"tier": 1}

    monkeypatch.setattr(module, "request_account", respond)
    result = accounts.login(
        {"mode": "credentials", "email": "test@example.com", "password": "test-password"}
    )
    assert calls[0][1] == {"key": derive_access_key("test@example.com", "test-password")}
    assert calls[0][0] == "https://image.novelai.net/user/login"
    assert calls[1][0] == "https://image.novelai.net/user/subscription"
    assert calls[1][1] == {"token": "test-access-token"}
    raw = accounts.providers.path.read_text(encoding="utf-8")
    assert "test-password" not in raw
    assert calls[0][1]["key"] not in raw
    assert result["provider"]["label"] == "test"


def test_subscription_refresh_and_manual_edits_preserve_valid_account(accounts, monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    monkeypatch.setattr(
        module, "request_account", lambda *_args, **_kwargs: {"tier": 3, "trainingStepsLeft": 99}
    )
    logged_in = accounts.login({"token": "pst-test-only"})
    provider = logged_in["provider"]
    accounts.providers.save({"provider": {**provider, "model": "nai-diffusion-5-full"}})
    assert accounts.session(provider["id"], refresh=True)["subscription"]["fixed_anlas"] == 99
    accounts.providers.save({"provider": {**provider, "api_key": "different-token"}})
    assert not accounts.session(provider["id"])["authenticated"]


def test_account_api_routes_only_return_public_data(settings, monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    monkeypatch.setattr(module, "request_account", lambda *_args, **_kwargs: {"tier": 3})
    with TestClient(create_app(settings)) as client:
        result = client.post("/api/studio/novelai/login", json={"token": "pst-route-secret"})
        assert result.status_code == 200
        assert "pst-route-secret" not in result.text
        identifier = result.json()["provider"]["id"]
        session = client.get(
            "/api/studio/novelai/session", params={"provider_id": identifier, "refresh": True}
        )
        assert session.json()["authenticated"]
        assert "pst-route-secret" not in client.get("/api/studio/bootstrap").text
        assert (
            client.post("/api/studio/novelai/logout", json={"provider_id": identifier}).status_code
            == 200
        )
        assert not client.get(
            "/api/studio/novelai/session", params={"provider_id": identifier}
        ).json()["authenticated"]


def test_remote_auth_failure_never_exposes_response_or_credentials(monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    def denied(*args, **_kwargs):
        request = args[0]
        assert request.get_header("User-agent") == "NAI-Launcher/1.0"
        assert request.get_header("Origin") == "https://novelai.net"
        assert request.get_header("Referer") == "https://novelai.net/"
        msg = "https://image.novelai.net/user/subscription"
        raise HTTPError(msg, 401, "secret-message", {}, None)

    monkeypatch.setattr(module, "urlopen", denied)
    with pytest.raises(StudioError) as error:
        module.request_account(module.OFFICIAL_USER_API + "/user/subscription", token="test-secret")  # noqa: S106 - fixed dummy token for the authentication regression
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "values", [{"mode": {}}, {"token": {}}, {"mode": "credentials"}, {"token": ""}]
)
def test_invalid_login_inputs_are_rejected(accounts, values):
    with pytest.raises(StudioError):
        accounts.login(values)


def test_legacy_numeric_anlas_balance_is_supported():
    assert subscription_summary({"trainingStepsLeft": 75})["fixed_anlas"] == 75


def test_logged_out_official_account_cannot_queue_generation(accounts, monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    monkeypatch.setattr(module, "request_account", lambda *_args, **_kwargs: {"tier": 3})
    identifier = accounts.login({"token": "pst-test-only"})["provider"]["id"]
    accounts.logout(identifier)
    with pytest.raises(StudioError, match="登入"):
        accounts.providers.require(identifier, "novelai")


def test_malformed_subscription_fields_do_not_break_account_saving():
    summary = subscription_summary(
        {"tier": {}, "expiresAt": float("inf"), "usage": {"percent": None}}
    )
    assert summary["tier"] == "Unknown"
    assert summary["expires_at"] is None
    assert summary["usage"]["percent"] == 0


def test_rejected_refresh_invalidates_cached_auth_and_generation(accounts, monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    monkeypatch.setattr(module, "request_account", lambda *_args, **_kwargs: {"tier": 3})
    identifier = accounts.login({"token": "pst-test-only"})["provider"]["id"]

    def rejected(*_args, **_kwargs):
        msg = "Authentication rejected"
        raise module.NovelAIAuthenticationError(msg)

    monkeypatch.setattr(module, "request_account", rejected)
    result = accounts.session(identifier, refresh=True)
    assert not result["authenticated"]
    assert result["subscription"] is None
    assert not accounts.session(identifier)["authenticated"]
    assert result["provider"]["has_api_key"]
    with pytest.raises(StudioError, match="登入"):
        accounts.providers.require(identifier, "novelai")


def test_network_failure_preserves_the_last_verified_account(accounts, monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    monkeypatch.setattr(module, "request_account", lambda *_args, **_kwargs: {"tier": 3})
    identifier = accounts.login({"token": "pst-test-only"})["provider"]["id"]

    def offline(*_args, **_kwargs):
        msg = "Connection timed out"
        raise StudioError(msg)

    monkeypatch.setattr(module, "request_account", offline)
    with pytest.raises(StudioError):
        accounts.session(identifier, refresh=True)
    assert accounts.session(identifier)["authenticated"]


def test_official_subscription_refresh_uses_the_launcher_user_api_host(accounts, monkeypatch):
    import prompt_hub.novelai_auth as module  # noqa: PLC0415 - isolate test-specific dependency and monkeypatch setup

    urls = []

    def subscription(url, **_kwargs):
        urls.append(url)
        return {"tier": 3}

    monkeypatch.setattr(module, "request_account", subscription)
    identifier = accounts.login({"token": "pst-test-only"})["provider"]["id"]
    assert accounts.session(identifier, refresh=True)["authenticated"]
    assert urls == ["https://image.novelai.net/user/subscription"] * 2
