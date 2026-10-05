from __future__ import annotations

import json

import prompt_hub.generation_evidence as evidence_module
from prompt_hub.comfy_results import parse_generation_metadata
from prompt_hub.generation_evidence import inspect_generation_evidence


def test_api_evidence_excludes_disconnected_loras_and_keeps_stack_order_nodes() -> None:
    prompt = {
        "1": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
        "2": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0]}},
        "3": {"class_type": "KSampler", "inputs": {"model": ["4", 0]}},
        "4": {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["5", 0],
                "lora_name": "style.safetensors",
                "strength_model": 0.4,
                "strength_clip": 0.3,
            },
        },
        "5": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "style.safetensors",
                "strength_model": 0.2,
                "strength_clip": 0.1,
            },
        },
        "6": {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "unused.safetensors", "strength_model": 1},
        },
    }
    evidence = inspect_generation_evidence(prompt, None)
    assert evidence["scope"] == "output_connected"
    assert [item["node_id"] for item in evidence["loras"]] == ["4", "5"]
    assert evidence["loras"][1]["strength_model"] == 0.2
    assert evidence["warnings"]  # Saved connections are not a runtime execution receipt.


def test_gui_evidence_follows_links_and_excludes_bypass_and_muted_nodes() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "SaveImage", "mode": 0},
            {"id": 2, "type": "LoraLoader", "widgets_values": ["active.safetensors", 0.5, 0.7]},
            {
                "id": 3,
                "type": "LoraLoader",
                "mode": 4,
                "widgets_values": ["bypass.safetensors", 1, 1],
            },
            {
                "id": 4,
                "type": "LoraLoader",
                "mode": 2,
                "widgets_values": ["muted.safetensors", 1, 1],
            },
            {"id": 5, "type": "LoraLoader", "widgets_values": ["unused.safetensors", 1, 1]},
            {
                "id": 6,
                "type": "LoraLoaderModelOnly",
                "widgets_values": ["behind-mute.safetensors", 1],
            },
        ],
        "links": [
            [1, 2, 0, 1, 0, "IMAGE"],
            [2, 3, 0, 2, 0, "MODEL"],
            [3, 4, 0, 3, 0, "MODEL"],
            [4, 6, 0, 4, 0, "MODEL"],
        ],
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert evidence["status"] == "saved_workflow"
    assert [item["name"] for item in evidence["loras"]] == ["active.safetensors"]
    assert evidence["loras"][0]["strength_clip"] == 0.7


def test_gui_structured_lora_collection_ignores_disabled_and_zero_strength() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "SaveImage"},
            {
                "id": 2,
                "type": "Lora Loader (LoraManager)",
                "widgets_values": [
                    {
                        "loras": [
                            {"name": "kept.safetensors", "strength": 0.63, "active": True},
                            {"name": "disabled.safetensors", "strength": 0.7, "active": False},
                            {"name": "zero.safetensors", "strength_model": 0, "strength_clip": 0},
                        ]
                    }
                ],
            },
        ],
        "links": [[1, 2, 0, 1, 0, "IMAGE"]],
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert [item["name"] for item in evidence["loras"]] == ["kept.safetensors"]
    assert evidence["loras"][0]["strength_clip"] == 0.63
    assert evidence["unknown_lora_nodes"] == []


def test_unrecognized_lora_widget_is_reported_without_guessing_weights() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "CustomLoraSwitch", "widgets_values": ["maybe.safetensors", 0.8]}
        ]
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert evidence["loras"] == []
    assert evidence["unknown_lora_nodes"] == [{"node_id": "1", "node_type": "CustomLoraSwitch"}]
    assert evidence["scope"] == "saved_nodes"


def test_api_collection_and_cycle_are_bounded_without_nan_weights() -> None:
    prompt = {
        "1": {"class_type": "Image Saver", "inputs": {"images": ["2", 0]}},
        "2": {
            "class_type": "LoraManager",
            "inputs": {
                "model": ["2", 0],
                "loras": [
                    {
                        "lora_name": "test.safetensors",
                        "strength_model": float("nan"),
                        "strength_clip": True,
                    },
                ],
            },
        },
    }
    evidence = inspect_generation_evidence(prompt, None)
    assert len(evidence["candidate_loras"]) == 1
    assert evidence["candidate_loras"][0]["strength_model"] is None
    assert evidence["candidate_loras"][0]["strength_clip"] is None


def test_inactive_standard_lora_does_not_mean_unknown_schema() -> None:
    evidence = inspect_generation_evidence(
        {
            "1": {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": "zero.safetensors",
                    "strength_model": 0,
                    "strength_clip": 0,
                },
            }
        },
        None,
    )
    assert evidence["loras"] == []
    assert evidence["unknown_lora_nodes"] == []


def test_gui_only_metadata_preserves_legacy_shape_and_adds_evidence() -> None:
    metadata = parse_generation_metadata(
        {
            "workflow": {
                "nodes": [
                    {
                        "id": 1,
                        "type": "LoraLoaderModelOnly",
                        "widgets_values": ["style.safetensors", -0.3],
                    },
                ]
            }
        },
        width=960,
        height=1280,
    )
    assert metadata["loras"] == []  # Existing API semantics are preserved.
    assert metadata["metadata_present"]
    assert metadata["generation_evidence"]["candidate_loras"][0]["strength_model"] == -0.3
    assert metadata["generation_evidence"]["candidate_loras"][0]["strength_clip"] == 0


def test_invalid_and_absent_graph_have_no_invented_lora_records() -> None:
    for prompt, workflow in ((None, None), ("not json", []), ([], {"nodes": "invalid"})):
        evidence = inspect_generation_evidence(prompt, workflow)
        assert evidence["status"] == "unavailable"
        assert evidence["loras"] == []


def test_oversized_integer_weight_is_unavailable_without_crashing() -> None:
    evidence = inspect_generation_evidence(
        {
            "1": {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": "style.safetensors",
                    "strength_model": 10**400,
                    "strength_clip": 0.4,
                },
            }
        },
        None,
    )
    assert evidence["candidate_loras"][0]["strength_model"] is None
    assert evidence["candidate_loras"][0]["strength_clip"] == 0.4


def _gui_node(node_id, kind, inputs=(), widgets=(), **extra):
    return {
        "id": node_id,
        "type": kind,
        "inputs": [{"name": key} for key in inputs],
        "widgets_values": list(widgets),
        **extra,
    }


def _definition_link(origin, origin_slot, target, target_slot):
    return {
        "id": f"{origin}/{origin_slot}/{target}/{target_slot}",
        "origin_id": origin,
        "origin_slot": origin_slot,
        "target_id": target,
        "target_slot": target_slot,
    }


def _nested_workflow():
    fields = ("model", "width", "height", "seed", "steps", "cfg")
    inner = {
        "id": "anonymous-inner-subgraph",
        "nodes": [
            _gui_node(
                10, "LoraLoader", ("model", "clip"), ("anonymous-style.safetensors", 0.6, 0.4)
            ),
            _gui_node(11, "EmptyLatentImage", ("width", "height"), (512, 512, 1)),
            _gui_node(
                12,
                "KSampler",
                ("model", "latent_image", "seed", "steps", "cfg"),
                (7, "fixed", 20, 7, "euler", "normal", 0.9),
            ),
            _gui_node(13, "VAEDecode", ("samples",)),
            _gui_node(14, "Image Saver", ("images",)),
        ],
        "links": [
            _definition_link(-10, 0, 10, 0),
            _definition_link(-10, 1, 11, 0),
            _definition_link(-10, 2, 11, 1),
            _definition_link(10, 0, 12, 0),
            _definition_link(11, 0, 12, 1),
            _definition_link(-10, 3, 12, 2),
            _definition_link(-10, 4, 12, 3),
            _definition_link(-10, 5, 12, 4),
            _definition_link(12, 0, 13, 0),
            _definition_link(13, 0, 14, 0),
            _definition_link(13, 0, -20, 0),
        ],
    }
    outer = {
        "id": "anonymous-outer-subgraph",
        "nodes": [_gui_node(6, inner["id"], fields)],
        "links": [
            *[_definition_link(-10, slot, 6, slot) for slot in range(len(fields))],
            _definition_link(6, 0, -20, 0),
        ],
    }
    unused = {
        "id": "unused-subgraph",
        "nodes": [_gui_node(10, "LoraLoader", widgets=("unused.safetensors", 1, 1))],
    }
    return {
        "nodes": [
            _gui_node(1, outer["id"], fields),
            _gui_node(2, "CheckpointLoaderSimple", widgets=("anonymous-base.safetensors",)),
            _gui_node(3, "ResolutionMasterSimplify", widgets=(1536, 1024)),
            _gui_node(4, "Seed (rgthree)", widgets=(2**63 + 15, "fixed")),
            _gui_node(
                5,
                "Input Parameters (Image Saver)",
                widgets=(77, "fixed", 12, 1.5, "heun", "simple", 1),
            ),
            _gui_node(9, outer["id"], fields, mode=2),
        ],
        "links": [
            [1, 2, 0, 1, 0, "MODEL"],
            [2, 3, 0, 1, 1, "INT"],
            [3, 3, 1, 1, 2, "INT"],
            [4, 4, 0, 1, 3, "INT"],
            [5, 5, 1, 1, 4, "INT"],
            [6, 5, 2, 1, 5, "FLOAT"],
        ],
        "definitions": {"subgraphs": [outer, inner, unused]},
    }


def test_nested_gui_boundaries_override_stale_widgets_and_preserve_seed_precision() -> None:
    evidence = inspect_generation_evidence(None, _nested_workflow())
    assert evidence["scope"] == "output_connected"
    assert [(record["node_id"], record["name"]) for record in evidence["loras"]] == [
        ("1/6/10", "anonymous-style.safetensors")
    ]
    assert evidence["models"] == [
        {
            "name": "anonymous-base.safetensors",
            "kind": "checkpoint",
            "node_id": "2",
            "node_type": "CheckpointLoaderSimple",
        }
    ]
    assert evidence["sampling"] == [
        {
            "seed": str(2**63 + 15),
            "steps": 12,
            "cfg": 1.5,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 0.9,
            "width": 1536,
            "height": 1024,
            "node_id": "1/6/12",
        }
    ]


def test_api_prompt_takes_precedence_and_tracks_custom_sampling_components() -> None:
    prompt = {
        "save": {
            "class_type": "Image Saver",
            "inputs": {
                "images": ["sample", 0],
                "positive": "anonymous positive fullPrompt",
                "negative": "anonymous negative",
                "width": 4096,
                "height": 3072,
            },
        },
        "sample": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["noise", 0],
                "guider": ["guider", 0],
                "sampler": ["sampler", 0],
                "sigmas": ["sigmas", 0],
                "latent_image": ["latent", 0],
            },
        },
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": "18446744073709551615"}},
        "sampler": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "heun"}},
        "sigmas": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["base", 0],
                "scheduler": "simple",
                "steps": 15,
                "denoise": 0.7,
            },
        },
        "guider": {"class_type": "CFGGuider", "inputs": {"model": ["base", 0], "cfg": 2.5}},
        "latent": {"class_type": "EmptyLatentImage", "inputs": {"width": 960, "height": 1440}},
        "base": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "anonymous-diffusion.safetensors"},
        },
        "unconnected": {"class_type": "LoraLoader", "inputs": {"lora_name": "unused.safetensors"}},
    }
    evidence = inspect_generation_evidence(prompt, _nested_workflow())
    assert evidence["status"] == "saved_api_prompt"
    assert evidence["loras"] == []
    assert evidence["models"][0]["kind"] == "diffusion_model"
    assert evidence["sampling"] == [
        {
            "seed": "18446744073709551615",
            "steps": 15,
            "cfg": 2.5,
            "sampler_name": "heun",
            "scheduler": "simple",
            "denoise": 0.7,
            "width": 960,
            "height": 1440,
            "node_id": "sample",
        }
    ]
    assert evidence["prompts"] == [
        {"polarity": "positive", "text": "anonymous positive fullPrompt", "node_id": "save"},
        {"polarity": "negative", "text": "anonymous negative", "node_id": "save"},
    ]


def test_gui_loramanager_actual_widget_array_parses_string_weights_and_active_flag() -> None:
    workflow = {
        "nodes": [
            _gui_node(1, "SaveImage", ("images",)),
            _gui_node(
                2, "Lora Loader (LoraManager)", ("model", "lora_stack"), ({"version": 1}, "", [])
            ),
            _gui_node(
                3,
                "Lora Stacker (LoraManager)",
                widgets=(
                    {"version": 1, "textWidgetName": "text"},
                    "",
                    [
                        {
                            "name": "anonymous-a.safetensors",
                            "strength": "0.80",
                            "clipStrength": "0.55",
                            "active": True,
                            "selected": False,
                        },
                        {
                            "name": "disabled.safetensors",
                            "strength": 1,
                            "active": False,
                            "selected": True,
                        },
                        {
                            "name": "zero.safetensors",
                            "strength": "0",
                            "clipStrength": "0",
                            "active": True,
                        },
                    ],
                ),
            ),
        ],
        "links": [[1, 2, 0, 1, 0, "IMAGE"], [2, 3, 0, 2, 1, "LORA_STACK"]],
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert evidence["unknown_lora_nodes"] == []
    assert evidence["candidate_loras"] == [
        {
            "name": "anonymous-a.safetensors",
            "strength_model": 0.8,
            "strength_clip": 0.55,
            "node_id": "3",
            "node_type": "Lora Stacker (LoraManager)",
            "reason": "LoRA 节点或启用状态无法确认",
        }
    ]


def test_power_lora_loader_respects_on_and_optional_clip_strength() -> None:
    prompt = {
        "1": {
            "class_type": "Power Lora Loader (rgthree)",
            "inputs": {
                "clip": ["clip", 0],
                "lora_1": {"on": True, "lora": "anonymous-one.safetensors", "strength": 0.4},
                "lora_2": {
                    "on": True,
                    "lora": "anonymous-two.safetensors",
                    "strength": 0.8,
                    "strengthTwo": 0.2,
                },
                "lora_3": {"on": False, "lora": "disabled.safetensors", "strength": 1},
            },
        },
        "clip": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "anonymous-encoder.safetensors"},
        },
    }
    evidence = inspect_generation_evidence(prompt, None)
    assert [
        (record["strength_model"], record["strength_clip"])
        for record in evidence["candidate_loras"]
    ] == [(0.4, 0.4), (0.8, 0.2)]
    del prompt["1"]["inputs"]["clip"]
    evidence = inspect_generation_evidence(prompt, None)
    assert [record["strength_clip"] for record in evidence["candidate_loras"]] == [0, 0]


def test_bypassed_constant_has_no_output_and_any_switch_uses_active_parameter() -> None:
    workflow = {
        "nodes": [
            _gui_node(1, "KSampler", ("steps",), (17, "fixed", 99, 7, "euler", "normal", 1)),
            _gui_node(2, "Any Switch (rgthree)", ("any_01", "any_02")),
            _gui_node(3, "Int Literal", widgets=(30,), mode=4, outputs=[{"type": "INT"}]),
            _gui_node(4, "Int Literal", widgets=(12,), outputs=[{"type": "INT"}]),
            _gui_node(5, "SaveImage", ("images",)),
        ],
        "links": [
            [1, 3, 0, 2, 0, "INT"],
            [2, 4, 0, 2, 1, "INT"],
            [3, 2, 0, 1, 0, "INT"],
            [4, 1, 0, 5, 0, "IMAGE"],
        ],
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert evidence["sampling"][0]["steps"] == 12
    assert evidence["sampling"][0]["cfg"] == 7


def test_conditional_lora_branch_excludes_disabled_path() -> None:
    prompt = {
        "save": {"class_type": "SaveImage", "inputs": {"images": ["switch", 0]}},
        "switch": {
            "class_type": "ComfySwitchNode",
            "inputs": {
                "switch": ["flag", 0],
                "on_true": ["lora", 0],
                "on_false": ["base", 0],
            },
        },
        "flag": {"class_type": "PrimitiveBoolean", "inputs": {"value": False}},
        "lora": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"lora_name": "unused.safetensors", "strength_model": 1},
        },
        "base": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "anonymous-base.safetensors"},
        },
    }
    evidence = inspect_generation_evidence(prompt, None)
    assert evidence["loras"] == []
    prompt["flag"]["inputs"]["value"] = True
    assert len(inspect_generation_evidence(prompt, None)["loras"]) == 1


def test_qwen_positive_and_negative_ports_do_not_cross_label_prompt_components() -> None:
    prompt = {
        "save": {"class_type": "SaveImage", "inputs": {"images": ["sample", 0]}},
        "sample": {
            "class_type": "KSampler",
            "inputs": {"positive": ["encode", 0], "negative": ["encode", 1]},
        },
        "encode": {
            "class_type": "TextEncodeQwenImage21",
            "inputs": {"prompt": ["pos", 0], "negative_prompt": ["neg", 0]},
        },
        "pos": {
            "class_type": "PrimitiveStringMultiline",
            "inputs": {"value": "anonymous positive"},
        },
        "neg": {
            "class_type": "PrimitiveStringMultiline",
            "inputs": {"value": "anonymous negative"},
        },
    }
    evidence = inspect_generation_evidence(prompt, None)
    assert [record["polarity"] for record in evidence["prompts"] if record["node_id"] == "pos"] == [
        "positive"
    ]
    assert [record["polarity"] for record in evidence["prompts"] if record["node_id"] == "neg"] == [
        "negative"
    ]
    assert {
        record["polarity"]: record["text"]
        for record in evidence["prompts"]
        if record["node_id"] == "encode"
    } == {"positive": "anonymous positive", "negative": "anonymous negative"}


def test_recursive_subgraph_is_bounded_and_warns_without_lora_inference() -> None:
    workflow = {
        "nodes": [_gui_node(1, "recursive", ())],
        "definitions": {
            "subgraphs": [
                {
                    "id": "recursive",
                    "nodes": [_gui_node(1, "recursive")],
                    "links": [_definition_link(1, 0, -20, 0)],
                }
            ]
        },
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert evidence["loras"] == []
    assert any("深度" in warning for warning in evidence["warnings"])


def test_dynamic_text_is_not_evaluated_or_replaced_with_cached_preview() -> None:
    prompt = {
        "1": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
        "2": {"class_type": "KSampler", "inputs": {"positive": ["3", 0], "latent_image": ["6", 0]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": ["4", 0]}},
        "4": {
            "class_type": "ShowText|pysssss",
            "inputs": {"text": ["5", 0]},
            "widgets_values": ["stale preview"],
        },
        "5": {
            "class_type": "MathExpression|pysssss",
            "inputs": {"expression": "untrusted expression"},
        },
        "6": {"class_type": "VAEEncode", "inputs": {}},
    }
    evidence = inspect_generation_evidence(prompt, None)
    assert evidence["prompts"] == []
    assert "width" not in evidence["sampling"][0]
    assert evidence["sampling"][0]["seed"] is None
    assert any("自定义" in warning for warning in evidence["warnings"])


def test_upscalers_are_separate_from_base_model_facets_and_sd3_latent_size_is_saved() -> None:
    workflow = {
        "nodes": [
            _gui_node(1, "KSampler", ("latent_image",), (23, "fixed", 8, 1, "euler", "simple", 1)),
            _gui_node(2, "EmptySD3LatentImage", widgets=(832, 1248, 1)),
            {
                "id": 3,
                "type": "SeedVR2LoadDiTModel",
                "widgets_values": ["anonymous-upscaler.safetensors"],
                "inputs": [{"name": "model", "widget": {"name": "model"}, "type": "COMBO"}],
            },
            _gui_node(4, "UpscaleModelLoader", widgets=("anonymous-super-resolution.pth",)),
        ],
        "links": [[1, 2, 0, 1, 0, "LATENT"]],
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert [record["kind"] for record in evidence["models"]] == ["upscale_model", "upscale_model"]
    assert evidence["sampling"][0]["width"] == 832
    assert evidence["sampling"][0]["height"] == 1248


def test_malformed_nodes_and_unknown_mode_do_not_crash_or_invent_records() -> None:
    evidence = inspect_generation_evidence(
        {"bad": {"class_type": "LoraLoader", "inputs": ["invalid"]}},
        None,
    )
    assert evidence["loras"] == []
    evidence = inspect_generation_evidence(
        None,
        {
            "nodes": [
                _gui_node(
                    1, "LoraLoader", widgets=("unknown.safetensors", 1, 1), mode={"invalid": True}
                ),
            ],
            "links": [{"origin_id": 1, "origin_slot": [], "target_id": 2, "target_slot": 0}],
        },
    )
    assert evidence["loras"] == []
    assert evidence["models"] == []
    assert any("模式" in warning for warning in evidence["warnings"])


def test_unavailable_schema_has_all_structured_arrays_for_incremental_rescan() -> None:
    evidence = inspect_generation_evidence(None, None)
    assert evidence["scope"] == "none"
    for field in ("models", "loras", "prompts", "sampling"):
        assert evidence[field] == []


def test_api_loramanager_value_wrapper_matches_generated_workflow_profile_shape() -> None:
    prompt = {
        "1": {
            "class_type": "Lora Loader (LoraManager)",
            "inputs": {
                "loras": {
                    "__value__": [
                        {
                            "name": "anonymous-style.safetensors",
                            "strength": 0.7,
                            "clipStrength": 0.5,
                            "active": True,
                        },
                    ]
                },
            },
        },
    }
    evidence = inspect_generation_evidence(prompt, None)
    assert evidence["candidate_loras"] == [
        {
            "name": "anonymous-style.safetensors",
            "strength_model": 0.7,
            "strength_clip": 0.5,
            "node_id": "1",
            "node_type": "Lora Loader (LoraManager)",
            "reason": "没有可确认的图像输出连接",
        }
    ]
    assert evidence["unknown_lora_nodes"] == []


def test_bypassed_lora_model_port_does_not_count_unconsumed_clip_branch() -> None:
    workflow = {
        "nodes": [
            _gui_node(1, "SaveImage", ("images",)),
            _gui_node(2, "LoraLoader", ("model", "clip"), ("bypass.safetensors", 1, 1), mode=4),
            _gui_node(3, "CheckpointLoaderSimple", widgets=("anonymous-base.safetensors",)),
            _gui_node(4, "LoraLoader", ("model", "clip"), ("unconsumed.safetensors", 1, 1)),
        ],
        "links": [[1, 2, 0, 1, 0, "IMAGE"], [2, 3, 0, 2, 0, "MODEL"], [3, 4, 1, 2, 1, "CLIP"]],
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert evidence["loras"] == []
    assert evidence["models"][0]["name"] == "anonymous-base.safetensors"


def test_power_gui_requires_explicit_on_flag_and_preserves_two_strengths() -> None:
    workflow = {
        "nodes": [
            _gui_node(
                1,
                "Power Lora Loader (rgthree)",
                ("clip",),
                (
                    {
                        "on": True,
                        "lora": "anonymous-style.safetensors",
                        "strength": 0.6,
                        "strengthTwo": 0.3,
                    },
                    {"lora": "missing-on.safetensors", "strength": 1},
                ),
            ),
            _gui_node(
                2,
                "CLIPLoader",
                widgets=("anonymous-encoder.safetensors", "stable_diffusion", "default"),
            ),
        ],
        "links": [[1, 2, 0, 1, 0, "CLIP"]],
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert len(evidence["candidate_loras"]) == 1
    assert evidence["candidate_loras"][0]["strength_clip"] == 0.3


def _usage_lora(name: str, **inputs: object) -> dict[str, object]:
    return {
        "class_type": "LoraLoader",
        "inputs": {"lora_name": name, "strength_model": 0.5, "strength_clip": 0.5, **inputs},
    }


def test_usage_trigger_words_port_does_not_mean_model_applied() -> None:
    graph = {
        "l": {
            "class_type": "Lora Loader (LoraManager)",
            "inputs": {
                "loras": [
                    {"name": "text-only", "strength": 0.5, "clipStrength": 0.5, "active": True}
                ]
            },
        },
        "text": {"class_type": "CLIPTextEncode", "inputs": {"text": ["l", 2]}},
        "sampler": {"class_type": "KSampler", "inputs": {"positive": ["text", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["sampler", 0]}},
    }
    assert inspect_generation_evidence(graph, None)["loras"] == []


def test_usage_model_port_does_not_traverse_unused_clip_branch() -> None:
    graph = {
        "a": _usage_lora("unused-clip"),
        "b": _usage_lora("used-model", clip=["a", 1]),
        "sampler": {"class_type": "KSampler", "inputs": {"model": ["b", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["sampler", 0]}},
    }
    assert [r["name"] for r in inspect_generation_evidence(graph, None)["loras"]] == ["used-model"]
    graph["sampler"]["inputs"]["positive"] = ["encode", 0]
    graph["encode"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["a", 1]}}
    assert {r["name"] for r in inspect_generation_evidence(graph, None)["loras"]} == {
        "used-model",
        "unused-clip",
    }


def test_usage_unknown_switch_candidates_are_separate() -> None:
    graph = {
        "a": _usage_lora("a"),
        "b": _usage_lora("b"),
        "flag": {"class_type": "RuntimeFlag", "inputs": {}},
        "switch": {
            "class_type": "ComfySwitchNode",
            "inputs": {"switch": ["flag", 0], "on_true": ["a", 0], "on_false": ["b", 0]},
        },
        "save": {"class_type": "SaveImage", "inputs": {"images": ["switch", 0]}},
    }
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["loras"] == []
    assert {r["name"] for r in evidence["candidate_loras"]} == {"a", "b"}
    assert all(r["reason"] for r in evidence["candidate_loras"])
    graph["switch"]["inputs"]["switch"] = False
    assert [r["name"] for r in inspect_generation_evidence(graph, None)["loras"]] == ["b"]


def test_usage_multiple_outputs_only_confirm_common_chain() -> None:
    graph = {
        "base": _usage_lora("common"),
        "a": _usage_lora("only-a", model=["base", 0]),
        "b": _usage_lora("only-b", model=["base", 0]),
        "save-a": {"class_type": "SaveImage", "inputs": {"images": ["a", 0]}},
        "save-b": {"class_type": "Image Saver", "inputs": {"images": ["b", 0]}},
    }
    evidence = inspect_generation_evidence(graph, None)
    assert [r["name"] for r in evidence["loras"]] == ["common"]
    assert {r["name"] for r in evidence["candidate_loras"]} == {"only-a", "only-b"}


def test_usage_no_output_is_candidate_and_loader_product_name_is_not_output() -> None:
    graph = {
        "l": _usage_lora("saved-only"),
        "loader": {"class_type": "UNet loader with Name (Image Saver)", "inputs": {}},
    }
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["scope"] == "saved_nodes"
    assert evidence["extractor_version"] == 4
    assert evidence["loras"] == []
    assert evidence["candidate_loras"][0]["name"] == "saved-only"


def test_usage_single_any_switch_and_actual_manager_rows_preserve_duplicates() -> None:
    rows = [
        {
            "name": str(i % 16),
            "active": True,
            "selected": False,
            "strength": -0.2 if i == 0 else 0.3,
            "clipStrength": 0.4,
        }
        for i in range(22)
    ]
    rows.append({"name": "disabled", "active": False, "strength": 1, "clipStrength": 1})
    graph = {
        "77": {"class_type": "Lora Loader (LoraManager)", "inputs": {"loras": {"__value__": rows}}},
        "184": {
            "class_type": "ImpactWildcardEncode",
            "inputs": {"model": ["77", 0], "clip": ["77", 1]},
        },
        "pipe": {"class_type": "ToBasicPipe", "inputs": {"model": ["184", 0], "clip": ["184", 1]}},
        "sample": {"class_type": "ImpactKSamplerBasicPipe", "inputs": {"basic_pipe": ["pipe", 0]}},
        "any": {"class_type": "Any Switch (rgthree)", "inputs": {"any_02": ["sample", 0]}},
        "save": {"class_type": "Image Saver", "inputs": {"images": ["any", 0]}},
    }
    evidence = inspect_generation_evidence(graph, None)
    assert len(evidence["loras"]) == 22
    assert len({r["name"] for r in evidence["loras"]}) == 16
    assert evidence["loras"][0]["strength_model"] == -0.2
    assert evidence["candidate_loras"] == []


def test_usage_clip_only_patch_and_negative_weight_require_consumed_port() -> None:
    graph = {
        "l": _usage_lora("clip-only", strength_model=0, strength_clip=-0.7),
        "encode": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["l", 1]}},
        "sample": {"class_type": "KSampler", "inputs": {"positive": ["encode", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["sample", 0]}},
    }
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["loras"][0]["strength_clip"] == -0.7
    graph["sample"]["inputs"] = {"model": ["l", 0]}
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["loras"] == evidence["candidate_loras"] == []


def test_usage_metadata_port_and_saver_metadata_inputs_are_not_patches() -> None:
    graph = {
        "l": {
            "class_type": "Lora Loader (LoraManager)",
            "inputs": {
                "loras": [
                    {"name": "metadata-only", "active": True, "strength": 1, "clipStrength": 1}
                ]
            },
        },
        "image": {"class_type": "VAEDecode", "inputs": {}},
        "save": {
            "class_type": "Image Saver",
            "inputs": {"images": ["image", 0], "additional_hashes": ["l", 3]},
        },
    }
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["loras"] == evidence["candidate_loras"] == []
    graph["image"]["inputs"] = {"samples": ["l", 3]}
    assert inspect_generation_evidence(graph, None)["loras"] == []


def test_usage_unknown_complex_node_and_missing_activation_are_candidates() -> None:
    graph = {
        "l": _usage_lora("ambiguous"),
        "other": {"class_type": "ImageSource", "inputs": {}},
        "custom": {
            "class_type": "CustomImageChooser",
            "inputs": {"a": ["l", 0], "b": ["other", 0]},
        },
        "save": {"class_type": "SaveImage", "inputs": {"images": ["custom", 0]}},
    }
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["loras"] == []
    assert evidence["candidate_loras"][0]["name"] == "ambiguous"
    graph["custom"] = {"class_type": "KSampler", "inputs": {"model": ["l", 0]}}
    graph["l"] = {
        "class_type": "Lora Loader (LoraManager)",
        "inputs": {"loras": [{"name": "flag-absent", "strength": 1, "clipStrength": 1}]},
    }
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["loras"] == []
    assert evidence["candidate_loras"] == []  # Manager defaults absent active to False.


def test_usage_shared_global_visit_budget_keeps_multiple_outputs_bounded(monkeypatch) -> None:
    monkeypatch.setattr(evidence_module, "MAX_GRAPH_LINKS", 4)
    graph = {"l": _usage_lora("shared")}
    graph.update(
        {str(i): {"class_type": "SaveImage", "inputs": {"images": ["l", 0]}} for i in range(5)}
    )
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["loras"] == []
    assert len(evidence["candidate_loras"]) == 1
    assert any("上限" in warning for warning in evidence["warnings"])


def test_usage_unknown_single_input_toggle_is_not_confirmed() -> None:
    graph = {
        "l": _usage_lora("candidate"),
        "toggle": {
            "class_type": "CustomModelToggle",
            "inputs": {"model": ["l", 0], "enabled": False},
        },
        "sample": {"class_type": "KSampler", "inputs": {"model": ["toggle", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["sample", 0]}},
    }
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["loras"] == []
    assert evidence["candidate_loras"][0]["name"] == "candidate"
    graph["toggle"] = {"class_type": "LayerUtility: PurgeVRAM V2", "inputs": {"anything": ["l", 0]}}
    assert len(inspect_generation_evidence(graph, None)["loras"]) == 1


def test_usage_unknown_gui_mode_cannot_confirm_upstream_lora() -> None:
    workflow = {
        "nodes": [
            _gui_node(1, "SaveImage", ("images",)),
            _gui_node(2, "KSampler", ("model",), mode=7),
            _gui_node(3, "LoraLoader", widgets=("candidate", 0.5, 0.5)),
        ],
        "links": [[1, 2, 0, 1, 0, "IMAGE"], [2, 3, 0, 2, 0, "MODEL"]],
    }
    evidence = inspect_generation_evidence(None, workflow)
    assert evidence["loras"] == []
    assert evidence["candidate_loras"][0]["name"] == "candidate"


def _final_graph(*, positive="QA positive", negative="QA negative"):
    return {
        "base": {"class_type": "UNETLoader", "inputs": {"unet_name": "Krea2/qa-base.safetensors"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qa-clip.safetensors"}},
        "p": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": positive}},
        "n": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": negative}},
        "s": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["base", 0],
                "positive": ["p", 0],
                "negative": ["n", 0],
                "seed": 9007199254740993,
            },
        },
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["s", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0]}},
    }


def test_v3_final_prompt_is_encoder_input_not_components_or_longest_text() -> None:
    graph = _final_graph(positive=["join", 0], negative="")
    graph["a"] = {"class_type": "String Literal", "inputs": {"string": "QA prefix"}}
    graph["b"] = {"class_type": "String Literal", "inputs": {"string": "QA body"}}
    graph["join"] = {
        "class_type": "StringConcatenate",
        "inputs": {"string_a": ["a", 0], "string_b": ["b", 0], "delimiter": " | "},
    }
    graph["unused"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "unused" * 1000}}
    evidence = inspect_generation_evidence(graph, None)
    final = evidence["final_generation"]
    assert evidence["extractor_version"] == 4
    assert final["stage_id"] == "s"
    assert final["model_family"] == "krea2"
    assert final["positive"]["text"] == "QA prefix | QA body"
    assert final["positive"]["status"] == "exact"
    assert final["negative"]["text"] == ""
    assert final["negative"]["status"] == "exact"
    assert final["sampler"]["seed"] == "9007199254740993"
    assert final["saved_export_prompts"]["positive"] is None


def test_v3_manager_active_is_only_widget_switch_and_clip_defaults_strength() -> None:
    graph = _final_graph()
    graph["l"] = {
        "class_type": "Lora Loader (LoraManager)",
        "inputs": {
            "model": ["base", 0],
            "clip": ["clip", 0],
            "loras": {
                "__value__": [
                    {"name": "off", "active": False, "enabled": True, "on": True, "strength": 0.8},
                    {
                        "name": "on",
                        "active": True,
                        "enabled": False,
                        "on": False,
                        "selected": False,
                        "strength": 0.4,
                    },
                    {"name": "missing-active", "enabled": True, "strength": 1},
                ]
            },
        },
    }
    graph["s"]["inputs"]["model"] = ["l", 0]
    graph["p"]["inputs"]["clip"] = ["l", 1]
    evidence = inspect_generation_evidence(graph, None)
    assert [r["name"] for r in evidence["loras"]] == ["on"]
    assert evidence["loras"][0]["strength_clip"] == 0.4
    assert evidence["final_generation"]["loras"] == []
    assert evidence["final_generation"]["lora_source"]["status"] == "missing"


def test_v3_basic_pipe_model_component_excludes_unconsumed_clip_patch() -> None:
    for kind, model_port in (("FromBasicPipe", 0), ("FromBasicPipe_v2", 1)):
        graph = _final_graph()
        graph["l"] = _usage_lora(
            "clip-only", model=["base", 0], clip=["clip", 0], strength_model=0, strength_clip=0.6
        )
        graph["pipe"] = {
            "class_type": "ToBasicPipe",
            "inputs": {
                "model": ["l", 0],
                "clip": ["l", 1],
                "positive": ["p", 0],
                "negative": ["n", 0],
            },
        }
        graph["from"] = {"class_type": kind, "inputs": {"basic_pipe": ["pipe", 0]}}
        graph["s"]["inputs"]["model"] = ["from", model_port]
        evidence = inspect_generation_evidence(graph, None)
        assert evidence["loras"] == []
        assert evidence["final_generation"]["loras"] == []


def test_v3_runtime_text_is_unknown_and_export_is_separate_fallback() -> None:
    graph = _final_graph(positive=["wild", 3])
    graph["wild"] = {
        "class_type": "ImpactWildcardEncode",
        "inputs": {"populated_text": "cached body", "mode": "populate"},
    }
    evidence = inspect_generation_evidence(
        graph,
        None,
        parameters=(
            "QA exported final\nNegative prompt: QA exported negative\n"
            "Steps: 8, Model: Krea2/qa-base.safetensors"
        ),
    )
    final = evidence["final_generation"]
    assert final["positive"]["text"] is None
    assert final["positive"]["status"] == "unavailable"
    assert final["negative"]["text"] == "QA negative"
    assert final["saved_export_prompts"]["positive"]["text"] == "QA exported final"
    assert final["saved_export_prompts"]["positive"]["status"] == "saved_export"
    graph["p"]["inputs"]["text"] = ["date", 0]
    graph["date"] = {"class_type": "JWDatetimeString", "inputs": {"format": "%Y-%m-%d"}}
    assert inspect_generation_evidence(graph, None)["final_generation"]["positive"]["text"] is None


def test_v3_terminal_krea_stage_does_not_mix_latent_history_loras_or_prompts() -> None:
    graph = _final_graph(positive="QA first pass")
    graph["a"] = _usage_lora("first-pass", model=["base", 0])
    graph["s"]["inputs"]["model"] = ["a", 0]
    graph["b"] = _usage_lora("final-pass", model=["base", 0])
    graph["p2"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "QA final pass", "clip": ["clip", 0]},
    }
    graph["latent"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["decode", 0]}}
    graph["s2"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["b", 0],
            "positive": ["p2", 0],
            "negative": ["n", 0],
            "latent_image": ["latent", 0],
        },
    }
    graph["d2"] = {"class_type": "VAEDecode", "inputs": {"samples": ["s2", 0]}}
    graph["save"]["inputs"]["images"] = ["d2", 0]
    final = inspect_generation_evidence(
        graph, None, saved_metadata={"Lora hashes": "final-pass: ABCDEF1234"}
    )["final_generation"]
    assert final["stage_id"] == "s2"
    assert final["positive"]["text"] == "QA final pass"
    assert [r["name"] for r in final["loras"]] == ["final-pass"]
    assert {r["stage_id"] for r in final["stages"]} == {"s", "s2"}


def test_v3_multiple_outputs_or_unknown_stage_branch_do_not_promote_export() -> None:
    graph = _final_graph()
    graph["p2"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "another", "clip": ["clip", 0]},
    }
    graph["s2"] = {
        "class_type": "KSampler",
        "inputs": {"model": ["base", 0], "positive": ["p2", 0]},
    }
    graph["save2"] = {"class_type": "SaveImage", "inputs": {"images": ["s2", 0]}}
    final = inspect_generation_evidence(graph, None, parameters="QA exported\nSteps: 8")[
        "final_generation"
    ]
    assert final["status"] == "ambiguous"
    assert final["stage_id"] is None
    assert final["saved_export_prompts"]["positive"] is None
    graph.pop("save2")
    graph["switch"] = {
        "class_type": "ComfySwitchNode",
        "inputs": {"switch": ["unknown", 0], "on_false": ["decode", 0], "on_true": ["s2", 0]},
    }
    graph["save"]["inputs"]["images"] = ["switch", 0]
    final = inspect_generation_evidence(graph, None)["final_generation"]
    assert final["status"] == "ambiguous"
    assert final["positive"]["text"] is None


def test_v3_multiple_conditionings_cannot_be_joined_into_one_final_prompt() -> None:
    graph = _final_graph()
    graph["p2"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "another", "clip": ["clip", 0]},
    }
    graph["combine"] = {
        "class_type": "ConditioningCombine",
        "inputs": {"conditioning_1": ["p", 0], "conditioning_2": ["p2", 0]},
    }
    graph["s"]["inputs"]["positive"] = ["combine", 0]
    final = inspect_generation_evidence(graph, None)["final_generation"]
    assert final["positive"]["text"] is None
    assert final["positive"]["status"] == "ambiguous"


def test_v3_basic_pipe_passthrough_vae_output_is_not_generation() -> None:
    graph = _final_graph()
    graph["vae"] = {"class_type": "VAELoader", "inputs": {"vae_name": "qa-vae"}}
    graph["pipe"] = {
        "class_type": "ToBasicPipe",
        "inputs": {
            "model": ["base", 0],
            "clip": ["clip", 0],
            "vae": ["vae", 0],
            "positive": ["p", 0],
            "negative": ["n", 0],
        },
    }
    graph["s"] = {"class_type": "ImpactKSamplerBasicPipe", "inputs": {"basic_pipe": ["pipe", 0]}}
    graph["decode"]["inputs"] = {"vae": ["s", 2]}
    final = inspect_generation_evidence(graph, None)["final_generation"]
    assert final["stage_id"] is None
    assert final["stages"] == []
    graph["decode"]["inputs"]["samples"] = ["s", 1]
    assert inspect_generation_evidence(graph, None)["final_generation"]["stage_id"] == "s"


def test_v3_exact_trigger_empty_original_known_override_and_unknown_override() -> None:
    graph = _final_graph(positive=["trigger", 0])
    graph["trigger"] = {
        "class_type": "TriggerWord Toggle (LoraManager)",
        "inputs": {"trigger_words": "", "toggle_trigger_words": {"__value__": []}},
    }
    assert inspect_generation_evidence(graph, None)["final_generation"]["positive"]["text"] == ""
    graph["trigger"]["inputs"]["orinalMessage"] = "old"
    graph["trigger"]["inputs"]["trigger_words"] = "new"
    assert inspect_generation_evidence(graph, None)["final_generation"]["positive"]["text"] == "new"
    graph["trigger"]["inputs"]["trigger_words"] = ["unrecorded", 0]
    assert inspect_generation_evidence(graph, None)["final_generation"]["positive"]["text"] is None


def test_v3_unknown_conditioning_node_does_not_promote_one_encoder() -> None:
    graph = _final_graph()
    graph["toggle"] = {
        "class_type": "UnknownConditioningToggle",
        "inputs": {"conditioning": ["p", 0], "enabled": False},
    }
    graph["s"]["inputs"]["positive"] = ["toggle", 0]
    final = inspect_generation_evidence(graph, None)["final_generation"]
    assert final["positive"]["text"] is None
    assert final["positive"]["status"] == "ambiguous"


def test_v3_parameters_only_preserves_explicit_empty_negative_without_header_text() -> None:
    final = inspect_generation_evidence(
        None, None, parameters="QA final\nNegative prompt:\nSteps: 8"
    )["final_generation"]
    assert final["saved_export_prompts"]["positive"]["text"] == "QA final"
    assert final["saved_export_prompts"]["negative"]["text"] == ""
    assert final["models"] == final["loras"] == []


def test_v3_unknown_basic_pipe_branch_keeps_loras_and_models_unconfirmed() -> None:
    graph = _final_graph()
    graph["other-base"] = {
        "class_type": "UNETLoader",
        "inputs": {"unet_name": "other-base.safetensors"},
    }
    for suffix, model in (("a", "base"), ("b", "other-base")):
        graph[suffix] = _usage_lora(suffix, model=[model, 0])
        graph[f"pipe-{suffix}"] = {
            "class_type": "ToBasicPipe",
            "inputs": {
                "model": [suffix, 0],
                "positive": ["p", 0],
                "negative": ["n", 0],
            },
        }
    graph["switch"] = {
        "class_type": "ComfySwitchNode",
        "inputs": {
            "switch": ["unrecorded", 0],
            "on_false": ["pipe-a", 0],
            "on_true": ["pipe-b", 0],
        },
    }
    graph["s"] = {
        "class_type": "ImpactKSamplerBasicPipe",
        "inputs": {"basic_pipe": ["switch", 0]},
    }
    graph["decode"]["inputs"]["samples"] = ["s", 1]
    evidence = inspect_generation_evidence(graph, None)
    final = evidence["final_generation"]
    assert final["loras"] == []
    assert {row["name"] for row in evidence["candidate_loras"]} == {"a", "b"}
    assert final["lora_source"]["status"] == "missing"
    assert final["models"] == []
    assert final["model_family"] is None
    assert final["positive"]["text"] is None


def test_v3_exact_append_tidy_preserves_single_newline_and_edge_commas() -> None:
    graph = _final_graph(positive=["append", 0])
    graph["append"] = {
        "class_type": "StringFunction|pysssss",
        "inputs": {
            "action": "append",
            "tidy_tags": "yes",
            "text_a": ",alpha\nbeta,",
            "text_b": " gamma,, ",
        },
    }
    final = inspect_generation_evidence(graph, None)["final_generation"]
    assert final["positive"]["status"] == "exact"
    assert final["positive"]["text"] == ",alpha\nbeta, gamma,"
    graph["append"]["inputs"].update(tidy_tags="no", text_a=" ,alpha\nbeta, ", text_b="tail")
    assert inspect_generation_evidence(graph, None)["final_generation"]["positive"]["text"] == (
        " ,alpha\nbeta, tail"
    )


def test_v3_exact_append_rejects_unrecorded_or_unknown_tidy_control() -> None:
    graph = _final_graph(positive=["append", 0])
    graph["append"] = {
        "class_type": "StringFunction|pysssss",
        "inputs": {"action": "append", "text_a": "alpha", "text_b": "beta"},
    }
    for control in (None, "unsupported", ["unrecorded", 0]):
        graph["append"]["inputs"]["tidy_tags"] = control
        final = inspect_generation_evidence(graph, None)["final_generation"]
        assert final["positive"]["text"] is None
        assert final["positive"]["status"] == "unavailable"
    graph["append"]["inputs"].pop("tidy_tags")
    assert inspect_generation_evidence(graph, None)["final_generation"]["positive"]["text"] is None


def test_v4_four_saved_hashes_override_twenty_two_graph_active_rows() -> None:
    graph = _final_graph()
    graph["l"] = {
        "class_type": "Lora Loader (LoraManager)",
        "inputs": {
            "model": ["base", 0],
            "loras": {
                "__value__": [
                    {"name": f"graph-{i}", "active": True, "strength": 0.8} for i in range(22)
                ]
            },
        },
    }
    graph["s"]["inputs"]["model"] = ["l", 0]
    hashes = ", ".join(f"saved-{i}: {i + 1:010X}" for i in range(4))
    evidence = inspect_generation_evidence(
        graph, None, parameters=f'QA\nSteps: 8, Lora hashes: "{hashes}"'
    )
    final = evidence["final_generation"]
    assert evidence["extractor_version"] == 4
    assert len(evidence["loras"]) == 22
    assert [row["name"] for row in final["loras"]] == [f"saved-{i}" for i in range(4)]
    assert all(row["strength_model"] is None for row in final["loras"])
    assert final["lora_source"]["status"] == "recorded"
    assert final["lora_source"]["fields"] == ["Lora hashes"]
    other = inspect_generation_evidence(
        graph, None, saved_metadata={"Lora hashes": "other: ABCDEF1234"}
    )
    assert [row["name"] for row in other["final_generation"]["loras"]] == ["other"]


def test_v4_missing_saved_list_is_unknown_even_when_graph_has_active_lora() -> None:
    graph = _final_graph()
    graph["l"] = _usage_lora("graph-active", model=["base", 0])
    graph["s"]["inputs"]["model"] = ["l", 0]
    evidence = inspect_generation_evidence(graph, None)
    assert evidence["loras"][0]["name"] == "graph-active"
    assert evidence["final_generation"]["loras"] == []
    assert evidence["final_generation"]["lora_source"]["status"] == "missing"


def test_v4_runtime_resources_strict_kind_and_explicit_empty_are_distinct() -> None:
    rows = [
        {
            "kind": "lora",
            "status": "resolved",
            "name": "used",
            "hash": "ABCDEF1234",
            "weight": -0.2,
        },
        {
            "kind": "url",
            "type": "lora",
            "status": "resolved",
            "name": "manual",
            "hash": "BBBBBBBBBB",
        },
        {"kind": "lora", "status": "missing", "name": "missing"},
        {"kind": "lora", "status": "duplicate", "name": "duplicate", "hash": "ABCDEF1234"},
    ]
    final = inspect_generation_evidence(
        None,
        None,
        saved_metadata={"resources_json": json.dumps(rows), "Lora hashes": "extra: CCCCCCCCCC"},
    )["final_generation"]
    assert [row["name"] for row in final["loras"]] == ["used"]
    assert final["loras"][0]["strength_model"] == -0.2
    assert final["loras"][0]["strength_clip"] is None
    assert final["lora_source"]["status"] == "partial"
    empty = inspect_generation_evidence(None, None, saved_metadata={"resources_json": "[]"})
    assert empty["final_generation"]["lora_source"]["status"] == "recorded_empty"
    assert empty["final_generation"]["loras"] == []


def test_v4_hash_members_enriched_only_by_explicit_same_png_identity() -> None:
    fields = {
        "Lora hashes": "stem-a: ABCDEF1234, stem-b: BBBBBBBBBB",
        "additional_hashes": "stem-a:ABCDEF1234:0.3,checkpoint:CCCCCCCCCC:1,stem-b:EEEEEEEEEE:0.9",
        "Civitai resources": [
            {
                "modelName": "different display",
                "hash": "BBBBBBBBBB",
                "type": "lora",
                "weight": 0.05,
            },
            {"modelName": "not a stem", "type": "lora", "weight": 0.99},
        ],
    }
    final = inspect_generation_evidence(None, None, saved_metadata=fields)["final_generation"]
    assert [(row["name"], row["strength_model"]) for row in final["loras"]] == [
        ("stem-a", 0.3),
        ("stem-b", 0.05),
    ]
    assert len(final["loras"]) == 2


def test_v4_civitai_fallback_filters_resource_kind_without_model_family_guess() -> None:
    resources = [
        {"modelName": "base", "air": "urn:air:krea2:unet:civitai:1@2"},
        {"modelName": "style", "air": "urn:air:anima:lora:civitai:3@4", "weight": 0.5},
        {"modelName": "tool", "type": "LoCon", "weight": 0},
        {"modelName": "unknown", "weight": 1},
    ]
    final = inspect_generation_evidence(
        None, None, parameters=f"QA\nSteps: 8, Civitai resources: {json.dumps(resources)}"
    )["final_generation"]
    assert [row["name"] for row in final["loras"]] == ["style", "tool"]
    assert [row["strength_model"] for row in final["loras"]] == [0.5, 0]
    assert final["lora_source"]["fields"] == ["Civitai resources"]
    assert final["model_family"] is None


def test_v4_hash_only_never_matches_civitai_weights_by_order_or_fuzzy_name() -> None:
    final = inspect_generation_evidence(
        None,
        None,
        saved_metadata={
            "Lora hashes": "light_c1-st2000: B24C8D432F, Ps_impasto: E22D6DA913",
            "Civitai resources": [
                {"modelName": "Light style", "type": "lora", "weight": 0.3},
                {"modelName": "Ps impasto art", "type": "lora", "weight": 0.05},
            ],
        },
    )["final_generation"]
    assert [row["strength_model"] for row in final["loras"]] == [None, None]


def test_v4_quotes_settings_boundaries_invalid_source_and_numeric_safety() -> None:
    parameters = (
        'A prompt mentioning Lora hashes: "fake: DDDDDDDDDD"\n'
        'Steps: 8, Lora hashes: "stem: ABCDEF1234, another: BBBBBBBBBB", '
        'Civitai resources: [{"modelName":"unmatched, with colon:","type":"lora","weight":0.9}], '
        "Sampler: test"
    )
    final = inspect_generation_evidence(None, None, parameters=parameters)["final_generation"]
    assert [row["name"] for row in final["loras"]] == ["stem", "another"]
    invalid = inspect_generation_evidence(
        None, None, saved_metadata={"resources_json": "{bad", "Lora hashes": "valid: ABCDEF1234"}
    )["final_generation"]
    assert invalid["lora_source"]["status"] == "invalid"
    assert invalid["loras"] == []
    for value in (float("nan"), float("inf"), -float("inf"), 10**500):
        numeric = inspect_generation_evidence(
            None,
            None,
            saved_metadata={
                "resources_json": [
                    {"kind": "lora", "status": "resolved", "name": "a", "weight": value}
                ]
            },
        )["final_generation"]
        assert numeric["loras"][0]["strength_model"] is None
        assert numeric["lora_source"]["warnings"]
        json.dumps(numeric, allow_nan=False)


def test_v4_duplicate_hash_is_not_summed_and_conflicting_saved_weights_warn() -> None:
    final = inspect_generation_evidence(
        None,
        None,
        saved_metadata={
            "resources_json": [
                {
                    "kind": "lora",
                    "status": "resolved",
                    "name": "first",
                    "hash": "ABCDEF1234",
                    "weight": 0.3,
                },
                {
                    "kind": "lora",
                    "status": "resolved",
                    "name": "alias",
                    "hash": "ABCDEF1234",
                    "weight": 0.6,
                },
            ]
        },
    )["final_generation"]
    assert [(row["name"], row["strength_model"]) for row in final["loras"]] == [("first", 0.3)]
    assert final["lora_source"]["status"] == "partial"
    assert any("冲突" in warning for warning in final["lora_source"]["warnings"])


def test_v4_duplicate_stems_cannot_receive_unkeyed_resource_weight() -> None:
    final = inspect_generation_evidence(
        None,
        None,
        saved_metadata={
            "Lora hashes": "same: ABCDEF1234, same: BBBBBBBBBB",
            "Civitai resources": [{"modelName": "same", "type": "lora", "weight": 0.5}],
        },
    )["final_generation"]
    assert [row["strength_model"] for row in final["loras"]] == [None, None]
    assert final["lora_source"]["status"] == "partial"


def test_v4_explicit_empty_hashes_and_quoted_additional_weights() -> None:
    final = inspect_generation_evidence(None, None, parameters='QA\nSteps: 8, Lora hashes: ""')[
        "final_generation"
    ]
    assert final["lora_source"]["status"] == "recorded_empty"
    assert final["loras"] == []
    weighted = inspect_generation_evidence(
        None,
        None,
        parameters=(
            'QA\nSteps: 8, Lora hashes: "a: ABCDEF1234", additional_hashes: "a:ABCDEF1234:0.25"'
        ),
    )["final_generation"]
    assert weighted["loras"][0]["strength_model"] == 0.25


def test_v4_saved_plugin_field_aliases_and_hash_fragment_prefix() -> None:
    for key, value in (
        ("lora_hashes", 'Lora hashes: "saved: ABCDEF1234"'),
        ("LORA_HASHES", "saved: ABCDEF1234"),
        ("lora hashes", '"saved: ABCDEF1234"'),
    ):
        final = inspect_generation_evidence(None, None, saved_metadata={key: value})[
            "final_generation"
        ]
        assert [row["name"] for row in final["loras"]] == ["saved"]
        assert final["lora_source"]["status"] == "recorded"
    resources = inspect_generation_evidence(
        None,
        None,
        saved_metadata={
            "civitai_resources": '[{"modelName":"saved display","type":"lora","weight":0.5}]'
        },
    )["final_generation"]
    assert resources["loras"][0]["name"] == "saved display"
