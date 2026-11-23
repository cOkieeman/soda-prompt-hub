from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from prompt_hub.studio_store import WILDCARD_V2_SAMPLING_FIELDS, StudioError, wildcard_v2_active
from prompt_hub.studio_wildcard_v2_tags import strip_tag_headers
from prompt_hub.studio_workflow_values import (
    input_value,
    output_source,
    set_state_value,
    state_fields,
    widget_text,
)

TEXT_INPUTS = {"text", "string", "prompt", "wildcard_text", "populated_text", "PromptStackState"}
NUMBER_INPUTS = {"width", "height", "steps", "cfg", "seed", "noise_seed"}
GENERATION_INPUT_NODES = {
    "KSampler",
    "KSamplerAdvanced",
    "SamplerCustom",
    "ImpactKSamplerBasicPipe",
    "ImpactKSamplerAdvancedBasicPipe",
    "EmptyLatentImage",
    "EmptySD3LatentImage",
    "EmptyAnimaLatentImage",
    "ResolutionMasterSimplify",
    "Seed (rgthree)",
    "RandomNoise",
    "PixaromaSeed",
    "PixaromaSizes",
}
POSTPROCESS_PATTERN = re.compile(
    r"FaceDetailer|HandDetailer|DetailerForEachPipe|SeedVR2VideoUpscaler|Nvidia.*(?:VSR|DLSS)|"
    r"(?:VSR|DLSS).*Enhance|RTXVideoSuperResolution|DLSS5NeuralRender|"
    r"UltimateSDUpscale|CR Upscale Image|ImageUpscaleWithModel",
    re.IGNORECASE,
)


COMFY_LINK_LENGTH = 2
MAX_GENERATION_CFG = 30
MAX_GENERATION_EDGE = 4096
MAX_GENERATION_STEPS = 200
MIN_GENERATION_EDGE = 64
V2_DIRECT_SAMPLERS = {"KSampler", "KSamplerAdvanced", "SamplerCustom"}
V2_PIPE_SAMPLERS = {"ImpactKSamplerBasicPipe", "ImpactKSamplerAdvancedBasicPipe"}
V2_TEXT_ENCODERS = {"CLIPTextEncode", "PCLazyTextEncode", "PCLazyTextEncodeAdvanced"}
V2_POSITIVE_FIELDS = {"prefix", "body", "suffix", "positive"}


def field_key(node_id: str, name: str) -> str:
    return f"{node_id}::{name}"


def _connected_outputs(graph: dict[str, Any]) -> dict[tuple[str, int], list[dict[str, str]]]:
    connected_outputs: dict[tuple[str, int], list[dict[str, str]]] = {}
    for consumer_id, consumer in graph.items():
        for input_name, value in consumer["inputs"].items():
            if (
                not isinstance(value, list)
                or len(value) != COMFY_LINK_LENGTH
                or str(value[0]) not in graph
                or not isinstance(value[1], int)
                or isinstance(value[1], bool)
            ):
                continue
            source_id = str(value[0])
            connected_outputs.setdefault((source_id, value[1]), []).append(
                {
                    "node_id": str(consumer_id),
                    "title": str(consumer.get("_meta", {}).get("title") or consumer["class_type"]),
                    "class_type": str(consumer["class_type"]),
                    "input": str(input_name),
                }
            )
    return connected_outputs


def _scalar_input_entries(
    graph: dict[str, Any], node: dict[str, Any]
) -> list[tuple[str, str, Any, dict[str, Any] | None]]:
    entries = [
        (name, name, value, None)
        for name, value in node["inputs"].items()
        if isinstance(value, (str, int, float, bool))
        and not (node["class_type"] == "PixaromaSeed" and name == "seed")
    ]
    entries.extend(state_fields(node))
    if node["class_type"] not in GENERATION_INPUT_NODES:
        return entries
    for name, link in node["inputs"].items():
        if name not in NUMBER_INPUTS or not isinstance(link, list):
            continue
        try:
            source = output_source(graph, link)
            value = input_value(graph, source) if source else None
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            entries.append((name + "#", name, value, None))
    return entries


def _control_targets(
    graph: dict[str, Any],
    outputs: dict[tuple[str, int], list[dict[str, str]]],
    node_id: str,
    slot: int,
) -> list[dict[str, str]]:
    targets = []
    for target in outputs.get((node_id, slot), []):
        enriched_target = dict(target)
        if enriched_target["class_type"] == "ComfySwitchNode" and enriched_target["input"] in {
            "on_true",
            "on_false",
        }:
            switch_value = graph[enriched_target["node_id"]]["inputs"].get("switch")
            if (
                isinstance(switch_value, list)
                and len(switch_value) == COMFY_LINK_LENGTH
                and isinstance(switch_value[1], int)
            ):
                switch_outputs = outputs.get((str(switch_value[0]), switch_value[1]), [])
                if any("turbo" in item["title"].lower() for item in switch_outputs):
                    enriched_target["mode"] = "turbo"
        targets.append(enriched_target)
    return targets


def _scalar_field(
    graph: dict[str, Any],
    node_id: str,
    node: dict[str, Any],
    entry: tuple[str, str, Any, dict[str, Any] | None],
    outputs: dict[tuple[str, int], list[dict[str, str]]],
) -> dict[str, Any]:
    key_name, name, value, control = entry
    field = {
        "key": field_key(node_id, key_name),
        "node_id": node_id,
        "input": name,
        "title": str(node.get("_meta", {}).get("title") or node["class_type"]),
        "class_type": node["class_type"],
        "value": value,
        "type": (
            "boolean"
            if isinstance(value, bool)
            else "number"
            if isinstance(value, (int, float))
            else "text"
        ),
    }
    if key_name.endswith("#"):
        field["source_key"] = output_source(graph, node["inputs"][name])
    if control is not None:
        slot = int(name.removeprefix("value_")) - 1
        control["connected"] = (node_id, slot) in outputs
        control["targets"] = _control_targets(graph, outputs, node_id, slot)
        field["control"] = control
    return field


def scalar_inputs(graph: dict[str, Any]) -> list[dict[str, Any]]:
    fields = []
    outputs = _connected_outputs(graph)
    for node_id, node in graph.items():
        for entry in _scalar_input_entries(graph, node):
            _, _, value, _ = entry
            if isinstance(value, (str, int, float, bool)):
                fields.append(_scalar_field(graph, str(node_id), node, entry, outputs))
    return fields


def infer_bindings(graph: dict[str, Any]) -> dict[str, list[str]]:  # noqa: C901 - protocol validation and dispatch stay together
    bindings: dict[str, list[str]] = {}
    for item in scalar_inputs(graph):
        name = item["input"]
        title = item["title"].lower()
        node_type = item["class_type"]
        field = ""
        if name in {"seed", "noise_seed"}:
            if node_type in {"Raffle", "ImpactWildcardEncode", "ImpactWildcardProcessor"}:
                field = "text_seed"
            elif node_type in GENERATION_INPUT_NODES:
                field = "seed"
        elif name in {"width", "height", "steps", "cfg"} and node_type in GENERATION_INPUT_NODES:
            field = name
        elif name in TEXT_INPUTS:
            if re.search(r"negative|负面|負面|不希望", title):
                field = "negative"
            elif re.search(r"suffix|signature|后缀|後綴|署名|签名|簽名", title):
                field = "suffix"
            elif (
                re.search(r"prefix|前缀|前綴|主题|主題|风格|風格|quality", title)
                or name == "PromptStackState"
            ):
                field = "prefix"
            elif re.search(r"正文|body", title) or node_type in {
                "ImpactWildcardEncode",
                "ImpactWildcardProcessor",
            }:
                field = "body"
            elif node_type == "CLIPTextEncode":
                field = "positive"
        if field:
            bindings.setdefault(field, []).append(item["key"])
    return bindings


def source_values(graph: dict[str, Any], bindings: dict[str, list[str]]) -> dict[str, Any]:
    fields = {item["key"]: item for item in scalar_inputs(graph)}
    values: dict[str, Any] = {}
    for name, keys in bindings.items():
        if keys and keys[0] in fields:
            value = fields[keys[0]]["value"]
            if fields[keys[0]]["input"] == "PromptStackState":
                try:
                    state = json.loads(value)
                    values["prefix_rows"] = state.get("rows", [])
                    value = state.get("separator", ", ").join(
                        row.get("text", "") for row in state.get("rows", []) if row.get("enabled")
                    )
                except (TypeError, ValueError):
                    value = ""
            if name in {"seed", "text_seed"} and (
                not isinstance(value, int) or not 0 <= value < 2**53
            ):
                continue
            if name in {"width", "height"} and (
                not isinstance(value, int)
                or not MIN_GENERATION_EDGE <= value <= MAX_GENERATION_EDGE
            ):
                continue
            if name == "steps" and (
                not isinstance(value, int) or not 1 <= value <= MAX_GENERATION_STEPS
            ):
                continue
            if name == "cfg" and (
                not isinstance(value, (int, float)) or not 0 <= value <= MAX_GENERATION_CFG
            ):
                continue
            values["body" if name == "positive" else name] = value
    return values


def postprocess_nodes(graph: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "node_id": node_id,
            "label": str(node.get("_meta", {}).get("title") or node["class_type"]),
            "class_type": node["class_type"],
        }
        for node_id, node in graph.items()
        if POSTPROCESS_PATTERN.search(node["class_type"])
        and any(isinstance(node["inputs"].get(name), list) for name in ("image", "images"))
    ]


def set_input(  # noqa: C901 - protocol validation and dispatch stay together
    graph: dict[str, Any],
    key: str,
    value: object,
    *,
    routing_graph: dict[str, Any] | None = None,
) -> None:
    node_id, separator, name = key.rpartition("::")
    if separator and name.endswith("#"):
        routing = routing_graph if routing_graph is not None else graph
        try:
            source = output_source(routing, routing[node_id]["inputs"][name[:-1]])
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
            msg = "工作流參數來源無效"
            raise StudioError(msg) from error
        if source is None:
            msg = "工作流參數來源已改變，請重新匯入"
            raise StudioError(msg)
        set_input(graph, source, value)
        return
    if separator and "#/" in name:
        set_state_value(graph, key, value)
        return
    if not separator or node_id not in graph or name not in graph[node_id]["inputs"]:
        msg = f"工作流欄位不存在 {key}"
        raise StudioError(msg)
    original = graph[node_id]["inputs"][name]
    if not isinstance(value, (str, int, float, bool, list)):
        msg = "工作流輸入格式有誤"
        raise StudioError(msg)
    if not isinstance(original, list):
        expected = type(original)
        if expected is bool and not isinstance(value, bool):
            msg = f"{name} 需要開關值"
            raise StudioError(msg)
        if expected is str and not isinstance(value, str):
            msg = f"{name} 需要文字"
            raise StudioError(msg)
        if expected in (int, float) and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            msg = f"{name} 需要數字"
            raise StudioError(msg)
    graph[node_id]["inputs"][name] = value


def bypass_image_node(graph: dict[str, Any], node_id: str) -> None:
    node = graph.get(node_id)
    if node is None:
        msg = "後處理節點不存在"
        raise StudioError(msg)
    source = next(
        (
            node["inputs"][name]
            for name in ("image", "images")
            if isinstance(node["inputs"].get(name), list)
        ),
        None,
    )
    if source is None or len(source) != COMFY_LINK_LENGTH or str(source[0]) not in graph:
        msg = "這個後處理分支需要設定原圖輸入或使用已保存的工作流變體"
        raise StudioError(msg)
    replacements = {0: source}
    if node["class_type"] == "DetailerForEachPipe":
        # The user's hand detailer consumes the face detailer's BASIC_PIPE.
        # Bypassing a detailer also forwards its original segments and pipe.
        replacements.update({1: node["inputs"].get("segs"), 2: node["inputs"].get("basic_pipe")})
    for consumer in graph.values():
        for value in consumer["inputs"].values():
            if (
                isinstance(value, list)
                and len(value) == COMFY_LINK_LENGTH
                and str(value[0]) == node_id
                and replacements.get(value[1]) is None
            ):
                msg = "這個後處理節點另有輸出被使用，請匯入對應的關閉版工作流"
                raise StudioError(msg)
    for consumer in graph.values():
        for name, value in consumer["inputs"].items():
            if (
                isinstance(value, list)
                and len(value) == COMFY_LINK_LENGTH
                and str(value[0]) == node_id
            ):
                consumer["inputs"][name] = deepcopy(replacements[value[1]])
    del graph[node_id]


def _upstream_node(
    graph: dict[str, Any],
    link: object,
) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(link, list) or len(link) != COMFY_LINK_LENGTH or link[1] != 0:
        return None
    node_id = str(link[0])
    return (node_id, graph[node_id]) if node_id in graph else None


def _v2_text_encoders(
    graph: dict[str, Any],
    link: object,
    visited: frozenset[str] = frozenset(),
    *,
    required: bool = True,
) -> set[str]:
    upstream = _upstream_node(graph, link)
    if upstream is None or upstream[0] in visited:
        if not required:
            return set()
        msg = "Wildcard V2 無法識別工作流的正向文字編碼節點"
        raise StudioError(msg)
    node_id, node = upstream
    inputs = node["inputs"]
    if node["class_type"] in V2_TEXT_ENCODERS and "text" in inputs:
        return {node_id}
    if node["class_type"] == "Any Switch (rgthree)":
        candidates = [value for name, value in inputs.items() if name.startswith("any_")]
        if candidates:
            return set().union(
                *(
                    _v2_text_encoders(graph, candidate, visited | {node_id}, required=required)
                    for candidate in candidates
                )
            )
    if not required:
        return set()
    msg = "Wildcard V2 需要工作流的正向輸入連接到 CLIPTextEncode 或 PCLazyTextEncode"
    raise StudioError(msg)


def _apply_v2_conditioning(
    graph: dict[str, Any],
    recipe: dict[str, Any],
    positive: str,
    negative: str | None,
) -> None:
    positive_targets = set()
    negative_targets = set()
    for node in graph.values():
        inputs = node["inputs"]
        if node["class_type"] in V2_PIPE_SAMPLERS:
            upstream = _upstream_node(graph, inputs.get("basic_pipe"))
            if upstream is None or upstream[1]["class_type"] != "ToBasicPipe":
                msg = "Wildcard V2 需要可追蹤的 ToBasicPipe 工作流正向管線"
                raise StudioError(msg)
            inputs = upstream[1]["inputs"]
        elif node["class_type"] not in V2_DIRECT_SAMPLERS:
            continue
        positive_targets.update(_v2_text_encoders(graph, inputs.get("positive")))
        if negative is not None:
            negative_targets.update(
                _v2_text_encoders(graph, inputs.get("negative"), required=False)
            )
    if not positive_targets:
        msg = "Wildcard V2 需要帶正向文字編碼節點的 ComfyUI 採樣工作流"
        raise StudioError(msg)
    reference_keys = recipe.get("reference_bindings", {}).values()
    if any(
        field_key(node_id, "text") in reference_keys
        for node_id in positive_targets | negative_targets
    ):
        msg = "參考圖不能綁定到 Wildcard V2 的提示詞文字欄位"
        raise StudioError(msg)
    for node_id in negative_targets - positive_targets:
        graph[node_id]["inputs"]["text"] = negative
    for node_id in positive_targets:
        graph[node_id]["inputs"]["text"] = positive


def _v2_text_binding_keys(bindings: dict[str, Any]) -> set[str]:
    return {
        key
        for field in V2_POSITIVE_FIELDS & bindings.keys()
        for key in ([bindings[field]] if isinstance(bindings[field], str) else bindings[field])
    }


def _apply_bound_inputs(
    graph: dict[str, Any],
    routing_graph: dict[str, Any],
    bindings: dict[str, Any],
    values: dict[str, Any],
) -> None:
    for field, binding_keys in bindings.items():
        if field not in values:
            continue
        keys = [binding_keys] if isinstance(binding_keys, str) else binding_keys
        for key in keys:
            node_id, _, name = key.rpartition("::")
            value = values[field]
            if name == "PromptStackState":
                rows = [{"text": value, "enabled": True}]
                value = json.dumps({"rows": rows, "separator": ", "}, ensure_ascii=False)
            set_input(graph, key, value, routing_graph=routing_graph)
            if graph[node_id]["class_type"] in {"ImpactWildcardEncode", "ImpactWildcardProcessor"}:
                graph[node_id]["inputs"]["mode"] = "fixed"


def compile_graph(  # noqa: C901, PLR0912 - protocol validation and dispatch stay together
    original: dict[str, Any],
    recipe: dict[str, Any],
    expanded: dict[str, Any],
) -> dict[str, Any]:
    graph = deepcopy(original)
    routing_graph = deepcopy(original)
    v2 = wildcard_v2_active(recipe)
    bindings = recipe.get("bindings")
    inferred = infer_bindings(graph) if v2 or not bindings else {}
    bindings = bindings or inferred
    ignored_overrides = _v2_text_binding_keys(bindings) if v2 else set()
    overrides = {
        key: value
        for key, value in recipe.get("overrides", {}).items()
        if key not in ignored_overrides
    }
    for key, value in overrides.items():
        set_input(routing_graph, key, value)
    values = {**recipe, **expanded}
    sampling_bindings = {}
    if v2:
        # The workflow's legacy prompt stack is independent of the Impact result.
        values["body"] = ""
        values.pop("positive", None)
        sampling_bindings = {
            field: bindings[field] if field in bindings else inferred[field]
            for field in WILDCARD_V2_SAMPLING_FIELDS
            if field in bindings or field in inferred
        }
        bindings = {
            field: keys for field, keys in bindings.items() if field not in sampling_bindings
        }
    else:
        body_parts = []
        if not bindings.get("prefix"):
            body_parts.append(expanded["prefix"])
        body_parts.append(expanded["body"])
        if not bindings.get("suffix"):
            body_parts.append(expanded["suffix"])
        values["body"] = "\n\n".join(part for part in body_parts if part.strip())
    _apply_bound_inputs(graph, routing_graph, bindings, values)
    for key, value in overrides.items():
        set_input(graph, key, value)
    if v2:
        # Studio's sampling fields use the active routing and take priority over
        # node overrides saved before the preset was applied.
        _apply_bound_inputs(graph, graph, sampling_bindings, values)
    available = {item["node_id"] for item in postprocess_nodes(original)}
    for node_id, enabled in recipe.get("branches", {}).items():
        if node_id not in available:
            msg = "後處理設定與工作流不一致，請重新選擇工作流"
            raise StudioError(msg)
        if not enabled:
            bypass_image_node(graph, node_id)
    for node in graph.values():
        if node["class_type"] == "WidgetToString":
            text = widget_text(graph, node)
            node.update(class_type="PrimitiveString", inputs={"value": text})
    if v2:
        fallback_negative = values["negative"] if "negative" not in sampling_bindings else None
        _apply_v2_conditioning(
            graph, recipe, strip_tag_headers(expanded["positive"]), fallback_negative
        )
    return graph
