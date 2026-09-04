from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.web_capture import FetchResult, WebCaptureError, WebCaptureService


def _service(settings, fetcher):
    database = PromptDatabase(settings.database_path)
    database.initialize()
    return WebCaptureService(settings, database, fetcher=fetcher), database


def test_civitai_is_link_only_and_never_fetches(settings) -> None:
    def forbidden_fetcher(_url: str, _limit: int) -> FetchResult:
        message = "link-only capture must not fetch the page"
        raise AssertionError(message)

    service, database = _service(settings, forbidden_fetcher)
    captured = service.capture(
        url="https://civitai.red/models/2885952/linhuier?modelVersionId=3262276",
        title="林悔儿 LoRA",
        note="回到模型页核对推荐提示词",
        safety="adult",
        license_name="unknown",
    )

    assert captured["cache_policy"] == "link_only"
    assert captured["cached"] is False
    assert captured["content_sha256"]
    assert service.list_captures()[0]["title"] == "林悔儿 LoRA"
    result = database.search("林悔儿", limit=5)[0]
    assert result["source_url"] == captured["url"]
    assert result["metadata"]["capture_policy"] == "link_only"


def test_github_text_capture_hashes_and_incrementally_preserves_marks(settings) -> None:
    responses = [
        FetchResult(
            final_url="https://raw.githubusercontent.com/example/prompts/main/README.md",
            content_type="text/markdown; charset=utf-8",
            body=b"# Lighting\ncinematic rim light, dusk library",
        ),
        FetchResult(
            final_url="https://raw.githubusercontent.com/example/prompts/main/README.md",
            content_type="text/markdown",
            body=b"# Lighting\ncinematic rim light, dusk archive, dust motes",
        ),
    ]

    def fetcher(_url: str, _limit: int) -> FetchResult:
        return responses.pop(0)

    service, database = _service(settings, fetcher)
    first = service.capture(
        url="https://raw.githubusercontent.com/example/prompts/main/README.md",
        title="Lighting notes",
        note="我的电影灯光摘录",
        safety="sfw",
        license_name="MIT",
    )
    database.save_mark(
        source_id=first["source_id"],
        external_id=first["external_id"],
        favorite=True,
        rating=5,
        note="实测很好",
    )
    second = service.capture(
        url=first["url"],
        title="Lighting notes v2",
        note="我的电影灯光摘录",
        safety="sfw",
        license_name="MIT",
    )

    assert second["capture_id"] == first["capture_id"]
    assert second["content_sha256"] != first["content_sha256"]
    assert second["cached"] is True
    manifest_path = settings.web_sources_root / first["capture_id"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["content_sha256"] == second["content_sha256"]
    result = database.search("dusk archive", limit=5)[0]
    assert result["favorite"] is True
    assert result["user_rating"] == 5
    assert result["user_note"] == "实测很好"


def test_direct_github_image_is_cached_with_safe_media_path(settings) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"safe-test-image"

    def fetcher(_url: str, _limit: int) -> FetchResult:
        return FetchResult(
            final_url="https://raw.githubusercontent.com/example/prompts/main/reference.png",
            content_type="image/png",
            body=png,
        )

    service, database = _service(settings, fetcher)
    captured = service.capture(
        url="https://raw.githubusercontent.com/example/prompts/main/reference.png",
        title="服装视觉参考",
        note="蓝白制服",
        safety="suggestive",
        license_name="unknown",
    )

    assert captured["media_kind"] == "image"
    assert captured["cached_media_path"].endswith("asset.png")
    assert service.resolve_media(captured["capture_id"]).read_bytes() == png
    source = next(
        item for item in database.list_sources() if item["source_id"] == captured["source_id"]
    )
    assert source["visual_count"] == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/example/prompts",
        "https://localhost/prompts",
        "https://127.0.0.1/prompts",
        "https://user:secret@github.com/prompts",
        "https://github.com:8443/prompts",
        "https://example.com/prompts",
    ],
)
def test_capture_rejects_untrusted_or_unsafe_urls(settings, url) -> None:
    service, _database = _service(settings, lambda *_args: None)
    with pytest.raises(WebCaptureError):
        service.capture(
            url=url,
            title="unsafe",
            note="",
            safety="sfw",
            license_name="unknown",
        )


def test_capture_rejects_untrusted_redirect_and_oversized_content(settings) -> None:
    def redirected(_url: str, _limit: int) -> FetchResult:
        return FetchResult(
            final_url="https://example.com/private",
            content_type="text/plain",
            body=b"prompt",
        )

    service, _database = _service(settings, redirected)
    with pytest.raises(WebCaptureError, match="重定向"):
        service.capture(
            url="https://raw.githubusercontent.com/example/prompts/main/a.txt",
            title="redirect",
            note="",
            safety="sfw",
            license_name="unknown",
        )


def test_web_capture_api_saves_link_only_source_and_exposes_page_marker(settings) -> None:
    with TestClient(create_app(settings)) as client:
        saved = client.post(
            "/api/web-captures",
            json={
                "url": "https://civitai.com/models/123/example",
                "title": "Civitai 提示词参考",
                "note": "回看示例图和触发词",
                "safety": "adult",
                "license_name": "unknown",
            },
        )
        assert saved.status_code == 201
        assert saved.json()["cache_policy"] == "link_only"
        captures = client.get("/api/web-captures")
        assert captures.status_code == 200
        assert captures.json()[0]["title"] == "Civitai 提示词参考"
        media = client.get(f"/api/web-captures/{saved.json()['capture_id']}/media")
        assert media.status_code == 404
        assert 'id="sourceCaptureForm"' in client.get("/").text

    def oversized(_url: str, limit: int) -> FetchResult:
        return FetchResult(
            final_url="https://raw.githubusercontent.com/example/prompts/main/a.txt",
            content_type="text/plain",
            body=b"x" * (limit + 1),
        )

    service, _database = _service(settings, oversized)
    with pytest.raises(WebCaptureError, match="过大"):
        service.capture(
            url="https://raw.githubusercontent.com/example/prompts/main/a.txt",
            title="oversized",
            note="",
            safety="sfw",
            license_name="unknown",
        )
