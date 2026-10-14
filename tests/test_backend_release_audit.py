from __future__ import annotations

import os
import stat
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from functools import partial
from http.client import RemoteDisconnected
from io import BytesIO
from threading import Event, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub import comfy_routes, dataset_routes, local_model, model_connections, project_journey
from prompt_hub.api import create_app
from prompt_hub.creative import CreativeStore, compile_prompt, export_project
from prompt_hub.dataset_export import DatasetExportError, create_dataset_export
from prompt_hub.local_model import (
    MAX_MODEL_RESPONSE_BYTES,
    LocalModelError,
    _request_json,
    expand_sourcing_queries,
    organize_slots,
    request_creative_json,
    revise_caption_with_model,
)
from prompt_hub.maintenance import BackupManager, MaintenanceError, verify_backup
from prompt_hub.model_connections import (
    ModelConnectionError,
    ModelConnectionStore,
    _fetch_openai_models,
)
from prompt_hub.remote_nodes import RemoteNodeStore
from prompt_hub.result_media import store_result_image


def _png():
    output = BytesIO()
    Image.new("RGB", (32, 32), "navy").save(output, "PNG")
    return output.getvalue()


@pytest.mark.parametrize("profile", ["anima", "krea2"])
def test_creative_export_and_recipe_keep_target_profile_when_recreated(settings, profile):
    store = CreativeStore(settings.database_path)
    store.initialize()
    original = store.create_project(
        {"target_profile": profile, "slots": {"action": "shielding a flame"}}
    )
    exported = export_project(original)
    recipe = store.save_recipe(original["project_id"], "scene")
    for snapshot in (exported, recipe["snapshot"]):
        restored = store.create_project(snapshot["project"])
        assert restored["target_profile"] == profile
        assert restored["slots"] == original["slots"]
    assert store.get_project(original["project_id"]) == original


@pytest.mark.parametrize("relative", ["private/nested-backup", "exports/backup", "cache/backup"])
def test_backup_rejects_target_inside_library_without_creating_files(settings, relative):
    target = settings.library_root / relative
    with pytest.raises(MaintenanceError, match="资料库内"):
        BackupManager(settings).create(target)
    assert not target.exists()
    assert not list(settings.library_root.rglob(".nested-backup.tmp-*"))


@pytest.mark.parametrize("relative", ["payload/restored", "metadata/restored"])
def test_restore_rejects_nested_destination_and_preserves_backup(settings, tmp_path, relative):
    store = CreativeStore(settings.database_path)
    store.initialize()
    store.create_project({"title": "Keep source intact"})
    backup = tmp_path / "backup"
    manager = BackupManager(settings)
    manager.create(backup)
    before = verify_backup(backup)
    target = backup / relative
    with pytest.raises(MaintenanceError, match="备份目录内"):
        manager.restore_to_new_directory(backup, target)
    assert not target.exists()
    assert verify_backup(backup) == before


def test_concurrent_model_endpoint_saves_preserve_both_records(settings, monkeypatch):
    store = ModelConnectionStore(settings)
    original_list = store.list_endpoints
    first_read = Event()
    second_read = Event()
    count_lock = Lock()
    reads = 0

    def synchronized_list():
        nonlocal reads
        current = original_list()
        with count_lock:
            reads += 1
            first = reads == 1
        if first:
            first_read.set()
            second_read.wait(timeout=0.3)
        else:
            second_read.set()
        return current

    monkeypatch.setattr(store, "list_endpoints", synchronized_list)

    def save(label):
        return store.save_endpoint({"label": label, "base_url": "https://models.example.test/v1"})

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(save, "first")
        assert first_read.wait(timeout=2)
        second = executor.submit(save, "second")
        first.result(timeout=3)
        second.result(timeout=3)
    assert {endpoint.label for endpoint in original_list()} == {"first", "second"}


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are checked on macOS/Linux")
def test_model_connection_temp_is_private_before_any_payload_is_written(settings, monkeypatch):
    store = ModelConnectionStore(settings)
    original_fdopen = model_connections.os.fdopen
    initial_modes = []

    def inspect_descriptor(descriptor, *args, **kwargs):
        initial_modes.append(stat.S_IMODE(os.fstat(descriptor).st_mode))
        assert os.fstat(descriptor).st_size == 0
        return original_fdopen(descriptor, *args, **kwargs)

    monkeypatch.setattr(model_connections.os, "fdopen", inspect_descriptor)
    store.save_endpoint({"label": "private", "base_url": "https://models.example.test/v1"})
    assert initial_modes == [0o600]
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert not list(store.path.parent.glob(".*.tmp"))


@pytest.mark.parametrize("kind", ["loras", "models"])
def test_resource_catalog_pages_cover_626_items_without_duplicates(settings, kind):
    store = RemoteNodeStore(settings.remote_nodes_root)
    store.initialize()
    if kind == "loras":
        store.import_lora_catalog(
            snapshot_id="catalog-626",
            worker_id="compute-test",
            source_manager="local files",
            items=[
                {
                    "lora_id": f"lora-{index}",
                    "name": f"{'ink' if index % 2 else 'paint'} {index}",
                    "relative_path": f"styles/{index}.safetensors",
                    "model_family": "anima",
                }
                for index in range(626)
            ],
        )
        id_field = "lora_id"
    else:
        store.import_model_catalog(
            snapshot_id="catalog-626",
            worker_id="compute-test",
            source_manager="local files",
            items=[
                {
                    "asset_id": f"model-{index}",
                    "name": f"{'ink' if index % 2 else 'paint'} {index}",
                    "relative_path": f"models/{index}.safetensors",
                    "root_id": "checkpoint-root",
                    "asset_type": "checkpoint",
                    "model_family": "anima",
                }
                for index in range(626)
            ],
        )
        id_field = "asset_id"
    with TestClient(create_app(settings)) as client:
        url = f"/api/windows-{kind}"
        first = client.get(url, params={"limit": 500}).json()
        second = client.get(url, params={"limit": 500, "offset": 500}).json()
        exhausted = client.get(url, params={"limit": 500, "offset": 626}).json()
        assert (first["count"], second["count"], exhausted["count"]) == (500, 126, 0)
        assert first["total"] == second["total"] == exhausted["total"] == 626
        assert first["limit"] == second["limit"] == 500
        assert (first["offset"], second["offset"]) == (0, 500)
        assert first["snapshot_id"] == second["snapshot_id"] == "catalog-626"
        all_ids = [item[id_field] for page in (first, second) for item in page["results"]]
        assert len(all_ids) == len(set(all_ids)) == 626
        filtered = client.get(url, params={"query": "ink", "limit": 200, "offset": 200}).json()
        assert filtered["total"] == 313
        assert filtered["count"] == 113
        assert all("ink" in item["name"] for item in filtered["results"])
        assert client.get(url, params={"offset": -1}).status_code == 422


def test_comfy_attach_rejects_generation_changed_during_import(settings, monkeypatch):
    store = CreativeStore(settings.database_path)
    original_store_image = comfy_routes.store_result_image

    def edit_during_import(*args, **kwargs):
        asset = original_store_image(*args, **kwargs)
        store.update_project(
            kwargs["project_id"],
            {"generation": {"width": 1280}, "slots": {"action": "manually revised"}},
        )
        return asset

    monkeypatch.setattr(comfy_routes, "store_result_image", edit_during_import)
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/creative/projects", json={"generation": {"width": 1024}}).json()
        imported = client.post(
            "/api/comfy-results/import?filename=result.png", content=_png()
        ).json()
        result = imported["result"]
        response = client.post(
            f"/api/comfy-results/{result['result_id']}/attach/{project['project_id']}"
        )
        assert response.status_code == 409
        current = store.get_project(project["project_id"])
        assert current["generation"] == {"width": 1280}
        assert current["slots"]["action"] == "manually revised"
        returned = client.get(f"/api/comfy-results/{result['result_id']}").json()
        assert not returned.get("association")


@pytest.mark.parametrize("route_kind", ["attach", "candidate"])
def test_comfy_attach_checks_client_revision_before_copying_image(
    settings, monkeypatch, route_kind
):
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/creative/projects", json={}).json()
        result = client.post(
            "/api/comfy-results/import?filename=result.png", content=_png()
        ).json()["result"]
        current = client.put(
            f"/api/creative/projects/{project['project_id']}",
            json={"slots": {"action": "manual action"}, "slot_locks": {"action": True}},
        ).json()
        copier = Mock()
        monkeypatch.setattr(comfy_routes, "store_result_image", copier)
        response = client.post(
            f"/api/comfy-results/{result['result_id']}/{route_kind}/{project['project_id']}",
            json={"expected_revision": project["revision"]},
        )
        assert response.status_code == 409
        copier.assert_not_called()
        assert client.get(f"/api/creative/projects/{project['project_id']}").json() == current


def test_dataset_export_rejects_stale_scene_before_writing_archive(settings):
    store = CreativeStore(settings.database_path)
    store.initialize()
    project = store.create_project(
        {
            "target_profile": "krea2",
            "slots": {"action": "shielding a flame"},
            "generation": {
                "scene_plan": {
                    "input_fingerprint": "previous-input",
                    "prompt_usable": True,
                    "prompts": {"krea2": "Previous prompt"},
                }
            },
        }
    )
    asset = store_result_image(
        settings,
        project_id=project["project_id"],
        filename="selected.png",
        raw=_png(),
        safety_mode="sfw",
    )
    project["generation"]["result_assets"] = [{**asset, "dataset_selected": True}]
    assert compile_prompt(project, "krea2")["ready"] is False
    with pytest.raises(DatasetExportError, match="过期"):
        create_dataset_export(settings, project=project, profile_id="krea2")
    assert not list(settings.dataset_exports_root.glob("*.zip"))


@pytest.mark.parametrize("body", [b"{}", b"\xff"])
def test_model_json_reads_are_bounded_and_invalid_encoding_is_reported(monkeypatch, body):
    read_sizes = []

    class Response:
        def read(self, size=None):
            read_sizes.append(size)
            return body

    @contextmanager
    def open_response(*_args, **_kwargs):
        yield Response()

    monkeypatch.setattr(local_model, "urlopen", open_response)
    if body == b"{}":
        assert _request_json("http://127.0.0.1:1234/v1/models") == {}
    else:
        with pytest.raises(LocalModelError):
            _request_json("http://127.0.0.1:1234/v1/models")
    assert read_sizes == [MAX_MODEL_RESPONSE_BYTES + 1]


@pytest.mark.parametrize("kind", ["scene", "slots", "sourcing", "caption"])
def test_text_model_helpers_reject_truncated_valid_content(monkeypatch, kind):
    monkeypatch.setattr(
        local_model,
        "_request_json",
        Mock(
            return_value={
                "choices": [{"finish_reason": "max_tokens", "message": {"content": "{}"}}]
            }
        ),
    )
    connection = SimpleNamespace(
        model_name="external", base_url="https://example.test/v1", api_key=""
    )
    connections = Mock()
    connections.get_caption_assist.return_value = connection
    calls = {
        "scene": partial(request_creative_json, model="local", system_prompt="JSON", context={}),
        "slots": partial(
            organize_slots, brief="scene", slots={}, locks={}, model="local", target_profile="anima"
        ),
        "sourcing": partial(
            expand_sourcing_queries, brief="scene", slots={}, locks={}, model="local"
        ),
        "caption": partial(
            revise_caption_with_model, "a woman", "add rain", connections=connections
        ),
    }
    with pytest.raises(LocalModelError, match="截断"):
        calls[kind]()


def test_caption_revision_does_not_follow_redirects_with_credentials(monkeypatch):
    connection = SimpleNamespace(
        model_name="external", base_url="https://example.test/v1", api_key="fake-test-key"
    )
    connections = Mock()
    connections.get_caption_assist.return_value = connection
    request = Mock(return_value={"choices": [{"message": {"content": "a woman in rain"}}]})
    monkeypatch.setattr(local_model, "_request_json", request)
    assert revise_caption_with_model("a woman", "add rain", connections=connections)
    assert request.call_args.kwargs.get("allow_redirects") is False
    assert request.call_args.kwargs.get("response_limit") == MAX_MODEL_RESPONSE_BYTES


def test_model_discovery_disconnect_is_a_domain_error(monkeypatch):
    opener = SimpleNamespace(open=Mock(side_effect=RemoteDisconnected("disconnected")))
    monkeypatch.setattr(model_connections, "build_opener", lambda *_: opener)
    with pytest.raises(ModelConnectionError, match="无法连接"):
        _fetch_openai_models("https://example.test/v1", "")


def _dataset_project(client):
    project = client.post(
        "/api/creative/projects",
        json={"slots": {"character": "1girl"}, "generation": {"seed": 123}},
    ).json()
    project_id = project["project_id"]
    assets = [
        client.post(
            f"/api/creative/projects/{project_id}/results",
            params={"filename": f"{index}.png"},
            content=_png(),
        ).json()["asset"]
        for index in range(2)
    ]
    project = client.put(
        f"/api/creative/projects/{project_id}/results/{assets[0]['asset_id']}/dataset",
        json={"selected": True, "caption_override": "1girl, solo"},
    ).json()["project"]
    return project, assets


def _dataset_request(route_kind, project, asset):
    base = f"/api/creative/projects/{project['project_id']}"
    result = f"{base}/results/{asset['asset_id']}"
    return {
        "dataset": ("PUT", f"{result}/dataset", {"caption_override": "1girl, blue eyes"}),
        "single_tag": ("POST", f"{result}/tag", {"tagger": "model", "model": "test-model"}),
        "batch_tag": ("POST", f"{base}/dataset-tag", {"tagger": "model", "model": "test-model"}),
        "review": ("PUT", f"{result}/tag-review", {"draft_tags": "1girl", "confirm_anima": True}),
        "export": ("POST", f"{base}/dataset-export", {"profile_id": "anima"}),
        "workspace": ("POST", f"{base}/dataset-workspace", {"profile_id": "anima"}),
    }[route_kind]


def _model_tags():
    return {
        "tagger": "model",
        "model": "test-model",
        "provider": "LM Studio",
        "general": [{"tag": "1girl"}],
        "characters": [],
        "rating": {"tag": "unknown"},
        "tag_string": "1girl",
    }


@pytest.mark.parametrize("route_kind", ["dataset", "single_tag", "batch_tag", "review"])
def test_dataset_mutations_preserve_edits_during_generation(settings, monkeypatch, route_kind):
    store = CreativeStore(settings.database_path)
    with TestClient(create_app(settings)) as client:
        project, assets = _dataset_project(client)
        asset = assets[0]
        if route_kind == "review":
            monkeypatch.setattr(
                dataset_routes, "_tag_dataset_asset", lambda *_a, **_k: _model_tags()
            )
            project = client.post(
                f"/api/creative/projects/{project['project_id']}/results/{asset['asset_id']}/tag",
                json={"tagger": "model", "model": "test-model"},
            ).json()["project"]

        concurrent = {}

        def edit_project():
            generation = deepcopy(project["generation"])
            generation["seed"] = 999
            generation["result_assets"][0]["dataset_captions"]["anima"] = "manual caption"
            concurrent.update(
                store.update_project(project["project_id"], {"generation": generation})
            )

        if route_kind in {"single_tag", "batch_tag"}:

            def edit_while_tagging(*_args, **_kwargs):
                edit_project()
                return _model_tags()

            monkeypatch.setattr(dataset_routes, "_tag_dataset_asset", edit_while_tagging)
        else:
            helper_name = "update_dataset_asset" if route_kind == "dataset" else "review_wd14_draft"
            original = getattr(dataset_routes, helper_name)

            def edit_while_preparing(*args, **kwargs):
                edit_project()
                return original(*args, **kwargs)

            monkeypatch.setattr(dataset_routes, helper_name, edit_while_preparing)

        method, url, payload = _dataset_request(route_kind, project, asset)
        response = client.request(method, url, json=payload)
        assert response.status_code == 409
        current = client.get(f"/api/creative/projects/{project['project_id']}").json()
        assert current == concurrent
        assert current["generation"]["seed"] == 999
        assert (
            current["generation"]["result_assets"][0]["dataset_captions"]["anima"]
            == "manual caption"
        )
        assert [item["asset_id"] for item in current["generation"]["result_assets"]] == [
            item["asset_id"] for item in assets
        ]


@pytest.mark.parametrize(
    "route_kind", ["dataset", "single_tag", "batch_tag", "review", "export", "workspace"]
)
def test_dataset_rejects_stale_view_before_preparing_or_model_call(
    settings, monkeypatch, route_kind
):
    with TestClient(create_app(settings)) as client:
        project, assets = _dataset_project(client)
        current = client.put(
            f"/api/creative/projects/{project['project_id']}",
            json={"slots": {"action": "manually changed"}},
        ).json()
        blocked = Mock(side_effect=AssertionError("Stale view must be rejected first"))
        for helper in (
            "update_dataset_asset",
            "_tag_dataset_asset",
            "review_wd14_draft",
            "create_dataset_export",
        ):
            monkeypatch.setattr(dataset_routes, helper, blocked)
        monkeypatch.setattr(project_journey, "sync_project_results", blocked)
        method, url, payload = _dataset_request(route_kind, project, assets[0])
        response = client.request(
            method, url, json={**payload, "expected_revision": project["revision"]}
        )
        assert response.status_code == 409
        blocked.assert_not_called()
        assert client.get(f"/api/creative/projects/{project['project_id']}").json() == current


def test_dataset_batch_writes_once_and_export_does_not_change_revision(settings, monkeypatch):
    monkeypatch.setattr(dataset_routes, "_tag_dataset_asset", lambda *_a, **_k: _model_tags())
    with TestClient(create_app(settings)) as client:
        project, assets = _dataset_project(client)
        base = f"/api/creative/projects/{project['project_id']}"
        project = client.put(
            f"{base}/results/{assets[1]['asset_id']}/dataset",
            json={"selected": True, "expected_revision": project["revision"]},
        ).json()["project"]
        tagged = client.post(
            f"{base}/dataset-tag",
            json={
                "tagger": "model",
                "model": "test-model",
                "expected_revision": project["revision"],
            },
        )
        assert tagged.status_code == 200
        tagged_project = tagged.json()["project"]
        assert tagged.json()["tagged_count"] == 2
        assert tagged_project["revision"] == project["revision"] + 1
        exported = client.post(
            f"{base}/dataset-export",
            json={"profile_id": "anima", "expected_revision": tagged_project["revision"]},
        )
        assert exported.status_code == 200
        assert client.get(base).json() == tagged_project


def test_dataset_workspace_sync_does_not_change_project_revision(settings):
    with TestClient(create_app(settings)) as client:
        project, _assets = _dataset_project(client)
        base = f"/api/creative/projects/{project['project_id']}"
        response = client.post(
            f"{base}/dataset-workspace",
            json={"profile_id": "anima", "expected_revision": project["revision"]},
        )
        assert response.status_code == 202
        assert response.json()["synced"] == 1
        assert client.get(base).json() == project


def test_dataset_workspace_rejects_stale_scene_without_creating_source(settings):
    with TestClient(create_app(settings)) as client:
        project, _assets = _dataset_project(client)
        base = f"/api/creative/projects/{project['project_id']}"
        generation = {
            **project["generation"],
            "scene_plan": {
                "input_fingerprint": "old",
                "prompts": {"anima": "1girl"},
                "prompt_usable": True,
            },
        }
        project = client.put(base, json={"generation": generation}).json()
        response = client.post(
            f"{base}/dataset-workspace",
            json={"profile_id": "anima", "expected_revision": project["revision"]},
        )
        assert response.status_code == 422
        assert "过期" in response.json()["detail"]
        assert not (settings.project_dataset_sources_root / project["project_id"]).exists()
