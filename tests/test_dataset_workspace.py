from __future__ import annotations

import time
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient
from PIL import Image, ImageEnhance

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobStore, JobContext
from prompt_hub.dataset_workspace import DatasetWorkspaceStore
from prompt_hub.remote_nodes import BRIDGE_DIRECTORIES


def _build_dataset(root: Path) -> Path:
    source = root / "training-set"
    source.mkdir()
    base = Image.linear_gradient("L").resize((80, 64)).convert("RGB")
    base.save(source / "paired.png")
    (source / "paired.txt").write_text("1girl, red dress", encoding="utf-8")
    (source / "duplicate.png").write_bytes((source / "paired.png").read_bytes())
    ImageEnhance.Brightness(base).enhance(0.99).save(source / "near.png")
    (source / "broken.jpg").write_bytes(b"not an image")
    (source / "orphan.txt").write_text("orphan caption", encoding="utf-8")
    return source


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "canceled"}:
            return job
        time.sleep(0.02)
    message = "Dataset scan did not finish"
    raise AssertionError(message)


def _assert_existing_copy_is_not_overwritten(
    client: TestClient,
    workspace_id: str,
    version_id: str,
    target: Path,
) -> dict:
    (target / "manifest.json").write_text("{}", encoding="utf-8")
    conflict = client.post(
        f"/api/dataset-workspaces/{workspace_id}/exports/{version_id}/copy",
        json={"node_id": "compute_5060ti"},
    )
    assert conflict.status_code == 422
    assert "未覆盖" in conflict.json()["detail"]
    assert (target / "manifest.json").read_text(encoding="utf-8") == "{}"
    return client.get(f"/api/dataset-workspaces/{workspace_id}/exports").json()[0]


def _assert_smb_offline_then_recovers(
    client: TestClient,
    *,
    workspace_id: str,
    version_id: str,
    mount: Path,
    exported_directory: str,
) -> None:
    offline_mount = mount.with_name(f"{mount.name}-offline")
    mount.rename(offline_mount)
    offline = client.post(
        f"/api/dataset-workspaces/{workspace_id}/exports/{version_id}/copy",
        json={"node_id": "compute_5060ti"},
    )
    assert offline.status_code == 422
    assert "共享目录离线或不可写" in offline.json()["detail"]
    assert Path(exported_directory).is_dir()
    assert client.get("/api/remote-nodes/compute_5060ti/diagnostics").json()["state"] == (
        "mount_missing"
    )
    offline_mount.rename(mount)
    recovered = client.get("/api/remote-nodes/compute_5060ti/diagnostics").json()
    assert recovered["state"] == "ready"
    assert recovered["bridge_writable"] is True


def test_dataset_workspace_scan_preserves_source_and_versions_reports(settings, tmp_path) -> None:
    source = _build_dataset(tmp_path)
    original_bytes = {path: path.read_bytes() for path in source.iterdir() if path.is_file()}
    workspace_store = DatasetWorkspaceStore(settings)
    workspace_store.initialize()
    workspace = workspace_store.register(source, name="角色训练集")
    assert workspace_store.register(source)["workspace_id"] == workspace["workspace_id"]

    job_store = BackgroundJobStore(settings.database_path)
    job_store.initialize()
    job = job_store.enqueue("dataset_scan", {"workspace_id": workspace["workspace_id"]})
    claimed = job_store.claim_next({"dataset_scan"})
    assert claimed is not None
    context = JobContext(job_store, job["job_id"], Event())
    result = workspace_store.scan(workspace["workspace_id"], context)
    report = workspace_store.read_current_report(workspace["workspace_id"])
    assert report is not None
    assert result["image_count"] == 4
    assert report["summary"] == {
        "exact_duplicate_groups": 1,
        "image_count": 4,
        "invalid_image_count": 1,
        "missing_caption_count": 3,
        "near_duplicate_groups": 1,
        "orphan_caption_count": 1,
        "paired_caption_count": 1,
        "valid_image_count": 3,
    }
    assert report["orphan_captions"] == ["orphan.txt"]
    assert report["exact_duplicates"][0]["files"] == ["duplicate.png", "paired.png"]
    paired = next(item for item in report["images"] if item["filename"] == "paired.png")
    broken = next(item for item in report["images"] if item["filename"] == "broken.jpg")
    assert paired["caption"] == "1girl, red dress"
    assert paired["width"] == 80
    assert (
        settings.dataset_workspaces_root / workspace["workspace_id"] / paired["thumbnail"]
    ).is_file()
    assert broken["valid"] is False
    assert broken["error"]
    assert {path: path.read_bytes() for path in original_bytes} == original_bytes

    first_workspace = workspace_store.get(workspace["workspace_id"])
    assert first_workspace is not None
    first_report = first_workspace["current_report"]
    workspace_store.scan(workspace["workspace_id"], context)
    second_workspace = workspace_store.get(workspace["workspace_id"])
    assert second_workspace is not None
    second_report = second_workspace["current_report"]
    assert first_report != second_report
    assert (settings.dataset_workspaces_root / workspace["workspace_id"] / first_report).is_file()
    assert {path: path.read_bytes() for path in original_bytes} == original_bytes


def test_dataset_workspace_api_runs_recoverable_scan(settings, tmp_path) -> None:
    source = tmp_path / "api-dataset"
    source.mkdir()
    Image.new("RGB", (48, 64), "navy").save(source / "character.webp")
    (source / "character.txt").write_text("1girl, navy hair", encoding="utf-8")

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source), "name": "API dataset"},
        )
        assert response.status_code == 202
        payload = response.json()
        workspace_id = payload["workspace"]["workspace_id"]
        job = _wait_for_job(client, payload["job"]["job_id"])
        assert job["status"] == "completed"
        assert job["result"]["valid_image_count"] == 1

        workspace = client.get(f"/api/dataset-workspaces/{workspace_id}").json()
        assert workspace["status"] == "ready"
        report = client.get(f"/api/dataset-workspaces/{workspace_id}/report")
        assert report.status_code == 200
        assert report.json()["images"][0]["caption"] == "1girl, navy hair"
        thumbnail_url = report.json()["images"][0]["thumbnail_url"]
        assert client.get(thumbnail_url).headers["content-type"] == "image/webp"
        assert client.get(thumbnail_url.replace(".webp", "../test.sqlite")).status_code == 404
        assert client.get("/api/dataset-workspaces").json()[0]["workspace_id"] == workspace_id
        assert (
            client.get("/api/jobs", params={"job_status": "completed"}).json()[0]["job_id"]
            == job["job_id"]
        )
        assert client.post(f"/api/dataset-workspaces/{workspace_id}/rescan").status_code == 202
        assert client.get("/api/dataset-workspaces/missing").status_code == 404
        assert client.get("/api/jobs/missing").status_code == 404

        broad = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(Path.home())},
        )
        assert broad.status_code == 422


def test_dataset_workspace_review_original_and_remove_preserve_source(settings, tmp_path) -> None:
    source = tmp_path / "review-source"
    source.mkdir()
    image_path = source / "nested" / "portrait.png"
    image_path.parent.mkdir()
    Image.new("RGB", (96, 128), "purple").save(image_path)
    caption_path = image_path.with_suffix(".txt")
    caption_path.write_text("1girl, purple hair", encoding="utf-8")
    original_image = image_path.read_bytes()
    original_caption = caption_path.read_bytes()

    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source), "name": "Review source"},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait_for_job(client, imported["job"]["job_id"])["status"] == "completed"

        report = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        item = report["images"][0]
        assert item["review"]["status"] == "pending"
        assert client.get(item["original_url"]).headers["content-type"] == "image/png"
        assert (
            client.get(
                f"/dataset-workspaces/{workspace_id}/original",
                params={"relative_path": "../test.sqlite"},
            ).status_code
            == 404
        )

        updated = client.put(
            f"/api/dataset-workspaces/{workspace_id}/review",
            json={
                "items": [
                    {
                        "relative_path": "nested/portrait.png",
                        "status": "approved",
                        "selected": True,
                        "note": "face is clear",
                    }
                ]
            },
        )
        assert updated.status_code == 200
        reviewed = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        assert reviewed["images"][0]["review"]["status"] == "approved"
        assert reviewed["images"][0]["review"]["selected"] is True

        removed = client.delete(f"/api/dataset-workspaces/{workspace_id}")
        assert removed.json()["source_untouched"] is True
        assert client.get(f"/api/dataset-workspaces/{workspace_id}").status_code == 404

    assert image_path.read_bytes() == original_image
    assert caption_path.read_bytes() == original_caption


def test_dataset_export_history_reveal_and_controlled_smb_copy(
    settings,
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "delivery-source"
    source.mkdir()
    image_path = source / "portrait.png"
    Image.new("RGB", (96, 128), "purple").save(image_path)
    (source / "portrait.txt").write_text("1girl, purple hair", encoding="utf-8")
    source_digest = image_path.read_bytes()
    revealed: list[Path] = []

    def record_reveal(path: Path) -> None:
        revealed.append(path)

    monkeypatch.setattr(
        "prompt_hub.workspace_routes._reveal_in_finder",
        record_reveal,
    )

    mount = tmp_path / "mounted-share"
    mount.mkdir()
    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source), "name": "林悔儿 / Delivery"},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait_for_job(client, imported["job"]["job_id"])["status"] == "completed"
        assert (
            client.post(
                f"/api/dataset-workspaces/{workspace_id}/source-captions/apply",
                json={"profile_id": "anima", "caption_status": "reviewed"},
            ).status_code
            == 200
        )
        assert (
            client.put(
                f"/api/dataset-workspaces/{workspace_id}/review",
                json={
                    "items": [
                        {
                            "relative_path": "portrait.png",
                            "status": "approved",
                            "selected": True,
                            "note": "",
                        }
                    ]
                },
            ).status_code
            == 200
        )
        preflight = client.post(
            f"/api/dataset-workspaces/{workspace_id}/preflight",
            json={"profile_id": "anima", "paths": ["portrait.png"]},
        )
        assert preflight.status_code == 200
        assert preflight.json()["ready"] is True
        exported = client.post(
            f"/api/dataset-workspaces/{workspace_id}/export",
            json={"profile_id": "anima", "paths": ["portrait.png"]},
        )
        assert exported.status_code == 201
        version_id = exported.json()["version_id"]

        history = client.get(f"/api/dataset-workspaces/{workspace_id}/exports")
        assert history.status_code == 200
        assert history.json()[0]["version_id"] == version_id
        revealed_response = client.post(
            f"/api/dataset-workspaces/{workspace_id}/exports/{version_id}/reveal"
        )
        assert revealed_response.status_code == 200
        assert revealed
        assert revealed[0].is_dir()

        saved = client.put(
            "/api/remote-nodes/compute_5060ti",
            json={
                "label": "5060 Ti",
                "role": "compute_5060ti",
                "host": "192.168.1.10",
                "smb_mount": str(mount),
                "enabled": True,
                "capabilities": [],
            },
        )
        assert saved.status_code == 200
        assert client.post("/api/remote-nodes/compute_5060ti/prepare").status_code == 201
        assert all((mount / "prompt-hub" / name).is_dir() for name in BRIDGE_DIRECTORIES)

        _assert_smb_offline_then_recovers(
            client,
            workspace_id=workspace_id,
            version_id=version_id,
            mount=mount,
            exported_directory=exported.json()["directory"],
        )

        copied = client.post(
            f"/api/dataset-workspaces/{workspace_id}/exports/{version_id}/copy",
            json={"node_id": "compute_5060ti"},
        )
        assert copied.status_code == 201
        target = Path(copied.json()["target_directory"])
        assert target.is_relative_to(mount / "prompt-hub" / "datasets")
        assert (target / "train" / "portrait.png").is_file()
        assert (target / "hashes.sha256").is_file()
        repeated = client.post(
            f"/api/dataset-workspaces/{workspace_id}/exports/{version_id}/copy",
            json={"node_id": "compute_5060ti"},
        )
        assert repeated.status_code == 200
        assert repeated.json()["status"] == "already_present"
        assert image_path.read_bytes() == source_digest

        refreshed = _assert_existing_copy_is_not_overwritten(
            client, workspace_id, version_id, target
        )
        assert refreshed["copies"][0]["node_id"] == "compute_5060ti"
        assert refreshed["copies"][0]["status"] == "failed"


def test_dataset_export_io_failure_is_readable_and_cleans_partial_files(
    settings,
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "io-failure-source"
    source.mkdir()
    image_path = source / "portrait.png"
    Image.new("RGB", (96, 128), "purple").save(image_path)
    caption_path = source / "portrait.txt"
    caption_path.write_text("1girl, purple hair", encoding="utf-8")
    original_image = image_path.read_bytes()
    original_caption = caption_path.read_bytes()

    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(source), "name": "I/O failure"},
        ).json()
        workspace_id = imported["workspace"]["workspace_id"]
        assert _wait_for_job(client, imported["job"]["job_id"])["status"] == "completed"
        assert (
            client.post(
                f"/api/dataset-workspaces/{workspace_id}/source-captions/apply",
                json={"profile_id": "anima", "caption_status": "reviewed"},
            ).status_code
            == 200
        )
        assert (
            client.put(
                f"/api/dataset-workspaces/{workspace_id}/review",
                json={
                    "items": [
                        {
                            "relative_path": "portrait.png",
                            "status": "approved",
                            "selected": True,
                            "note": "",
                        }
                    ]
                },
            ).status_code
            == 200
        )

        def fail_copy(_source: Path, _target: Path) -> None:
            message = "No space left on device"
            raise OSError(message)

        monkeypatch.setattr("prompt_hub.dataset_curation.shutil.copy2", fail_copy)
        response = client.post(
            f"/api/dataset-workspaces/{workspace_id}/export",
            json={"profile_id": "anima", "paths": ["portrait.png"]},
        )

        assert response.status_code == 422
        assert "冻结数据集失败" in response.json()["detail"]
        assert "未完成文件已清理" in response.json()["detail"]
        export_root = settings.dataset_exports_root / "workspaces" / workspace_id
        assert not list(export_root.glob("anima-*"))
        assert client.get(f"/api/dataset-workspaces/{workspace_id}/exports").json() == []

    assert image_path.read_bytes() == original_image
    assert caption_path.read_bytes() == original_caption
