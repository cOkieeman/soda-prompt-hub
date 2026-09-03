from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.tag_locale import TagLocaleError, localize_tag, localize_tags, tag_catalog


def test_tag_locale_keeps_canonical_english_and_switches_display() -> None:
    chinese = localize_tag("silver_hair", language="zh")
    assert chinese == {
        "tag": "silver_hair",
        "en": "silver_hair",
        "zh": "银发",
        "display": "银发 (silver_hair)",
        "known": True,
    }
    assert localize_tag("silver_hair", language="en")["display"] == "silver_hair"
    assert localize_tag("blue eyes", language="zh")["zh"] == "蓝眼睛"
    assert localize_tag("custom_artist_style", language="zh")["display"] == "custom_artist_style"


def test_tag_locale_resolves_known_chinese_but_rejects_unknown_chinese() -> None:
    localized = localize_tags(["银发", "solo", "银发"], language="zh")
    assert [item["tag"] for item in localized] == ["silver_hair", "solo"]
    with pytest.raises(TagLocaleError, match="无法确认中文标签"):
        localize_tag("自创标签", language="zh")


def test_tag_catalog_exposes_chinese_choices_with_canonical_ids() -> None:
    catalog = tag_catalog(language="zh")
    silver_hair = next(item for item in catalog if item["en"] == "silver_hair")
    watermark = next(item for item in catalog if item["en"] == "watermark")
    assert silver_hair["display"] == "银发 (silver_hair)"
    assert watermark["zh"] == "水印"
    assert all(item["tag"].isascii() for item in catalog)


def test_tag_locale_api(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/tags/localize",
            json={"tags": ["1girl", "blue_eyes", "full_body"], "language": "zh"},
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert [item["en"] for item in items] == ["1girl", "blue_eyes", "full_body"]
        assert [item["zh"] for item in items] == ["一名女孩", "蓝眼睛", "全身"]

        catalog = client.get("/api/tags/catalog?language=zh")
        assert catalog.status_code == 200
        assert any(
            item["en"] == "silver_hair" and item["zh"] == "银发" for item in catalog.json()["items"]
        )

        invalid = client.post(
            "/api/tags/localize",
            json={"tags": ["无法映射的中文"], "language": "zh"},
        )
        assert invalid.status_code == 422
