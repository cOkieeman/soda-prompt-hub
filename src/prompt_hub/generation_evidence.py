from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Any

from prompt_hub.saved_lora_metadata import inspect_saved_loras

MAX_GRAPH_NODES = 5000
EXTRACTOR_VERSION = 4
MAX_GENERATION_STAGES = 64
PIPE_FIELDS = ("model", "clip", "vae", "positive", "negative")
POSTPROCESS_SAMPLERS = {"detailerforeachpipe", "ultimatesdupscale"}
MAX_GRAPH_LINKS = 25000
MAX_SUBGRAPH_DEPTH = 8
MAX_VALUE_DEPTH = 60
MAX_COLLECTION_DEPTH = 6
MAX_TEXT_LENGTH = 100000
MAX_NUMERIC_TEXT_LENGTH = 100
TRIGGER_ROWS_WIDGET_INDEX = 3
TRIGGER_ORIGINAL_WIDGET_INDEX = 4
BASIC_PIPE_SAMPLER_VAE_PORT = 2
LINK_INPUT_LENGTH = 2
GUI_LINK_LENGTH = 6
MUTED_MODE = 2
BYPASS_MODE = 4
UNKNOWN = object()
STANDARD_LORA_TYPES = {"loraloader", "loraloadermodelonly"}
SAMPLER_TYPES = {
    "ksampler",
    "ksampleradvanced",
    "impactksamplerbasicpipe",
    "impactksampleradvancedbasicpipe",
    "lanpaint_ksampler",
    "samplercustom",
    "samplercustomadvanced",
    "ultimatesdupscale",
    "detailerforeachpipe",
}
SAMPLING_FIELDS = ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise")
MODEL_SCHEMAS = {
    "checkpointloadersimple": ("ckpt_name", "checkpoint"),
    "checkpointloader": ("ckpt_name", "checkpoint"),
    "checkpoint loader with name (image saver)": ("ckpt_name", "checkpoint"),
    "unetloader": ("unet_name", "diffusion_model"),
    "unet loader with name (image saver)": ("unet_name", "diffusion_model"),
    "cliploader": ("clip_name", "text_encoder"),
    "dualcliploader": ("clip_name1", "text_encoder"),
    "triplecliploader": ("clip_name1", "text_encoder"),
    "vaeloader": ("vae_name", "vae"),
    "seedvr2loadvaemodel": ("model", "vae"),
    "seedvr2loadditmodel": ("model", "upscale_model"),
    "upscalemodelloader": ("model_name", "upscale_model"),
    "modelpatchloader": ("name", "unknown"),
}
# Explicit schemas include controls which are serialized but are not node inputs.
WIDGET_SCHEMAS = {
    "loraloader": ("lora_name", "strength_model", "strength_clip"),
    "loraloadermodelonly": ("lora_name", "strength_model"),
    "ksampler": ("seed", None, "steps", "cfg", "sampler_name", "scheduler", "denoise"),
    "impactksamplerbasicpipe": (
        "seed",
        None,
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "denoise",
    ),
    "lanpaint_ksampler": (
        "seed",
        None,
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "denoise",
    ),
    "ksampleradvanced": (
        "add_noise",
        "noise_seed",
        None,
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "start_at_step",
        "end_at_step",
        "return_with_leftover_noise",
    ),
    "input parameters (image saver)": (
        "seed",
        None,
        "steps",
        "cfg",
        "sampler",
        "scheduler",
        "denoise",
    ),
    "lora loader (loramanager)": (None, "text", "loras"),
    "lora stacker (loramanager)": (None, "text", "loras"),
    "impactwildcardencode": (
        "wildcard_text",
        "populated_text",
        "mode",
        "Select to add LoRA",
        "Select to add Wildcard",
        "seed",
        None,
    ),
    "impactwildcardprocessor": (
        "wildcard_text",
        "populated_text",
        "mode",
        "seed",
        None,
        "Select to add Wildcard",
    ),
    "seed (rgthree)": ("seed",),
    "primitiveint": ("value", None),
    "primitiveboolean": ("value",),
    "primitivestring": ("value",),
    "primitivestringmultiline": ("value",),
    "floatconstant": ("value",),
    "boolconstant": ("value",),
    "string literal": ("string",),
    "int literal": ("int",),
    "cfg literal": ("float",),
    "cliptextencode": ("text",),
    "pclazytextencode": ("text",),
    "textencodeqwenimage21": ("prompt", "negative_prompt", "resolution"),
    "emptylatentimage": ("width", "height", "batch_size"),
    "emptysd3latentimage": ("width", "height", "batch_size"),
    "emptyqnimage21latentimage": ("width", "height", "batch_size"),
    "resolutionmastersimplify": ("width", "height"),
    "unetloader": ("unet_name", "weight_dtype"),
    "unet loader with name (image saver)": ("unet_name", "weight_dtype"),
    "checkpointloadersimple": ("ckpt_name",),
    "checkpoint loader with name (image saver)": ("ckpt_name",),
    "cliploader": ("clip_name", "type", "device"),
    "vaeloader": ("vae_name",),
    "upscalemodelloader": ("model_name",),
    "modelpatchloader": ("name",),
    "promptselector": ("selected_prompts", None),
    "stringconcatenate": ("string_a", "string_b", "delimiter"),
    "stringfunction|pysssss": ("action", "tidy_tags", "text_a", "text_b", "text_c"),
    "comfyswitchnode": ("switch",),
    "switch string [crystools]": ("on_true", "on_false", "boolean"),
    "randomnoise": ("noise_seed", None),
    "ksamplerselect": ("sampler_name",),
    "basicscheduler": ("scheduler", "steps", "denoise"),
    "cfgguider": ("cfg",),
    "image saver": (
        "filename",
        "path",
        "extension",
        "steps",
        "cfg",
        "modelname",
        "sampler_name",
        "scheduler_name",
        "positive",
        "negative",
        "seed_value",
        "width",
        "height",
        "lossless_webp",
        "quality_jpeg_or_webp",
        "optimize_png",
        "counter",
        "denoise",
        "clip_skip",
        "time_format",
        "save_workflow_as_json",
        "embed_workflow",
        "additional_hashes",
        "download_civitai_data",
        "easy_remix",
        "show_preview",
        "custom",
        "label",
    ),
}
CONSTANT_FIELDS = {
    "string literal": "string",
    "int literal": "int",
    "cfg literal": "float",
    "primitivestring": "value",
    "primitivestringmultiline": "value",
    "primitiveint": "value",
    "primitiveboolean": "value",
    "floatconstant": "value",
    "boolconstant": "value",
    "impactfloat": "value",
    "primitive float [crystools]": "float",
    "seed (rgthree)": "seed",
    "float": "Number",
}
OUTPUT_FIELDS = {
    "resolutionmastersimplify": {0: "width", 1: "height"},
    "input parameters (image saver)": dict(
        enumerate(("seed", "steps", "cfg", "sampler", "scheduler", "denoise"))
    ),
    "unet loader with name (image saver)": {1: "unet_name"},
    "checkpoint loader with name (image saver)": {3: "ckpt_name"},
}


def _type(node: Mapping[str, Any]) -> str:
    return str(node.get("class_type", "")).casefold()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _items(value: Any, limit: int) -> list[Any]:
    return value[:limit] if isinstance(value, list) else []


def _reference(value: Any) -> tuple[str, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == LINK_INPUT_LENGTH
        and isinstance(value[0], (str, int))
        and not isinstance(value[0], bool)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
    ):
        return str(value[0]), value[1]
    return None


def _is_output(node: Mapping[str, Any]) -> bool:
    compact = _type(node).replace(" ", "").replace("_", "")
    return compact.startswith(("saveimage", "imagesaver", "previewimage"))


def _gui_link(value: Any) -> tuple[Any, Any, Any, Any] | None:
    if isinstance(value, list) and len(value) >= GUI_LINK_LENGTH:
        return value[1], value[2], value[3], value[4]
    if isinstance(value, Mapping) and all(
        key in value for key in ("origin_id", "origin_slot", "target_id", "target_slot")
    ):
        return value["origin_id"], value["origin_slot"], value["target_id"], value["target_slot"]
    return None


def _widget_inputs(node: Mapping[str, Any], warnings: set[str]) -> dict[str, Any]:
    widgets = node.get("widgets_values", [])
    if isinstance(widgets, Mapping):
        return dict(widgets)
    if not isinstance(widgets, list):
        return {}
    schema = WIDGET_SCHEMAS.get(str(node.get("type", "")).casefold())
    if schema is not None:
        return {key: value for key, value in zip(schema, widgets, strict=False) if key}
    declared = [
        item
        for item in _items(node.get("inputs"), MAX_GRAPH_NODES)
        if isinstance(item, Mapping) and isinstance(item.get("widget"), Mapping)
    ]
    if len(declared) != len(widgets):
        return {}
    result = {}
    for item, value in zip(declared, widgets, strict=True):
        data_type = str(item.get("type", ""))
        valid = True
        if data_type == "BOOLEAN":
            valid = isinstance(value, bool)
        elif data_type in {"INT", "FLOAT"}:
            valid = _number(value) is not None
        elif data_type in {"STRING", "COMBO"}:
            valid = isinstance(value, str)
        if valid:
            result[str(item.get("name", ""))] = value
        else:
            warnings.add("部分 widget 与声明类型不一致，已忽略可能过时的静态值。")
    return result


class _SavedGraph:
    def __init__(self, prompt: Any, workflow: Any) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.warnings: set[str] = set()
        self.link_count = 0
        self.usage_visit_count = 0
        self.gui = True
        if isinstance(prompt, Mapping):
            for key, value in list(prompt.items())[:MAX_GRAPH_NODES]:
                if isinstance(value, Mapping) and value.get("class_type"):
                    self.nodes[str(key)] = {**value, "inputs": dict(_mapping(value.get("inputs")))}
            if len(prompt) > MAX_GRAPH_NODES:
                self.warnings.add("节点数量超过识别上限，记录可能不完整。")
        if self.nodes:
            self.gui = False
            return
        definitions = _mapping(_mapping(workflow).get("definitions")).get("subgraphs", [])
        self.definitions = {
            str(item["id"]): item
            for item in _items(definitions, MAX_GRAPH_NODES)
            if isinstance(item, Mapping) and "id" in item
        }
        self._flatten(_mapping(workflow), "", {}, (), 0)

    def _add(self, key: str, node: dict[str, Any]) -> bool:
        if len(self.nodes) >= MAX_GRAPH_NODES:
            self.warnings.add("节点数量超过识别上限，记录可能不完整。")
            return False
        self.nodes[key] = node
        return True

    def _graph_links(
        self,
        graph: Mapping[str, Any],
        prefix: str,
        boundaries: Mapping[int, Any],
    ) -> tuple[dict[str, dict[int, Any]], dict[int, Any]]:
        incoming: dict[str, dict[int, Any]] = {}
        outputs = {}
        for raw_link in _items(graph.get("links"), MAX_GRAPH_LINKS):
            if self.link_count >= MAX_GRAPH_LINKS:
                self.warnings.add("连接数量超过识别上限，记录可能不完整。")
                break
            self.link_count += 1
            link = _gui_link(raw_link)
            if link is None:
                continue
            origin, origin_slot, target, target_slot = link
            if not isinstance(origin_slot, int) or not isinstance(target_slot, int):
                continue
            source_id = f"{prefix}{origin}"
            if str(origin) == "-10":
                source_id = f"{prefix}@input:{origin_slot}"
                self._add(
                    source_id,
                    {
                        "class_type": "@boundary",
                        "inputs": {"value": boundaries.get(origin_slot, UNKNOWN)},
                    },
                )
            source = [source_id, origin_slot if str(origin) != "-10" else 0]
            if str(target) == "-20":
                outputs[target_slot] = source
            else:
                incoming.setdefault(str(target), {})[target_slot] = source
        if isinstance(graph.get("links"), list) and len(graph["links"]) > MAX_GRAPH_LINKS:
            self.warnings.add("连接数量超过识别上限，记录可能不完整。")
        return incoming, outputs

    def _flatten(
        self,
        graph: Mapping[str, Any],
        prefix: str,
        boundaries: Mapping[int, Any],
        ancestry: tuple[str, ...],
        parent_mode: Any,
    ) -> dict[int, Any]:
        if len(self.nodes) >= MAX_GRAPH_NODES:
            self.warnings.add("节点数量超过识别上限，记录可能不完整。")
            return {}
        incoming, outputs = self._graph_links(graph, prefix, boundaries)
        wrappers = []
        for raw in _items(graph.get("nodes"), MAX_GRAPH_NODES):
            if not isinstance(raw, Mapping) or "id" not in raw or not raw.get("type"):
                continue
            node_id = f"{prefix}{raw['id']}"
            inputs = _widget_inputs(raw, self.warnings)
            links = incoming.get(str(raw["id"]), {})
            declarations = _items(raw.get("inputs"), MAX_GRAPH_NODES)
            for slot, source in links.items():
                declaration = declarations[slot] if 0 <= slot < len(declarations) else {}
                key = str(_mapping(declaration).get("name", f"@input:{slot}"))
                inputs[key] = source
            mode = parent_mode if parent_mode in {MUTED_MODE, BYPASS_MODE} else raw.get("mode", 0)
            if (
                not isinstance(mode, int)
                or isinstance(mode, bool)
                or mode not in {0, MUTED_MODE, BYPASS_MODE}
            ):
                self.warnings.add("存在未知的节点模式，未将其内容视为启用记录。")
                mode = 1
            normalized = {
                **raw,
                "class_type": raw["type"],
                "inputs": inputs,
                "mode": mode,
                "_links": links,
                "_input_declarations": declarations,
            }
            if not self._add(node_id, normalized):
                break
            definition_id = str(raw["type"])
            if definition_id in self.definitions:
                boundary_values = {
                    index: inputs.get(str(_mapping(item).get("name", "")), UNKNOWN)
                    for index, item in enumerate(declarations)
                }
                boundary_values.update(links)
                wrappers.append((node_id, definition_id, boundary_values, mode))
        for node_id, definition_id, values, mode in wrappers:
            if definition_id in ancestry or len(ancestry) >= MAX_SUBGRAPH_DEPTH:
                self.warnings.add("子图存在循环或超过深度上限，未展开的部分保留为未知。")
                self.nodes[node_id]["_outputs"] = {}
                continue
            self.nodes[node_id]["_outputs"] = self._flatten(
                self.definitions[definition_id],
                f"{node_id}/",
                values,
                (*ancestry, definition_id),
                mode,
            )
        return outputs

    def _switch_values(self, node: Mapping[str, Any]) -> list[Any] | None:
        inputs = _mapping(node.get("inputs"))
        kind = _type(node)
        if kind in {"comfyswitchnode", "switch string [crystools]"}:
            flag = self.resolve(inputs.get("switch", inputs.get("boolean", UNKNOWN)))
            if isinstance(flag, bool):
                return [inputs.get("on_true" if flag else "on_false", UNKNOWN)]
            self.warnings.add("条件分支无法从保存记录确定，列出的分支仅为候选。")
            return [inputs.get("on_false", UNKNOWN), inputs.get("on_true", UNKNOWN)]
        if kind == "any switch (rgthree)":
            candidates = [value for key, value in inputs.items() if key.startswith("any_")]
            candidates = [
                value
                for value in candidates
                if value is not None
                and not (
                    (ref := _reference(value))
                    and self.nodes.get(ref[0], {}).get("mode", 0) == MUTED_MODE
                )
            ]
            for index, value in enumerate(candidates):
                ref = _reference(value)
                if ref and self.nodes.get(ref[0], {}).get("mode", 0) == MUTED_MODE:
                    continue
                resolved = self.resolve(value)
                if resolved is UNKNOWN:
                    if len(candidates[index:]) > 1:
                        self.warnings.add("Any Switch 的运行时空值无法确认，后续连接仅为候选。")
                    return candidates[index:]
                if resolved is not None:
                    return [value]
            return []
        return None

    def dependencies(self, node_id: str, port: int = 0) -> list[Any]:
        node = self.nodes[node_id]
        if node.get("mode", 0) == MUTED_MODE:
            return []
        if node.get("mode", 0) == BYPASS_MODE:
            return [self._bypass_value(node, port)]
        if "_outputs" in node and node.get("mode", 0) != BYPASS_MODE:
            return [node["_outputs"].get(port, UNKNOWN)]
        if _type(node) == "@boundary":
            return [node["inputs"]["value"]]
        switched = self._switch_values(node)
        if switched is not None:
            return switched
        inputs = _mapping(node.get("inputs"))
        values = list(inputs.values())
        if _is_output(node):
            image_keys = [key for key in inputs if key in {"images", "image"}]
            if image_keys:
                values = [inputs[key] for key in image_keys]
        return values

    @staticmethod
    def _bypass_value(node: Mapping[str, Any], port: int) -> Any:
        inputs = _mapping(node.get("inputs"))
        if _type(node) in STANDARD_LORA_TYPES:
            return inputs.get(
                "model" if port == 0 else "clip", _mapping(node.get("_links")).get(port)
            )
        outputs = _items(node.get("outputs"), MAX_GRAPH_NODES)
        output_type = _mapping(outputs[port]).get("type") if 0 <= port < len(outputs) else None
        declarations = _items(node.get("_input_declarations"), MAX_GRAPH_NODES)
        matching = [
            inputs.get(str(_mapping(item).get("name", "")), UNKNOWN)
            for item in declarations
            if output_type is not None
            and _mapping(item).get("type") == output_type
            and _reference(inputs.get(str(_mapping(item).get("name", "")))) is not None
        ]
        return matching[0] if len(matching) == 1 else None

    def walk(self, roots: list[Any]) -> set[str]:
        selected = set()
        visited = set()
        pending = [(value, 0) for value in roots]
        while pending:
            value, depth = pending.pop()
            ref = _reference(value)
            if ref is None or ref in visited or ref[0] not in self.nodes:
                continue
            if depth >= MAX_VALUE_DEPTH:
                self.warnings.add("连接链超过识别深度上限，记录可能不完整。")
                continue
            visited.add(ref)
            node_id, port = ref
            selected.add(node_id)
            pending.extend((item, depth + 1) for item in self.dependencies(node_id, port))
        return selected

    def lora_usage(
        self, root: str, *, roots: list[Any] | None = None, all_nodes: bool = False
    ) -> dict[str, dict[str, Any]]:
        """Track consumed ports and uncertain branches without executing nodes."""
        usage: dict[str, dict[str, Any]] = {}
        pending = [(value, 0, "") for value in (roots if roots is not None else [[root, 0]])]
        visited: set[tuple[str, int, bool]] = set()
        while pending:
            value, depth, reason = pending.pop()
            ref = _reference(value)
            if ref is None or ref[0] not in self.nodes:
                continue
            visit = (*ref, bool(reason))
            if visit in visited:
                continue
            visited.add(visit)
            self.usage_visit_count += 1
            if self.usage_visit_count > MAX_GRAPH_LINKS:
                self.warnings.add("连接链超过识别上限，未确认的部分不计入已使用 LoRA。")
                break
            if depth >= MAX_VALUE_DEPTH:
                self.warnings.add("连接链超过识别上限，未确认的部分不计入已使用 LoRA。")
                continue
            node_id, port = ref
            node = self.nodes[node_id]
            if node.get("mode", 0) == MUTED_MODE:
                continue
            reason = reason or {0: "", MUTED_MODE: "", BYPASS_MODE: ""}.get(
                node.get("mode", 0), "节点模式无法确认"
            )
            if node.get("mode", 0) == 0 and (all_nodes or "lora" in _type(node)):
                if _lora_output_schema(node) and port not in {0, 1}:
                    continue  # Trigger words / loaded-resources metadata are not patches.
                entry = usage.setdefault(
                    node_id, {"confirmed": set(), "candidate": set(), "reason": ""}
                )
                entry["candidate" if reason else "confirmed"].add(port)
                if reason:
                    entry["reason"] = reason
            values, uncertainty = self._usage_dependencies(node_id, port)
            pending.extend((item, depth + 1, reason or uncertainty) for item in values)
        return usage

    def pipe_refs(
        self, value: Any, field: str, seen: tuple[tuple[str, int], ...] = ()
    ) -> tuple[list[Any], bool]:
        ref = _reference(value)
        if ref is None or ref[0] not in self.nodes:
            return [UNKNOWN], False
        if ref in seen or len(seen) >= MAX_VALUE_DEPTH:
            self.warnings.add("BasicPipe 连接无法完整解析，未合并不同组件。")
            return [UNKNOWN], False
        node = self.nodes[ref[0]]
        inputs = _mapping(node.get("inputs"))
        kind = _type(node)
        if node.get("mode", 0) == MUTED_MODE:
            return [], True
        if kind == "tobasicpipe" and node.get("mode", 0) == 0:
            return [inputs.get(field, UNKNOWN)], True
        if kind == "frombasicpipe_v2" and ref[1] == 0:
            values, certain = [inputs.get("basic_pipe", UNKNOWN)], True
        else:
            values = self.dependencies(*ref)
            certain = (
                "_outputs" in node
                or kind
                in {
                    "@boundary",
                    "comfyswitchnode",
                    "switch string [crystools]",
                    "any switch (rgthree)",
                }
                or node.get("mode", 0) == BYPASS_MODE
            )
        if not certain:
            return values, False
        parts = [self.pipe_refs(item, field, (*seen, ref)) for item in values]
        return [item for refs, _ in parts for item in refs], len(values) == 1 and all(
            flag for _, flag in parts
        )

    def stage_roots(self, node_id: str, field: str) -> tuple[list[Any], bool]:
        inputs = _mapping(self.nodes[node_id].get("inputs"))
        if "basic_pipe" in inputs:
            return self.pipe_refs(inputs["basic_pipe"], field)
        guider = _reference(inputs.get("guider"))
        if (
            guider
            and guider[0] in self.nodes
            and _type(self.nodes[guider[0]]) in {"cfgguider", "basicguider"}
        ):
            return [self.nodes[guider[0]]["inputs"].get(field, UNKNOWN)], True
        return [inputs.get(field, UNKNOWN)], True

    def _pipe_usage(self, node_id: str, port: int) -> tuple[list[Any], str] | None:
        node = self.nodes[node_id]
        kind = _type(node)
        inputs = _mapping(node.get("inputs"))
        if kind in {"impactksamplerbasicpipe", "impactksampleradvancedbasicpipe"}:
            if port == 0:
                return [inputs.get("basic_pipe", UNKNOWN)], ""
            if port == BASIC_PIPE_SAMPLER_VAE_PORT:
                values, certain = self.pipe_refs(inputs.get("basic_pipe", UNKNOWN), "vae")
                return values, "" if certain else "BasicPipe VAE 来源无法确认"
        if kind in {"frombasicpipe", "frombasicpipe_v2"}:
            index = port - (1 if kind == "frombasicpipe_v2" else 0)
            if 0 <= index < len(PIPE_FIELDS):
                values, certain = self.pipe_refs(
                    inputs.get("basic_pipe", UNKNOWN), PIPE_FIELDS[index]
                )
                return values, "" if certain else "BasicPipe 组件来源无法确认"
        if kind in SAMPLER_TYPES and "basic_pipe" in inputs:
            parts = [
                self.stage_roots(node_id, field) for field in ("model", "positive", "negative")
            ]
            values = [value for refs, _ in parts for value in refs]
            values.extend(
                inputs[key] for key in ("latent_image", "image", "samples") if key in inputs
            )
            return values, "" if all(flag for _, flag in parts) else "BasicPipe 组件来源无法确认"
        if kind == "impactwildcardencode" and port in {0, 1, 2}:
            return [inputs.get("model" if port == 0 else "clip", UNKNOWN)], ""
        return None

    def _usage_dependencies(self, node_id: str, port: int) -> tuple[list[Any], str]:
        node = self.nodes[node_id]
        kind = _type(node)
        inputs = _mapping(node.get("inputs"))
        if (
            node.get("mode", 0) in {MUTED_MODE, BYPASS_MODE}
            or "_outputs" in node
            or kind == "@boundary"
        ):
            return self.dependencies(node_id, port), ""
        if _lora_output_schema(node):
            return [inputs.get("model" if port == 0 else "clip", UNKNOWN)], ""
        piped = self._pipe_usage(node_id, port)
        if piped is not None:
            return piped
        if kind in {"comfyswitchnode", "switch string [crystools]"}:
            flag = self.resolve(inputs.get("switch", inputs.get("boolean", UNKNOWN)))
            return self.dependencies(node_id, port), "" if isinstance(
                flag, bool
            ) else "条件分支无法确认"
        if kind == "any switch (rgthree)":
            values = self._switch_values(node) or []
            return values, "Any Switch 的运行时选择无法确认" if len(values) > 1 else ""
        values = self.dependencies(node_id, port)
        known = kind in SAMPLER_TYPES or kind in {
            "vaedecode",
            "vaedecodetiled",
            "vaeencode",
            "vaeencodetiled",
            "tobasicpipe",
            "frombasicpipe",
            "cliptextencode",
            "pclazytextencode",
            "textencodeqwenimage21",
            "seedvr2videoupscaler",
            "seedvr2loadditmodel",
            "seedvr2loadvaemodel",
            "cfgguider",
            "randomnoise",
            "basicscheduler",
            "ksamplerselect",
            "layerutility: purgevram v2",
        }
        reason = "自定义节点的输出依赖无法确认" if not known and not _is_output(node) else ""
        return values, reason

    def resolve(self, value: Any, seen: tuple[tuple[str, int], ...] = ()) -> Any:
        ref = _reference(value)
        if ref is None:
            return value
        if ref[0] not in self.nodes or ref in seen or len(seen) >= MAX_VALUE_DEPTH:
            return UNKNOWN
        return self._resolve_node(ref, (*seen, ref))

    def _resolve_node(self, ref: tuple[str, int], path: tuple[tuple[str, int], ...]) -> Any:
        node = self.nodes[ref[0]]
        if node.get("mode", 0) == MUTED_MODE:
            return None
        inputs = _mapping(node.get("inputs"))
        kind = _type(node)
        if "_outputs" in node and node.get("mode", 0) != BYPASS_MODE:
            value = node["_outputs"].get(ref[1], UNKNOWN)
        elif kind == "@boundary":
            value = inputs.get("value", UNKNOWN)
        elif node.get("mode", 0) == BYPASS_MODE:
            value = self._bypass_value(node, ref[1])
        elif kind in CONSTANT_FIELDS:
            value = inputs.get(CONSTANT_FIELDS[kind], UNKNOWN)
        elif ref[1] in OUTPUT_FIELDS.get(kind, {}):
            value = inputs.get(OUTPUT_FIELDS[kind][ref[1]], UNKNOWN)
        else:
            return self._resolve_switch_or_text(node, path)
        return self.resolve(value, path)

    def _resolve_switch_or_text(
        self, node: Mapping[str, Any], path: tuple[tuple[str, int], ...]
    ) -> Any:
        inputs = _mapping(node.get("inputs"))
        kind = _type(node)
        if kind in {"comfyswitchnode", "switch string [crystools]"}:
            flag = self.resolve(inputs.get("switch", inputs.get("boolean", UNKNOWN)), path)
            if isinstance(flag, bool):
                return self.resolve(inputs.get("on_true" if flag else "on_false", UNKNOWN), path)
            return UNKNOWN
        if kind == "any switch (rgthree)":
            for key, item in inputs.items():
                if key.startswith("any_"):
                    resolved = self.resolve(item, path)
                    if resolved is not None:
                        return resolved
            return None
        return self._resolve_text(node, path)

    def _resolve_text(self, node: Mapping[str, Any], path: tuple[tuple[str, int], ...]) -> Any:
        kind = _type(node)
        inputs = _mapping(node.get("inputs"))
        if kind in {"reroute", "any to string (image saver)", "showtext|pysssss"}:
            values = [value for value in inputs.values() if _reference(value) is not None]
            if len(values) == 1:
                resolved = self.resolve(values[0], path)
                if kind == "any to string (image saver)" and isinstance(
                    resolved, (int, float, str)
                ):
                    resolved = str(resolved)
                return resolved
        if kind in {"impactwildcardencode", "impactwildcardprocessor"}:
            self.warnings.add("通配词文本为保存时的 populated_text，不能证明本次运行展开结果。")
            return inputs.get("populated_text", UNKNOWN)
        if kind in {"stringconcatenate", "stringfunction|pysssss"}:
            return self._combine_text(inputs, kind, path)
        if kind == "stringformat":
            return self._format_text(inputs, path)
        if kind == "triggerword toggle (loramanager)":
            return self._trigger_text(node)
        return self._resolve_prefix_or_unknown(inputs, kind, path)

    def _combine_text(
        self, inputs: Mapping[str, Any], kind: str, path: tuple[tuple[str, int], ...]
    ) -> Any:
        if kind == "stringconcatenate":
            a = self.resolve(inputs.get("string_a", ""), path)
            b = self.resolve(inputs.get("string_b", ""), path)
            delimiter = self.resolve(inputs.get("delimiter", ""), path)
            if all(isinstance(item, str) for item in (a, b, delimiter)):
                return (a + delimiter + b)[:MAX_TEXT_LENGTH]
        if kind == "stringfunction|pysssss" and inputs.get("action") == "append":
            values = [
                self.resolve(inputs.get(key, ""), path) for key in ("text_a", "text_b", "text_c")
            ]
            if all(isinstance(item, str) for item in values):
                tidy = inputs.get("tidy_tags") == "yes"
                text = (", " if tidy else "").join(item for item in values if item)
                if tidy:
                    text = re.sub(r"\s+", " ", text)
                    text = re.sub(r"\s+,", ",", text)
                    text = re.sub(r",+", ",", text).strip(" ,")
                return text[:MAX_TEXT_LENGTH]
        return UNKNOWN

    def _format_text(self, inputs: Mapping[str, Any], path: tuple[tuple[str, int], ...]) -> Any:
        template = inputs.get("f_string")
        if not isinstance(template, str) or len(template) > MAX_TEXT_LENGTH:
            return UNKNOWN
        tokens = list(re.finditer(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}", template))
        remainder = re.sub(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}", "", template)
        if "{" in remainder or "}" in remainder:
            return UNKNOWN
        result, cursor = [], 0
        for token in tokens:
            value = self.resolve(inputs.get(f"values.{token[1]}", UNKNOWN), path)
            if not isinstance(value, (str, int, float, bool)):
                return UNKNOWN
            result.extend((template[cursor : token.start()], str(value)))
            cursor = token.end()
        result.append(template[cursor:])
        return "".join(result)[:MAX_TEXT_LENGTH]

    def _trigger_text(self, node: Mapping[str, Any]) -> Any:
        widgets = _items(node.get("widgets_values"), 100)
        rows = (
            widgets[TRIGGER_ROWS_WIDGET_INDEX]
            if len(widgets) > TRIGGER_ROWS_WIDGET_INDEX
            else UNKNOWN
        )
        if not isinstance(rows, list):
            return UNKNOWN
        values = []
        for row in rows[:100]:
            if not isinstance(row, Mapping) or row.get("active") is not True:
                continue
            if row.get("strength") is not None or not isinstance(row.get("text"), str):
                return UNKNOWN
            values.append(row["text"])
        self.warnings.add("触发词切换记录来自保存的 widget 状态，仍需与运行输出核对。")
        return ", ".join(values)[:MAX_TEXT_LENGTH]

    def _resolve_prefix_or_unknown(
        self, inputs: Mapping[str, Any], kind: str, path: tuple[tuple[str, int], ...]
    ) -> Any:
        if kind == "promptselector" and inputs.get("selected_prompts") == "":
            return self.resolve(inputs.get("prefix_prompt", ""), path)
        self.warnings.add("部分自定义节点输出无法静态解析；原始工作流保留，未执行表达式或扩展。")
        return UNKNOWN


def _number(value: Any) -> int | float | None:
    if (
        isinstance(value, str)
        and len(value) <= MAX_NUMERIC_TEXT_LENGTH
        and re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", value.strip())
    ):
        value = float(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        finite = math.isfinite(value)
    except OverflowError:
        return None
    return value if finite else None


def _seed(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 0 <= value < 2**64:
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"\d{1,20}", value) and int(value) < 2**64:
        return str(int(value))
    return None


def _lora_record(value: Mapping[str, Any]) -> dict[str, Any] | None:
    name = next(
        (value[key] for key in ("lora_name", "name", "lora") if isinstance(value.get(key), str)), ""
    )
    enabled = next((value[key] for key in ("enabled", "on", "active") if key in value), True)
    if not name.strip() or enabled is not True:
        return None
    model = next(
        (
            _number(value[key])
            for key in ("strength_model", "model_strength", "strength")
            if key in value
        ),
        None,
    )
    clip = next(
        (
            _number(value[key])
            for key in ("strength_clip", "clip_strength", "clipStrength", "strengthTwo")
            if key in value
        ),
        None,
    )
    if model == 0 and clip == 0:
        return None
    return {"name": name[:1000], "strength_model": model, "strength_clip": clip}


def _collection_records(value: Any, depth: int = 0) -> list[dict[str, Any]]:
    if depth >= MAX_COLLECTION_DEPTH:
        return []
    if isinstance(value, Mapping):
        record = _lora_record(value)
        if record:
            explicit = next(
                (value[key] for key in ("enabled", "on", "active") if key in value), None
            )
            return [{**record, "_activation_confirmed": explicit is True}]
        keys = [
            key
            for key in value
            if key in {"loras", "lora_stack", "lora_list", "__value__"}
            or str(key).startswith("lora_")
        ]
        return [item for key in keys[:100] for item in _collection_records(value[key], depth + 1)]
    return [item for child in _items(value, 100) for item in _collection_records(child, depth + 1)]


def _manager_records(value: Any, depth: int = 0) -> list[dict[str, Any]]:
    if depth >= MAX_COLLECTION_DEPTH:
        return []
    if isinstance(value, Mapping):
        if isinstance(value.get("name"), str):
            if value.get("active", False) is not True:
                return []
            strength = value.get("strength")
            record = _lora_record(
                {
                    "name": value["name"],
                    "strength_model": strength,
                    "strength_clip": value.get("clipStrength", strength),
                }
            )
            return [record] if record else []
        return [
            item
            for key in ("loras", "__value__")
            if key in value
            for item in _manager_records(value[key], depth + 1)
        ]
    return [item for child in _items(value, 100) for item in _manager_records(child, depth + 1)]


def _node_loras(node: Mapping[str, Any], graph: _SavedGraph) -> list[dict[str, Any]]:
    inputs = _mapping(node.get("inputs"))
    kind = _type(node)
    if kind in STANDARD_LORA_TYPES:
        values = {
            key: graph.resolve(inputs.get(key, UNKNOWN))
            for key in ("lora_name", "strength_model", "strength_clip")
        }
        if kind == "loraloadermodelonly":
            values["strength_clip"] = 0
        record = _lora_record(values)
        return [record] if record else []
    if kind in {"lora loader (loramanager)", "lora stacker (loramanager)"}:
        collection = node.get("widgets_values", []) if graph.gui else inputs
        return _manager_records(collection)
    if "power lora loader" in kind or "powerloraloader" in kind:
        result = []
        collection = node.get("widgets_values", []) if graph.gui else inputs
        entries = (
            list(collection.values())
            if isinstance(collection, Mapping)
            else _items(collection, 100)
        )
        clip_present = "clip" in inputs and graph.resolve(inputs["clip"]) is not None
        for value in entries[:100]:
            if not isinstance(value, Mapping) or "lora" not in value or value.get("on") is not True:
                continue
            values = dict(value)
            strength_two = value.get("strengthTwo")
            values["strength_clip"] = (
                (value.get("strength") if strength_two is None else strength_two)
                if clip_present
                else 0
            )
            record = _lora_record(values)
            if record:
                result.append(record)
        return result
    collection = node.get("widgets_values", []) if graph.gui else inputs
    return _collection_records(collection)


def _lora_output_schema(node: Mapping[str, Any]) -> bool:
    kind = _type(node)
    return (
        kind in STANDARD_LORA_TYPES
        or kind
        in {
            "lora loader (loramanager)",
            "loramanager",
        }
        or "power lora loader" in kind
        or "powerloraloader" in kind
    )


def _record_usage(record: Mapping[str, Any], ports: set[int]) -> tuple[bool, bool]:
    weights = [
        record.get("strength_model" if port == 0 else "strength_clip")
        for port in ports
        if port in {0, 1}
    ]
    return any(value is not None and value != 0 for value in weights), any(
        value is None for value in weights
    )


def _known_lora_schema(node: Mapping[str, Any]) -> bool:
    kind = _type(node)
    if (
        kind in STANDARD_LORA_TYPES
        or "loramanager" in kind
        or "power lora loader" in kind
        or "powerloraloader" in kind
    ):
        return True
    values = [node.get("inputs", {}), node.get("widgets_values", {})]
    for value in values:
        children = value if isinstance(value, list) else [value]
        if any(
            isinstance(item, Mapping)
            and any(key in item for key in ("lora_name", "loras", "lora_stack", "lora_list"))
            for item in children
        ):
            return True
    return False


def _node_models(node_id: str, node: Mapping[str, Any], graph: _SavedGraph) -> list[dict[str, Any]]:
    schema = MODEL_SCHEMAS.get(_type(node))
    if schema is None:
        return []
    field, kind = schema
    fields = [field]
    if _type(node) in {"dualcliploader", "triplecliploader"}:
        fields.append("clip_name2")
    if _type(node) == "triplecliploader":
        fields.append("clip_name3")
    result = []
    for key in fields:
        value = graph.resolve(_mapping(node.get("inputs")).get(key, UNKNOWN))
        if isinstance(value, str) and value.strip():
            result.append(
                {
                    "name": value[:1000],
                    "kind": kind,
                    "node_id": node_id,
                    "node_type": node["class_type"],
                }
            )
    return result


def _conditioning_nodes(graph: _SavedGraph, value: Any, polarity: str) -> set[str]:
    selected, visited, pending = set(), set(), [value]
    encoders = {
        "cliptextencode",
        "pclazytextencode",
        "cliptextencodesdxl",
        "cliptextencodeflux",
        "impactwildcardencode",
        "impactwildcardprocessor",
        "textencodeqwenimage21",
    }
    while pending and len(visited) < MAX_GRAPH_NODES:
        ref = _reference(pending.pop())
        if ref is None or ref in visited or ref[0] not in graph.nodes:
            continue
        visited.add(ref)
        node = graph.nodes[ref[0]]
        if node.get("mode", 0) != 0:
            continue
        selected.add(ref[0])
        if _type(node) in encoders:
            continue
        inputs = _mapping(node.get("inputs"))
        if _type(node) == "tobasicpipe":
            pending.append(inputs.get(polarity, UNKNOWN))
        else:
            pending.extend(graph.dependencies(*ref))
    return selected


def _prompt_roles(graph: _SavedGraph, selected: set[str]) -> dict[str, set[str]]:
    roles: dict[str, set[str]] = {}
    for node_id in selected:
        inputs = _mapping(graph.nodes[node_id].get("inputs"))
        for polarity in ("positive", "negative"):
            if polarity in inputs:
                for dependency in _conditioning_nodes(graph, inputs[polarity], polarity):
                    roles.setdefault(dependency, set()).add(polarity)
    for node_id in selected:
        node = graph.nodes[node_id]
        fields = {}
        if _type(node) == "textencodeqwenimage21":
            fields = {"prompt": {"positive"}, "negative_prompt": {"negative"}}
        elif _type(node) in {"cliptextencode", "pclazytextencode"}:
            fields = {"text": roles.get(node_id, {"unknown"})}
        for field, polarities in fields.items():
            for dependency in graph.walk([_mapping(node.get("inputs")).get(field, UNKNOWN)]):
                roles.setdefault(dependency, set()).update(polarities)
    return roles


def _node_prompts(
    node_id: str, node: Mapping[str, Any], graph: _SavedGraph, roles: Mapping[str, set[str]]
) -> list[dict[str, Any]]:
    inputs = _mapping(node.get("inputs"))
    kind = _type(node)
    fields = []
    if _is_output(node):
        fields = [(key, key) for key in ("positive", "negative")]
    elif kind == "textencodeqwenimage21":
        fields = [("prompt", "positive"), ("negative_prompt", "negative")]
    elif kind in {"cliptextencode", "pclazytextencode", "cliptextencodesdxl", "cliptextencodeflux"}:
        fields = [
            (key, role)
            for key in ("text", "text_g", "text_l", "clip_l", "t5xxl")
            for role in sorted(roles.get(node_id, {"unknown"}))
        ]
    elif kind in {"impactwildcardencode", "impactwildcardprocessor"}:
        fields = [("populated_text", role) for role in sorted(roles.get(node_id, {"unknown"}))]
        graph.warnings.add("通配词文本为保存时的 populated_text，不能证明本次运行展开结果。")
    elif (
        kind in {"string literal", "primitivestring", "primitivestringmultiline"}
        and node_id in roles
    ):
        fields = [(CONSTANT_FIELDS[kind], role) for role in sorted(roles[node_id])]
        graph.warnings.add("提示词包含保存的文本组件；动态组合未解析时不能当作完整最终 Prompt。")
    result = []
    for key, polarity in fields:
        text = graph.resolve(inputs.get(key, UNKNOWN))
        if isinstance(text, str) and text.strip():
            record = {"polarity": polarity, "text": text[:MAX_TEXT_LENGTH], "node_id": node_id}
            if record not in result:
                result.append(record)
    return result


def _unique_sampling_value(graph: _SavedGraph, selected: set[str], kind: str, field: str) -> Any:
    candidates = [
        graph.resolve(_mapping(graph.nodes[key].get("inputs")).get(field, UNKNOWN))
        for key in selected
        if _type(graph.nodes[key]) == kind and graph.nodes[key].get("mode", 0) == 0
    ]
    values = [value for value in candidates if value is not UNKNOWN]
    if values and all(value == values[0] for value in values):
        return values[0]
    if len(values) > 1:
        graph.warnings.add("采样链存在多个参数来源，未将不同阶段合并为一组参数。")
    return UNKNOWN


def _node_sampling(
    node_id: str, node: Mapping[str, Any], graph: _SavedGraph
) -> dict[str, Any] | None:
    kind = _type(node)
    if kind not in SAMPLER_TYPES:
        return None
    inputs = _mapping(node.get("inputs"))
    values = {key: graph.resolve(inputs.get(key, UNKNOWN)) for key in SAMPLING_FIELDS}
    if values["seed"] is UNKNOWN:
        values["seed"] = graph.resolve(inputs.get("noise_seed", UNKNOWN))
    dependencies = graph.walk([[node_id, 0]])
    if kind in {"samplercustom", "samplercustomadvanced"}:
        sources = {
            "seed": ("randomnoise", "noise_seed"),
            "cfg": ("cfgguider", "cfg"),
            "sampler_name": ("ksamplerselect", "sampler_name"),
            "scheduler": ("basicscheduler", "scheduler"),
            "steps": ("basicscheduler", "steps"),
            "denoise": ("basicscheduler", "denoise"),
        }
        for key, (source_type, field) in sources.items():
            if values[key] is UNKNOWN:
                values[key] = _unique_sampling_value(graph, dependencies, source_type, field)
    record = {
        "seed": _seed(values["seed"]),
        "steps": _number(values["steps"]),
        "cfg": _number(values["cfg"]),
        "sampler_name": values["sampler_name"][:1000]
        if isinstance(values["sampler_name"], str)
        else None,
        "scheduler": values["scheduler"][:1000] if isinstance(values["scheduler"], str) else None,
        "denoise": _number(values["denoise"]),
        "node_id": node_id,
    }
    latent = inputs.get("latent_image", inputs.get("samples", UNKNOWN))
    latent_nodes = graph.walk([latent])
    sizes = []
    for key in latent_nodes:
        source = graph.nodes[key]
        if (
            _type(source)
            not in {"emptylatentimage", "emptysd3latentimage", "emptyqnimage21latentimage"}
            or source.get("mode", 0) != 0
        ):
            continue
        dimensions = tuple(
            _number(graph.resolve(_mapping(source.get("inputs")).get(field, UNKNOWN)))
            for field in ("width", "height")
        )
        if all(isinstance(value, int) and value > 0 for value in dimensions):
            sizes.append(dimensions)
    if sizes and all(size == sizes[0] for size in sizes):
        record["width"], record["height"] = sizes[0]
    return record


def _classify_lora_record(
    node_id: str,
    node: Mapping[str, Any],
    record: Mapping[str, Any],
    entries: list[dict[str, Any]],
    root_count: int,
) -> tuple[str, dict[str, Any]] | None:
    item = {key: value for key, value in record.items() if not key.startswith("_")}
    item.update(node_id=node_id, node_type=str(node["class_type"]))
    enabled = record.get("_activation_confirmed", True)
    confirmed = (
        bool(root_count)
        and _lora_output_schema(node)
        and enabled
        and all(_record_usage(record, entry.get("confirmed", set()))[0] for entry in entries)
    )
    if confirmed:
        return "loras", item
    consumed = set().union(
        *(entry.get("confirmed", set()) | entry.get("candidate", set()) for entry in entries)
    )
    effect, unknown = _record_usage(record, consumed)
    if root_count and _lora_output_schema(node) and not effect and not unknown:
        return None
    if not root_count:
        reason = "没有可确认的图像输出连接"
    elif not _lora_output_schema(node) or not enabled:
        reason = "LoRA 节点或启用状态无法确认"
    elif root_count > 1 and not all(entries):
        reason = "多个图像输出，无法确认此 PNG 对应哪一条分支"
    elif unknown and not effect:
        reason = "所用输出端口的权重未记录或无效"
    else:
        reason = next(
            (entry.get("reason") for entry in entries if entry.get("reason")),
            "输出参与情况无法确认",
        )
    return "candidate_loras", {**item, "reason": reason}


def _append_lora_records(
    node_id: str,
    node: Mapping[str, Any],
    graph: _SavedGraph,
    result: dict[str, Any],
    usages: list[dict[str, dict[str, Any]]],
) -> None:
    node_type = str(node["class_type"])
    records = _node_loras(node, graph)
    for record in records:
        classified = _classify_lora_record(
            node_id, node, record, [usage.get(node_id, {}) for usage in usages], len(usages)
        )
        if classified:
            field, item = classified
            result[field].append(item)
    if not records and not _known_lora_schema(node):
        result["unknown_lora_nodes"].append({"node_id": node_id, "node_type": node_type})


def inspect_generation_evidence(
    prompt: Any,
    workflow: Any,
    *,
    parameters: str = "",
    saved_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read saved graphs as evidence; do not execute custom nodes or infer from pixels."""
    graph = _SavedGraph(prompt, workflow)
    result: dict[str, Any] = {
        "extractor_version": EXTRACTOR_VERSION,
        "status": "unavailable",
        "scope": "none",
        "loras": [],
        "candidate_loras": [],
        "models": [],
        "prompts": [],
        "sampling": [],
        "unknown_lora_nodes": [],
        "warnings": [],
    }
    if not graph.nodes:
        result["warnings"] = ["没有可识别的节点记录，不能从画面反推实际 LoRA 组合。"]
        result["final_generation"] = _final_generation(graph, [], parameters, saved_metadata)
        return result
    roots = [
        key for key, node in graph.nodes.items() if _is_output(node) and node.get("mode", 0) == 0
    ]
    selected = graph.walk([[key, 0] for key in roots]) if roots else set(graph.nodes)
    usages = [graph.lora_usage(root) for root in roots]
    roles = _prompt_roles(graph, selected)
    for node_id in sorted(selected):
        node = graph.nodes[node_id]
        if node.get("mode", 0) != 0:
            continue
        node_type = str(node["class_type"])
        if "lora" in node_type.casefold():
            _append_lora_records(node_id, node, graph, result, usages)
        result["models"].extend(_node_models(node_id, node, graph))
        result["prompts"].extend(_node_prompts(node_id, node, graph, roles))
        sampling = _node_sampling(node_id, node, graph)
        if sampling:
            result["sampling"].append(sampling)
    graph.warnings.add("记录来自图片保存的节点图；条件节点、动态展开和运行时替换仍需核对。")
    if not roots:
        graph.warnings.add("未识别到图像输出连接，以下仅为保存的节点记录，不能确认参与了出图。")
    if result["unknown_lora_nodes"]:
        graph.warnings.add("存在未识别的 LoRA 节点，列表可能不完整。")
    if result["candidate_loras"]:
        graph.warnings.add("存在未确认的 LoRA 候选记录，未计入已使用列表。")
    result.update(
        status="saved_workflow" if graph.gui else "saved_api_prompt",
        scope="output_connected" if roots else "saved_nodes",
        warnings=sorted(graph.warnings),
    )
    result["final_generation"] = _final_generation(graph, roots, parameters, saved_metadata)
    return result


def _exact_combine(
    graph: _SavedGraph, node: Mapping[str, Any], seen: tuple[tuple[str, int], ...]
) -> Any:
    inputs = _mapping(node.get("inputs"))
    kind = _type(node)
    fields = (
        ("string_a", "string_b", "delimiter")
        if kind == "stringconcatenate"
        else ("text_a", "text_b", "text_c")
    )
    values = {field: _exact_text(graph, inputs.get(field, ""), seen) for field in fields}
    if not all(isinstance(value, str) for value in values.values()):
        return UNKNOWN
    controls = {key: graph.resolve(inputs.get(key, UNKNOWN)) for key in ("action", "tidy_tags")}
    if kind == "stringconcatenate":
        return (values["string_a"] + values["delimiter"] + values["string_b"])[:MAX_TEXT_LENGTH]
    if controls["action"] != "append" or controls["tidy_tags"] not in ("yes", "no"):
        return UNKNOWN
    text = (", " if controls["tidy_tags"] == "yes" else "").join(
        item for item in values.values() if item
    )
    if controls["tidy_tags"] == "yes":
        text = re.sub(r"\s{2,}", " ", text)
        text = text.replace(" ,", ",")
        text = re.sub(r",{2,}", ",", text).strip()
    return text[:MAX_TEXT_LENGTH]


def _unwrap(value: Any) -> Any:
    return value.get("__value__", UNKNOWN) if isinstance(value, Mapping) else value


def _exact_trigger(
    graph: _SavedGraph, node: Mapping[str, Any], seen: tuple[tuple[str, int], ...]
) -> Any:
    inputs = _mapping(node.get("inputs"))
    widgets = _items(node.get("widgets_values"), 100)
    original = inputs.get(
        "orinalMessage",
        widgets[TRIGGER_ORIGINAL_WIDGET_INDEX]
        if len(widgets) > TRIGGER_ORIGINAL_WIDGET_INDEX
        else "",
    )
    original = _exact_text(graph, _unwrap(original), seen)
    override = _exact_text(graph, _unwrap(inputs.get("trigger_words", "")), seen)
    if not isinstance(original, str) or not isinstance(override, str):
        return UNKNOWN

    def normalized(text: str) -> set[str]:
        return {item.strip() for item in text.split(",") if item.strip()}

    if override and normalized(override) != normalized(original):
        return override
    rows = _unwrap(
        inputs.get(
            "toggle_trigger_words",
            widgets[TRIGGER_ROWS_WIDGET_INDEX] if len(widgets) > TRIGGER_ROWS_WIDGET_INDEX else [],
        )
    )
    if isinstance(rows, str):
        try:
            rows = json.loads(rows)
        except json.JSONDecodeError:
            rows = UNKNOWN
    if not rows:
        return original
    if not isinstance(rows, list) or inputs.get("allow_strength_adjustment", False) is not False:
        return UNKNOWN
    if any(
        not isinstance(row, Mapping) or "items" in row or not isinstance(row.get("text"), str)
        for row in rows[:100]
    ):
        return UNKNOWN
    return ", ".join(
        row["text"].strip()
        for row in rows[:100]
        if row.get("active", False) and row["text"].strip()
    )


def _exact_text(graph: _SavedGraph, value: Any, seen: tuple[tuple[str, int], ...] = ()) -> Any:
    ref = _reference(value)
    if ref is None:
        return value if isinstance(value, str) and len(value) < MAX_TEXT_LENGTH else UNKNOWN
    if ref[0] not in graph.nodes or ref in seen or len(seen) >= MAX_VALUE_DEPTH:
        return UNKNOWN
    node = graph.nodes[ref[0]]
    kind = _type(node)
    inputs = _mapping(node.get("inputs"))
    path = (*seen, ref)
    result = UNKNOWN
    if node.get("mode", 0) in {0, BYPASS_MODE}:
        if kind in CONSTANT_FIELDS:
            result = _exact_text(graph, inputs.get(CONSTANT_FIELDS[kind], UNKNOWN), path)
        elif kind in {"stringconcatenate", "stringfunction|pysssss"}:
            result = _exact_combine(graph, node, path)
        elif kind == "triggerword toggle (loramanager)":
            result = _exact_trigger(graph, node, path)
        elif kind == "promptselector" and inputs.get("selected_prompts") == "":
            result = _exact_text(graph, inputs.get("prefix_prompt", ""), path)
        elif (
            "_outputs" in node
            or kind
            in {
                "@boundary",
                "reroute",
                "showtext|pysssss",
                "comfyswitchnode",
                "switch string [crystools]",
                "any switch (rgthree)",
            }
            or node.get("mode", 0) == BYPASS_MODE
        ):
            refs = graph.dependencies(*ref)
            if len(refs) == 1:
                result = _exact_text(graph, refs[0], path)
    return result if isinstance(result, str) and len(result) < MAX_TEXT_LENGTH else UNKNOWN


def _empty_final_prompt(status: str = "unavailable") -> dict[str, Any]:
    return {"text": None, "status": status, "source": None}


def _stage_prompt(
    graph: _SavedGraph, stage_id: str, polarity: str, usage: Mapping[str, Any]
) -> dict[str, Any]:
    refs, certain = graph.stage_roots(stage_id, polarity)
    encoders: set[str] = set()
    for ref in refs:
        encoders.update(
            key
            for key in _conditioning_nodes(graph, ref, polarity)
            if _type(graph.nodes[key])
            in {
                "cliptextencode",
                "pclazytextencode",
                "cliptextencodesdxl",
                "cliptextencodeflux",
                "textencodeqwenimage21",
                "impactwildcardencode",
            }
        )
    if not certain or len(encoders) > 1:
        return _empty_final_prompt("ambiguous")
    if not encoders:
        return _empty_final_prompt()
    node_id = next(iter(encoders))
    if not _mapping(usage.get(node_id)).get("confirmed"):
        return _empty_final_prompt("ambiguous")
    node = graph.nodes[node_id]
    kind = _type(node)
    fields = (
        [polarity + "_prompt" if polarity == "negative" else "prompt"]
        if kind == "textencodeqwenimage21"
        else [
            key for key in ("text", "text_g", "text_l", "clip_l", "t5xxl") if key in node["inputs"]
        ]
    )
    if kind == "impactwildcardencode" or len(fields) != 1:
        return _empty_final_prompt("ambiguous" if len(fields) > 1 else "unavailable")
    field = fields[0]
    text = _exact_text(graph, node["inputs"][field])
    if not isinstance(text, str):
        return _empty_final_prompt()
    return {
        "text": text,
        "status": "exact",
        "source": {
            "node_id": node_id,
            "port": 0,
            "field": field,
            "kind": "saved_conditioning_input",
        },
    }


def _saved_exports(parameters: str) -> dict[str, Any]:
    result: dict[str, Any] = {"positive": None, "negative": None}
    if not isinstance(parameters, str) or not parameters.strip():
        return result
    value = parameters[:200_000]
    positive = re.match(
        r"\s*(.*?)(?=\r?\n(?:Negative prompt|Steps):|$)", value, re.IGNORECASE | re.DOTALL
    )
    negative = re.search(
        r"Negative prompt:[ \t]*(.*?)(?:\r?\nSteps:|$)", value, re.IGNORECASE | re.DOTALL
    )
    for polarity, match in (("positive", positive), ("negative", negative)):
        if match:
            result[polarity] = {
                "text": match.group(1).strip(),
                "status": "saved_export",
                "source": {"kind": "png_parameters"},
            }
    return result


def _stage_context(
    graph: _SavedGraph, stage_id: str
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    usage: dict[str, dict[str, Any]] = {}
    for field in ("model", "positive", "negative"):
        refs, certain = graph.stage_roots(stage_id, field)
        for key, entry in graph.lora_usage(stage_id, roots=refs, all_nodes=True).items():
            target = usage.setdefault(key, {"confirmed": set(), "candidate": set(), "reason": ""})
            target["confirmed" if certain else "candidate"].update(entry["confirmed"])
            target["candidate"].update(entry["candidate"])
            target["reason"] = (
                target["reason"]
                or entry["reason"]
                or ("" if certain else "BasicPipe 组件分支无法确认")
            )
    models = [
        item
        for key in sorted(usage)
        if 0 in usage[key]["confirmed"]
        for item in _node_models(key, graph.nodes[key], graph)
    ]
    return models, usage


def _stage_family(models: list[dict[str, Any]]) -> str | None:
    return (
        "krea2"
        if any(
            re.search(r"krea[ _-]?2", item["name"], re.IGNORECASE)
            for item in models
            if item["kind"] in {"checkpoint", "diffusion_model"}
        )
        else None
    )


def _stage_output_port(node: Mapping[str, Any]) -> int:
    return 1 if _type(node) in {"impactksamplerbasicpipe", "impactksampleradvancedbasicpipe"} else 0


def _select_final_stage(
    graph: _SavedGraph, roots: list[str]
) -> tuple[str | None, list[dict[str, Any]], str]:
    if not roots:
        return None, [], "unavailable"
    graph.usage_visit_count = 0
    paths = [graph.lora_usage(root, all_nodes=True) for root in roots]
    identifiers = {
        key
        for usage in paths
        for key in usage
        if _type(graph.nodes[key]) in SAMPLER_TYPES
        and graph.nodes[key].get("mode", 0) == 0
        and _stage_output_port(graph.nodes[key])
        in usage[key]["confirmed"] | usage[key]["candidate"]
    }
    if len(identifiers) > MAX_GENERATION_STAGES:
        graph.warnings.add("采样阶段数量超过识别上限，未猜测最终阶段。")
        return None, [], "ambiguous"
    stages: list[dict[str, Any]] = []
    for key in sorted(identifiers):
        models, _ = _stage_context(graph, key)
        role = "postprocess" if _type(graph.nodes[key]) in POSTPROCESS_SAMPLERS else "generation"
        stages.append(
            {
                "stage_id": key,
                "node_type": graph.nodes[key]["class_type"],
                "kind": role,
                "model_family": _stage_family(models),
                "selected": False,
            }
        )
    candidates = [item["stage_id"] for item in stages if item["kind"] == "generation"]
    krea = [
        item["stage_id"]
        for item in stages
        if item["kind"] == "generation" and item["model_family"] == "krea2"
    ]
    candidates = krea or candidates
    ancestors = {
        key: graph.walk([[key, _stage_output_port(graph.nodes[key])]]) for key in candidates
    }
    terminal = [
        key
        for key in candidates
        if not any(key in ancestors[other] for other in candidates if other != key)
    ]
    certain = (
        len(roots) == 1
        and len(terminal) == 1
        and _stage_output_port(graph.nodes[terminal[0]]) in paths[0][terminal[0]]["confirmed"]
    )
    if not certain:
        return None, stages, "ambiguous" if candidates else "unavailable"
    selected = terminal[0]
    for item in stages:
        item["selected"] = item["stage_id"] == selected
    return selected, stages, "partial"


def _final_generation(
    graph: _SavedGraph,
    roots: list[str],
    parameters: str,
    saved_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    stage_id, stages, status = _select_final_stage(graph, roots)
    saved_loras, lora_source = inspect_saved_loras(parameters, saved_metadata)
    result: dict[str, Any] = {
        "status": status,
        "stage_id": stage_id,
        "model_family": None,
        "sampler": None,
        "models": [],
        "loras": saved_loras,
        "lora_source": lora_source,
        "candidate_loras": [],
        "positive": _empty_final_prompt("ambiguous" if status == "ambiguous" else "unavailable"),
        "negative": _empty_final_prompt("ambiguous" if status == "ambiguous" else "unavailable"),
        "saved_export_prompts": {"positive": None, "negative": None},
        "stages": stages,
        "warnings": [],
    }
    if not graph.nodes:
        result["saved_export_prompts"] = _saved_exports(parameters)
    if not stage_id:
        return result
    models, usage = _stage_context(graph, stage_id)
    result.update(
        models=models,
        model_family=_stage_family(models),
        sampler=_node_sampling(stage_id, graph.nodes[stage_id], graph),
    )
    for polarity in ("positive", "negative"):
        result[polarity] = _stage_prompt(graph, stage_id, polarity, usage)
    result["saved_export_prompts"] = _saved_exports(parameters)
    result["status"] = (
        "resolved"
        if all(result[polarity]["status"] == "exact" for polarity in ("positive", "negative"))
        else "partial"
    )
    if result["status"] == "partial":
        result["warnings"].append(
            "部分最终编码输入无法从保存记录完整还原；未拼接节点组件或执行动态节点。"
        )
    if any(result["saved_export_prompts"].values()):
        result["warnings"].append(
            "PNG 导出提示词是保存节点写入的文本，可能含格式标签，不能冒充精确编码输入。"
        )
    return result
