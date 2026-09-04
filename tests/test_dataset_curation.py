from __future__ import annotations

import json
import time
import zipfile
from threading import Event
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobStore, JobContext, JobInterruptedError
from prompt_hub.dataset_curation import DatasetCurationStore
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


def _fake_krea2_captioner(calls: list[tuple[str, str, str]]):
    def caption(path: Path, model: str, existing: str) -> dict[str, object]:
        calls.append((path.name, model, existing))
        return {
            "model": model,
            "draft": f"A studio portrait from {path.stem} with soft directional light.",
            "observations": {"composition": "portrait", "lighting": "soft directional light"},
            "safety_warning": "",
        }

    return caption


def test_workspace_wd14_captions_bulk_snapshots_and_export(settings, tmp_path) -> None:
    source, workspace_store, workspace = _scanned_workspace(settings, tmp_path)
    source_before = {path.name: path.read_bytes() for path in source.iterdir()}
    factory_calls: list[str] = []
    curation = DatasetCurationStore(
        settings,
        workspace_store,
        tagger_factory=lambda _general, _character, _provider: _fake_factory(factory_calls),
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
    assert first["wd14"]["model"] == "fake-wd14"
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
        {"add": ["白发"], "remove": ["一名女孩"]},
    )
    assert applied["snapshot"].startswith("snapshot-")
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
    assert preview["invalid"] == [
        {"relative_path": "image-2.png", "reason": "最终 caption 必须使用英文"}
    ]
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

    def factory(_self, _general, _character, _provider):
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
        tagger_factory=lambda _general, _character, _provider: _fake_factory(factory_calls),
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


def test_krea2_vlm_draft_is_separate_until_confirmed(settings, tmp_path) -> None:
    _source_path, workspace_store, workspace = _scanned_workspace(settings, tmp_path, count=2)
    calls: list[tuple[str, str, str]] = []
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
    assert calls[0] == (
        "image-0.png",
        "test-vision-model",
        "The reviewed Krea caption remains authoritative.",
    )
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
    calls: list[tuple[str, str, str]] = []
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
        assert calls == [("image-0.png", "test-vision-model", "")]
