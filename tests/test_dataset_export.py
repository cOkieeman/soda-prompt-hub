from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.dataset_export import resolve_dataset_export


def _image_bytes(color: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (80, 96), color).save(output, "PNG")
    return output.getvalue()


def _project() -> dict[str, object]:
    return {
        "title": "银发调查员 数据集",
        "brief_zh": "成年银发调查员在黄昏图书馆读信",
        "safety_mode": "adult",
        "target_profile": "anima",
        "slots": {
            "character": "1woman, adult, silver hair",
            "action": "reading a letter",
            "scene": "old library, sunset",
        },
    }


def _upload(client: TestClient, project_id: str, filename: str, color: str) -> dict:
    response = client.post(
        f"/api/creative/projects/{project_id}/results",
        params={"filename": filename},
        content=_image_bytes(color),
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 201
    return response.json()["asset"]


def test_dataset_selection_and_anima_zip(settings) -> None:
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/creative/projects", json=_project()).json()
        project_id = project["project_id"]
        first = _upload(client, project_id, "first.png", "navy")
        _upload(client, project_id, "second.png", "maroon")

        empty_export = client.post(
            f"/api/creative/projects/{project_id}/dataset-export",
            json={"profile_id": "anima"},
        )
        assert empty_export.status_code == 422

        selected = client.put(
            f"/api/creative/projects/{project_id}/results/{first['asset_id']}/dataset",
            json={
                "selected": True,
                "profile_id": "anima",
                "caption_override": "1woman, silver hair, reading a letter",
            },
        )
        assert selected.status_code == 200
        assert selected.json()["asset"]["dataset_selected"] is True
        assert selected.json()["asset"]["dataset_captions"]["anima"].startswith("1woman")

        exported = client.post(
            f"/api/creative/projects/{project_id}/dataset-export",
            json={"profile_id": "anima"},
        )
        assert exported.status_code == 200
        payload = exported.json()
        assert payload["item_count"] == 1
        download = client.get(payload["download_url"])
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/zip"

    with ZipFile(BytesIO(download.content)) as archive:
        names = archive.namelist()
        image_names = [name for name in names if name.endswith(".png")]
        caption_names = [name for name in names if name.endswith(".txt")]
        assert len(image_names) == len(caption_names) == 1
        assert image_names[0].removesuffix(".png") == caption_names[0].removesuffix(".txt")
        assert archive.read(caption_names[0]).decode().strip() == (
            "1woman, silver hair, reading a letter"
        )
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format"] == "soda-prompt-hub-dataset-v1"
        assert manifest["profile"]["profile_id"] == "anima"
        assert manifest["items"][0]["caption_source"] == "override"
        assert manifest["project"]["safety_mode"] == "adult"


def test_krea_profile_fallback_and_export_path_safety(settings) -> None:
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/creative/projects", json=_project()).json()
        project_id = project["project_id"]
        asset = _upload(client, project_id, "krea.png", "teal")
        asset_url = f"/api/creative/projects/{project_id}/results/{asset['asset_id']}/dataset"
        selected = client.put(
            asset_url,
            json={"selected": True, "profile_id": "krea2"},
        )
        assert selected.status_code == 200

        exported = client.post(
            f"/api/creative/projects/{project_id}/dataset-export",
            json={"profile_id": "krea2"},
        ).json()
        download = client.get(exported["download_url"])
        assert download.status_code == 200
        with ZipFile(BytesIO(download.content)) as archive:
            caption_name = next(name for name in archive.namelist() if name.endswith(".txt"))
            caption = archive.read(caption_name).decode()
            manifest = json.loads(archive.read("manifest.json"))
        assert "创作意图" in caption
        assert manifest["profile"]["profile_id"] == "krea2"
        assert manifest["items"][0]["caption_source"] == "profile"

        cleared = client.put(
            asset_url,
            json={"selected": False, "profile_id": "krea2", "caption_override": ""},
        )
        assert cleared.json()["asset"]["dataset_selected"] is False
        assert (
            client.put(
                f"/api/creative/projects/{project_id}/results/missing/dataset",
                json={"selected": True},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/creative/projects/missing/dataset-export",
                json={"profile_id": "anima"},
            ).status_code
            == 404
        )

    assert resolve_dataset_export(settings, "../outside.zip") is None
    assert resolve_dataset_export(settings, "not-a-zip.txt") is None
