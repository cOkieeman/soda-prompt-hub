from __future__ import annotations

import io
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobRunner, BackgroundJobStore
from prompt_hub.studio_prompts import prepare_batch
from prompt_hub.studio_store import StudioError, normalize_recipe
from prompt_hub.studio_workflows import compile_graph

V2_OPTIONS = {
    "enabled": True,
    "family": "anima",
    "character_mode": "fixed",
    "character": "固定角色[甲]",
    "style_mode": "fixed",
    "style": "@fixture_style",
}
ANIMA_NEGATIVE = (
    "lowres, blurry, bad anatomy, extra fingers, extra limbs, deformed, watermark, "
    "signature, text, logo, loli, child, kid"
)
MOSS_NEGATIVE = (
    "worst quality, low quality, blurry, jpeg artifacts, overexposed, blown-out highlights, "
    "blinding glare, harsh white specular patches, washed out, bad anatomy, bad hands, "
    "deformed hands, fused fingers, extra fingers, missing fingers, extra limbs, deformed, "
    "text, watermark, signature"
)
SAMPLING_FIELDS = ("width", "height", "steps", "cfg", "negative")
WHOLE_PROMPT_POOLS = (
    "__moss_lora_v2/world/scenery__",
    "__moss_lora_v2/world/creature__",
    "__moss_lora_v2/world/still_life__",
    "__moss_lora_v2/all__",
    "__moss_lora_v2/anima/editorial_design__",
    "__moss_lora_v2/anima/editorial_world__",
    "__moss_lora_v2/nl/editorial_design__",
    "__moss_lora_v2/nl/editorial_world__",
)


def test_v2_batch_enqueues_unmodified_impact_results(settings, monkeypatch):
    requests = []
    returned = []

    class Connection:
        def __init__(self, host, port, *, timeout):
            assert (host, port, timeout) == ("127.0.0.1", 8190, 20)

        def request(self, method, path, *, body, headers):
            assert (method, path, headers) == (
                "POST",
                "/impact/wildcards",
                {"Content-Type": "application/json"},
            )
            requests.append(json.loads(body))

        def getresponse(self):
            raw = f"  固定角色甲 @fixture_style 主題{requests[-1]['seed']}\n"
            returned.append(raw)
            stream = io.BytesIO(json.dumps({"text": raw}).encode())
            stream.status = 200
            return stream

        def close(self):
            pass

    monkeypatch.setattr("prompt_hub.studio_prompts.HTTPConnection", Connection)
    monkeypatch.setattr(BackgroundJobRunner, "start", lambda _self: None)
    original_graph = {
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "舊正文"}},
        "8": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "舊負詞"},
            "_meta": {"title": "負面"},
        },
        "10": {
            "class_type": "KSampler",
            "inputs": {"positive": ["7", 0], "negative": ["8", 0], "seed": 10},
        },
        "12": {"class_type": "SaveImage", "inputs": {"images": ["10", 0]}},
    }
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/studio/projects", json={"title": "測試", "target": "anima"})
        base = f"/api/studio/projects/{project.json()['project_id']}"
        workflow = client.post("/api/studio/workflows?target=anima", json=original_graph)
        settings_saved = client.put(
            base,
            json={
                "studio": {
                    "workflow_id": workflow.json()["profile_id"],
                    "wildcard_v2": V2_OPTIONS,
                    "prefix": "舊前綴",
                    "body": "舊正文",
                    "negative": "此次負詞",
                    "suffix": "舊後綴",
                    "locks": {"body": True},
                    "locked_values": {"body": "舊鎖定"},
                    "overrides": {"7::text": "舊欄位覆寫"},
                    "batch_mode": "same_text",
                    "text_seed_mode": "fixed",
                    "text_seed": 42,
                    "seed_mode": "fixed",
                    "seed": 901,
                    "count": 3,
                },
            },
        )
        assert settings_saved.status_code == 200
        saved_options = settings_saved.json()["studio"]["wildcard_v2"]
        assert {key: saved_options[key] for key in V2_OPTIONS} == V2_OPTIONS
        assert saved_options["layout"] == "bundled"
        assert saved_options["lighting_mode"] == "random"
        preview = client.post(f"{base}/preview", json={})
        assert preview.status_code == 200
        assert [entry["seed"] for entry in requests] == [42, 43, 44]
        templates = {entry["text"] for entry in requests}
        assert len(templates) == 1
        template = templates.pop()
        assert "固定角色甲" in template
        assert "[" not in template
        assert "]" not in template
        assert "@fixture_style" in template
        assert "__moss_lora_v2/anima/slots/theme_sfw__" in template
        assert "__moss_lora_v2/anima/slots/lighting__" in template
        assert "random_girl" not in template
        assert "舊" not in template
        assert [row["positive"] for row in preview.json()["rows"]] == returned

        queue = client.post(f"{base}/generate", json={"preview_id": preview.json()["preview_id"]})
        assert queue.status_code == 202
        jobs = BackgroundJobStore(settings.database_path)
        for raw, identifier in zip(returned, queue.json()["job_ids"], strict=True):
            job = jobs.get(identifier)["payload"]
            assert job["prompt"]["positive"] == raw
            graph = compile_graph(original_graph, job["recipe"], job["prompt"])
            assert graph["7"]["inputs"]["text"] == raw
            assert graph["8"]["inputs"]["text"] == "此次負詞"
            assert graph["10"]["inputs"]["seed"] == 901
        assert len(requests) == 3


def test_v2_bypasses_workflow_composition_for_pipe_sampler():
    graph = {
        "1": {"class_type": "String Literal", "inputs": {"string": "舊正向"}},
        "2": {"class_type": "PCLazyTextEncode", "inputs": {"text": ["1", 0]}},
        "3": {"class_type": "Any Switch (rgthree)", "inputs": {"any_02": ["2", 0]}},
        "4": {
            "class_type": "ToBasicPipe",
            "inputs": {"positive": ["3", 0], "negative": ["6", 0]},
        },
        "5": {"class_type": "ImpactKSamplerBasicPipe", "inputs": {"basic_pipe": ["4", 0]}},
        "6": {"class_type": "PCLazyTextEncode", "inputs": {"text": "舊負向"}},
    }
    recipe = normalize_recipe({"wildcard_v2": V2_OPTIONS})
    raw = "  Impact 回傳原文\n"
    prompt = {"prefix": "", "body": raw, "suffix": "", "positive": raw}
    result = compile_graph(graph, recipe, prompt)
    assert result["2"]["inputs"]["text"] == raw
    assert result["6"]["inputs"]["text"] == ANIMA_NEGATIVE
    assert graph["2"]["inputs"]["text"] == ["1", 0]
    with pytest.raises(StudioError, match="ToBasicPipe"):
        compile_graph({"5": graph["5"]}, recipe, prompt)


@pytest.mark.parametrize(
    ("recipe_fields", "slots", "message"),
    [
        ({"comfy_url": "https://example.com"}, {}, "需要本機 ComfyUI"),
        ({}, {"character": ""}, "請填寫固定角色"),
        ({}, {"style": "{甲|乙}"}, "固定畫風需要直接填寫文字"),
    ],
)
def test_v2_rejects_invalid_fixed_slots_before_expansion(recipe_fields, slots, message):
    recipe = normalize_recipe({**recipe_fields, "wildcard_v2": {**V2_OPTIONS, **slots}})
    with pytest.raises(StudioError, match=message):
        prepare_batch(None, recipe, {})


@pytest.mark.parametrize(
    ("family", "namespace"),
    [("anima", "anima"), ("moss", "nl"), ("krea2", "nl")],
)
@pytest.mark.parametrize(
    ("preset", "layout_scene_pair"),
    [
        ("design", ("layout_design", "scene_light_design")),
        ("world", ("layout_camera", "scene_light_world")),
    ],
)
def test_v2_independent_template_uses_paired_native_slots_in_order(
    monkeypatch, family, namespace, preset, layout_scene_pair
):
    calls = []

    def expand(text, seed):
        calls.append((text, seed))
        return f"  選詞 {seed}\n"

    monkeypatch.setattr("prompt_hub.studio_prompts._expand_v2", expand)
    recipe = normalize_recipe(
        {
            "count": 2,
            "text_seed": 20,
            "wildcard_v2": {
                "enabled": True,
                "family": family,
                "layout": "independent",
                "scene_preset": preset,
                "style_mode": "fixed",
                "style": "@fixture_style",
            },
        }
    )
    rows = prepare_batch(None, recipe, {})
    assert [seed for _, seed in calls] == [20, 21]
    assert calls[0][0] == calls[1][0]
    text = calls[0][0]
    head = f"__moss_lora_v2/{namespace}/slots/"
    layout_name, scene_name = layout_scene_pair
    layout = f"{head}{layout_name}__"
    assert text.startswith(layout)
    expected = [
        layout,
        "@fixture_style",
        *(f"{head}{slot}__" for slot in ("hair", "eyes_expr", "outfit", "action", scene_name)),
    ]
    positions = [text.index(value) for value in expected]
    assert positions == sorted(positions)
    assert "__soda/" not in text
    assert f"{head}lighting__" not in text
    assert "theme_sfw" not in text
    assert [row["positive"] for row in rows] == ["  選詞 20\n", "  選詞 21\n"]


def test_v2_independent_supports_fully_fixed_slots_and_explicit_pools(monkeypatch):
    monkeypatch.setattr("prompt_hub.studio_prompts._expand_v2", lambda text, _seed: text)
    fixed = {
        "layout_text": "版式[甲]",
        "style": "畫風[乙]",
        "character": "角色[甲]",
        "outfit": "服裝[丙]",
        "action": "動作[丁]",
        "scene_light": "場景[戊]\n第二行",
    }
    options = {
        "enabled": True,
        "family": "anima",
        "layout": "independent",
        **fixed,
        **{f"{slot}_mode": "fixed" for slot in fixed if slot != "layout_text"},
        "layout_mode": "fixed",
    }
    recipe = normalize_recipe({"wildcard_v2": options})
    text = prepare_batch(None, recipe, {})[0]["positive"]
    positions = [text.index(value.replace("[", "").replace("]", "")) for value in fixed.values()]
    assert positions[0] == 0
    assert positions == sorted(positions)
    assert "[" not in text
    assert "]" not in text
    assert "__" not in text
    options.update(
        layout_mode="random",
        layout_pool="__moss_lora_v2/anima/slots/layout_camera__",
        scene_light_mode="random",
        scene_light_pool="__moss_lora_v2/anima/slots/scene_light_world__",
    )
    recipe = normalize_recipe({"wildcard_v2": options})
    text = prepare_batch(None, recipe, {})[0]["positive"]
    assert text.startswith("__moss_lora_v2/anima/slots/layout_camera__")
    assert "__moss_lora_v2/anima/slots/scene_light_world__" in text
    assert "__moss_lora_v2/anima/slots/lighting__" not in text
    assert "場景戊" not in text


@pytest.mark.parametrize(
    ("old_lighting", "mode", "ending"),
    [
        ({"lighting_mode": "random"}, "none", "舊場景"),
        ({"lighting_mode": "fixed", "lighting": "舊測試光線"}, "fixed", "舊測試光線"),
        (
            {"lighting_mode": "random", "lighting_pool": "__soda/tags/custom_light__"},
            "random",
            "__soda/tags/custom_light__",
        ),
    ],
)
def test_v2_test_light_replaces_scene_light_and_old_choices_can_be_restored(
    monkeypatch, old_lighting, mode, ending
):
    monkeypatch.setattr("prompt_hub.studio_prompts._expand_v2", lambda text, _seed: text)
    recipe = normalize_recipe(
        {
            "wildcard_v2": {
                "enabled": True,
                "layout": "independent",
                "scene_mode": "fixed",
                "scene": "舊場景",
                **old_lighting,
            },
        },
    )
    options = recipe["wildcard_v2"]
    assert options["scene_light"] == "舊場景"
    assert options["test_lighting_mode"] == mode
    text = prepare_batch(None, recipe, {})[0]["positive"]
    assert text.endswith(ending)
    if mode != "none":
        assert "舊場景" not in text

    options["test_lighting_mode"] = "random"
    options["test_lighting_pool"] = ""
    text = prepare_batch(None, recipe, {})[0]["positive"]
    assert text.endswith("__moss_lora_v2/anima/slots/lighting__")
    assert "舊場景" not in text

    options["test_lighting_mode"] = "none"
    restored = normalize_recipe(recipe)
    text = prepare_batch(None, restored, {})[0]["positive"]
    assert text.endswith("舊場景")
    assert "__moss_lora_v2/anima/slots/lighting__" not in text


def test_v2_style_preset_uses_bound_workflow_style_and_none_omits_slots(settings, monkeypatch):
    monkeypatch.setattr("prompt_hub.studio_prompts._expand_v2", lambda text, _seed: text)
    monkeypatch.setattr(BackgroundJobRunner, "start", lambda _self: None)
    graph = {
        "5": {"class_type": "String Literal", "inputs": {"string": "@bound_style"}},
        "6": {"class_type": "String Literal", "inputs": {"string": "@bound_prefix"}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "旧正文"}},
        "8": {"class_type": "KSampler", "inputs": {"positive": ["7", 0]}},
    }
    with TestClient(create_app(settings)) as client:
        workflow = client.post("/api/studio/workflows?target=anima", json=graph).json()
        project = client.post("/api/studio/projects", json={"target": "anima"}).json()
        base = f"/api/studio/projects/{project['project_id']}"
        options = {
            "enabled": True,
            "layout": "independent",
            "layout_mode": "none",
            "character_mode": "none",
            "outfit_mode": "none",
            "action_mode": "none",
            "scene_light_mode": "none",
            "style_mode": "preset",
        }
        recipe = {
            "workflow_id": workflow["profile_id"],
            "bindings": {"style": ["5::string"], "prefix": ["6::string"], "body": ["7::text"]},
            "wildcard_v2": options,
        }
        saved = client.put(base, json={"studio": recipe})
        assert saved.status_code == 200
        preview = client.post(f"{base}/preview", json={})
        assert preview.status_code == 200
        prompt = preview.json()["rows"][0]["positive"]
        assert prompt.startswith("@bound_style,")
        assert "@bound_prefix" not in prompt
        assert "旧正文" not in prompt
        assert "__" not in prompt
        options["style_mode"] = "none"
        saved = client.put(base, json={"studio": recipe})
        assert saved.status_code == 200
        preview = client.post(f"{base}/preview", json={})
        assert preview.status_code == 200
        prompt = preview.json()["rows"][0]["positive"]
        assert "@bound_style" not in prompt
        assert "__" not in prompt


def test_v2_bundled_keeps_native_alias_or_uses_explicit_character_and_lighting(monkeypatch):
    monkeypatch.setattr("prompt_hub.studio_prompts._expand_v2", lambda text, _seed: text)
    recipe = normalize_recipe({"wildcard_v2": {"enabled": True}})
    text = prepare_batch(None, recipe, {})[0]["positive"]
    assert "__moss_lora_v2/anima/random_girl__" in text
    recipe = normalize_recipe(
        {
            "wildcard_v2": {
                "enabled": True,
                "character_pool": "__soda/tags/character__",
                "lighting_mode": "fixed",
                "lighting": "光線[固定]",
                "outfit_mode": "fixed",
            },
        }
    )
    text = prepare_batch(None, recipe, {})[0]["positive"]
    assert "__soda/tags/character__" in text
    assert "__moss_lora_v2/anima/slots/theme_sfw__" in text
    assert "光線固定" in text
    assert "random_girl" not in text


def test_v2_legacy_style_pool_migrates_but_can_be_cleared(monkeypatch):
    monkeypatch.setattr("prompt_hub.studio_prompts._expand_v2", lambda text, _seed: text)
    legacy = {**V2_OPTIONS, "style_mode": "wildcard", "style": "__soda/tags/style__"}
    recipe = normalize_recipe({"wildcard_v2": legacy})
    assert recipe["wildcard_v2"]["style_pool"] == "__soda/tags/style__"
    assert "__soda/tags/style__" in prepare_batch(None, recipe, {})[0]["positive"]

    cleared = normalize_recipe({"wildcard_v2": {**legacy, "style_pool": ""}})
    with pytest.raises(StudioError, match="請選擇畫風詞池"):
        prepare_batch(None, cleared, {})


def test_v2_pool_picker_lists_valid_refs_from_local_impact(settings, monkeypatch):
    class Connection:
        def __init__(self, host, port, *, timeout):
            assert (host, port, timeout) == ("127.0.0.1", 8190, 20)

        def request(self, method, path, *, body, headers):
            assert (method, path, body, headers) == ("GET", "/impact/wildcards/list", None, {})

        def getresponse(self):
            stream = io.BytesIO(
                json.dumps(
                    {"data": ["__z__", "__a/b__", "__z__", "bad", 5, *WHOLE_PROMPT_POOLS]}
                ).encode(),
            )
            stream.status = 200
            return stream

        def close(self):
            pass

    monkeypatch.setattr("prompt_hub.studio_prompts.HTTPConnection", Connection)
    monkeypatch.setattr(BackgroundJobRunner, "start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/studio/wildcard-v2/pools")
    assert response.status_code == 200
    assert response.json() == {
        "pools": sorted(["__a/b__", "__z__", *WHOLE_PROMPT_POOLS]),
        "scene_pools": ["__a/b__", "__z__"],
        "tags_by_pool": {},
    }


def sampling_values(recipe):
    return tuple(recipe[key] for key in SAMPLING_FIELDS)


@pytest.mark.parametrize(
    ("family", "expected"),
    [
        ("anima", (1024, 1536, 12, 1.0, ANIMA_NEGATIVE)),
        ("moss", (832, 1216, 25, 2.5, MOSS_NEGATIVE)),
        ("krea2", (832, 1216, 10, 1.0, "")),
    ],
)
def test_v2_uses_family_sampling_defaults(settings, monkeypatch, family, expected):
    monkeypatch.setattr(BackgroundJobRunner, "start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        bootstrap = client.get("/api/studio/bootstrap").json()
    assert sampling_values(bootstrap["wildcard_v2_sampling_presets"][family]) == expected
    namespace = "anima" if family == "anima" else "nl"
    slot_root = f"__moss_lora_v2/{namespace}/slots/"
    pools = bootstrap["wildcard_v2_default_pools"][family]
    assert pools["design"]["layout"] == [f"{slot_root}layout_design__"]
    assert pools["design"]["scene_light"] == [f"{slot_root}scene_light_design__"]
    assert pools["world"]["layout"] == [f"{slot_root}layout_camera__"]
    assert pools["world"]["scene_light"] == [f"{slot_root}scene_light_world__"]
    assert pools["world"]["test_lighting"] == [f"{slot_root}lighting__"]
    assert pools["bundled"]["theme"] == [f"{slot_root}theme_sfw__"]
    recipe = normalize_recipe({"wildcard_v2": {"enabled": True, "family": family}})
    assert sampling_values(recipe) == expected
    assert recipe["wildcard_v2"]["layout"] == "bundled"
    assert recipe["wildcard_v2"]["scene_preset"] == "design"
    assert recipe["wildcard_v2"]["character_mode"] == "random"
    assert recipe["wildcard_v2"]["test_lighting_mode"] == "none"


def test_v2_saves_preset_transitions_and_preserves_later_manual_edits(settings, monkeypatch):
    monkeypatch.setattr(BackgroundJobRunner, "start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/studio/projects", json={"target": "anima"}).json()
        base = f"/api/studio/projects/{project['project_id']}"
        recipe = project["studio"]
        recipe["wildcard_v2"] = {"enabled": True, "family": "anima"}
        enabled = client.put(base, json={"studio": recipe})
        assert enabled.status_code == 200
        recipe = enabled.json()["studio"]
        assert sampling_values(recipe) == (1024, 1536, 12, 1.0, ANIMA_NEGATIVE)

        recipe.update(width=896, height=1344, steps=16, cfg=1.5, negative="")
        edited = client.put(base, json={"studio": recipe})
        assert edited.status_code == 200
        recipe = client.get(base).json()["project"]["studio"]
        assert sampling_values(recipe) == (896, 1344, 16, 1.5, "")

        recipe["wildcard_v2"]["family"] = "moss"
        switched = client.put(base, json={"studio": recipe})
        assert switched.status_code == 200
        recipe = switched.json()["studio"]
        assert sampling_values(recipe) == (832, 1216, 25, 2.5, MOSS_NEGATIVE)

        recipe["wildcard_v2"]["family"] = "krea2"
        switched = client.put(base, json={"studio": recipe})
        assert switched.status_code == 200
        assert sampling_values(switched.json()["studio"]) == (832, 1216, 10, 1.0, "")


@pytest.mark.parametrize(("width", "height"), [(512, 768), (832, 1216)])
def test_v2_legacy_anima_sampling_defaults_migrate(width, height):
    recipe = normalize_recipe(
        {
            "width": width,
            "height": height,
            "steps": 25,
            "cfg": 4.0,
            "negative": "",
            "wildcard_v2": {"enabled": True, "family": "anima"},
        }
    )
    assert sampling_values(recipe) == (1024, 1536, 12, 1.0, ANIMA_NEGATIVE)


@pytest.mark.parametrize("layout", ["bundled", "independent"])
def test_v2_generic_fixed_character_keeps_native_hair_and_eyes(monkeypatch, layout):
    monkeypatch.setattr("prompt_hub.studio_prompts._expand_v2", lambda text, _seed: text)
    recipe = normalize_recipe(
        {
            "wildcard_v2": {
                "enabled": True,
                "layout": layout,
                "character_mode": "fixed",
                "character": "1girl, adult woman, solo",
                "lighting_mode": "none",
            }
        }
    )
    positive = prepare_batch(None, recipe, {})[0]["positive"]
    assert "__moss_lora_v2/anima/slots/hair__" in positive
    assert "__moss_lora_v2/anima/slots/eyes_expr__" in positive


@pytest.mark.parametrize("pool", WHOLE_PROMPT_POOLS)
def test_v2_rejects_whole_prompt_pools_in_independent_scene(monkeypatch, pool):
    def unexpected_expansion(*_args):
        pytest.fail("A whole-prompt pool must be rejected before Impact expansion")

    monkeypatch.setattr("prompt_hub.studio_prompts._expand_v2", unexpected_expansion)
    recipe = normalize_recipe(
        {
            "wildcard_v2": {
                "enabled": True,
                "layout": "independent",
                "scene_light_mode": "random",
                "scene_light_pool": pool,
            }
        }
    )
    with pytest.raises(StudioError, match="整句詞池只能單獨使用"):
        prepare_batch(None, recipe, {})


def test_v2_applies_preset_to_sampler_and_untitled_negative_encoder():
    graph = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old positive"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "old negative"}},
        "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1536}},
        "4": {
            "class_type": "KSampler",
            "inputs": {
                "positive": ["1", 0],
                "negative": ["2", 0],
                "latent_image": ["3", 0],
                "steps": 12,
                "cfg": 1.0,
            },
        },
    }
    original = deepcopy(graph)
    recipe = normalize_recipe(
        {
            "wildcard_v2": {"enabled": True},
            "overrides": {"3::width": 512, "3::height": 768, "4::steps": 25, "4::cfg": 4.0},
        }
    )
    positive = "  Impact original text\n"
    compiled = compile_graph(
        graph, recipe, {"prefix": "", "body": positive, "suffix": "", "positive": positive}
    )
    assert graph == original
    assert compiled["3"]["inputs"] == {"width": 1024, "height": 1536}
    assert compiled["4"]["inputs"]["steps"] == 12
    assert compiled["4"]["inputs"]["cfg"] == 1.0
    assert compiled["1"]["inputs"]["text"] == positive
    assert compiled["2"]["inputs"]["text"] == ANIMA_NEGATIVE
