from __future__ import annotations

import json
import time
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app


def _image_bytes(color: str = "purple") -> bytes:
    output = BytesIO()
    Image.new("RGB", (96, 128), color).save(output, "PNG")
    return output.getvalue()


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "canceled"}:
            return job
        time.sleep(0.02)
    message = "Project dataset scan did not finish"
    raise AssertionError(message)


def _project_payload() -> dict:
    return {
        "title": "林悔儿 · 雨夜",
        "brief_zh": "林悔儿在雨夜回望镜头",
        "safety_mode": "sfw",
        "target_profile": "anima",
        "slots": {
            "character": "1girl, long black hair, green eyes",
            "outfit": "black coat",
            "action": "looking back",
            "composition": "medium shot",
            "scene": "rainy street at night",
            "lighting": "neon rim light",
            "style": "cinematic illustration",
        },
        "references": [
            {
                "key": "test:reference:character",
                "slot": "character",
                "source_id": "test",
                "external_id": "reference",
                "title": "角色参考",
            }
        ],
        "generation": {
            "seed": "314159",
            "steps": 28,
            "cfg": 5.5,
            "workflow_controls": {
                "anima": {
                    "models": {"checkpoint": "anima-test.safetensors"},
                    "loras": [{"lora_id": "linhuier", "strength": 0.8}],
                    "sampler": "euler",
                    "scheduler": "normal",
                }
            },
        },
    }


def test_project_journey_sync_and_delivery_keep_lineage_without_reviewing(  # noqa: PLR0915
    settings,
    tmp_path,
) -> None:
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/creative/projects", json=_project_payload()).json()
        project_id = project["project_id"]
        empty = client.post(
            f"/api/creative/projects/{project_id}/dataset-workspace",
            json={"profile_id": "anima"},
        )
        assert empty.status_code == 422
        assert "手动精选" in empty.json()["detail"]

        uploaded = client.post(
            f"/api/creative/projects/{project_id}/results?filename=rain.png",
            content=_image_bytes(),
            headers={"Content-Type": "image/png"},
        ).json()
        asset = uploaded["asset"]
        generation = uploaded["project"]["generation"]
        generation["result_assets"][0]["comfy_metadata"] = {
            "seed": 271828,
            "steps": 32,
            "cfg": 6.0,
            "checkpoint": "anima-actual.safetensors",
            "loras": [{"name": "linhuier.safetensors", "strength_model": 0.9}],
            "prompt": {"1": {"class_type": "KSampler"}},
            "workflow": {"nodes": [{"id": 1, "type": "KSampler"}]},
        }
        updated = client.put(
            f"/api/creative/projects/{project_id}",
            json={"generation": generation},
        )
        assert updated.status_code == 200
        selected = client.put(
            f"/api/creative/projects/{project_id}/results/{asset['asset_id']}/dataset",
            json={
                "selected": True,
                "profile_id": "anima",
                "caption_override": "1girl, long black hair, rainy street",
            },
        )
        assert selected.status_code == 200

        before = client.get(f"/api/creative/projects/{project_id}/journey").json()
        assert before["summary"] == {
            "result_count": 1,
            "selected_count": 1,
            "workspace_count": 0,
            "delivery_count": 0,
        }
        assert [stage["stage_id"] for stage in before["stages"]] == [
            "inspiration",
            "prompts",
            "generation",
            "results",
            "dataset",
            "delivery",
        ]

        synced = client.post(
            f"/api/creative/projects/{project_id}/dataset-workspace",
            json={"profile_id": "anima"},
        )
        assert synced.status_code == 202
        sync_payload = synced.json()
        assert sync_payload["synced"] == 1
        assert sync_payload["existing"] == 0
        assert sync_payload["review_changed"] is False
        workspace_id = sync_payload["workspace"]["workspace_id"]
        assert _wait_for_job(client, sync_payload["job"]["job_id"])["status"] == "completed"

        workspace = client.get(f"/api/dataset-workspaces/{workspace_id}").json()
        assert workspace["origin"]["project_id"] == project_id
        assert workspace["origin"]["result_asset_ids"] == [asset["asset_id"]]
        report = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        item = report["images"][0]
        assert item["review"]["status"] == "pending"
        assert item["review"]["selected"] is False
        assert item["caption"].strip() == "1girl, long black hair, rainy street"

        lineage_path = (
            settings.project_dataset_sources_root / project_id / ".prompt-hub-lineage.json"
        )
        lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
        source = lineage["items"][item["relative_path"]]
        assert source["project_id"] == project_id
        assert source["asset_id"] == asset["asset_id"]
        assert source["prompt"]["profile_id"] == "anima"
        assert source["workflow"]["graph"]["nodes"][0]["type"] == "KSampler"
        assert source["checkpoint"] == "anima-actual.safetensors"
        assert source["loras"][0]["name"] == "linhuier.safetensors"
        assert source["seed"] == 271828

        repeated = client.post(
            f"/api/creative/projects/{project_id}/dataset-workspace",
            json={"profile_id": "anima"},
        ).json()
        assert repeated["workspace"]["workspace_id"] == workspace_id
        assert repeated["synced"] == 0
        assert repeated["existing"] == 1
        assert _wait_for_job(client, repeated["job"]["job_id"])["status"] == "completed"
        repeated_report = client.get(f"/api/dataset-workspaces/{workspace_id}/report").json()
        assert repeated_report["images"][0]["review"]["status"] == "pending"

        current_journey = client.get(f"/api/creative/projects/{project_id}/journey").json()
        dataset_stage = next(
            stage for stage in current_journey["stages"] if stage["stage_id"] == "dataset"
        )
        assert dataset_stage["status"] != "项目或精选内容有更新"
        assert dataset_stage["action"] == {
            "label": "打开数据集工作区",
            "view": "datasets",
            "target_id": workspace_id,
        }

        changed = client.put(
            f"/api/creative/projects/{project_id}",
            json={"brief_zh": "林悔儿在雨夜回望镜头, 增加潮湿路面倒影"},
        )
        assert changed.status_code == 200
        changed_journey = client.get(f"/api/creative/projects/{project_id}/journey").json()
        changed_dataset_stage = next(
            stage for stage in changed_journey["stages"] if stage["stage_id"] == "dataset"
        )
        assert changed_dataset_stage["status"] == "项目或精选内容有更新"
        assert changed_dataset_stage["action"] == {
            "label": "更新并打开工作区",
            "view": "creative",
            "target_id": "",
        }

        relative_path = item["relative_path"]
        captioned = client.post(
            f"/api/dataset-workspaces/{workspace_id}/source-captions/apply",
            json={
                "profile_id": "anima",
                "paths": [relative_path],
                "overwrite_existing": False,
                "caption_status": "reviewed",
            },
        )
        assert captioned.status_code == 200
        reviewed = client.put(
            f"/api/dataset-workspaces/{workspace_id}/review",
            json={
                "items": [
                    {
                        "relative_path": relative_path,
                        "status": "approved",
                        "selected": True,
                        "note": "人工确认",
                    }
                ]
            },
        )
        assert reviewed.status_code == 200
        exported = client.post(
            f"/api/dataset-workspaces/{workspace_id}/export",
            json={"profile_id": "anima", "paths": [relative_path]},
        )
        assert exported.status_code == 201
        delivery = exported.json()
        assert delivery["manifest"]["origin"]["project_id"] == project_id
        delivered_source = delivery["manifest"]["items"][0]["source"]
        assert delivered_source["asset_id"] == asset["asset_id"]
        assert delivered_source["seed"] == 271828
        with ZipFile(
            settings.dataset_exports_root / "workspaces" / workspace_id / delivery["archive_name"]
        ) as archive:
            archived = json.loads(archive.read("manifest.json"))
        assert archived["items"][0]["source"]["source_result_url"].endswith(asset["asset_id"])

        history = client.get(f"/api/dataset-workspaces/{workspace_id}/exports").json()
        assert history[0]["origin"]["project_id"] == project_id
        assert history[0]["source_result_asset_ids"] == [asset["asset_id"]]
        complete = client.get(f"/api/creative/projects/{project_id}/journey").json()
        assert complete["summary"]["workspace_count"] == 1
        assert complete["summary"]["delivery_count"] == 1
        assert complete["stages"][-1]["state"] == "ready"
        assert complete["review_changed"] is False

        external_source = tmp_path / "external-independent"
        external_source.mkdir()
        Image.new("RGB", (48, 64), "navy").save(external_source / "external.png")
        external = client.post(
            "/api/dataset-workspaces/import",
            json={"source_path": str(external_source), "name": "外部独立数据集"},
        ).json()
        assert external["workspace"]["origin"] == {}
        assert _wait_for_job(client, external["job"]["job_id"])["status"] == "completed"
        unchanged = client.get(f"/api/creative/projects/{project_id}/journey").json()
        assert unchanged["summary"]["workspace_count"] == 1
