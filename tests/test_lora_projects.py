from __future__ import annotations

import hashlib
import json
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.lora_projects import LoraProjectStore


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "canceled"}:
            return job
        time.sleep(0.02)
    message = "Dataset scan did not finish"
    raise AssertionError(message)


def test_lora_project_store_creates_standard_handoff_layout(settings) -> None:
    store = LoraProjectStore(settings.lora_projects_root)
    store.initialize()
    assert store.options()["risk_flag_labels_zh"]["concept_drift"] == "概念漂移"
    for concept_type in ("character", "outfit", "character_outfit", "style"):
        project = store.create(
            {
                "name": f"Test {concept_type}",
                "concept_type": concept_type,
                "trigger_word": f"test_{concept_type}",
                "target_families": ["anima", "krea2"],
                "features": {
                    "fixed": ["silver hair"],
                    "controllable": ["hair ornament"],
                    "variable": ["pose", "background"],
                    "forbidden_drift": ["eye color"],
                },
            }
        )
        root = Path(project["project_path"])
        assert (root / "00_项目管理" / "角色配置.yaml").is_file()
        assert (root / "00_项目管理" / "图片清单.csv").is_file()
        assert (root / "04_正式训练集").is_dir()
        assert (root / "08_丹炉导入").is_dir()
        assert (root / "project.json").is_file()
        assert project["concept_type"] == concept_type


def test_lora_project_api_references_workspace_without_mutating_source(settings, tmp_path) -> None:
    source = tmp_path / "lora-source"
    source.mkdir()
    image_path = source / "portrait.png"
    caption_path = source / "portrait.txt"
    Image.new("RGB", (96, 128), "navy").save(image_path)
    caption_path.write_text("1girl, navy hair", encoding="utf-8")
    original = {path.name: path.read_bytes() for path in source.iterdir()}

    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source), "name": "LoRA source"},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait_for_job(client, imported["job"]["job_id"])["status"] == "completed"
        created = client.post(
            "/api/lora/projects",
            json={
                "name": "Ariya character",
                "concept_type": "character",
                "trigger_word": "ariya_test",
                "target_families": ["anima", "krea2"],
                "features": {
                    "fixed": ["silver eyes"],
                    "controllable": [],
                    "variable": ["outfit", "pose", "background"],
                    "forbidden_drift": ["dark eyes"],
                },
            },
        )
        assert created.status_code == 201
        project_id = created.json()["project_id"]
        added = client.post(
            f"/api/lora/projects/{project_id}/assets",
            json={"workspace_id": workspace_id, "paths": ["portrait.png"]},
        )
        assert added.status_code == 201
        assert added.json()["added"] == 1
        asset = added.json()["assets"][0]
        updated = client.put(
            f"/api/lora/projects/{project_id}/assets/{asset['asset_id']}",
            json={
                "status": "approved",
                "coverage": {
                    "shot": ["upper_body"],
                    "view": ["three_quarter"],
                    "expression": ["neutral"],
                    "background": ["simple"],
                },
                "risk_flags": ["background_bias"],
            },
        )
        assert updated.status_code == 200
        project = updated.json()
        assert project["coverage_report"]["status_counts"]["approved"] == 1
        expected_sha256 = hashlib.sha256(original["portrait.png"]).hexdigest()
        assert project["assets"][0]["sha256"] == expected_sha256
        assert client.get(project["assets"][0]["thumbnail_url"]).status_code == 200
        assert client.get(project["assets"][0]["original_url"]).status_code == 200

        for profile_id, caption in (
            ("anima", "1girl, ariya_test, upper body, three-quarter view"),
            (
                "krea2",
                "ariya_test is shown from the waist up in a three-quarter view.",
            ),
        ):
            response = client.put(
                f"/api/dataset-workspaces/{workspace_id}/caption",
                json={
                    "relative_path": "portrait.png",
                    "profile_id": profile_id,
                    "caption": caption,
                    "caption_status": "reviewed",
                },
            )
            assert response.status_code == 200
        frozen = client.post(f"/api/lora/projects/{project_id}/freeze")
        assert frozen.status_code == 201
        export = frozen.json()["export"]
        assert export["families"] == ["anima", "krea2"]
        assert client.get(export["download_url"]).status_code == 200
        with zipfile.ZipFile(export["archive"]) as archive:
            names = set(archive.namelist())
            assert "Anima/train/0001-portrait.txt" in names
            assert "Krea2/train/0001-portrait.txt" in names
            assert "Krea2/config/training-draft.yaml" in names
            assert "manifest.json" in names
            krea_config = archive.read("Krea2/config/training-draft.yaml").decode()
            assert "base_variant: raw_fp8" in krea_config
            assert "blocks_to_swap: 28" in krea_config
            assert "shuffle_caption: false" in krea_config

    assert {path.name: path.read_bytes() for path in source.iterdir()} == original


def test_lora_coverage_review_previews_then_merges_caption_evidence(settings, tmp_path) -> None:
    source = tmp_path / "coverage-source"
    source.mkdir()
    image_path = source / "upper_body-three_quarter.png"
    caption_path = source / "upper_body-three_quarter.txt"
    Image.new("RGB", (96, 144), "purple").save(image_path)
    caption_path.write_text(
        "1girl, upper body, three-quarter view, smile, indoors, soft lighting",
        encoding="utf-8",
    )
    original = {path.name: path.read_bytes() for path in source.iterdir()}

    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source), "name": "Coverage source"},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait_for_job(client, imported["job"]["job_id"])["status"] == "completed"
        project = client.post(
            "/api/lora/projects",
            json={
                "name": "Coverage review",
                "concept_type": "character",
                "trigger_word": "coverage_test",
                "target_families": ["anima"],
            },
        ).json()
        project_id = project["project_id"]
        added = client.post(
            f"/api/lora/projects/{project_id}/assets",
            json={"workspace_id": workspace_id, "paths": [image_path.name]},
        ).json()
        asset_id = added["assets"][0]["asset_id"]

        preview = client.post(f"/api/lora/projects/{project_id}/coverage/preview")
        assert preview.status_code == 200
        payload = preview.json()
        assert payload["suggested_assets"] == 1
        suggestions = payload["items"][0]["additions"]
        assert suggestions["shot"] == ["upper_body"]
        assert suggestions["view"] == ["three_quarter"]
        assert suggestions["expression"] == ["smile"]
        assert suggestions["background"] == ["indoor"]
        assert suggestions["lighting"] == ["soft"]
        assert suggestions["composition"] == ["portrait"]
        unchanged = client.get(f"/api/lora/projects/{project_id}").json()
        assert unchanged["assets"][0]["coverage"] == {}
        assert unchanged["assets"][0]["status"] == "candidate"

        applied = client.post(f"/api/lora/projects/{project_id}/coverage/apply")
        assert applied.status_code == 200
        saved = applied.json()["project"]
        asset = next(item for item in saved["assets"] if item["asset_id"] == asset_id)
        assert asset["coverage"] == suggestions
        assert asset["coverage_review"]["status"] == "confirmed"
        assert asset["coverage_review"]["source"] == "filename-original-caption-rules-v1"
        assert asset["status"] == "candidate"
        repeated = client.post(f"/api/lora/projects/{project_id}/coverage/preview").json()
        assert repeated["suggested_values"] == 0

    assert {path.name: path.read_bytes() for path in source.iterdir()} == original


def test_lora_project_from_oc_manager_is_read_only(settings) -> None:
    export = {
        "format": "oc-manager-full-database",
        "characters": [
            {
                "id": "char-lora",
                "name": "阿莉娅",
                "world": "镜海",
                "story": "调查员",
            }
        ],
        "worlds": [{"id": "world-lora", "name": "镜海"}],
        "lore": {},
    }
    raw = json.dumps(export, ensure_ascii=False).encode()
    with TestClient(create_app(settings)) as client:
        assert (
            client.post(
                "/api/oc-manager/import",
                params={"filename": "oc-lora.json"},
                content=raw,
            ).status_code
            == 200
        )
        before = client.get("/api/oc-manager/characters/char-lora").json()
        before_hash = hashlib.sha256(
            json.dumps(before, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        created = client.post(
            "/api/lora/projects",
            json={
                "concept_type": "character",
                "trigger_word": "ariya_lora",
                "target_families": ["anima"],
                "source_oc_character_id": "char-lora",
            },
        )
        assert created.status_code == 201
        assert created.json()["name"] == "阿莉娅 · LoRA"
        assert created.json()["source_oc"]["character_id"] == "char-lora"
        after = client.get("/api/oc-manager/characters/char-lora").json()
        after_hash = hashlib.sha256(
            json.dumps(after, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        assert after_hash == before_hash
        assert client.get("/api/stats").json()["oc_manager"]["characters"] == 1
