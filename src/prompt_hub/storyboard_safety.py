"""Resource and filesystem boundaries around the pinned storyboard release."""

from __future__ import annotations

import json
import math
from importlib import import_module
from pathlib import Path, PureWindowsPath
from typing import Any

MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
MAX_ELEMENTS = 50_000
MAX_DEPTH = 48
MAX_TREE_FILES = 20_000
MAX_CANVAS_SIDE = 8192
MAX_CANVAS_PIXELS = 16_000_000
MAX_PAGE_ITEMS = 256
MAX_JSON_NUMBER = 2**64
PRODUCTION_PATH_FIELDS = {
    "path",
    "selected_render",
    "selected",
    "source_render",
    "mask",
    "candidate_sheet",
    "underlay",
    "font",
}


def identifier(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or value in {".", ".."}
        or value.endswith((" ", "."))
        or any(character in value for character in '/\\:.\x00<>"|?*')
        or any(ord(character) < 32 for character in value)
        or PureWindowsPath(value).is_reserved()
    ):
        raise ValueError("分镜标识不能包含路径、保留文件名或控制字符")
    return value


def json_document(source: dict[str, Any] | str) -> dict[str, Any]:
    """Accept JSON content only; never interpret user strings as local paths."""
    if isinstance(source, str):
        if len(source.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError("分镜文件不能超过 16 MiB")
        try:
            source = json.loads(source.lstrip("\ufeff"))
        except (json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("请输入有效的分镜 JSON 内容") from exc
    if not isinstance(source, dict):
        raise TypeError("分镜文件必须是 JSON 对象")
    count = 0

    def walk(value: object, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_ELEMENTS or depth > MAX_DEPTH:
            raise ValueError("分镜 JSON 嵌套或元素数量超过限制")
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise TypeError("JSON 键必须是字符串")
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                walk(child, depth + 1)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if (isinstance(value, float) and not math.isfinite(value)) or abs(
                value
            ) > MAX_JSON_NUMBER:
                raise ValueError("分镜数字必须有限且在可处理范围内")
        elif value is not None and not isinstance(value, (str, bool)):
            raise TypeError("分镜只接受 JSON 数据")

    walk(source, 0)
    content = json.dumps(source, ensure_ascii=False, allow_nan=False)
    if len(content.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ValueError("分镜文件不能超过 16 MiB")
    return json.loads(content)


def local_path(root: Path, relative: str) -> Path:
    if root.is_symlink() or root.is_junction():
        raise ValueError("分镜目录不接受符号链接或目录联接")
    text = relative.replace("\\", "/")
    windows = PureWindowsPath(text)
    if (
        not text
        or windows.drive
        or windows.root
        or any(part in {"", ".", ".."} for part in text.split("/"))
        or any(character in text for character in ":\x00")
    ):
        raise ValueError("分镜文件必须使用项目内相对路径")
    target = root / text
    current = root
    for part in Path(text).parts:
        current /= part
        if current.is_symlink() or current.is_junction():
            raise ValueError("分镜目录不接受符号链接或目录联接")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("分镜路径不能越出目录")
    return target


def audit_tree(root: Path) -> None:
    """Reject linked inputs before any core API can traverse or overwrite them."""
    if root.is_symlink() or root.is_junction():
        raise ValueError("分镜目录不接受符号链接或目录联接")
    pending = [root]
    count = 0
    while pending:
        directory = pending.pop()
        if not directory.exists():
            continue
        for path in directory.iterdir():
            count += 1
            if count > MAX_TREE_FILES:
                raise ValueError("分镜目录文件数量超过限制")
            if path.is_symlink() or path.is_junction():
                raise ValueError("分镜目录不接受符号链接或目录联接")
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("分镜路径不能越出目录")
            if path.is_dir():
                pending.append(path)
            elif path.is_file() and path.stat().st_nlink > 1:
                raise ValueError("分镜目录不接受硬链接文件")


def validate_paths(raw: dict[str, Any], root: Path) -> list[str]:
    """Reuse the core path API when available; shield the pinned pre-F9 wheel too."""
    errors: list[str] = []

    def walk(value: object, *, production: bool = False) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if (
                    key in {"image_path", "selected_render", "candidate_sheet"}
                    or (production and key in PRODUCTION_PATH_FIELDS)
                ) and child is not None:
                    try:
                        if not isinstance(child, str):
                            raise TypeError("production 路径必须是字符串")
                        local_path(root, child)
                    except (ValueError, TypeError) as exc:
                        errors.append(str(exc))
                elif not production or key not in {"meta", "lora"}:
                    walk(child, production=production or key in {"production", "renders"})
        elif isinstance(value, list):
            for child in value:
                walk(child, production=production)

    walk(raw)
    try:
        module = import_module("soda_storyboard.production.paths")
    except ModuleNotFoundError:
        return errors
    errors.extend(module.validate_production_paths(raw, root))
    return list(dict.fromkeys(errors))


def page_limits(raw: dict[str, Any], root: Path) -> None:
    identifier(raw.get("page_id", raw.get("id")))
    width = raw.get("canvas_width", raw.get("width", 1024))
    height = raw.get("canvas_height", raw.get("height", 1536))
    canvas = raw.get("canvas", raw.get("canvas_size", {}))
    if isinstance(canvas, dict):
        width = raw.get("canvas_width", raw.get("width", canvas.get("width", width)))
        height = raw.get("canvas_height", raw.get("height", canvas.get("height", height)))
    if (
        type(width) is not int
        or type(height) is not int
        or not 1 <= width <= MAX_CANVAS_SIDE
        or not 1 <= height <= MAX_CANVAS_SIDE
        or width * height > MAX_CANVAS_PIXELS
    ):
        raise ValueError("分镜画布须为正整数，单边最多 8192，总计最多 1600 万像素")
    for name in ("panels", "texts", "objects", "overlays"):
        items = raw.get(name, [])
        if not isinstance(items, list) or len(items) > MAX_PAGE_ITEMS:
            raise ValueError("每种分镜元素最多 256 个")
        for item in items:
            if not isinstance(item, dict):
                raise TypeError("分镜元素必须是 JSON 对象")
            if item.get("id"):
                identifier(item["id"])
            for key in ("character_id", "speaker_id", "panel_id"):
                if item.get(key):
                    identifier(item[key])
            for referenced in item.get("character_ids", []):
                identifier(referenced)
            figures = item.get("figures", [])
            if not isinstance(figures, list) or len(figures) > MAX_PAGE_ITEMS:
                raise ValueError("每格人物数量超过限制")
            for figure in figures:
                if not isinstance(figure, dict):
                    raise TypeError("人物必须是 JSON 对象")
                if figure.get("character_id"):
                    identifier(figure["character_id"])
    errors = validate_paths(raw, root)
    if errors:
        raise ValueError("；".join(errors))
