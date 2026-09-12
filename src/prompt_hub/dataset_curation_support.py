from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, TypedDict
from uuid import uuid4

from prompt_hub.dataset_tagging import DatasetTaggingError, normalize_tag_draft
from prompt_hub.dataset_workspace import DatasetWorkspaceError
from prompt_hub.tag_locale import TagLocaleError, resolve_canonical_tag

if TYPE_CHECKING:
    from pathlib import Path

CaptionProfile = Literal["anima", "krea2"]
CaptionMode = Literal["general", "portrait", "outfit", "style"]
MAX_CAPTION_CHARS = 12000
MAX_CAPTION_TOKENS = 300
CAPTION_OPTION_IDS = (
    "age",
    "lighting",
    "light_source",
    "camera_angle",
    "action",
    "content_rating",
    "exclude_artwork_info",
    "avoid_meta_phrases",
    "depth_of_field",
    "shot_type",
    "avoid_vague",
    "plain_words",
)
TAG_IGNORED_OPTIONS = {"avoid_meta_phrases", "avoid_vague", "plain_words"}
ANIMA_MEDIA_TAGS = {
    "3d",
    "3d_render",
    "anime_coloring",
    "digital_art",
    "illustration",
    "lineart",
    "oil_painting_(medium)",
    "painting_(medium)",
    "photo",
    "photorealistic",
    "realistic",
    "sketch",
    "traditional_media",
    "watercolor_(medium)",
}
KREA2_MEDIA_SUFFIX = re.compile(
    r"\s+(?:(?:rendered|depicted)\s+)?(?:in|as)\s+(?:an?\s+)?"
    r"(?:realistic\s+)?(?:photo(?:graphic)?|photograph|anime|illustration|digital art|"
    r"3d render|painting|watercolor|sketch)(?:\s+(?:medium|style))?(?=[.!?,;:]|$)",
    flags=re.IGNORECASE,
)


class CaptionSettings(TypedDict):
    profile_id: CaptionProfile
    mode: CaptionMode
    trigger: str
    media_tags: bool
    options: dict[str, bool]
    max_tokens: int


# 视觉模型常常输出弯引号、破折号和省略号。那不是「不是英文」。
# 只是排版字符。训练用的说明统一成 ASCII 标点也更干净。
_TYPOGRAPHY_FOLD = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u00b4": "'",
        "\u02bc": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\u2026": "...",
        "\u00a0": " ",
        "\u2009": " ",
        "\u202f": " ",
    }
)

# 要挡的是模型回了中文或日文。不是所有非 ASCII 字符。
# 之前用 isascii 当代理。结果 "a woman's shirt" 只因为一个弯引号
# 就被判成「不是英文」——讯息本身还是错的。cafe 上的重音同理。
_CJK_PATTERN = re.compile(
    "[\u3000-\u303f\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf"
    "\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff\uff00-\uffef]"
)
CAPTION_NOT_ENGLISH_MESSAGE = "最终 caption 必须使用英文。模型这次返回了中日韩文字"


def _normalize_caption(profile_id: CaptionProfile, caption: str) -> str:
    clean = caption.strip().translate(_TYPOGRAPHY_FOLD)[:MAX_CAPTION_CHARS]
    if clean and _CJK_PATTERN.search(clean):
        raise DatasetWorkspaceError(CAPTION_NOT_ENGLISH_MESSAGE)
    if profile_id == "anima":
        try:
            return normalize_tag_draft(clean)
        except DatasetTaggingError as error:
            raise DatasetWorkspaceError(str(error)) from error
    return " ".join(clean.split())


def normalize_caption_with_settings(
    profile_id: CaptionProfile,
    caption: str,
    settings: CaptionSettings,
) -> str:
    clean = _normalize_caption(profile_id, caption)
    if profile_id == "anima":
        return ", ".join(_apply_anima_caption_settings(_split_tags(clean), settings))
    return _apply_krea2_caption_settings(clean, settings)


def caption_mode_contract() -> dict[str, Any]:
    options = [
        {
            "id": option_id,
            "label": _caption_option_label(option_id),
            "profiles": ["krea2"] if option_id in TAG_IGNORED_OPTIONS else ["anima", "krea2"],
            "default": False,
        }
        for option_id in CAPTION_OPTION_IDS
    ]
    return {
        "modes": [
            {
                "id": "general",
                "label": "通用",
                "omits": "无",
                "trigger_label": "",
            },
            {
                "id": "portrait",
                "label": "肖像",
                "omits": "面部五官",
                "trigger_label": "人物称呼",
            },
            {
                "id": "outfit",
                "label": "服装",
                "omits": "服装",
                "trigger_label": "服装名称",
            },
            {
                "id": "style",
                "label": "风格",
                "omits": "画风、色调、光线",
                "trigger_label": "风格名称",
            },
        ],
        "options": options,
        "media_tags_default": True,
        "media_tags_by_mode": {"general": True, "portrait": True, "outfit": True, "style": False},
        "max_tokens_default": MAX_CAPTION_TOKENS,
    }


def normalize_caption_settings(
    profile_id: CaptionProfile,
    payload: Mapping[str, Any] | None = None,
) -> CaptionSettings:
    raw = payload or {}
    mode = str(raw.get("mode", "general"))
    if mode not in {"general", "portrait", "outfit", "style"}:
        message = "Unsupported caption mode"
        raise DatasetWorkspaceError(message)
    # 触发词是选填的。留空只是让省略掉的内容没有词承载。
    # 说明本身照样生成得出来。要不要接受这个代价是使用者的判断。
    # 之前后端强制要求。前端放行、后端在第一张之前就整个队列失败。
    trigger = "" if mode == "general" else " ".join(str(raw.get("trigger", "")).split())
    raw_options = raw.get("options", {})
    option_values = raw_options if isinstance(raw_options, Mapping) else {}
    options = {
        option_id: bool(option_values.get(option_id, False))
        for option_id in CAPTION_OPTION_IDS
        if profile_id != "anima" or option_id not in TAG_IGNORED_OPTIONS
    }
    with_default = raw.get("media_tags", mode != "style")
    with_tokens = raw.get("max_tokens", MAX_CAPTION_TOKENS)
    try:
        max_tokens = int(with_tokens)
    except (TypeError, ValueError) as error:
        message = "Invalid max_tokens"
        raise DatasetWorkspaceError(message) from error
    return {
        "profile_id": profile_id,
        "mode": mode,  # type: ignore[typeddict-item]
        "trigger": trigger[:120],
        "media_tags": bool(with_default),
        "options": options,
        "max_tokens": min(max(max_tokens, 1), 1200),
    }


def _caption_option_label(option_id: str) -> str:
    return {
        "age": "包含年龄信息",
        "lighting": "描述光线",
        "light_source": "描述光源",
        "camera_angle": "描述镜头角度",
        "action": "描述动作",
        "content_rating": "包含内容分级",
        "exclude_artwork_info": "排除作品信息",
        "avoid_meta_phrases": "避免元短语",
        "depth_of_field": "描述景深",
        "shot_type": "描述景别",
        "avoid_vague": "避免模糊描述",
        "plain_words": "使用直白词汇",
    }.get(option_id, option_id)


def _apply_tag_operation(caption: str, operation: Mapping[str, Any]) -> str:
    tags = _split_tags(caption)
    remove = set(_normalize_tag_list(operation.get("remove", [])))
    replacements_raw = operation.get("replace", {})
    replacements = (
        {
            _normalize_tag(str(before)): _normalize_tag(str(after))
            for before, after in replacements_raw.items()
        }
        if isinstance(replacements_raw, dict)
        else {}
    )
    edited = [replacements.get(tag, tag) for tag in tags if tag not in remove]
    edited.extend(_normalize_tag_list(operation.get("add", [])))
    deduped = list(dict.fromkeys(tag for tag in edited if tag))
    if _should_apply_caption_settings(operation):
        deduped = _apply_anima_caption_settings(
            deduped,
            normalize_caption_settings("anima", operation),
        )
    if bool(operation.get("sort", False)):
        trigger = _trigger_tag(operation)
        if trigger and deduped[:1] == [trigger]:
            deduped = [trigger, *sorted(deduped[1:])]
        else:
            deduped.sort()
    return ", ".join(_prepend_tags(deduped, operation))


def _prepend_tags(tags: list[str], operation: Mapping[str, Any]) -> list[str]:
    """把触发词放到最前面。

    触发词只有排在第一位才是触发词。所以插入要在排序之后做。
    已经出现在别处时先删掉再放到最前——同一个词出现两次会稀释它。
    """
    leading = _normalize_tag_list(operation.get("prepend", []))
    if not leading:
        return tags
    head = list(dict.fromkeys(tag for tag in leading if tag))
    return [*head, *(tag for tag in tags if tag not in head)]


def _apply_krea2_operation(caption: str, operation: Mapping[str, Any]) -> str:
    clean = _normalize_caption("krea2", caption)
    remove = [str(item).strip() for item in operation.get("remove", []) if str(item).strip()]
    for item in remove:
        clean = clean.replace(item, "")
    replacements = operation.get("replace", {})
    if isinstance(replacements, dict):
        for before, after in replacements.items():
            clean = clean.replace(str(before), str(after))
    additions = [str(item).strip() for item in operation.get("add", []) if str(item).strip()]
    if additions:
        suffix = ", ".join(additions)
        clean = f"{clean}, {suffix}" if clean else suffix
    clean = _prepend_krea2(clean, operation)
    clean = _normalize_caption("krea2", clean)
    if _should_apply_caption_settings(operation):
        return _apply_krea2_caption_settings(
            clean,
            normalize_caption_settings("krea2", operation),
        )
    return clean


def _prepend_krea2(caption: str, operation: Mapping[str, Any]) -> str:
    """把触发词插到整段说明的最前面。

    自然语言说明没有标签那种顺序无关性。触发词要在开头才会被学到。
    已经以它开头的就不再插一次——批量操作会被人反复按。
    """
    leading = [str(item).strip() for item in operation.get("prepend", []) if str(item).strip()]
    if not leading:
        return caption
    head = ", ".join(dict.fromkeys(leading))
    if not caption:
        return head
    if caption.lower().startswith(head.lower()):
        return caption
    return f"{head}, {caption}"


def _normalize_tag_list(value: object) -> list[str]:
    if isinstance(value, str):
        values = value.replace("\n", ",").split(",")
    elif isinstance(value, Iterable):
        values = value
    else:
        return []
    return list(dict.fromkeys(_normalize_tag(str(item)) for item in values if str(item).strip()))


def _normalize_tag(value: str) -> str:
    try:
        canonical = resolve_canonical_tag(value)
        return normalize_tag_draft(canonical.replace(" ", "_"))
    except (DatasetTaggingError, TagLocaleError) as error:
        raise DatasetWorkspaceError(str(error)) from error


def _apply_anima_caption_settings(
    tags: list[str],
    settings: CaptionSettings,
) -> list[str]:
    omitted = _omitted_anima_markers(settings["mode"])
    filtered = [
        tag
        for tag in tags
        if not any(_tag_matches_omitted_marker(tag, marker) for marker in omitted)
    ]
    if not settings["media_tags"]:
        filtered = [tag for tag in filtered if tag not in ANIMA_MEDIA_TAGS]
    if settings["mode"] != "general" and settings["trigger"]:
        filtered.insert(0, normalize_tag_draft(settings["trigger"].replace(" ", "_")))
    return list(dict.fromkeys(tag for tag in filtered if tag))


def _apply_krea2_caption_settings(caption: str, settings: CaptionSettings) -> str:
    clean = caption
    trigger = settings["trigger"]
    if settings["mode"] != "general" and trigger:
        clean = _replace_krea2_subject(clean, trigger)
    if not settings["media_tags"]:
        clean = KREA2_MEDIA_SUFFIX.sub("", clean)
    return clean


def _replace_krea2_subject(caption: str, trigger: str) -> str:
    patterns = (
        (
            r"^(?:an?\s+)?(?:young\s+|adult\s+)?(?:woman|female|girl|man|male|boy|person|character|subject)\s+",
            f"{trigger} ",
        ),
        (
            r"\b(?:an?\s+)?(?:young\s+|adult\s+)?(?:woman|female|girl|man|male|boy|person|character|subject)\b",
            trigger,
        ),
    )
    result = caption
    for pattern, replacement in patterns:
        result, count = re.subn(pattern, replacement, result, count=1, flags=re.IGNORECASE)
        if count:
            return result
    return caption


def _operation_profile(operation: Mapping[str, Any]) -> CaptionProfile:
    profile_id = str(operation.get("profile_id", "anima"))
    if profile_id not in {"anima", "krea2"}:
        message = "Invalid bulk caption profile"
        raise DatasetWorkspaceError(message)
    return profile_id  # type: ignore[return-value]


def is_prepend_only_operation(operation: Mapping[str, Any]) -> bool:
    """这一批是不是只在最前面插了一个触发词。

    一般的批量整理会改写说明内容。改完要人重新看一遍。所以落成草稿。
    但插触发词不改任何一个既有的字。人也是刚刚亲手输入的。
    把它当成需要重新确认的改写。就会把整批已确认的说明打回草稿。
    然后交付被自己挡下来。
    """
    if not [str(item).strip() for item in operation.get("prepend", []) if str(item).strip()]:
        return False
    if operation.get("add") or operation.get("remove") or operation.get("replace"):
        return False
    if bool(operation.get("sort", False)):
        return False
    return not _should_apply_caption_settings(operation)


def _should_apply_caption_settings(operation: Mapping[str, Any]) -> bool:
    return str(operation.get("mode", "general")) != "general" or bool(
        str(operation.get("trigger", "")).strip()
    )


def _trigger_tag(operation: Mapping[str, Any]) -> str:
    if not _should_apply_caption_settings(operation):
        return ""
    settings = normalize_caption_settings("anima", operation)
    if settings["mode"] == "general" or not settings["trigger"]:
        return ""
    return normalize_tag_draft(settings["trigger"].replace(" ", "_"))


def _omitted_anima_markers(mode: CaptionMode) -> tuple[str, ...]:
    if mode == "portrait":
        return ("eye", "eyes", "face", "nose", "mouth", "lip", "lips", "smile", "expression")
    if mode == "outfit":
        return (
            "dress",
            "shirt",
            "skirt",
            "pants",
            "jacket",
            "coat",
            "uniform",
            "outfit",
            "clothes",
            "sleeve",
        )
    if mode == "style":
        return ("style", "lighting", "light", "color", "tone")
    return ()


def _tag_matches_omitted_marker(tag: str, marker: str) -> bool:
    return tag == marker or tag.endswith(f"_{marker}") or tag.startswith(f"{marker}_")


def _split_tags(caption: str) -> list[str]:
    return [tag.strip() for tag in caption.split(",") if tag.strip()]


def _suspicious_tag(tag: str) -> bool:
    return not tag.isascii() or tag != tag.casefold() or " " in tag or "__" in tag


def _change_summary(changes: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    added = 0
    removed = 0
    for change in changes:
        before = set(_split_tags(str(change.get("before", ""))))
        after = set(_split_tags(str(change.get("after", ""))))
        added += len(after - before)
        removed += len(before - after)
    return {"added_instances": added, "removed_instances": removed}


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        message = f"Invalid JSON object: {path}"
        raise DatasetWorkspaceError(message)
    return loaded


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _inside_directory(root: Path, relative_path: str) -> Path:
    clean_root = root.resolve()
    path = (clean_root / relative_path).resolve()
    if not path.is_relative_to(clean_root):
        message = "Dataset export path escapes its version directory"
        raise DatasetWorkspaceError(message)
    return path


def _safe_directory_name(value: str) -> str:
    clean = "".join(
        character if character.isalnum() or character in "-_." else "-" for character in value
    )
    clean = re.sub(r"-+", "-", clean).strip("-.")[:80]
    return clean or "dataset"


def _directory_stats(root: Path) -> tuple[int, int]:
    files = [path for path in root.rglob("*") if path.is_file()] if root.is_dir() else []
    return len(files), sum(path.stat().st_size for path in files)


def _source_result_asset_ids(items: Iterable[Mapping[str, Any]]) -> list[str]:
    result = []
    for item in items:
        source = item.get("source", {})
        if isinstance(source, Mapping) and source.get("asset_id"):
            result.append(str(source["asset_id"]))
    return result


def _directory_digest_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_hash_manifest(root: Path) -> None:
    lines = [
        f"{digest}  {relative_path}"
        for relative_path, digest in _directory_digest_map(root).items()
        if relative_path != "hashes.sha256"
    ]
    (root / "hashes.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timestamp_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
