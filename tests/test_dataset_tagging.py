from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.dataset_tagging import (
    DatasetTaggingError,
    normalize_tag_draft,
    review_wd14_draft,
    store_wd14_result,
)
from prompt_hub.wd14 import WD14Error


def _image_bytes(color: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (72, 96), color).save(output, "PNG")
    return output.getvalue()


def _tag_result(tag: str = "1girl") -> dict[str, object]:
    return {
        "model": "SmilingWolf/wd-swinv2-tagger-v3",
        "provider": "CPUExecutionProvider",
        "general_threshold": 0.35,
        "character_threshold": 0.85,
        "rating": {"tag": "sensitive", "score": 0.98},
        "general": [
            {"tag": tag, "score": 0.99},
            {"tag": "solo", "score": 0.95},
        ],
        "characters": [],
        "tag_string": f"{tag}, solo",
        "elapsed_seconds": 0.7,
    }


def _create_project(client: TestClient) -> dict:
    response = client.post(
        "/api/creative/projects",
        json={
            "title": "WD14 审核",
            "brief_zh": "银发角色",
            "target_profile": "anima",
            "slots": {"character": "1girl, silver hair"},
        },
    )
    assert response.status_code == 201
    return response.json()


def _upload(client: TestClient, project_id: str, filename: str, color: str) -> dict:
    response = client.post(
        f"/api/creative/projects/{project_id}/results",
        params={"filename": filename},
        content=_image_bytes(color),
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 201
    return response.json()["asset"]


def test_store_and_review_wd14_result_without_overwriting_other_profile() -> None:
    project = {
        "generation": {
            "result_assets": [
                {
                    "asset_id": "asset-1",
                    "dataset_captions": {"krea2": "A woman in a dark studio."},
                }
            ]
        }
    }
    generation, asset = store_wd14_result(project, asset_id="asset-1", result=_tag_result())
    assert asset["wd14_tagging"]["draft_tags"] == "1girl, solo"
    assert asset["wd14_tagging"]["rating"]["tag"] == "sensitive"
    assert asset["dataset_captions"] == {"krea2": "A woman in a dark studio."}

    draft_project = {"generation": generation}
    generation, asset = review_wd14_draft(
        draft_project,
        asset_id="asset-1",
        draft_tags="1girl, solo, solo\nblue eyes",
        confirm_anima=False,
    )
    assert asset["wd14_tagging"]["draft_tags"] == "1girl, solo, blue eyes"
    assert "anima" not in asset["dataset_captions"]

    generation, asset = review_wd14_draft(
        {"generation": generation},
        asset_id="asset-1",
        draft_tags="1girl, solo, blue eyes",
        confirm_anima=True,
    )
    assert asset["dataset_captions"]["anima"] == "1girl, solo, blue eyes"
    assert asset["dataset_captions"]["krea2"] == "A woman in a dark studio."
    assert asset["wd14_tagging"]["confirmed_at"]


def test_single_tag_and_review_api(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "prompt_hub.dataset_routes.tag_image",
        lambda *_args, **_kwargs: _tag_result(),
    )
    with TestClient(create_app(settings)) as client:
        project = _create_project(client)
        asset = _upload(client, project["project_id"], "single.png", "navy")
        base = f"/api/creative/projects/{project['project_id']}/results/{asset['asset_id']}"

        missing_draft = client.put(
            f"{base}/tag-review",
            json={"draft_tags": "1girl", "confirm_anima": True},
        )
        assert missing_draft.status_code == 422

        tagged = client.post(
            f"{base}/tag",
            json={"general_threshold": 0.4, "character_threshold": 0.9, "limit": 40},
        )
        assert tagged.status_code == 200
        assert tagged.json()["asset"]["wd14_tagging"]["draft_tags"] == "1girl, solo"
        assert "dataset_captions" not in tagged.json()["asset"]

        saved = client.put(
            f"{base}/tag-review",
            json={"draft_tags": "1girl, solo, blue_eyes", "confirm_anima": False},
        )
        assert "dataset_captions" not in saved.json()["asset"]
        confirmed = client.put(
            f"{base}/tag-review",
            json={"draft_tags": "1girl, solo, blue_eyes", "confirm_anima": True},
        )
        assert confirmed.json()["asset"]["dataset_captions"]["anima"].endswith("blue_eyes")


def test_selected_batch_returns_partial_failures(settings, monkeypatch) -> None:
    calls = 0

    def fake_tag_image(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            message = "测试图片无法打标"
            raise WD14Error(message)
        return _tag_result("1woman")

    monkeypatch.setattr("prompt_hub.dataset_routes.tag_image", fake_tag_image)
    with TestClient(create_app(settings)) as client:
        project = _create_project(client)
        project_id = project["project_id"]
        first = _upload(client, project_id, "first.png", "black")
        second = _upload(client, project_id, "second.png", "white")
        for asset in (first, second):
            selected = client.put(
                f"/api/creative/projects/{project_id}/results/{asset['asset_id']}/dataset",
                json={"selected": True, "profile_id": "anima"},
            )
            assert selected.status_code == 200

        batch = client.post(
            f"/api/creative/projects/{project_id}/dataset-tag",
            json={"general_threshold": 0.35, "character_threshold": 0.85, "limit": 80},
        )
        assert batch.status_code == 200
        assert batch.json()["tagged_count"] == 1
        assert batch.json()["failed_count"] == 1
        assets = batch.json()["project"]["generation"]["result_assets"]
        assert "wd14_tagging" in assets[0]
        assert "wd14_tagging" not in assets[1]


def test_tag_normalization() -> None:
    assert normalize_tag_draft(" 1girl, solo, SOLO, blue_eyes\nfull_body ") == (
        "1girl, solo, blue_eyes, full_body"
    )
    assert normalize_tag_draft("银发, 单人") == "silver_hair, solo"
    with pytest.raises(DatasetTaggingError, match="无法确认中文标签"):
        normalize_tag_draft("自创中文标签")
