from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobRunner
from prompt_hub.studio_store import StudioError, normalize_recipe
from prompt_hub.studio_wildcard_v2_tags import route_tagged_template
from prompt_hub.studio_workflows import compile_graph

LAYOUT_POOL = "__moss_lora_v2/anima/slots/layout_design__"
OUTFIT_POOL = "__moss_lora_v2/anima/slots/outfit__"


@pytest.fixture
def tagged_comfy_root(tmp_path):
    pool_directory = (
        tmp_path
        / "ComfyUI"
        / "custom_nodes"
        / "ComfyUI-Impact-Pack"
        / "wildcards"
        / "moss_lora_v2"
        / "anima"
        / "slots"
    )
    pool_directory.mkdir(parents=True)
    (pool_directory / "layout_design.txt").write_text(
        "# [style:magazine_cover][line:clean]\nLayout A\n"
        "# [style:magazine_cover][line:clean]\nLayout B {left|right}\n"
        "# [style:magazine_cover][line:rough]\nExcluded rough layout\n"
        "# [style:poster][line:clean]\nExcluded poster layout\n"
        "Untagged layout\n",
        encoding="utf-8-sig",
    )
    (pool_directory / "outfit.txt").write_text(
        "# [clothing:couture]\nCouture outfit\n# [clothing:casual]\nExcluded casual outfit\n",
        encoding="utf-8",
    )
    return tmp_path


def test_v2_tag_route_filters_before_impact_and_strips_model_metadata(
    settings, monkeypatch, tagged_comfy_root
):
    requests = []
    sent_to_model = "  Selected layout and Couture outfit\n"

    class Connection:
        def __init__(self, host, port, *, timeout):
            assert (host, port, timeout) == ("127.0.0.1", 8190, 20)

        def request(self, method, path, *, body, headers):
            self.method = method
            if method == "POST":
                assert path == "/impact/wildcards"
                assert headers == {"Content-Type": "application/json"}
                request = json.loads(body)
                assert "[" not in request["text"]
                assert "]" not in request["text"]
                requests.append(request)
            else:
                assert (method, path) == ("GET", "/impact/wildcards/list")

        def getresponse(self):
            if self.method == "GET":
                data = {"data": [LAYOUT_POOL, OUTFIT_POOL]}
            elif len(requests) == 1:
                data = {"text": "1\n0"}
            else:
                data = {"text": "[style:magazine_cover]" + sent_to_model}
            stream = io.BytesIO(json.dumps(data).encode())
            stream.status = 200
            return stream

        def close(self):
            pass

    monkeypatch.setattr("prompt_hub.studio_prompts.HTTPConnection", Connection)
    monkeypatch.setattr(BackgroundJobRunner, "start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        assert client.put(
            "/api/studio/settings", json={"comfy_root": str(tagged_comfy_root)}
        ).is_success
        catalogue = client.get("/api/studio/wildcard-v2/pools").json()["tags_by_pool"]
        assert catalogue == {
            LAYOUT_POOL: {"style": ["magazine_cover", "poster"], "line": ["clean", "rough"]},
            OUTFIT_POOL: {"clothing": ["casual", "couture"]},
        }

        project = client.post("/api/studio/projects", json={"title": "tagged", "target": "anima"})
        base = f"/api/studio/projects/{project.json()['project_id']}"
        save = client.put(
            base,
            json={
                "studio": {
                    "text_seed": 31,
                    "wildcard_v2": {
                        "enabled": True,
                        "family": "anima",
                        "layout": "independent",
                        "scene_preset": "design",
                        "style_mode": "fixed",
                        "style": "[line:metadata] style trigger",
                        "tag_filters": {
                            "style": ["MAGAZINE_COVER"],
                            "line": ["clean"],
                            "clothing": ["couture"],
                        },
                    },
                },
            },
        )
        assert save.is_success, save.text
        preview = client.post(f"{base}/preview", json={})
        assert preview.is_success, preview.text
        assert preview.json()["rows"][0]["positive"] == sent_to_model

    assert len(requests) == 2
    assert requests[0] == {"text": "{0|1}\n0", "seed": 31}
    final = requests[-1]
    assert final["seed"] == 31
    assert final["text"].startswith("Layout B {left|right},")
    assert "style trigger" in final["text"]
    assert "Couture outfit" in final["text"]
    assert LAYOUT_POOL not in final["text"]
    assert OUTFIT_POOL not in final["text"]
    assert "Excluded" not in final["text"]
    assert "metadata" not in final["text"]
    assert "__moss_lora_v2/anima/slots/scene_light_design__" in final["text"]


@pytest.mark.parametrize(
    ("filters", "message"),
    [
        ({"style": ["unknown"]}, "沒有符合所選標籤的詞條"),
        ({"clothing": ["couture"]}, "目前詞池沒有以下標籤分類 clothing"),
        ({"style": ["poster"], "line": ["rough"]}, "沒有符合所選標籤的詞條"),
    ],
)
def test_v2_unmatched_filters_fail_before_impact(tagged_comfy_root, filters, message):
    def unexpected_draw(*_args):
        pytest.fail("No Impact request should run for unmatched filters")

    with pytest.raises(StudioError, match=message):
        route_tagged_template(
            LAYOUT_POOL,
            filters,
            comfy_root=str(tagged_comfy_root),
            seed=1,
            expand=unexpected_draw,
        )


def test_v2_style_preset_uses_saved_workflow_style(settings, monkeypatch):
    monkeypatch.setattr("prompt_hub.studio_prompts._expand_v2", lambda text, _seed: text)
    monkeypatch.setattr(BackgroundJobRunner, "start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/studio/projects", json={"title": "style", "target": "anima"})
        base = f"/api/studio/projects/{project.json()['project_id']}"
        workflow = client.post(
            "/api/studio/workflows?target=anima",
            json={
                "1": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "original workflow style trigger"},
                    "_meta": {"title": "Style Prefix"},
                },
            },
        )
        recipe = {
            "workflow_id": workflow.json()["profile_id"],
            "wildcard_v2": {"enabled": True, "layout": "independent", "style_mode": "preset"},
        }
        assert client.put(base, json={"studio": recipe}).is_success
        response = client.post(f"{base}/preview", json={})
        assert response.is_success
        assert response.json()["rows"][0]["positive"].startswith(
            f"{LAYOUT_POOL}, original workflow style trigger, "
        )
        recipe["wildcard_v2"]["style_mode"] = "none"
        assert client.put(base, json={"studio": recipe}).is_success
        response = client.post(f"{base}/preview", json={})
        assert response.is_success
        assert "original workflow style trigger" not in response.json()["rows"][0]["positive"]


def test_v2_compile_strips_brackets_from_preexisting_queued_prompts():
    graph = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "2": {"class_type": "KSampler", "inputs": {"positive": ["1", 0]}},
    }
    recipe = normalize_recipe({"wildcard_v2": {"enabled": True}})
    expanded = {"positive": "[style:cover]portrait with [rim light]"}
    compiled = compile_graph(graph, recipe, expanded)
    assert compiled["1"]["inputs"]["text"] == "portrait with rim light"
