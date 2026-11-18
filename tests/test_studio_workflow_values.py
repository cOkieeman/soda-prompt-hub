from __future__ import annotations

import json
from copy import deepcopy

import pytest

from prompt_hub.studio_store import StudioError, normalize_recipe
from prompt_hub.studio_workflows import (
    compile_graph,
    infer_bindings,
    postprocess_nodes,
    scalar_inputs,
    set_input,
    source_values,
)


@pytest.mark.parametrize(
    ("kind", "image_input"),
    [
        ("DetailerForEachPipe", "image"),
        ("CR Upscale Image", "image"),
        ("ImageUpscaleWithModel", "image"),
        ("RTXVideoSuperResolution", "images"),
        ("DLSS5NeuralRender", "images"),
        ("DLSS5NeuralRenderAdvanced", "images"),
    ],
)
def test_user_postprocessors_can_be_switched_off_without_mutating_the_saved_graph(
    kind, image_input
):
    original = {
        "source": {"class_type": "LoadImage", "inputs": {"image": "sample.png"}},
        "finish": {"class_type": kind, "inputs": {image_input: ["source", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["finish", 0]}},
    }
    assert [item["node_id"] for item in postprocess_nodes(original)] == ["finish"]
    recipe = normalize_recipe({"branches": {"finish": False}})
    compiled = compile_graph(
        original, recipe, {"prefix": "", "body": "", "suffix": "", "positive": ""}
    )
    assert compiled["save"]["inputs"]["images"] == ["source", 0]
    assert "finish" not in compiled
    assert original["save"]["inputs"]["images"] == ["finish", 0]


def test_disabling_face_detailer_preserves_the_hand_detailers_pipe():
    original = {
        "image": {"class_type": "LoadImage", "inputs": {"image": "sample.png"}},
        "pipe": {"class_type": "ToBasicPipe", "inputs": {}},
        "mask": {"class_type": "MaskToSEGS", "inputs": {}},
        "face": {
            "class_type": "DetailerForEachPipe",
            "inputs": {"image": ["image", 0], "segs": ["mask", 0], "basic_pipe": ["pipe", 0]},
        },
        "hand": {
            "class_type": "DetailerForEachPipe",
            "inputs": {"image": ["face", 0], "segs": ["face", 1], "basic_pipe": ["face", 2]},
        },
    }
    recipe = normalize_recipe({"branches": {"face": False}})
    compiled = compile_graph(
        original, recipe, {"prefix": "", "body": "", "suffix": "", "positive": ""}
    )
    assert compiled["hand"]["inputs"] == {
        "image": ["image", 0],
        "segs": ["mask", 0],
        "basic_pipe": ["pipe", 0],
    }
    assert original["hand"]["inputs"]["basic_pipe"] == ["face", 2]


def pixaroma_graph(*, turbo=True):
    return {
        "seed": {
            "class_type": "PixaromaSeed",
            "inputs": {"SeedState": json.dumps({"runSeed": 123}), "seed": 999},
        },
        "size": {
            "class_type": "PixaromaSizes",
            "inputs": {
                "SizesState": json.dumps(
                    {"w": 1024, "h": 1536, "sizes": [[1024, 1536]], "selected": 0}
                )
            },
        },
        "controls": {
            "class_type": "PixaromaSliders",
            "inputs": {
                "SlidersState": json.dumps(
                    {
                        "version": 1,
                        "sliders": [
                            {"type": "toggle", "value": int(turbo), "out": "bool"},
                            {"type": "int", "value": 12},
                            {"type": "int", "value": 30},
                        ],
                    }
                )
            },
        },
        "switch": {
            "class_type": "ComfySwitchNode",
            "inputs": {
                "switch": ["controls", 0],
                "on_true": ["controls", 1],
                "on_false": ["controls", 2],
            },
        },
        "width": {"class_type": "Any Switch (rgthree)", "inputs": {"any_02": ["size", 0]}},
        "latent": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": ["width", 0], "height": ["size", 1], "batch_size": 1},
        },
        "sampler": {
            "class_type": "ImpactKSamplerBasicPipe",
            "inputs": {"seed": ["seed", 0], "steps": ["switch", 0], "cfg": 1},
        },
    }


@pytest.mark.parametrize(("turbo", "steps"), [(True, 12), (False, 30)])
def test_import_reads_pixaroma_execution_state(turbo, steps):
    graph = pixaroma_graph(turbo=turbo)
    fields = source_values(graph, infer_bindings(graph))
    assert fields["seed"] == 123
    assert fields["width"] == 1024
    assert fields["height"] == 1536
    assert fields["steps"] == steps
    assert (
        next(
            field
            for field in scalar_inputs(graph)
            if field["key"] == "controls::SlidersState#/sliders/0/value"
        )["type"]
        == "boolean"
    )


def test_pixaroma_fields_include_only_the_controls_metadata_the_editor_needs():
    graph = pixaroma_graph()
    graph["switch"]["_meta"] = {"title": "Turbo mode steps"}
    graph["controls"]["inputs"]["SlidersState"] = json.dumps(
        {
            "sliders": [
                {"type": "toggle", "value": 1, "out": "bool"},
                {"type": "int", "value": 12, "min": 1, "max": 50, "step": 1},
                {"type": "int", "value": 30, "min": 1, "max": 50, "step": 1},
                {"type": "float", "value": 0.4},
                {
                    "type": "combo",
                    "value": "er_sde",
                    "options": ["euler", "er_sde"],
                    "allowed": ["er_sde"],
                },
            ]
        }
    )
    graph["sampler_input"] = {
        "class_type": "Sampler Selector (Image Saver)",
        "inputs": {"sampler_name": ["controls", 4]},
    }

    fields = {field["input"]: field for field in scalar_inputs(graph) if field.get("control")}

    assert fields["value_1"]["control"]["connected"] is True
    assert fields["value_2"]["control"]["min"] == 1
    assert fields["value_2"]["control"]["max"] == 50
    assert fields["value_2"]["control"]["targets"][0]["mode"] == "turbo"
    assert fields["value_5"]["control"]["options"] == ["er_sde"]
    assert fields["value_5"]["control"]["connected"] is True
    assert fields["value_4"]["control"]["connected"] is False


@pytest.mark.parametrize("turbo", [True, False])
def test_compile_updates_shared_controls_and_preserves_routing_and_other_presets(turbo):
    original = pixaroma_graph(turbo=turbo)
    before = deepcopy(original)
    recipe = normalize_recipe({"seed": 456, "width": 832, "height": 1216, "steps": 50})
    graph = compile_graph(
        original, recipe, {"prefix": "", "body": "test", "suffix": "", "positive": "test"}
    )
    assert original == before
    assert json.loads(graph["seed"]["inputs"]["SeedState"])["runSeed"] == 456
    sizes = json.loads(graph["size"]["inputs"]["SizesState"])
    assert (sizes["w"], sizes["h"]) == (832, 1216)
    assert sizes["sizes"] == [[1024, 1536]]
    sliders = json.loads(graph["controls"]["inputs"]["SlidersState"])["sliders"]
    assert sliders[1 if turbo else 2]["value"] == 50
    assert sliders[2 if turbo else 1]["value"] == (30 if turbo else 12)
    assert graph["sampler"]["inputs"]["steps"] == ["switch", 0]


def test_binding_follows_the_turbo_switch_override():
    original = pixaroma_graph(turbo=True)
    recipe = normalize_recipe(
        {
            "steps": 50,
            "bindings": infer_bindings(original),
            "overrides": {"controls::SlidersState#/sliders/0/value": False},
        }
    )
    graph = compile_graph(
        original, recipe, {"prefix": "", "body": "test", "suffix": "", "positive": "test"}
    )
    controls = json.loads(graph["controls"]["inputs"]["SlidersState"])["sliders"]
    assert controls[0]["value"] == 0
    assert controls[1]["value"] == 12
    assert controls[2]["value"] == 50


def test_invalid_serialized_controls_do_not_break_import_or_allow_invalid_edits():
    graph = pixaroma_graph()
    graph["controls"]["inputs"]["SlidersState"] = "broken JSON"
    assert "steps" not in infer_bindings(graph)
    with pytest.raises(StudioError):
        set_input(graph, "controls::SlidersState#/sliders/0/value", True)  # noqa: FBT003
    with pytest.raises(StudioError):
        set_input(graph, "seed::SeedState#/runSeed", "not a number")


def test_widget_to_string_resolves_flattened_subgraph_and_current_controls():
    graph = {
        "600": {
            "class_type": "PixaromaSliders",
            "inputs": {"SlidersState": json.dumps({"sliders": [{"value": "sgm_uniform"}]})},
        },
        "559:574": {
            "class_type": "Scheduler Selector (Image Saver)",
            "inputs": {"scheduler": ["600", 0]},
        },
        "560:352": {
            "class_type": "WidgetToString",
            "inputs": {"id": 574, "widget_name": "scheduler", "return_all": False},
        },
    }
    compiled = compile_graph(
        graph, normalize_recipe({}), {"prefix": "", "body": "", "suffix": "", "positive": ""}
    )
    assert compiled["560:352"]["class_type"] == "PrimitiveString"
    assert compiled["560:352"]["inputs"]["value"] == "sgm_uniform"
    assert graph["560:352"]["class_type"] == "WidgetToString"
