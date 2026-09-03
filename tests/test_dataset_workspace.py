from __future__ import annotations

import time
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient
from PIL import Image, ImageEnhance

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobStore, JobContext
from prompt_hub.dataset_workspace import DatasetWorkspaceStore


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
