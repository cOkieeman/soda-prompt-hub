import io
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from prompt_hub.online_accounts import OnlineAccountStore
from prompt_hub.studio_store import StudioError


def test_account_verifies_before_saving_and_never_returns_the_key(tmp_path, monkeypatch):
    store = OnlineAccountStore(tmp_path)
    requests = []

    class Opener:
        def open(self, request, **_kwargs):
            requests.append(request)
            return io.BytesIO(b'{"id":123}')

    monkeypatch.setattr("prompt_hub.online_accounts.build_opener", lambda *_args: Opener())
    public = store.save({"username": "example", "api_key": "test-only-secret"})
    assert public == {"username": "example", "has_api_key": True}
    assert "test-only-secret" not in json.dumps(public)
    assert requests[0].full_url == "https://danbooru.donmai.us/profile.json"
    assert requests[0].get_header("Authorization").startswith("Basic ")
    assert store.save({"username": "example", "api_key": ""}) == public
    with pytest.raises(StudioError, match="帳號已變更"):
        store.save({"username": "another", "api_key": ""})
    assert store.clear() == {"username": "", "has_api_key": False}


def test_public_remote_favorites_use_launchers_favorite_time_order(tmp_path, monkeypatch):
    store = OnlineAccountStore(tmp_path)
    paths = []
    monkeypatch.setattr(store, "request", lambda path, **_kwargs: paths.append(path) or [])
    store.favorites("123", 2, general_only=True)
    params = parse_qs(urlsplit(paths[0]).query)
    assert params == {"tags": ["ordfav:123 rating:g"], "page": ["2"], "limit": ["36"]}


@pytest.mark.parametrize("username", ["", "test rating:e", 'test"', "test:other"])
def test_remote_username_cannot_insert_search_terms(tmp_path, username):
    with pytest.raises(StudioError):
        OnlineAccountStore(tmp_path).username(username)


def test_remote_favorite_changes_use_expected_api_and_require_an_account(tmp_path, monkeypatch):
    store = OnlineAccountStore(tmp_path)
    with pytest.raises(StudioError, match="API Key"):
        store.favorite("45", selected=True)
    store.path.parent.mkdir(parents=True)
    store.path.write_text(json.dumps({"username": "example", "api_key": "test-only"}))
    calls = []
    monkeypatch.setattr(store, "request", lambda path, **kwargs: calls.append((path, kwargs)) or [])
    assert store.favorite("45", selected=True)
    assert not store.favorite("45", selected=False)
    assert calls == [
        ("/favorites.json", {"method": "POST", "values": {"post_id": "45"}}),
        ("/favorites/45.json", {"method": "DELETE"}),
    ]


def test_invalid_favorite_is_not_reported_as_saved(tmp_path, monkeypatch):
    store = OnlineAccountStore(tmp_path)

    class Opener:
        def open(self, request, **_kwargs):
            raise HTTPError(request.full_url, 422, "Invalid post", {}, None)

    monkeypatch.setattr("prompt_hub.online_accounts.build_opener", lambda *_args: Opener())
    with pytest.raises(StudioError, match="HTTP 422"):
        store.request("/favorites.json", method="POST", values={"post_id": "45"})
