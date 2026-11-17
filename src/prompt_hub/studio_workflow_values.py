from __future__ import annotations

import json
import math
from typing import Any

from prompt_hub.studio_store import StudioError

COMFY_LINK_LENGTH = 2


def widget_text(graph: dict[str, Any], node: dict[str, Any]) -> str:
    """Read WidgetToString metadata from an API graph without a browser workflow."""
    options = node["inputs"]
    title = options.get("node_title", "")
    identifier = str(options.get("id", 0))
    if not title and identifier == "0":
        identifier = str(options.get("any_input", [""])[0])
    candidates = [
        value
        for key, value in graph.items()
        if (
            value.get("_meta", {}).get("title") == title
            if title
            else key == identifier or key.rsplit(":", 1)[-1] == identifier
        )
    ]
    if len(candidates) != 1:
        message = "WidgetToString 需要唯一對應的來源節點 ID 或標題"
        raise StudioError(message)
    inputs = candidates[0]["inputs"]
    names = (
        list(inputs)
        if options.get("return_all")
        else [name.strip() for name in options.get("widget_name", "").split(",") if name.strip()]
    )
    parts = []
    for name in names:
        if name not in inputs:
            message = "WidgetToString 的來源欄位不存在"
            raise StudioError(message)
        value = inputs[name]
        source = output_source(graph, value)
        if source is not None:
            value = input_value(graph, source)
        decimals = max(0, min(10, int(options.get("allowed_float_decimals", 2))))
        text = f"{value:.{decimals}f}" if isinstance(value, float) else str(value)
        parts.append(f"{name}: {text}" if options.get("return_all") or len(names) > 1 else text)
    return ", ".join(parts)


def input_value(graph: dict[str, Any], key: str) -> Any:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
    node_id, _, name = key.rpartition("::")
    name, marker, pointer = name.partition("#/")
    value = graph[node_id]["inputs"][name]
    if marker:
        state = json.loads(value)
        value = state
        for part in pointer.split("/"):
            value = value[int(part)] if isinstance(value, list) else value[part]
        if name == "SlidersState" and pointer.startswith("sliders/"):
            slider = state["sliders"][int(pointer.split("/")[1])]
            if slider.get("type") == "toggle":
                value = round(float(value))
                return value if slider.get("out") == "int" else bool(value)
    return value


def output_source(  # noqa: C901, PLR0911 - protocol validation and dispatch stay together
    graph: dict[str, Any],
    link: object,
    visited: frozenset[str] = frozenset(),
) -> str | None:
    """Resolve supported value/routing nodes without executing the workflow."""
    if not isinstance(link, list) or len(link) != COMFY_LINK_LENGTH:
        return None
    node_id, slot = str(link[0]), link[1]
    if node_id not in graph or node_id in visited or not isinstance(slot, int):
        return None
    node = graph[node_id]
    inputs, kind = node["inputs"], node["class_type"]
    prefix = node_id + "::"
    if kind == "PixaromaSeed" and slot == 0:
        state = json.loads(inputs.get("SeedState", "{}"))
        return prefix + "SeedState#/" + ("runSeed" if "runSeed" in state else "seed")
    if kind == "PixaromaSizes" and slot in (0, 1):
        state = json.loads(inputs.get("SizesState", "{}"))
        axis = ("w", "h")[slot]
        return prefix + "SizesState#/" + axis if axis in state else None
    if kind == "PixaromaSliders":
        sliders = json.loads(inputs.get("SlidersState", "{}")).get("sliders", [])
        return prefix + f"SlidersState#/sliders/{slot}/value" if 0 <= slot < len(sliders) else None
    visited = visited | {node_id}
    if kind == "ComfySwitchNode" and slot == 0:
        switch = inputs.get("switch")
        if isinstance(switch, list):
            source = output_source(graph, switch, visited)
            if source is None:
                return None
            switch = input_value(graph, source)
        branch = "on_true" if switch else "on_false"
        if not isinstance(inputs.get(branch), list):
            return prefix + branch
        return output_source(graph, inputs[branch], visited)
    if kind == "Any Switch (rgthree)" and slot == 0:
        links = [value for name, value in inputs.items() if name.startswith("any_")]
        return output_source(graph, links[0], visited) if len(links) == 1 else None
    if kind in {"Sampler Selector (Image Saver)", "Scheduler Selector (Image Saver)"}:
        name = "sampler_name" if kind.startswith("Sampler") else "scheduler"
        value = inputs.get(name)
        return output_source(graph, value, visited) if isinstance(value, list) else prefix + name
    if (
        kind in {"PrimitiveInt", "PrimitiveFloat", "PrimitiveBoolean", "PrimitiveString"}
        and slot == 0
    ):
        return prefix + "value"
    return None


def _slider_range(slider: dict[str, Any]) -> dict[str, int | float]:
    values = {}
    for name in ("min", "max", "step"):
        value = slider.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                if math.isfinite(value):
                    values[name] = value
            except OverflowError:
                continue
    return values


def _slider_control(slider: dict[str, Any]) -> dict[str, Any]:
    kind = str(slider.get("type") or "auto").lower()
    control = {"kind": kind, **_slider_range(slider)}
    label = slider.get("name")
    if isinstance(label, str) and label.strip():
        control["label"] = label.strip()
    if kind == "toggle":
        for name, key in (("on_label", "onLabel"), ("off_label", "offLabel")):
            value = slider.get(key)
            if isinstance(value, str) and value.strip():
                control[name] = value.strip()
    if kind == "combo":
        options = slider.get("options")
        allowed = slider.get("allowed")
        if isinstance(options, list):
            if isinstance(allowed, list) and allowed:
                options = [option for option in options if option in allowed]
            control["options"] = [option for option in options if isinstance(option, str)]
    return control


def _slider_fields(sliders: list[Any]) -> list[tuple[str, str, Any, dict[str, Any] | None]]:
    fields = []
    for index, slider in enumerate(sliders):
        if not isinstance(slider, dict):
            continue
        value = slider.get("value", 0)
        if str(slider.get("type") or "").lower() == "toggle" and slider.get("out") != "int":
            value = bool(round(float(value)))
        fields.append(
            (
                f"SlidersState#/sliders/{index}/value",
                f"value_{index + 1}",
                value,
                _slider_control(slider),
            )
        )
    return fields


def state_fields(
    node: dict[str, Any],
) -> list[tuple[str, str, Any, dict[str, Any] | None]]:
    """Expose serialized Pixaroma controls through the existing field editor."""
    inputs, kind = node["inputs"], node["class_type"]
    try:
        if kind == "PixaromaSeed":
            state = json.loads(inputs.get("SeedState", "{}"))
            name = "runSeed" if "runSeed" in state else "seed"
            return [("SeedState#/" + name, "seed", state.get(name, 0), None)]
        if kind == "PixaromaSizes":
            state = json.loads(inputs.get("SizesState", "{}"))
            if "w" not in state or "h" not in state:
                sizes = state.get("sizes") or [[1024, 1024]]
                index = max(0, min(int(state.get("selected", 0)), len(sizes) - 1))
                width, height = sorted(sizes[index])
                if state.get("orientation") == "landscape":
                    width, height = height, width
                step = int(state.get("snap", 0) or 0)
                state["w"] = round(width / step) * step if step else width
                state["h"] = round(height / step) * step if step else height
            return [
                ("SizesState#/w", "width", state["w"], None),
                ("SizesState#/h", "height", state["h"], None),
            ]
        if kind == "PixaromaSliders":
            state = json.loads(inputs.get("SlidersState", "{}"))
            return _slider_fields(state.get("sliders", []))
    except (ValueError, TypeError, AttributeError, KeyError):
        return []
    return []


def set_state_value(graph: dict[str, Any], key: str, value: Any) -> None:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
    if not isinstance(value, (str, int, float, bool)):
        msg = "工作流 JSON 狀態需要文字、數字或開關"
        raise StudioError(msg)
    node_id, _, name = key.rpartition("::")
    name, _, pointer = name.partition("#/")
    try:
        state = json.loads(graph[node_id]["inputs"].get(name, "{}"))
        target = state
        parts = pointer.split("/")
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        leaf = int(parts[-1]) if isinstance(target, list) else parts[-1]
        if (
            name == "SlidersState"
            and isinstance(target, dict)
            and target.get("type") == "toggle"
            and isinstance(value, bool)
        ):
            value = int(value)
        previous = target.get(leaf) if isinstance(target, dict) else target[leaf]
        if isinstance(previous, bool) and not isinstance(value, bool):
            msg = "工作流狀態需要開關值"
            raise StudioError(msg)
        if isinstance(previous, str) and not isinstance(value, str):
            msg = "工作流狀態需要文字"
            raise StudioError(msg)
        if isinstance(previous, (int, float)) and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            msg = "工作流狀態需要數字"
            raise StudioError(msg)
        target[leaf] = value
        graph[node_id]["inputs"][name] = json.dumps(state, ensure_ascii=False)
    except (ValueError, TypeError, KeyError, IndexError) as error:
        msg = "工作流 JSON 狀態欄位無效"
        raise StudioError(msg) from error
