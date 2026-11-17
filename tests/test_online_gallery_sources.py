import hashlib
import io
import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.gallery import GalleryStore
from prompt_hub.online_gallery import OnlineGallery, fetch_bytes, fetch_json
from prompt_hub.studio_store import StudioError


@pytest.fixture
def online(settings):
    return OnlineGallery(settings.library_root, GalleryStore(settings))


def test_aitag_monthly_and_random_results_keep_per_image_prompts(online, monkeypatch):
    calls = []

    def cached(url, _ttl=300):
        calls.append(url)
        if url.endswith("/api/config"):
            return {"asset_base_url": "https://ai-img.10118899.xyz"}
        if "/api/work/" in url:
            return {
                "work": {"title": "Two images"},
                "images": [
                    {
                        "image_type": "nai",
                        "author_id": 5,
                        "file_name": "one",
                        "ai_json": json.dumps(
                            {"Comment": json.dumps({"prompt": "blue coat", "uc": "text"})}
                        ),
                    },
                    {
                        "image_type": "nai",
                        "author_id": 5,
                        "file_name": "two",
                        "ai_json": "invalid json",
                        "prompt_text": "red coat",
                    },
                ],
            }
        return {
            "total": 120,
            "items": [
                {"id": 1, "tags": '["blue_hair"]'},
                {"id": 2, "tags": "red_hair coat"},
            ],
        }

    monkeypatch.setattr(online, "cached", cached)
    monthly = online.query("aitag", "", "popular", 1, 21, "2026-10")
    assert monthly["has_more"]
    assert monthly["items"][0]["tags"] == ["blue_hair"]
    assert monthly["items"][1]["tags"] == ["red_hair", "coat"]
    assert "/api/rank/monthly/fixed?" in calls[-1]
    assert parse_qs(urlsplit(calls[-1]).query)["month"] == ["2026-10"]
    random = online.query("aitag", "", "random", 1, 0)
    assert not random["has_more"]
    assert any(parse_qs(urlsplit(url).query).get("page") == ["2"] for url in calls)
    detail = online.detail("aitag", "1")
    assert detail["title"] == "Two images"
    assert [image["prompt"] for image in detail["media"]] == ["blue coat", "red coat"]
    assert detail["media"][0]["negative"] == "text"
    assert detail["media"][1]["url"].endswith("/nai/5/two.webp")
    with pytest.raises(StudioError, match="編號"):
        online.detail("aitag", "../profile")


def test_quicktag_signed_catalog_fallback_and_tamper_detection(online, monkeypatch):
    files = {
        "codexes.json": [
            {
                "id": "clothes",
                "title": "Clothes",
                "dataUrl": "https://assets.quicktagcloud.com/live.json",
                "fallbackDataUrl": "clothes.json",
            }
        ],
        "media.json": {"baseUrl": "https://assets.quicktagcloud.com"},
        "clothes.json": {
            "entries": [
                None,
                {
                    "id": "coat",
                    "name": "Coat",
                    "tags": ["coat", "blue"],
                    "assetRev": 7,
                    "image": "coat.webp",
                    "original": "coat.png",
                    "images": [
                        {"path": "coat.webp", "original": "coat.png", "rawTag": "blue coat"},
                        "back.webp",
                    ],
                },
                {"id": "hat", "value": "red hat", "images": ["hat.webp"]},
            ]
        },
    }
    raw = {name: json.dumps(value).encode() for name, value in files.items()}
    manifest_files = {
        name: {"sha256": hashlib.sha256(value).hexdigest(), "size": len(value)}
        for name, value in raw.items()
    }
    signature = "".join(
        name + "\0" + value["sha256"] + "\n" for name, value in sorted(manifest_files.items())
    )
    digest = hashlib.sha256(signature.encode()).hexdigest()
    manifest = {"files": manifest_files, "contentHash": digest}

    def cached(url, _ttl=300):
        if url.endswith("data-source.json"):
            return {"baseUrl": "https://assets.quicktagcloud.com/"}
        if url.endswith("current.json"):
            return {"manifest": "release/manifest.json", "contentHash": digest}
        if url.endswith("manifest.json"):
            return manifest
        if url.endswith("live.json"):
            message = "upstream unavailable"
            raise StudioError(message)
        return files[url.rsplit("/", 1)[-1]]

    monkeypatch.setattr(online, "cached", cached)
    monkeypatch.setattr(
        "prompt_hub.online_gallery.fetch_bytes", lambda url: raw[url.rsplit("/", 1)[-1]]
    )
    result = online.query("quicktagcloud", "coat", "random", 1, 42)
    assert result["total"] == 1
    coat = result["items"][0]
    assert coat["prompt"] == "coat, blue"
    assert coat["original_url"].endswith("/originals/clothes/coat.png?v=7")
    assert coat["media"][0]["prompt"] == "blue coat"
    assert coat["media"][1]["url"].endswith("/images/clothes/back.webp?v=7")
    assert online.detail("quicktagcloud", "clothes:coat") == coat
    online.cache.clear()
    monkeypatch.setattr("prompt_hub.online_gallery.fetch_bytes", lambda _url: b"{}")
    with pytest.raises(StudioError, match="校驗失敗"):
        online.quick_catalog()
    manifest["contentHash"] = "wrong"
    with pytest.raises(StudioError, match="清單校驗"):
        online.quick_catalog()


def test_remote_favorites_use_account_adapter_and_reject_unsupported_sources(online, monkeypatch):
    calls = []

    def favorites(user, page, *, general_only):
        calls.append((user, page, general_only))
        return [{"id": 21, "tag_string": "blue_coat", "rating": "g"}] * 36

    monkeypatch.setattr(online.accounts, "favorites", favorites)
    result = online.query("safebooru", "", "remote_favorites", 2, 0, username="example")
    assert result["has_more"]
    assert result["items"][0]["id"] == "21"
    assert calls == [("example", 2, True)]
    with pytest.raises(StudioError, match="不支援"):
        online.query("aitag", "", "remote_favorites", 1, 0)


def test_fetch_checks_each_redirect_and_reports_invalid_responses(monkeypatch):
    checked = []
    outcomes = [
        HTTPError("https://aitag.win/a", 302, "", {"Location": "/b"}, None),
        io.BytesIO(b'{"ok":true}'),
    ]

    class Opener:
        def open(self, _request, **_kwargs):
            value = outcomes.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

    monkeypatch.setattr("prompt_hub.online_gallery.public_url", checked.append)
    monkeypatch.setattr("prompt_hub.online_gallery.build_opener", lambda *_args: Opener())
    assert fetch_json("https://aitag.win/a") == {"ok": True}
    assert checked == ["https://aitag.win/a", "https://aitag.win/b"]
    outcomes.append(io.BytesIO(b"oversized"))
    with pytest.raises(StudioError, match="大小限制"):
        fetch_bytes("https://aitag.win/a", maximum=2)
    outcomes.append(io.BytesIO(b"<html>verification</html>"))
    with pytest.raises(StudioError, match="驗證頁"):
        fetch_json("https://aitag.win/a")
    outcomes.append(io.BytesIO(b"invalid"))
    with pytest.raises(StudioError, match="JSON"):
        fetch_json("https://aitag.win/a")
    outcomes.append(URLError("offline"))
    with pytest.raises(StudioError, match="連線失敗"):
        fetch_bytes("https://aitag.win/a")


def test_remote_account_routes_hide_secrets_and_require_valid_credentials(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/online-gallery/account").json() == {
            "username": "",
            "has_api_key": False,
        }
        bad = client.put("/api/online-gallery/account", json={"username": "example", "api_key": ""})
        assert bad.status_code == 422
        favorite = client.put("/api/online-gallery/remote-favorite/21", json={"favorite": True})
        assert favorite.status_code == 422
        assert client.delete("/api/online-gallery/account").json()["has_api_key"] is False
