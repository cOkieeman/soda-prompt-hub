from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.workflow_profiles import WorkflowProfileError, WorkflowProfileStore


def _node(class_type: str, **inputs: object) -> dict[str, object]:
    return {"class_type": class_type, "inputs": inputs}


def _krea_workflow() -> dict[str, dict[str, object]]:
    return {
        "1": _node("CheckpointLoader", ckpt_name="Krea2\\model.safetensors"),
        "87": _node(
            "ImpactKSamplerBasicPipe",
            basic_pipe=["141", 0],
            latent_image=["129", 0],
            seed=1,
            steps=20,
            cfg=4.0,
        ),
        "121": _node("CLIPTextEncode", clip=["1", 0], text="old negative"),
        "129": _node("EmptyLatentImage", width=1024, height=1024, batch_size=1),
        "132": _node("VAEDecode", samples=["87", 0], vae=["121", 0]),
        "133": _node("SaveImage", images=["999", 0], filename_prefix="old"),
        "141": _node(
            "ImpactWildcardEncode",
            model=["1", 0],
            clip=["1", 0],
            wildcard_text="old positive",
            populated_text="old positive",
            seed=1,
        ),
        "999": _node("SeedVR2Upscaler", images=["132", 0]),
    }


def _anima_workflow() -> dict[str, dict[str, object]]:
    return {
        "75": _node("String Literal", string="old negative"),
        "77": _node(
            "Lora Loader (LoraManager)",
            model=["150", 0],
            loras={"__value__": [{"name": "mansui-anima_v1.1", "active": True}]},
        ),
        "81": _node(
            "Image Saver",
            images=["999", 0],
            filename="old",
            path="old",
            steps=10,
            cfg=5.0,
            width=512,
            height=512,
        ),
        "84": _node("Seed (rgthree)", seed=1),
        "150": _node("ResolutionMasterSimplify", width=1024, height=1536),
        "182": _node("String Literal", string="masterpiece, best quality"),
        "184": _node(
            "ImpactWildcardEncode",
            model=["77", 0],
            clip=["182", 0],
            wildcard_text="old positive",
            populated_text="old positive",
            seed=1,
        ),
        "135:103": _node("Int Literal", int=20, source=["184", 0]),
        "135:104": _node("Cfg Literal", float=4.0, source=["84", 0]),
        "148:139": _node(
            "VAEDecode",
            samples=["135:103", 0],
            vae=["135:104", 0],
            negative=["75", 0],
            resolution=["150", 0],
        ),
        "999": _node("UltimateSDUpscale", images=["148:139", 0]),
    }


def _raw(workflow: dict[str, dict[str, object]]) -> bytes:
    return json.dumps(workflow, ensure_ascii=False).encode()


def test_profile_import_rejects_ui_wrong_nodes_and_credentials(tmp_path) -> None:
    store = WorkflowProfileStore(tmp_path / "profiles")
    with pytest.raises(WorkflowProfileError, match="API Format"):
        store.import_bytes(
            "krea2-ares-ocmanager",
            json.dumps({"nodes": []}).encode(),
            label="Krea",
            filename="ui.json",
        )
    wrong = _krea_workflow()
    wrong["132"]["class_type"] = "WrongDecode"
    with pytest.raises(WorkflowProfileError, match="类型不匹配"):
        store.import_bytes(
            "krea2-ares-ocmanager",
            _raw(wrong),
            label="Krea",
            filename="wrong.json",
        )
    credential = _krea_workflow()
    credential["1"]["inputs"] = {"api_key": "must-not-be-saved"}
    with pytest.raises(WorkflowProfileError, match="凭据"):
        store.import_bytes(
            "krea2-ares-ocmanager",
            _raw(credential),
            label="Krea",
            filename="secret.json",
        )


def test_krea_profile_is_idempotent_and_compiles_low_cost(tmp_path) -> None:
    store = WorkflowProfileStore(tmp_path / "profiles")
    raw = _raw(_krea_workflow())
    profile = store.import_bytes(
        "krea2-ares-ocmanager",
        raw,
        label="Krea 2 / Ares",
        filename="krea.json",
    )
    duplicate = store.import_bytes(
        "krea2-ares-ocmanager",
        raw,
        label="Ignored",
        filename="duplicate.json",
    )
    assert profile["duplicate"] is False
    assert duplicate["duplicate"] is True
    with pytest.raises(WorkflowProfileError, match="确认替换"):
        store.import_bytes(
            "krea2-ares-ocmanager",
            _raw({**_krea_workflow(), "2": _node("Extra")}),
            label="Changed",
            filename="changed.json",
        )
    package = store.compile_package(
        "krea2-ares-ocmanager",
        run_id="run-krea-test",
        positive="adult woman, cinematic portrait",
        negative="blur",
        seed=42,
        width=512,
        height=768,
        steps=6,
        cfg=1.5,
        low_cost=True,
    )
    prompt = package["api_prompt"]
    assert "999" not in prompt
    assert prompt["133"]["inputs"]["images"] == ["132", 0]
    assert prompt["141"]["inputs"]["wildcard_text"] == "adult woman, cinematic portrait"
    assert prompt["121"]["inputs"]["text"] == "blur"
    assert prompt["87"]["inputs"] | {"seed": 42, "steps": 6, "cfg": 1.5} == prompt["87"]["inputs"]
    assert prompt["129"]["inputs"] | {"width": 512, "height": 768} == prompt["129"]["inputs"]


def test_anima_profile_preserves_lora_and_rejects_source_tampering(tmp_path) -> None:
    store = WorkflowProfileStore(tmp_path / "profiles")
    store.import_bytes(
        "anima-mansui",
        _raw(_anima_workflow()),
        label="Anima / 满穗",
        filename="anima.json",
    )
    package = store.compile_package(
        "anima-mansui",
        run_id="run-anima-test",
        positive="masterpiece, 1girl, mansui",
        negative="bad hands",
        seed=7,
        width=512,
        height=768,
        steps=5,
        cfg=1.0,
        low_cost=True,
    )
    prompt = package["api_prompt"]
    assert "999" not in prompt
    assert prompt["81"]["inputs"]["images"] == ["148:139", 0]
    assert prompt["182"]["inputs"]["string"] == ""
    assert prompt["184"]["inputs"]["wildcard_text"] == "masterpiece, 1girl, mansui"
    assert prompt["77"]["inputs"]["loras"]["__value__"][0]["name"] == "mansui-anima_v1.1"
    assert prompt["84"]["inputs"]["seed"] == 7
    source = store.root / "anima-mansui" / "source-workflow.json"
    source.write_bytes(source.read_bytes() + b" ")
    with pytest.raises(WorkflowProfileError, match="哈希"):
        store.compile_package("anima-mansui", run_id="run-after-tamper")


def test_random_seed_uses_rgthree_safe_range(tmp_path, monkeypatch) -> None:
    store = WorkflowProfileStore(tmp_path / "profiles")
    store.import_bytes(
        "anima-mansui",
        _raw(_anima_workflow()),
        label="Anima / 满穗",
        filename="anima.json",
    )
    requested_stops = []

    def fake_randbelow(stop: int) -> int:
        requested_stops.append(stop)
        return stop - 1

    monkeypatch.setattr("prompt_hub.workflow_profiles.secrets.randbelow", fake_randbelow)
    package = store.compile_package("anima-mansui", run_id="run-seed-range", seed=-1)
    assert requested_stops == [2**50 + 1]
    assert package["api_prompt"]["84"]["inputs"]["seed"] == 2**50


def test_anima_saver_metadata_matches_effective_sampler_defaults(tmp_path) -> None:
    store = WorkflowProfileStore(tmp_path / "profiles")
    store.import_bytes(
        "anima-mansui",
        _raw(_anima_workflow()),
        label="Anima / 满穗",
        filename="anima.json",
    )
    package = store.compile_package(
        "anima-mansui",
        run_id="run-metadata-sync",
        seed=42,
        low_cost=True,
    )
    saver = package["api_prompt"]["81"]["inputs"]
    assert saver | {"steps": 20, "cfg": 4.0, "width": 1024, "height": 1536} == saver


def test_workflow_api_archives_and_submits_identical_package(settings, tmp_path) -> None:
    mount = tmp_path / "mounted-share"
    mount.mkdir()
    with TestClient(create_app(settings)) as client:
        client.put(
            "/api/remote-nodes/compute-5060ti",
            json={
                "role": "compute_5060ti",
                "host": "192.168.1.10",
                "smb_mount": str(mount),
                "enabled": True,
                "capabilities": ["comfyui_generate"],
            },
        )
        assert client.post("/api/remote-nodes/compute-5060ti/prepare").status_code == 201
        imported = client.post(
            "/api/workflow-profiles/krea2-ares-ocmanager/import",
            params={"label": "Krea 2 / Ares", "filename": "krea.json"},
            content=_raw(_krea_workflow()),
        )
        assert imported.status_code == 201
        project = client.post(
            "/api/creative/projects",
            json={
                "title": "Krea test",
                "target_profile": "krea2",
                "slots": {"character": "an adult woman", "lighting": "soft rim light"},
                "generation": {"steps": 7, "cfg": 1.2, "seed": 123},
            },
        ).json()
        submitted = client.post(
            "/api/workflow-profiles/krea2-ares-ocmanager/tasks",
            json={"project_id": project["project_id"], "low_cost": True},
        )
        assert submitted.status_code == 201, submitted.text
        result = submitted.json()
        local = Path(result["local_package"])
        remote = mount / "prompt-hub" / result["remote_package"]
        assert local.read_bytes() == remote.read_bytes()
        assert result["task"]["status"] == "queued"
        task_file = mount / "prompt-hub" / "outbox" / f"{result['task']['task_id']}.json"
        assert task_file.is_file()
        package = json.loads(local.read_text(encoding="utf-8"))
        assert package["api_prompt"]["87"]["inputs"]["steps"] == 7
        assert (
            package["api_prompt"]["129"]["inputs"]
            | {
                "width": 512,
                "height": 768,
            }
            == package["api_prompt"]["129"]["inputs"]
        )
        image_buffer = BytesIO()
        Image.new("RGB", (32, 48), "purple").save(image_buffer, format="PNG")
        image_raw = image_buffer.getvalue()
        image_relative = f"inbox/{result['task']['task_id']}/result.png"
        image_path = mount / "prompt-hub" / image_relative
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(image_raw)
        task = json.loads(task_file.read_text(encoding="utf-8"))
        returned = {
            "format": "soda-compute-result-v1",
            "protocol_version": "soda-compute-bridge-v2",
            "task_id": result["task"]["task_id"],
            "task_type": "comfyui_generate",
            "status": "completed",
            "source_hashes": task["manifest"],
            "outputs": [
                {
                    "kind": "image",
                    "relative_path": image_relative,
                    "sha256": hashlib.sha256(image_raw).hexdigest(),
                    "size_bytes": len(image_raw),
                }
            ],
        }
        inbox_result = mount / "prompt-hub" / "inbox" / task_file.name
        inbox_result.write_text(json.dumps(returned), encoding="utf-8")
        imported_result = client.post(
            f"/api/workflow-tasks/{result['task']['task_id']}/import-results",
            json={"node_id": "compute-5060ti"},
        )
        assert imported_result.status_code == 200, imported_result.text
        imported = imported_result.json()
        assert imported["image_count"] == 1
        assert imported["associated"] is True
        attached_project = client.get(f"/api/creative/projects/{project['project_id']}").json()
        assert (
            attached_project["generation"]["result_assets"][0]["comfy_import_id"]
            == (imported["results"][0]["result_id"])
        )
        repeated = client.post(
            f"/api/workflow-tasks/{result['task']['task_id']}/import-results",
            json={"node_id": "compute-5060ti"},
        ).json()
        assert repeated["duplicates"] == 1
