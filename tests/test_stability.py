from __future__ import annotations

import time

from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobStore
from prompt_hub.dataset_workspace import DatasetWorkspaceStore


def test_service_restart_recovers_interrupted_dataset_scan(settings, tmp_path) -> None:
    source = tmp_path / "restart-source"
    source.mkdir()
    image = source / "portrait.png"
    Image.new("RGB", (64, 96), "navy").save(image)
    caption = source / "portrait.txt"
    caption.write_text("1girl, navy hair", encoding="utf-8")
    original = {image: image.read_bytes(), caption: caption.read_bytes()}

    workspace_store = DatasetWorkspaceStore(settings)
    workspace_store.initialize()
    workspace = workspace_store.register(source, name="重启恢复测试")
    job_store = BackgroundJobStore(settings.database_path)
    job_store.initialize()
    queued = job_store.enqueue(
        "dataset_scan",
        {"workspace_id": workspace["workspace_id"]},
        max_attempts=2,
    )
    claimed = job_store.claim_next({"dataset_scan"})
    assert claimed is not None
    assert claimed["status"] == "running"

    with TestClient(create_app(settings)) as client:
        deadline = time.monotonic() + 5
        recovered = {}
        while time.monotonic() < deadline:
            recovered = client.get(f"/api/jobs/{queued['job_id']}").json()
            if recovered["status"] in {"completed", "failed", "canceled"}:
                break
            time.sleep(0.02)

        assert recovered["status"] == "completed"
        assert recovered["attempts"] == 2
        assert "服务重启" not in recovered["progress_message"]
        current = client.get(f"/api/dataset-workspaces/{workspace['workspace_id']}").json()
        assert current["status"] == "ready"
        assert current["summary"]["valid_image_count"] == 1

    assert {path: path.read_bytes() for path in original} == original
