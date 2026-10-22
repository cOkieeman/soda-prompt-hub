from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser
from importlib.resources import files

from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.storyboard_web import (
    STORYBOARD_HTML,
    STORYBOARD_SCRIPT,
    STORYBOARD_STYLES,
)
from prompt_hub.web import INDEX_HTML
from prompt_hub.workflow_profiles import MAX_SEED


class _Elements(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))


def test_storyboard_resources_are_packaged_and_assembled() -> None:
    assets = files("prompt_hub").joinpath("web_assets")
    assert assets.joinpath("storyboard.css").read_text(encoding="utf-8") in STORYBOARD_STYLES
    assert assets.joinpath("storyboard.js").read_text(encoding="utf-8") in STORYBOARD_SCRIPT
    assert STORYBOARD_HTML in INDEX_HTML
    assert STORYBOARD_STYLES in INDEX_HTML
    assert STORYBOARD_SCRIPT in INDEX_HTML


def test_storyboard_does_not_duplicate_existing_shell_element_ids() -> None:
    document = _Elements()
    document.feed(INDEX_HTML)
    ids = [attrs["id"] for _, attrs in document.elements if attrs.get("id")]
    duplicates = {value for value, count in Counter(ids).items() if count > 1}
    assert not {value for value in duplicates if value.startswith("storyboard")}
    assert sum(value == "storyboardPage" for value in ids) == 1


def test_home_serves_storyboard_entry_and_accessible_confirmation_actions(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/")
    assert response.status_code == 200
    document = _Elements()
    document.feed(response.text)
    by_id = {attrs["id"]: (tag, attrs) for tag, attrs in document.elements if attrs.get("id")}
    nav = [attrs for tag, attrs in document.elements if tag == "button"]
    assert any(attrs.get("data-view") == "storyboard" for attrs in nav)
    assert by_id["storyboardPage"][1]["aria-labelledby"] == "storyboardTitle"
    assert "hidden" in by_id["storyboardPage"][1]
    assert by_id["storyboardStatus"][1]["role"] == "status"
    assert by_id["storyboardStatus"][1]["aria-live"] == "polite"
    for element_id in (
        "storyboardAiApply",
        "storyboardTranslationApply",
        "storyboardOcApply",
    ):
        tag, attrs = by_id[element_id]
        assert tag == "button"
        assert attrs["type"] == "button"
        assert "hidden" in attrs
    assert by_id["storyboardDeleteDialog"][0] == "dialog"
    assert by_id["storyboardImportFile"][1]["type"] == "file"
    assert by_id["storyboardExportPage"][0] == "a"
    assert "npm" not in STORYBOARD_SCRIPT


def test_storyboard_resource_requests_follow_existing_http_contracts(settings) -> None:
    resource_urls = re.findall(r"api\('(/api/[^']+)'\)", STORYBOARD_SCRIPT)
    assert "/api/oc-manager/characters?limit=50" in resource_urls
    with TestClient(create_app(settings)) as client:
        for resource_url in resource_urls:
            response = client.get(resource_url)
            assert response.status_code == 200, (resource_url, response.text)


def test_storyboard_seed_control_matches_worker_safe_integer_limit() -> None:
    document = _Elements()
    document.feed(STORYBOARD_HTML)
    seed = next(attrs for _, attrs in document.elements if attrs.get("id") == "storyboardSeed")
    assert seed["max"] == str(MAX_SEED)
