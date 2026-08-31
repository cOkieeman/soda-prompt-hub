from __future__ import annotations

import json
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.creative import apply_result_review
from prompt_hub.local_model import analyze_result_image
from prompt_hub.result_media import resolve_result_image


def _image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (96, 128), "navy").save(output, "PNG")
    return output.getvalue()


def _project() -> dict[str, object]:
    return {
        "title": "结果图复盘",
        "brief_zh": "银发调查员在图书馆读信",
        "safety_mode": "adult",
        "target_profile": "anima",
        "slots": {"character": "adult investigator", "scene": "old library"},
        "slot_locks": {"character": True},
        "references": [{"source_id": "clio", "title": "Gothic Ink", "slot": "style"}],
        "generation": {"steps": 28, "seed": 123, "result_images": ["old-result.png"]},
        "test_notes": "原始记录",
    }


def _analysis() -> dict[str, object]:
    return {
        "model": "vision-model",
        "summary_zh": "画面主体清楚,服装细节不足。",
        "observed_slots": {
            "character": "silver-haired adult investigator",
            "outfit": "dark military coat",
            "scene": "bright studio",
        },
        "strengths": ["主体清晰"],
        "issues": ["手部不稳定"],
        "improvements": ["加强手部动作描述"],
        "reconstructed_prompts": {
            "anima_positive": "1girl, silver hair",
            "anima_negative": "bad hands",
            "krea2_positive": "An adult investigator reading a letter.",
            "krea2_avoid": "Avoid malformed hands.",
        },
        "safety_warning": "",
    }


def test_apply_result_review_respects_locks_and_existing_slots() -> None:
    result = apply_result_review(_project(), _analysis(), fill_empty_slots=True)
    assert result["slots"]["character"] == "adult investigator"
    assert result["slots"]["outfit"] == "dark military coat"
    assert result["slots"]["scene"] == "old library"
    assert "原始记录" in result["test_notes"]
    assert "手部不稳定" in result["test_notes"]


def test_result_upload_media_analyze_and_apply(settings, monkeypatch) -> None:
    captured = {}

    def fake_analyze_result_image(**kwargs):
        captured.update(kwargs)
        return _analysis()

    monkeypatch.setattr("prompt_hub.api.analyze_result_image", fake_analyze_result_image)
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/creative/projects", json=_project()).json()
        project_id = project["project_id"]
        upload = client.post(
            f"/api/creative/projects/{project_id}/results",
            params={"filename": "sample.png"},
            content=_image_bytes(),
            headers={"Content-Type": "image/png"},
        )
        assert upload.status_code == 201
        asset = upload.json()["asset"]
        assert asset["width"] == 96
        assert client.get(asset["thumbnail_url"]).headers["content-type"] == "image/webp"
        assert client.get(asset["original_url"]).headers["content-type"] == "image/png"

        analyzed = client.post(
            f"/api/creative/projects/{project_id}/results/{asset['asset_id']}/analyze",
            json={"model": "vision-model"},
        )
        assert analyzed.status_code == 200
        assert captured["image_path"].is_file()
        assert analyzed.json()["issues"] == ["手部不稳定"]

        branched = client.post(
            f"/api/creative/projects/{project_id}/results/{asset['asset_id']}/branch",
            json={"analysis": analyzed.json()},
        )
        assert branched.status_code == 201
        next_project = branched.json()
        assert next_project["title"] == "结果图复盘 · V2"
        assert next_project["lineage"]["iteration"] == 2
        assert next_project["lineage"]["parent_project_id"] == project_id
        assert next_project["lineage"]["source_asset_id"] == asset["asset_id"]
        assert next_project["lineage"]["review"]["observed_slots"]["outfit"] == (
            "dark military coat"
        )
        assert next_project["generation"]["steps"] == 28
        assert next_project["generation"]["seed"] == 123
        assert next_project["generation"]["result_images"] == []
        assert "result_assets" not in next_project["generation"]
        assert next_project["slots"] == project["slots"]
        assert next_project["slot_locks"] == project["slot_locks"]
        assert next_project["references"] == project["references"]
        assert "加强手部动作描述" in next_project["test_notes"]
        exported_branch = client.get(
            f"/api/creative/projects/{next_project['project_id']}/export"
        ).json()
        assert exported_branch["project"]["lineage"]["iteration"] == 2
        assert client.get(asset["original_url"]).status_code == 200

        applied = client.post(
            f"/api/creative/projects/{project_id}/results/{asset['asset_id']}/apply",
            json={"analysis": analyzed.json(), "fill_empty_slots": True},
        )
        assert applied.status_code == 200
        updated = applied.json()
        assert updated["slots"]["character"] == "adult investigator"
        assert updated["slots"]["outfit"] == "dark military coat"
        assert updated["slots"]["scene"] == "old library"
        assert "手部不稳定" in updated["test_notes"]
        assert (
            client.post(
                f"/api/creative/projects/{project_id}/results/missing/branch",
                json={"analysis": analyzed.json()},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/creative/projects/missing/results/missing/branch",
                json={"analysis": analyzed.json()},
            ).status_code
            == 404
        )


def test_iteration_context_and_apply_api(settings) -> None:
    with TestClient(create_app(settings)) as client:
        parent = client.post("/api/creative/projects", json=_project()).json()
        child_values = {
            **_project(),
            "title": "结果图复盘 · V2",
            "slots": {"character": "adult investigator", "scene": "old library"},
            "lineage": {
                "iteration": 2,
                "parent_iteration": 1,
                "parent_project_id": parent["project_id"],
                "review": _analysis(),
            },
        }
        child = client.post("/api/creative/projects", json=child_values).json()
        url = f"/api/creative/projects/{child['project_id']}/iteration"
        context = client.get(url)
        assert context.status_code == 200
        assert context.json()["parent_available"] is True
        assert context.json()["applicable_slots"] == ["outfit"]

        applied = client.post(url + "/apply")
        assert applied.status_code == 200
        assert applied.json()["applied_slots"] == ["outfit"]
        assert applied.json()["project"]["slots"]["outfit"] == "dark military coat"
        assert applied.json()["project"]["slots"]["character"] == "adult investigator"
        assert client.post(url + "/apply").json()["applied_slots"] == []
        assert client.get("/api/creative/projects/missing/iteration").status_code == 404
        assert client.post("/api/creative/projects/missing/iteration/apply").status_code == 404


def test_result_upload_rejects_invalid_media_and_paths(settings) -> None:
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/creative/projects", json=_project()).json()
        project_id = project["project_id"]
        response = client.post(
            f"/api/creative/projects/{project_id}/results",
            params={"filename": "fake.png"},
            content=b"not-an-image",
        )
        assert response.status_code == 422
        assert client.get(f"/result-media/{project_id}/original/missing").status_code == 404
    assert (
        resolve_result_image(
            settings,
            project_id="../outside",
            variant="original",
            stored_name="image.png",
        )
        is None
    )


def test_local_vision_analysis_normalizes_response(tmp_path, monkeypatch) -> None:
    image_path = tmp_path / "result.png"
    Image.new("RGB", (64, 64), "white").save(image_path)
    captured = {}

    def fake_request(_url, **kwargs):
        captured.update(kwargs)
        return {
            "output": [{"type": "message", "content": json.dumps(_analysis(), ensure_ascii=False)}]
        }

    monkeypatch.setattr("prompt_hub.local_model._request_json", fake_request)
    result = analyze_result_image(
        image_path=image_path,
        project=_project(),
        model="vision-model",
    )
    image_url = captured["payload"]["input"][0]["data_url"]
    assert image_url.startswith("data:image/jpeg;base64,")
    assert captured["payload"]["input"][1]["type"] == "text"
    assert captured["payload"]["reasoning"] == "off"
    assert captured["payload"]["store"] is False
    assert result["observed_slots"]["outfit"] == "dark military coat"
    assert result["reconstructed_prompts"]["anima_negative"] == "bad hands"
