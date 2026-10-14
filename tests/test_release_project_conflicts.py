from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub import api
from prompt_hub.api import create_app
from prompt_hub.creative import CreativeStore


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as active:
        yield active


def test_editor_revision_rejects_stale_inputs(client):
    project = client.post("/api/creative/projects", json={"brief_zh": "initial"}).json()
    endpoint = f"/api/creative/projects/{project['project_id']}"
    fresh = client.put(endpoint, json={"brief_zh": "new", "expected_revision": 1})
    assert fresh.status_code == 200
    assert fresh.json()["revision"] == 2
    stale = client.put(endpoint, json={"brief_zh": "old", "expected_revision": 1})
    assert stale.status_code == 409
    assert client.get(endpoint).json()["brief_zh"] == "new"
    # Existing clients without the optional compare-and-swap field remain compatible.
    assert client.put(endpoint, json={"title": "legacy"}).status_code == 200


def test_iteration_apply_detects_change_during_proposal(client, settings, monkeypatch):
    project = client.post("/api/creative/projects", json={}).json()
    store = CreativeStore(settings.database_path)

    def proposal(snapshot):
        store.update_project(snapshot["project_id"], {"slots": {"action": "user action"}})
        return {"slots": {"action": "older suggestion"}, "applied_slots": ["action"]}

    monkeypatch.setattr(api, "apply_iteration_suggestions", proposal)
    response = client.post(f"/api/creative/projects/{project['project_id']}/iteration/apply")
    assert response.status_code == 409
    assert store.get_project(project["project_id"])["slots"]["action"] == "user action"


def test_result_apply_detects_change_during_review(client, settings, monkeypatch):
    project = client.post(
        "/api/creative/projects",
        json={"generation": {"result_assets": [{"asset_id": "image-1"}]}},
    ).json()
    store = CreativeStore(settings.database_path)

    def review(snapshot, _analysis, **_kwargs):
        store.update_project(snapshot["project_id"], {"slots": {"scene": "new scene"}})
        return {"slots": {"scene": "old scene"}}

    monkeypatch.setattr(api, "apply_result_review", review)
    response = client.post(
        f"/api/creative/projects/{project['project_id']}/results/image-1/apply",
        json={"analysis": {}, "fill_empty_slots": True},
    )
    assert response.status_code == 409
    assert store.get_project(project["project_id"])["slots"]["scene"] == "new scene"


@pytest.mark.parametrize(
    "operation", ["iteration/apply", "results/image-1/apply", "results/image-1/branch"]
)
def test_review_operations_reject_already_stale_revision(client, operation):
    project = client.post(
        "/api/creative/projects",
        json={"generation": {"result_assets": [{"asset_id": "image-1"}]}},
    ).json()
    endpoint = f"/api/creative/projects/{project['project_id']}"
    client.put(endpoint, json={"test_notes": "changed"})
    response = client.post(f"{endpoint}/{operation}", json={"analysis": {}, "expected_revision": 1})
    assert response.status_code == 409
    assert len(client.get("/api/creative/projects").json()) == 1


def test_gallery_reference_race_cannot_remove_other_reference(client, settings, monkeypatch):
    raw = BytesIO()
    Image.new("RGB", (32, 32), "red").save(raw, "PNG")
    asset = client.post("/api/gallery/import?filename=qa.png", content=raw.getvalue()).json()
    project = client.post("/api/creative/projects", json={}).json()
    original = CreativeStore.update_project
    raced = False

    def update(store, project_id, values, **kwargs):
        nonlocal raced
        if not raced and "references" in values:
            raced = True
            original(store, project_id, {"references": [{"title": "new reference"}]})
        return original(store, project_id, values, **kwargs)

    monkeypatch.setattr(CreativeStore, "update_project", update)
    response = client.post(
        f"/api/gallery/assets/{asset['asset_id']}/reference/{project['project_id']}",
        json={"purpose": "composition"},
    )
    assert response.status_code == 409
    assert CreativeStore(settings.database_path).get_project(project["project_id"])[
        "references"
    ] == [{"title": "new reference"}]


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://external.example"},
        {"origin": "null"},
        {"origin": "http://testserver:8876"},
        {"origin": "http://testserver:invalid"},
        {"origin": "http://user@testserver"},
        {"origin": "http://testserver/unrelated"},
        {"sec-fetch-site": "cross-site"},
    ],
)
def test_cross_site_browser_cannot_mutate_local_data(client, headers):
    response = client.post("/api/creative/projects", json={"title": "cross-site"}, headers=headers)
    assert response.status_code == 403
    assert client.get("/api/creative/projects").json() == []


@pytest.mark.parametrize(
    "origin", ["http://testserver", "http://testserver:80", "http://TESTSERVER"]
)
def test_same_origin_browser_can_mutate(client, origin):
    assert (
        client.post("/api/creative/projects", json={}, headers={"origin": origin}).status_code
        == 201
    )


def test_stale_upload_is_rejected_before_creating_result_files(client, settings):
    project = client.post("/api/creative/projects", json={}).json()
    endpoint = f"/api/creative/projects/{project['project_id']}"
    client.put(endpoint, json={"brief_zh": "other tab changed"})
    response = client.post(f"{endpoint}/results?expected_revision=1", content=b"invalid image")
    assert response.status_code == 409
    assert client.get(endpoint).json()["generation"].get("result_assets", []) == []
    assert not list((settings.library_root / "results").rglob("*.png"))
