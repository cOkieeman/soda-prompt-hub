from __future__ import annotations

import json
import time
import zipfile
from threading import Event
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageEnhance

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobStore, JobContext, JobInterruptedError
from prompt_hub.dataset_curation import DatasetCurationStore
from prompt_hub.dataset_curation_jobs import _batch_failure_message
from prompt_hub.dataset_curation_support import (
    _normalize_caption,
    normalize_caption_settings,
    normalize_caption_with_settings,
)
from prompt_hub.dataset_workspace import DatasetWorkspaceError, DatasetWorkspaceStore

if TYPE_CHECKING:
    from pathlib import Path


class _RecordingContext:
    def __init__(self) -> None:
        self.job_id = "job-curation-test"
        self.updates: list[tuple[int, int, str]] = []

    def update(self, current: int, total: int, message: str = "") -> None:
        self.updates.append((current, total, message))


class _InterruptingContext(_RecordingContext):
    def __init__(self, stop_after: int) -> None:
        super().__init__()
        self.stop_after = stop_after

    def update(self, current: int, total: int, message: str = "") -> None:
        super().update(current, total, message)
        if current >= self.stop_after:
            raise JobInterruptedError


def _source(root: Path, count: int = 3) -> Path:
    source = root / "curation-source"
    source.mkdir()
    for index in range(count):
        color = ((index * 37) % 256, (index * 67) % 256, (index * 97) % 256)
        Image.new("RGB", (64 + index, 80 + index), color).save(source / f"image-{index}.png")
    return source


def _scanned_workspace(settings, tmp_path, *, count: int = 3):
    source = _source(tmp_path, count)
    workspace_store = DatasetWorkspaceStore(settings)
    workspace_store.initialize()
    workspace = workspace_store.register(source, name="Curation test")
    job_store = BackgroundJobStore(settings.database_path)
    job_store.initialize()
    job = job_store.enqueue("dataset_scan", {"workspace_id": workspace["workspace_id"]})
    assert job_store.claim_next({"dataset_scan"}) is not None
    workspace_store.scan(
        workspace["workspace_id"],
        JobContext(job_store, job["job_id"], Event()),
    )
    return source, workspace_store, workspace


def _fake_factory(calls: list[str]):
    calls.append("loaded")

    def tag(path: Path) -> dict[str, object]:
        index = int(path.stem.rsplit("-", 1)[-1])
        hair = "grey_hair" if index == 0 else "black_hair"
        return {
            "model": "fake-wd14",
            "provider": "CPUExecutionProvider",
            "general_threshold": 0.35,
            "character_threshold": 0.85,
            "rating": {"tag": "safe", "score": 0.9},
            "general": [
                {"tag": "1girl", "score": 0.99},
                {"tag": "solo", "score": 0.95},
                {"tag": hair, "score": 0.8},
            ],
            "characters": [],
            "tag_string": f"1girl, solo, {hair}",
            "elapsed_seconds": 0.01,
        }

    return tag


def _fake_factory_with_thresholds(calls: list[tuple[str, float, float, str]]):
    def factory(config, provider: str):
        general = config.general_threshold
        character = config.character_threshold
        calls.append((config.id, general, character, provider))

        def tag(_path: Path) -> dict[str, object]:
            return {
                "model": "fake-wd14",
                "provider": "CPUExecutionProvider",
                "general_threshold": general,
                "character_threshold": character,
                "rating": {"tag": "safe", "score": 0.9},
                "general": [
                    {"tag": "1girl", "score": 0.99},
                    {"tag": "solo", "score": 0.95},
                    {"tag": "blue_eyes", "score": 0.9},
                    {"tag": "white_dress", "score": 0.88},
                ],
                "characters": [],
                "tag_string": "1girl, solo, blue_eyes, white_dress",
                "elapsed_seconds": 0.01,
            }

        return tag

    return factory


def _fake_krea2_captioner(calls: list[tuple[str, str, str, dict]]):
    def caption(
        path: Path,
        model: str,
        existing: str,
        caption_settings: dict,
    ) -> dict[str, object]:
        calls.append((path.name, model, existing, caption_settings))
        return {
            "model": model,
            "draft": f"A studio portrait from {path.stem} with soft directional light.",
            "observations": {"composition": "portrait", "lighting": "soft directional light"},
            "safety_warning": "",
        }

    return caption


def _fake_anima_tagger(calls: list[tuple[str, str, str]]):
    def tag(path: Path, model: str, existing: str) -> dict[str, object]:
        calls.append((path.name, model, existing))
        return {
            "tagger": "model",
            "model": model,
            "provider": "vision",
            "rating": {"tag": "safe", "score": 1.0},
            "general": [
                {"tag": "1girl", "score": 1.0},
                {"tag": "solo", "score": 1.0},
            ],
            "characters": [],
            "tag_string": "1girl, solo",
            "safety_warning": "",
        }

    return tag


def test_workspace_wd14_applies_caption_settings_and_model_threshold_defaults(
    settings,
    tmp_path,
) -> None:
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    calls: list[tuple[str, float, float, str]] = []
    curation = DatasetCurationStore(
        settings,
        workspace_store,
        tagger_factory=_fake_factory_with_thresholds(calls),
    )

    result = curation.tag_job(
        {
            "workspace_id": workspace["workspace_id"],
            "scope": "all",
            "mode": "portrait",
            "trigger": "miru",
            "general_threshold": 0.99,
            "character_threshold": 0.99,
        },
        _RecordingContext(),
    )

    assert result["completed"] == 1
    assert calls == [
        (
            "wd-swinv2-tagger-v3",
            settings.wd14_general_threshold,
            settings.wd14_character_threshold,
            "auto",
        )
    ]
    state = curation.read_state(workspace["workspace_id"])
    item = state["items"]["image-0.png"]
    assert item["captions"]["anima"]["current"] == "miru, 1girl, solo, white_dress"
    assert item["wd14"]["tagger_model_id"] == "wd-swinv2-tagger-v3"
    assert item["wd14"]["general_threshold"] == settings.wd14_general_threshold
    assert item["wd14"]["caption_settings"]["trigger"] == "miru"


def test_workspace_wd14_captions_bulk_snapshots_and_export(settings, tmp_path) -> None:
    source, workspace_store, workspace = _scanned_workspace(settings, tmp_path)
    source_before = {path.name: path.read_bytes() for path in source.iterdir()}
    factory_calls: list[str] = []
    curation = DatasetCurationStore(
        settings,
        workspace_store,
        tagger_factory=lambda _config, _provider: _fake_factory(factory_calls),
    )
    curation.initialize()
    context = _RecordingContext()
    result = curation.tag_job(
        {"workspace_id": workspace["workspace_id"], "scope": "all"},
        context,
    )
    assert result == {
        "workspace_id": workspace["workspace_id"],
        "requested": 3,
        "completed": 3,
        "failed": 0,
        "skipped": 0,
    }
    assert factory_calls == ["loaded"]
    assert context.updates[-1][:2] == (3, 3)

    no_work = curation.tag_job(
        {"workspace_id": workspace["workspace_id"], "scope": "untagged"},
        _RecordingContext(),
    )
    assert no_work["requested"] == 0
    assert factory_calls == ["loaded"]
    resumed = curation.tag_job(
        {
            "workspace_id": workspace["workspace_id"],
            "scope": "all",
            "overwrite": True,
        },
        context,
    )
    assert resumed["requested"] == 0
    assert factory_calls == ["loaded"]

    state = curation.read_state(workspace["workspace_id"])
    first = state["items"]["image-0.png"]
    assert first["wd14"]["model"] == "SmilingWolf/wd-swinv2-tagger-v3"
    assert first["captions"]["anima"]["current"] == "1girl, solo, grey_hair"
    assert first["captions"]["krea2"]["current"] == ""

    with pytest.raises(DatasetWorkspaceError, match="英文"):
        curation.update_caption(
            workspace["workspace_id"],
            "image-0.png",
            profile_id="krea2",
            caption="一个银发角色",
        )
    krea_snapshots = []
    for index in range(3):
        updated_krea = curation.update_caption(
            workspace["workspace_id"],
            f"image-{index}.png",
            profile_id="krea2",
            caption=f"A character portrait number {index} against a simple background.",
        )
        krea_snapshots.append(updated_krea["snapshot"])
    curation.update_caption(
        workspace["workspace_id"],
        "image-0.png",
        profile_id="anima",
        caption="soda_trigger, solo, grey_hair",
    )

    preview = curation.bulk_preview(
        workspace["workspace_id"],
        ["image-0.png", "image-1.png"],
        {"add": ["白发"], "remove": ["一名女孩"]},
    )
    assert preview["changed"] == 2
    assert preview["summary"] == {"added_instances": 2, "removed_instances": 1}
    assert preview["conflicts"][0]["rule_id"] == "hair-grey-white"
    assert all("white_hair" in item["after"] for item in preview["changes"])
    assert all(item["after"].isascii() for item in preview["changes"])
    applied = curation.apply_bulk_edit(
        workspace["workspace_id"],
        ["image-0.png", "image-1.png"],
        {"add": ["白发"], "remove": ["一名女孩"], "mode": "portrait", "trigger": "miru"},
    )
    assert applied["snapshot"].startswith("snapshot-")
    assert applied["changes"][0]["after"].startswith("miru, ")
    assert curation.list_snapshots(workspace["workspace_id"])
    rolled_back = curation.rollback_snapshot(workspace["workspace_id"], applied["snapshot"])
    assert rolled_back["changed"] == 2
    assert (
        curation.read_state(workspace["workspace_id"])["items"]["image-0.png"]["captions"]["anima"][
            "current"
        ]
        == "soda_trigger, solo, grey_hair"
    )
    with pytest.raises(DatasetWorkspaceError, match="无法确认中文标签"):
        curation.bulk_preview(
            workspace["workspace_id"],
            ["image-0.png"],
            {"add": ["自创中文标签"]},
        )
    anima_before_krea_rollback = curation.read_state(workspace["workspace_id"])["items"][
        "image-0.png"
    ]["captions"]["anima"]["current"]
    krea_rollback = curation.rollback_snapshot(workspace["workspace_id"], krea_snapshots[0])
    rolled_state = curation.read_state(workspace["workspace_id"])["items"]["image-0.png"]
    assert krea_rollback["profile_id"] == "krea2"
    assert rolled_state["captions"]["krea2"]["current"] == ""
    assert rolled_state["captions"]["anima"]["current"] == anima_before_krea_rollback
    curation.update_caption(
        workspace["workspace_id"],
        "image-0.png",
        profile_id="krea2",
        caption="A character portrait number 0 against a simple background.",
    )

    workspace_store.update_review_state(
        workspace["workspace_id"],
        (
            {
                "relative_path": f"image-{index}.png",
                "status": "approved",
                "selected": True,
                "note": "",
            }
            for index in range(3)
        ),
    )
    exported = curation.export_version(
        workspace["workspace_id"],
        profile_id="krea2",
        paths=[f"image-{index}.png" for index in range(3)],
    )
    archive_path = curation.resolve_export(workspace["workspace_id"], exported["archive_name"])
    assert archive_path is not None
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert "audit.json" in names
        assert "hashes.sha256" in names
        assert len([name for name in names if name.endswith(".png")]) == 3
        assert len([name for name in names if name.endswith(".txt")]) == 3
        manifest = json.loads(archive.read("manifest.json"))
        hashes = archive.read("hashes.sha256").decode("utf-8")
    assert manifest["profile_id"] == "krea2"
    assert manifest["caption_language"] == "en"
    assert "train/image-0.png" in hashes
    assert "manifest.json" in hashes
    assert exported["file_count"] == 9
    assert exported["total_bytes"] > 0
    assert exported["archive_bytes"] == archive_path.stat().st_size
    assert (
        curation.list_exports(workspace["workspace_id"])[0]["version_id"] == exported["version_id"]
    )
    second = curation.export_version(
        workspace["workspace_id"],
        profile_id="krea2",
        paths=[f"image-{index}.png" for index in range(3)],
    )
    assert second["version_id"] != exported["version_id"]
    export_directory = curation.resolve_export_directory(
        workspace["workspace_id"], exported["version_id"]
    )
    assert export_directory is not None
    assert export_directory.is_dir()
    assert {path.name: path.read_bytes() for path in source.iterdir()} == source_before


def test_export_preflight_reports_blockers_and_requires_reviewed_caption(
    settings,
    tmp_path,
) -> None:
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=2)
    curation = DatasetCurationStore(settings, workspace_store)
    workspace_id = workspace["workspace_id"]
    curation.update_caption(
        workspace_id,
        "image-0.png",
        profile_id="anima",
        caption="1girl, solo, portrait",
        status="reviewed",
    )
    curation.update_caption(
        workspace_id,
        "image-1.png",
        profile_id="anima",
        caption="1girl, solo, outdoors",
        status="draft",
    )
    workspace_store.update_review_state(
        workspace_id,
        [
            {
                "relative_path": "image-0.png",
                "status": "approved",
                "selected": True,
                "note": "",
            },
            {
                "relative_path": "image-1.png",
                "status": "pending",
                "selected": True,
                "note": "",
            },
        ],
    )

    preflight = curation.preflight_export(
        workspace_id,
        profile_id="anima",
        paths=["image-0.png", "image-1.png"],
    )
    assert preflight["ready"] is False
    assert preflight["selected_count"] == 2
    assert {item["code"] for item in preflight["blockers"]} == {
        "caption_not_reviewed",
        "image_not_approved",
    }
    with pytest.raises(DatasetWorkspaceError, match="交付前检查未通过"):
        curation.export_version(
            workspace_id,
            profile_id="anima",
            paths=["image-0.png", "image-1.png"],
        )

    ready = curation.preflight_export(
        workspace_id,
        profile_id="anima",
        paths=["image-0.png"],
    )
    assert ready["ready"] is True
    assert ready["blockers"] == []

    source_image = workspace_store.resolve_source_image(workspace_id, "image-0.png")
    assert source_image is not None
    Image.new("RGB", (64, 80), "orange").save(source_image)
    changed = curation.preflight_export(
        workspace_id,
        profile_id="anima",
        paths=["image-0.png"],
    )
    assert "source_changed" in {item["code"] for item in changed["blockers"]}


def test_export_preflight_blocks_exact_duplicates_and_caption_name_collisions(
    settings,
    tmp_path,
) -> None:
    source = tmp_path / "collision-source"
    source.mkdir()
    Image.new("RGB", (64, 80), "navy").save(source / "same.png")
    Image.new("RGB", (64, 80), "purple").save(source / "same.jpg")
    (source / "duplicate.png").write_bytes((source / "same.png").read_bytes())
    workspace_store = DatasetWorkspaceStore(settings)
    workspace_store.initialize()
    workspace = workspace_store.register(source, name="Collision test")
    job_store = BackgroundJobStore(settings.database_path)
    job_store.initialize()
    job = job_store.enqueue("dataset_scan", {"workspace_id": workspace["workspace_id"]})
    assert job_store.claim_next({"dataset_scan"}) is not None
    workspace_store.scan(
        workspace["workspace_id"],
        JobContext(job_store, job["job_id"], Event()),
    )
    curation = DatasetCurationStore(settings, workspace_store)
    paths = ["same.png", "same.jpg", "duplicate.png"]
    for relative_path in paths:
        curation.update_caption(
            workspace["workspace_id"],
            relative_path,
            profile_id="anima",
            caption="1girl, solo, portrait",
            status="reviewed",
        )
    workspace_store.update_review_state(
        workspace["workspace_id"],
        [
            {
                "relative_path": relative_path,
                "status": "approved",
                "selected": True,
                "note": "",
            }
            for relative_path in paths
        ],
    )

    preflight = curation.preflight_export(
        workspace["workspace_id"],
        profile_id="anima",
        paths=paths,
    )
    assert preflight["ready"] is False
    assert {item["code"] for item in preflight["blockers"]} == {
        "caption_path_conflict",
        "exact_duplicate",
    }


def test_source_captions_preview_and_apply_as_one_snapshot(settings, tmp_path) -> None:
    source = _source(tmp_path, 3)
    (source / "image-0.txt").write_text("1girl, silver hair, upper body", encoding="utf-8")
    (source / "image-1.txt").write_text("1girl, smile, outdoors", encoding="utf-8")
    (source / "image-2.txt").write_text("中文标签", encoding="utf-8")
    source_before = {path.name: path.read_bytes() for path in source.iterdir()}
    workspace_store = DatasetWorkspaceStore(settings)
    workspace_store.initialize()
    workspace = workspace_store.register(source, name="Source caption test")
    job_store = BackgroundJobStore(settings.database_path)
    job_store.initialize()
    job = job_store.enqueue("dataset_scan", {"workspace_id": workspace["workspace_id"]})
    assert job_store.claim_next({"dataset_scan"}) is not None
    workspace_store.scan(
        workspace["workspace_id"],
        JobContext(job_store, job["job_id"], Event()),
    )
    curation = DatasetCurationStore(settings, workspace_store)

    preview = curation.source_caption_preview(
        workspace["workspace_id"],
        profile_id="anima",
    )
    assert preview["inspected"] == 3
    assert preview["paired"] == 3
    assert preview["changed"] == 2
    # 断言的是「这张因为不是英文而被挡下」。不逐字比对讯息。
    # 讯息措辞会随诊断变精确而调整。那不该算回归。
    assert [item["relative_path"] for item in preview["invalid"]] == ["image-2.png"]
    assert "英文" in preview["invalid"][0]["reason"]
    assert curation.list_snapshots(workspace["workspace_id"]) == []

    applied = curation.apply_source_captions(
        workspace["workspace_id"],
        profile_id="anima",
        status="draft",
    )
    assert applied["changed"] == 2
    assert applied["snapshot"].startswith("snapshot-")
    snapshots = curation.list_snapshots(workspace["workspace_id"])
    assert len(snapshots) == 1
    assert snapshots[0]["operation"] == "source-caption-to-anima"
    assert snapshots[0]["changed"] == 2
    state = curation.read_state(workspace["workspace_id"])
    first = state["items"]["image-0.png"]["captions"]["anima"]
    assert first["current"] == "1girl, silver hair, upper body"
    assert first["status"] == "draft"
    assert first["source"] == "original-caption"

    second_preview = curation.source_caption_preview(
        workspace["workspace_id"],
        profile_id="anima",
    )
    assert second_preview["changed"] == 0
    assert second_preview["skipped_existing"] == 2
    assert {path.name: path.read_bytes() for path in source.iterdir()} == source_before


def test_source_caption_batch_api_requires_preview_and_keeps_profiles_separate(
    settings,
    tmp_path,
) -> None:
    source = _source(tmp_path, 1)
    (source / "image-0.txt").write_text(
        "A full-body character portrait in daylight.",
        encoding="utf-8",
    )
    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source)},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait(client, imported["job"]["job_id"])["status"] == "completed"

        preview = client.post(
            f"/api/dataset-workspaces/{workspace_id}/source-captions/preview",
            json={"profile_id": "krea2"},
        )
        assert preview.status_code == 200
        assert preview.json()["changed"] == 1
        applied = client.post(
            f"/api/dataset-workspaces/{workspace_id}/source-captions/apply",
            json={"profile_id": "krea2", "caption_status": "reviewed"},
        )
        assert applied.status_code == 200
        assert applied.json()["changed"] == 1
        report = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        captions = report["images"][0]["curation"]["captions"]
        assert captions["anima"]["current"] == ""
        assert captions["krea2"]["current"] == "A full-body character portrait in daylight."
        assert captions["krea2"]["status"] == "reviewed"


def test_caption_modes_api_exposes_backend_contract(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/dataset-workspaces/caption-modes")

    assert response.status_code == 200
    payload = response.json()
    assert [mode["id"] for mode in payload["modes"]] == [
        "general",
        "portrait",
        "outfit",
        "style",
    ]
    assert payload["modes"][0]["trigger_label"] == ""
    assert payload["modes"][0]["omits"] == "无"
    assert payload["modes"][1]["omits"] == "面部五官"
    assert payload["modes"][1]["trigger_label"] == "人物称呼"
    assert payload["modes"][2]["label"] == "服装"
    assert payload["modes"][3]["label"] == "风格"
    assert payload["media_tags_default"] is True
    assert payload["media_tags_by_mode"]["style"] is False
    assert payload["max_tokens_default"] == 300
    assert {option["id"] for option in payload["options"] if option["profiles"] == ["krea2"]} == {
        "avoid_meta_phrases",
        "avoid_vague",
        "plain_words",
    }


def test_bulk_tags_routes_keep_profile_and_plain_edits_do_not_apply_generation_settings(
    settings,
    tmp_path,
) -> None:
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    curation = DatasetCurationStore(settings, workspace_store)
    workspace_id = workspace["workspace_id"]
    curation.update_caption(
        workspace_id,
        "image-0.png",
        profile_id="anima",
        caption="1girl, solo, blue_eyes",
    )
    curation.update_caption(
        workspace_id,
        "image-0.png",
        profile_id="krea2",
        caption="A woman stands indoors.",
    )

    plain = curation.bulk_preview(
        workspace_id,
        ["image-0.png"],
        {"profile_id": "anima", "add": ["white dress"]},
    )
    assert plain["changes"][0]["after"] == "1girl, solo, blue_eyes, white_dress"

    with TestClient(create_app(settings)) as client:
        post = client.post(
            f"/api/dataset-workspaces/{workspace_id}/bulk-tags/preview",
            json={"profile_id": "krea2", "paths": ["image-0.png"], "add": ["realistic photo"]},
        )
    assert post.status_code == 200
    assert post.json()["changes"][0]["after"] == "A woman stands indoors., realistic photo"


def test_caption_endpoint_accepts_contract_post_and_applies_trigger(settings, tmp_path) -> None:
    _source_path, _workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    workspace_id = workspace["workspace_id"]
    with TestClient(create_app(settings)) as client:
        response = client.post(
            f"/api/dataset-workspaces/{workspace_id}/caption",
            json={
                "relative_path": "image-0.png",
                "profile_id": "anima",
                "caption": "1girl, solo, blue_eyes",
                "caption_status": "reviewed",
                "mode": "portrait",
                "trigger": "miru",
            },
        )

    assert response.status_code == 200
    assert response.json()["caption"]["current"] == "miru, 1girl, solo"


def test_media_tags_keep_detected_medium_without_forcing_photo() -> None:
    anima_settings = normalize_caption_settings("anima", {"media_tags": True})
    assert (
        normalize_caption_with_settings(
            "anima",
            "1girl, solo, anime_coloring",
            anima_settings,
        )
        == "1girl, solo, anime_coloring"
    )

    krea_settings = normalize_caption_settings("krea2", {"media_tags": True})
    assert (
        normalize_caption_with_settings(
            "krea2",
            "An anime illustration with flat cel shading.",
            krea_settings,
        )
        == "An anime illustration with flat cel shading."
    )


def test_media_tags_can_be_omitted_and_style_mode_defaults_to_omitted() -> None:
    anima_settings = normalize_caption_settings("anima", {"media_tags": False})
    assert (
        normalize_caption_with_settings(
            "anima",
            "1girl, solo, photo, realistic, anime_coloring",
            anima_settings,
        )
        == "1girl, solo"
    )

    krea_settings = normalize_caption_settings("krea2", {"media_tags": False})
    assert (
        normalize_caption_with_settings(
            "krea2",
            "A woman stands by a window in a realistic photo medium.",
            krea_settings,
        )
        == "A woman stands by a window."
    )

    style_settings = normalize_caption_settings("krea2", {"mode": "style"})
    assert style_settings["media_tags"] is False


def test_workspace_can_select_photo_tagger_per_dataset(settings, tmp_path) -> None:
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    calls: list[tuple[str, float, float, str]] = []
    curation = DatasetCurationStore(
        settings,
        workspace_store,
        tagger_factory=_fake_factory_with_thresholds(calls),
    )

    result = curation.tag_job(
        {
            "workspace_id": workspace["workspace_id"],
            "scope": "all",
            "tagger_model_id": "idolsankaku-swinv2-tagger-v1",
        },
        _RecordingContext(),
    )

    assert result["completed"] == 1
    assert calls == [("idolsankaku-swinv2-tagger-v1", 0.3094, 0.85, "auto")]
    item = curation.read_state(workspace["workspace_id"])["items"]["image-0.png"]
    assert item["wd14"]["tagger_model_id"] == "idolsankaku-swinv2-tagger-v1"
    assert item["wd14"]["model"] == "deepghs/idolsankaku-swinv2-tagger-v1"


def test_workspace_rejects_unknown_local_tagger(settings, tmp_path) -> None:
    source = _source(tmp_path, 1)
    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source)},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait(client, imported["job"]["job_id"])["status"] == "completed"
        response = client.post(
            f"/api/dataset-workspaces/{workspace_id}/wd14",
            json={"scope": "all", "tagger_model_id": "unknown-tagger"},
        )

    assert response.status_code == 422


def _wait(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "canceled"}:
            return job
        time.sleep(0.02)
    message = "Background job did not finish"
    raise AssertionError(message)


def test_workspace_curation_api_queues_long_job_and_decorates_report(
    settings,
    tmp_path,
    monkeypatch,
) -> None:
    source = _source(tmp_path, 2)

    def factory(_self, _config, _provider):
        return _fake_factory([])

    monkeypatch.setattr(DatasetCurationStore, "_default_tagger_factory", factory)
    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source)},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait(client, imported["job"]["job_id"])["status"] == "completed"
        queued = client.post(
            f"/api/dataset-workspaces/{workspace_id}/wd14",
            json={"scope": "all", "provider": "cpu"},
        )
        assert queued.status_code == 202
        job = _wait(client, queued.json()["job"]["job_id"])
        assert job["status"] == "completed"
        assert job["result"]["completed"] == 2
        report = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        assert report["images"][0]["curation"]["wd14"]["status"] == "completed"
        analytics = client.get(f"/api/dataset-workspaces/{workspace_id}/analytics").json()
        assert analytics["captioned_images"] == 2
        preview = client.post(
            f"/api/dataset-workspaces/{workspace_id}/bulk-tags/preview",
            json={"paths": ["image-0.png"], "add": ["白发"], "remove": ["一名女孩"]},
        )
        assert preview.status_code == 200
        assert preview.json()["changes"][0]["after"].isascii()
        assert "white_hair" in preview.json()["changes"][0]["after"]


def test_wd14_queue_over_24_resumes_without_overwriting_reviewed_captions(
    settings,
    tmp_path,
) -> None:
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=30)
    factory_calls: list[str] = []
    curation = DatasetCurationStore(
        settings,
        workspace_store,
        tagger_factory=lambda _config, _provider: _fake_factory(factory_calls),
    )
    curation.update_caption(
        workspace["workspace_id"],
        "image-0.png",
        profile_id="anima",
        caption="soda_trigger, solo, portrait",
    )
    curation.update_caption(
        workspace["workspace_id"],
        "image-0.png",
        profile_id="krea2",
        caption="Soda trigger appears in a carefully reviewed portrait.",
    )

    interrupted = _InterruptingContext(stop_after=10)
    with pytest.raises(JobInterruptedError):
        curation.tag_job(
            {
                "workspace_id": workspace["workspace_id"],
                "scope": "all",
                "overwrite": True,
            },
            interrupted,
        )
    partial = curation.read_state(workspace["workspace_id"])
    completed_before_resume = sum(
        item["wd14"]["status"] == "completed" for item in partial["items"].values()
    )
    assert completed_before_resume == 10

    resumed = curation.tag_job(
        {
            "workspace_id": workspace["workspace_id"],
            "scope": "all",
            "overwrite": True,
        },
        _RecordingContext(),
    )
    assert resumed["requested"] == 20
    assert resumed["completed"] == 20
    final = curation.read_state(workspace["workspace_id"])
    assert sum(item["wd14"]["status"] == "completed" for item in final["items"].values()) == 30
    assert final["items"]["image-0.png"]["captions"]["anima"]["current"] == (
        "soda_trigger, solo, portrait"
    )
    assert final["items"]["image-0.png"]["captions"]["krea2"]["current"] == (
        "Soda trigger appears in a carefully reviewed portrait."
    )
    assert factory_calls == ["loaded", "loaded"]


def test_workspace_wd14_job_can_use_vision_model_tagger(settings, tmp_path, monkeypatch) -> None:
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    calls: list[tuple[str, str, str]] = []

    def fake_draft_anima_tags(
        *,
        image_path: Path,
        model: str,
        existing_tags: str = "",
        connections=None,
        **_caption_kwargs,
    ) -> dict[str, object]:
        del connections
        return _fake_anima_tagger(calls)(image_path, model, existing_tags)

    monkeypatch.setattr(
        "prompt_hub.dataset_curation_jobs.draft_anima_tags",
        fake_draft_anima_tags,
    )
    curation = DatasetCurationStore(settings, workspace_store)

    result = curation.tag_job(
        {
            "workspace_id": workspace["workspace_id"],
            "scope": "all",
            "tagger": "model",
            "model": "vision-model",
        },
        _RecordingContext(),
    )

    assert result["completed"] == 1
    state = curation.read_state(workspace["workspace_id"])
    wd14 = state["items"]["image-0.png"]["wd14"]
    assert wd14["tagger"] == "model"
    assert wd14["model"] == "vision-model"
    assert state["items"]["image-0.png"]["captions"]["anima"]["current"] == "1girl, solo"
    assert calls == [("image-0.png", "vision-model", "")]


def test_workspace_model_tagger_requires_model(settings, tmp_path) -> None:
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    curation = DatasetCurationStore(settings, workspace_store)

    with pytest.raises(DatasetWorkspaceError, match="打标模型"):
        curation.tag_job(
            {"workspace_id": workspace["workspace_id"], "scope": "all", "tagger": "model"},
            _RecordingContext(),
        )


def test_krea2_vlm_draft_is_separate_until_confirmed(settings, tmp_path) -> None:
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=2)
    calls: list[tuple[str, str, str, dict]] = []
    curation = DatasetCurationStore(
        settings,
        workspace_store,
        krea2_captioner=_fake_krea2_captioner(calls),
    )
    workspace_id = workspace["workspace_id"]
    curation.update_caption(
        workspace_id,
        "image-0.png",
        profile_id="anima",
        caption="soda_trigger, solo, portrait",
    )
    curation.update_caption(
        workspace_id,
        "image-0.png",
        profile_id="krea2",
        caption="The reviewed Krea caption remains authoritative.",
    )

    result = curation.krea2_vlm_job(
        {"workspace_id": workspace_id, "scope": "all", "model": "test-vision-model"},
        _RecordingContext(),
    )
    assert result["completed"] == 2
    assert calls[0][:3] == (
        "image-0.png",
        "test-vision-model",
        "The reviewed Krea caption remains authoritative.",
    )
    assert calls[0][3]["mode"] == "general"
    assert calls[0][3]["media_tags"] is True
    state = curation.read_state(workspace_id)
    first = state["items"]["image-0.png"]
    assert first["captions"]["anima"]["current"] == "soda_trigger, solo, portrait"
    assert first["captions"]["krea2"]["current"] == (
        "The reviewed Krea caption remains authoritative."
    )
    assert first["krea2_vlm"]["status"] == "completed"
    assert first["krea2_vlm"]["source_sha256"]
    assert first["krea2_vlm"]["draft"].startswith("A studio portrait")

    saved = curation.update_krea2_draft(
        workspace_id,
        "image-0.png",
        draft="An edited English Krea 2 draft with a centered portrait.",
        confirm=False,
    )
    assert saved["snapshot"] == ""
    assert saved["caption"]["current"] == "The reviewed Krea caption remains authoritative."

    confirmed = curation.update_krea2_draft(
        workspace_id,
        "image-0.png",
        draft="An edited English Krea 2 draft with a centered portrait.",
        confirm=True,
    )
    assert confirmed["snapshot"].startswith("snapshot-")
    assert confirmed["caption"]["source"] == "vlm-confirmed"
    assert confirmed["caption"]["status"] == "reviewed"
    assert (
        curation.read_state(workspace_id)["items"]["image-0.png"]["captions"]["anima"]["current"]
        == "soda_trigger, solo, portrait"
    )


def test_krea2_vlm_api_queues_drafts_and_requires_confirmation(
    settings,
    tmp_path,
    monkeypatch,
) -> None:
    source = _source(tmp_path, 1)
    calls: list[tuple[str, str, str, dict]] = []
    monkeypatch.setattr(
        DatasetCurationStore,
        "_default_krea2_captioner",
        staticmethod(_fake_krea2_captioner(calls)),
    )
    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source)},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait(client, imported["job"]["job_id"])["status"] == "completed"
        queued = client.post(
            f"/api/dataset-workspaces/{workspace_id}/krea2-vlm",
            json={"scope": "missing", "model": "test-vision-model"},
        )
        assert queued.status_code == 202
        job = _wait(client, queued.json()["job"]["job_id"])
        assert job["status"] == "completed"
        assert job["result"]["completed"] == 1

        report = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        image = report["images"][0]
        assert image["curation"]["krea2_vlm"]["status"] == "completed"
        assert image["curation"]["captions"]["krea2"]["current"] == ""

        remote = client.post(
            f"/api/dataset-workspaces/{workspace_id}/krea2-vlm/import",
            json={
                "task_id": "task-vlm-remote",
                "worker_id": "training-5060ti",
                "model": "remote-vision-model",
                "items": [
                    {
                        "relative_path": "image-0.png",
                        "source_sha256": image["sha256"],
                        "caption_draft": "A remote worker drafted this English Krea 2 caption.",
                        "observations": {"composition": "portrait"},
                    }
                ],
            },
        )
        assert remote.status_code == 201
        report = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        image = report["images"][0]
        assert image["curation"]["krea2_vlm"]["worker_id"] == "training-5060ti"
        assert image["curation"]["captions"]["krea2"]["current"] == ""

        confirmed = client.put(
            f"/api/dataset-workspaces/{workspace_id}/krea2-draft",
            json={
                "relative_path": "image-0.png",
                "draft": image["curation"]["krea2_vlm"]["draft"],
                "confirm": True,
            },
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["caption"]["source"] == "vlm-confirmed"
        assert calls[0][:3] == ("image-0.png", "test-vision-model", "")


def test_krea2_drafts_confirm_batch_writes_only_drafted_images(
    settings,
    tmp_path,
    monkeypatch,
) -> None:
    """人工审核阶段要能一次写入整批草稿。但不能压掉已经人工确认的说明。"""
    source = _source(tmp_path, 3)
    calls: list[tuple[str, str, str, dict]] = []
    monkeypatch.setattr(
        DatasetCurationStore,
        "_default_krea2_captioner",
        staticmethod(_fake_krea2_captioner(calls)),
    )
    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source)},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait(client, imported["job"]["job_id"])["status"] == "completed"
        queued = client.post(
            f"/api/dataset-workspaces/{workspace_id}/krea2-vlm",
            json={"scope": "missing", "model": "test-vision-model"},
        )
        job = _wait(client, queued.json()["job"]["job_id"])
        assert job["result"]["completed"] == 3

        handwritten = "A hand written English Krea 2 caption stays authoritative."
        assert (
            client.put(
                f"/api/dataset-workspaces/{workspace_id}/caption",
                json={
                    "relative_path": "image-2.png",
                    "profile_id": "krea2",
                    "caption": handwritten,
                    "caption_status": "reviewed",
                },
            ).status_code
            == 200
        )

        paths = ["image-0.png", "image-1.png", "image-2.png"]
        result = client.post(
            f"/api/dataset-workspaces/{workspace_id}/krea2-drafts/confirm",
            json={"paths": paths},
        )
        assert result.status_code == 200
        body = result.json()
        assert body["requested"] == 3
        assert body["confirmed"] == 2
        assert body["skipped_reviewed"] == 1
        assert body["skipped_reviewed_paths"] == ["image-2.png"]
        assert body["snapshot"].startswith("snapshot-")

        report = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        captions = {
            item["relative_path"]: item["curation"]["captions"]["krea2"]
            for item in report["images"]
        }
        vlm = {item["relative_path"]: item["curation"]["krea2_vlm"] for item in report["images"]}
        for relative_path in ("image-0.png", "image-1.png"):
            assert captions[relative_path]["status"] == "reviewed"
            assert captions[relative_path]["source"] == "vlm-confirmed"
            assert captions[relative_path]["current"] == vlm[relative_path]["draft"]
            assert vlm[relative_path]["status"] == "confirmed"
        assert captions["image-2.png"]["current"] == handwritten
        assert vlm["image-2.png"]["status"] == "completed"
        assert report["images"][0]["curation"]["captions"]["anima"]["current"] == ""

        repeated = client.post(
            f"/api/dataset-workspaces/{workspace_id}/krea2-drafts/confirm",
            json={"paths": paths},
        ).json()
        assert repeated["confirmed"] == 0
        assert repeated["skipped_unchanged"] == 2
        assert repeated["skipped_reviewed"] == 1
        assert repeated["snapshot"] == ""

        overwritten = client.post(
            f"/api/dataset-workspaces/{workspace_id}/krea2-drafts/confirm",
            json={"paths": ["image-2.png"], "overwrite_reviewed": True},
        ).json()
        assert overwritten["confirmed"] == 1
        report = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        confirmed_item = next(
            item for item in report["images"] if item["relative_path"] == "image-2.png"
        )
        assert (
            confirmed_item["curation"]["captions"]["krea2"]["current"]
            == confirmed_item["curation"]["krea2_vlm"]["draft"]
        )

        missing = client.post(
            f"/api/dataset-workspaces/{workspace_id}/krea2-drafts/confirm",
            json={"paths": ["image-9.png"]},
        )
        assert missing.status_code == 404


def test_bulk_prepend_puts_trigger_word_first(settings, tmp_path) -> None:
    """触发词只有排在最前面才是触发词。排序和去重都不能把它挤走。"""
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=2)
    curation = DatasetCurationStore(settings, workspace_store)
    workspace_id = workspace["workspace_id"]
    paths = ["image-0.png", "image-1.png"]
    for relative_path in paths:
        curation.update_caption(
            workspace_id,
            relative_path,
            profile_id="anima",
            caption="solo, portrait, soda_char",
        )
        curation.update_caption(
            workspace_id,
            relative_path,
            profile_id="krea2",
            caption="A studio portrait with soft light.",
        )

    anima = curation.apply_bulk_edit(
        workspace_id,
        paths,
        {"profile_id": "anima", "prepend": ["soda_char"], "sort": True},
    )
    assert anima["changed"] == 2
    state = curation.read_state(workspace_id)
    assert (
        state["items"]["image-0.png"]["captions"]["anima"]["current"] == "soda_char, portrait, solo"
    )

    krea2 = curation.apply_bulk_edit(
        workspace_id,
        paths,
        {"profile_id": "krea2", "prepend": ["soda_char"]},
    )
    assert krea2["changed"] == 2
    state = curation.read_state(workspace_id)
    assert (
        state["items"]["image-0.png"]["captions"]["krea2"]["current"]
        == "soda_char, A studio portrait with soft light."
    )

    repeated = curation.apply_bulk_edit(
        workspace_id,
        paths,
        {"profile_id": "krea2", "prepend": ["soda_char"]},
    )
    assert repeated["changed"] == 0


def test_krea2_locale_job_translates_selected_captions(settings, tmp_path, monkeypatch) -> None:
    """批次翻译只产生中文对照。英文说明一个字都不能动。"""
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=2)
    curation = DatasetCurationStore(settings, workspace_store)
    workspace_id = workspace["workspace_id"]
    english = "A studio portrait with soft directional light."
    curation.update_caption(
        workspace_id,
        "image-0.png",
        profile_id="krea2",
        caption=english,
    )
    calls: list[str] = []

    def _translate(caption: str, *, connections: object) -> str:  # noqa: ARG001
        calls.append(caption)
        return "一张柔和方向光下的棚拍肖像。"

    monkeypatch.setattr(
        "prompt_hub.dataset_curation_jobs.translate_caption_with_model",
        _translate,
    )
    result = curation.krea2_locale_job(
        {
            "workspace_id": workspace_id,
            "scope": "selected",
            "paths": ["image-0.png", "image-1.png"],
        },
        _RecordingContext(),
    )
    assert result["completed"] == 1
    assert result["skipped"] == 1
    assert calls == [english]
    state = curation.read_state(workspace_id)
    locale = state["items"]["image-0.png"]["krea2_locale"]
    assert locale["status"] == "completed"
    assert locale["source"] == english
    assert locale["localized"] == "一张柔和方向光下的棚拍肖像。"
    assert state["items"]["image-0.png"]["captions"]["krea2"]["current"] == english

    again = curation.krea2_locale_job(
        {"workspace_id": workspace_id, "scope": "selected", "paths": ["image-0.png"]},
        _RecordingContext(),
    )
    assert again["completed"] == 0
    assert again["skipped"] == 1
    assert calls == [english]


def test_krea2_locale_job_reports_a_dead_translation_service(
    settings,
    tmp_path,
    monkeypatch,
) -> None:
    """翻不出来要说出来。静默完成会让人以为这批没有可翻的内容。"""
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    curation = DatasetCurationStore(settings, workspace_store)
    workspace_id = workspace["workspace_id"]
    curation.update_caption(
        workspace_id,
        "image-0.png",
        profile_id="krea2",
        caption="A studio portrait with soft directional light.",
    )
    monkeypatch.setattr(
        "prompt_hub.dataset_curation_jobs.translate_caption_with_model",
        lambda caption, *, connections: "",  # noqa: ARG005
    )
    with pytest.raises(DatasetWorkspaceError, match="翻译服务没有返回结果"):
        curation.krea2_locale_job(
            {"workspace_id": workspace_id, "scope": "all"},
            _RecordingContext(),
        )
    state = curation.read_state(workspace_id)
    assert state["items"]["image-0.png"]["krea2_locale"]["status"] == "failed"


def test_review_batch_api_inserts_trigger_and_queues_translation(
    settings,
    tmp_path,
    monkeypatch,
) -> None:
    """人工审核页面上的两个批次按钮走的是这两条路由。装配错了只会在运行时才发现。"""
    _source_path, _workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    workspace_id = workspace["workspace_id"]
    monkeypatch.setattr(
        "prompt_hub.dataset_curation_jobs.translate_caption_with_model",
        lambda caption, *, connections: f"zh-{caption}",  # noqa: ARG005
    )
    with TestClient(create_app(settings)) as client:
        assert (
            client.put(
                f"/api/dataset-workspaces/{workspace_id}/caption",
                json={
                    "relative_path": "image-0.png",
                    "profile_id": "krea2",
                    "caption": "A studio portrait with soft light.",
                    "caption_status": "reviewed",
                },
            ).status_code
            == 200
        )
        inserted = client.post(
            f"/api/dataset-workspaces/{workspace_id}/bulk-tags/apply",
            json={
                "profile_id": "krea2",
                "paths": ["image-0.png"],
                "prepend": ["soda_char"],
            },
        )
        assert inserted.status_code == 200
        assert inserted.json()["changed"] == 1

        queued = client.post(
            f"/api/dataset-workspaces/{workspace_id}/krea2-locale",
            json={"scope": "selected", "paths": ["image-0.png"]},
        )
        assert queued.status_code == 202
        job = _wait(client, queued.json()["job"]["job_id"])
        assert job["status"] == "completed"
        assert job["result"]["completed"] == 1

        image = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()["images"][0]
        assert image["curation"]["captions"]["krea2"]["current"] == (
            "soda_char, A studio portrait with soft light."
        )
        assert image["curation"]["krea2_locale"]["localized"] == (
            "zh-soda_char, A studio portrait with soft light."
        )

        assert (
            client.post(
                "/api/dataset-workspaces/does-not-exist/krea2-locale",
                json={"scope": "all"},
            ).status_code
            == 404
        )


def test_prepend_keeps_a_confirmed_caption_confirmed(settings, tmp_path) -> None:
    """插触发词不改任何既有内容。把整批已确认的说明打回草稿会直接挡住交付。"""
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    curation = DatasetCurationStore(settings, workspace_store)
    workspace_id = workspace["workspace_id"]
    curation.update_caption(
        workspace_id,
        "image-0.png",
        profile_id="krea2",
        caption="A studio portrait with soft light.",
        status="reviewed",
    )
    curation.apply_bulk_edit(
        workspace_id,
        ["image-0.png"],
        {"profile_id": "krea2", "prepend": ["soda_char"]},
    )
    record = curation.read_state(workspace_id)["items"]["image-0.png"]["captions"]["krea2"]
    assert record["current"] == "soda_char, A studio portrait with soft light."
    assert record["status"] == "reviewed"
    assert record["source"] == "prepend-trigger"

    # 真正改写内容的批量整理仍然要人重新看一遍。
    curation.apply_bulk_edit(
        workspace_id,
        ["image-0.png"],
        {"profile_id": "krea2", "add": ["wearing a red coat"]},
    )
    rewritten = curation.read_state(workspace_id)["items"]["image-0.png"]["captions"]["krea2"]
    assert rewritten["status"] == "draft"
    assert rewritten["source"] == "bulk-edit"


def test_confirm_captions_marks_a_batch_reviewed_without_touching_text(
    settings,
    tmp_path,
) -> None:
    """草稿状态的说明要能整批确认。文字不动。空白的不确认。"""
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=2)
    curation = DatasetCurationStore(settings, workspace_store)
    workspace_id = workspace["workspace_id"]
    caption = "A studio portrait with soft light."
    curation.update_caption(
        workspace_id,
        "image-0.png",
        profile_id="krea2",
        caption=caption,
        status="draft",
    )
    result = curation.confirm_captions(
        workspace_id,
        ["image-0.png", "image-1.png"],
        profile_id="krea2",
    )
    assert result["confirmed"] == 1
    assert result["skipped_empty"] == 1
    assert result["snapshot"].startswith("snapshot-")
    record = curation.read_state(workspace_id)["items"]["image-0.png"]["captions"]["krea2"]
    assert record["current"] == caption
    assert record["status"] == "reviewed"
    assert record["source"] == "manual-confirmed"

    repeated = curation.confirm_captions(workspace_id, ["image-0.png"], profile_id="krea2")
    assert repeated["confirmed"] == 0
    assert repeated["skipped_reviewed"] == 1
    assert repeated["snapshot"] == ""


def test_confirm_captions_api_unblocks_delivery_preflight(settings, tmp_path) -> None:
    """交付前检查挡的就是这个状态。确认之后同一批图片要能通过。"""
    _source_path, _workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=1)
    workspace_id = workspace["workspace_id"]
    with TestClient(create_app(settings)) as client:
        client.put(
            f"/api/dataset-workspaces/{workspace_id}/caption",
            json={
                "relative_path": "image-0.png",
                "profile_id": "krea2",
                "caption": "A studio portrait with soft light.",
                "caption_status": "draft",
            },
        )
        client.put(
            f"/api/dataset-workspaces/{workspace_id}/review",
            json={"items": [{"relative_path": "image-0.png", "status": "approved"}]},
        )
        blocked = client.post(
            f"/api/dataset-workspaces/{workspace_id}/preflight",
            json={"profile_id": "krea2", "paths": ["image-0.png"]},
        ).json()
        assert any(item["code"] == "caption_not_reviewed" for item in blocked["blockers"])

        confirmed = client.post(
            f"/api/dataset-workspaces/{workspace_id}/captions/confirm",
            json={"profile_id": "krea2", "paths": ["image-0.png"]},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["confirmed"] == 1

        cleared = client.post(
            f"/api/dataset-workspaces/{workspace_id}/preflight",
            json={"profile_id": "krea2", "paths": ["image-0.png"]},
        ).json()
        assert cleared["ready"] is True


def test_preflight_warns_about_selected_near_duplicates(settings, tmp_path) -> None:
    """近似重复是 left_files / right_files 两边比出来的。

    照 exact 的 files 形状去读不会报错。只会永远读到空。提醒就成了摆设。
    """
    source = tmp_path / "near-duplicate-source"
    source.mkdir()
    base = Image.linear_gradient("L").resize((80, 64)).convert("RGB")
    base.save(source / "left.png")
    ImageEnhance.Brightness(base).enhance(0.99).save(source / "right.png")
    workspace_store = DatasetWorkspaceStore(settings)
    workspace_store.initialize()
    workspace = workspace_store.register(source, name="Near duplicates")
    job_store = BackgroundJobStore(settings.database_path)
    job_store.initialize()
    job = job_store.enqueue("dataset_scan", {"workspace_id": workspace["workspace_id"]})
    assert job_store.claim_next({"dataset_scan"}) is not None
    workspace_store.scan(workspace["workspace_id"], JobContext(job_store, job["job_id"], Event()))
    workspace_id = workspace["workspace_id"]
    report = workspace_store.read_current_report(workspace_id)
    assert report is not None
    assert report["near_duplicates"]
    assert "files" not in report["near_duplicates"][0]

    curation = DatasetCurationStore(settings, workspace_store)
    paths = ["left.png", "right.png"]
    for relative_path in paths:
        curation.update_caption(
            workspace_id,
            relative_path,
            profile_id="krea2",
            caption="A soft grey gradient study.",
        )
    workspace_store.update_review_state(
        workspace_id,
        [{"relative_path": path, "status": "approved"} for path in paths],
    )
    preflight = curation.preflight_export(workspace_id, profile_id="krea2", paths=paths)
    assert preflight["ready"] is True
    assert {item["code"] for item in preflight["warnings"]} == {"near_duplicate"}
    assert preflight["warnings"][0]["count"] == 2


class TestCaptionLanguageGate:
    """要挡的是模型回了中日韩文字。不是所有非 ASCII 字符。"""

    def test_typographic_characters_are_folded_not_rejected(self) -> None:
        """弯引号和破折号是排版字符。视觉模型经常输出。
        用 isascii 当代理时 "a woman's shirt" 会被判成不是英文。"""
        assert (
            _normalize_caption("krea2", "A woman’s white shirt drapes off her shoulders.")  # noqa: RUF001 (测试资料本身就必须是这个字符)
            == "A woman's white shirt drapes off her shoulders."
        )
        assert _normalize_caption("krea2", "A woman stands — looking back.") == (
            "A woman stands - looking back."
        )
        assert _normalize_caption("krea2", "She looks away… softly lit.") == (
            "She looks away... softly lit."
        )

    def test_accented_latin_is_still_english_enough(self) -> None:
        assert _normalize_caption("krea2", "A woman sitting in a café.") == (
            "A woman sitting in a café."
        )

    def test_cjk_output_is_still_rejected(self) -> None:
        for text in ("一位女性站在窗边", "女性が窓辺に"):
            with pytest.raises(DatasetWorkspaceError):
                _normalize_caption("krea2", text)

    def test_fullwidth_punctuation_signals_chinese_output(self) -> None:
        with pytest.raises(DatasetWorkspaceError):
            _normalize_caption("krea2", "A woman，standing.")  # noqa: RUF001 (测试资料本身就必须是这个字符)


def test_trigger_word_is_optional_in_every_mode() -> None:
    """触发词是选填的。

    前端放行、后端强制要求时。队列会在第一张之前就整个失败。
    错误停在 0/0——使用者看到的只是「执行失败」。
    """
    for mode in ("general", "portrait", "outfit", "style"):
        settings = normalize_caption_settings("krea2", {"mode": mode, "trigger": ""})
        assert settings["mode"] == mode
        assert settings["trigger"] == ""

    filled = normalize_caption_settings("krea2", {"mode": "portrait", "trigger": "miru"})
    assert filled["trigger"] == "miru"


def test_batch_failure_message_names_the_reason() -> None:
    """整批失败几乎总是同一个原因。

    只写「共 N 张失败」的话。使用者得自己去翻每一张的记录才知道为什么。
    """
    message = _batch_failure_message(
        "Krea 2 VLM",
        79,
        ["视觉模型没有返回可识别的草稿 JSON"] * 79,
    )
    assert "79" in message
    assert "视觉模型没有返回可识别的草稿 JSON" in message


def test_batch_failure_message_survives_having_no_reasons() -> None:
    assert "共 3 张" in _batch_failure_message("WD14", 3, [])
