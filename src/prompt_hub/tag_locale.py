from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

TAG_TRANSLATIONS_ZH = {
    "1girl": "一名女孩",
    "1woman": "一名成年女性",
    "1boy": "一名男孩",
    "1man": "一名成年男性",
    "solo": "单人",
    "multiple_girls": "多名女性",
    "looking_at_viewer": "看向观众",
    "full_body": "全身",
    "upper_body": "上半身",
    "cowboy_shot": "大腿以上构图",
    "portrait": "肖像",
    "standing": "站立",
    "sitting": "坐姿",
    "lying": "躺姿",
    "smile": "微笑",
    "open_mouth": "张嘴",
    "closed_mouth": "闭嘴",
    "blush": "脸红",
    "long_hair": "长发",
    "short_hair": "短发",
    "medium_hair": "中长发",
    "very_long_hair": "超长发",
    "silver_hair": "银发",
    "white_hair": "白发",
    "grey_hair": "灰发",
    "black_hair": "黑发",
    "brown_hair": "棕发",
    "blonde_hair": "金发",
    "red_hair": "红发",
    "blue_hair": "蓝发",
    "purple_hair": "紫发",
    "pink_hair": "粉发",
    "green_hair": "绿发",
    "blue_eyes": "蓝眼睛",
    "red_eyes": "红眼睛",
    "green_eyes": "绿眼睛",
    "purple_eyes": "紫眼睛",
    "brown_eyes": "棕眼睛",
    "yellow_eyes": "黄眼睛",
    "grey_eyes": "灰眼睛",
    "heterochromia": "异色瞳",
    "dress": "连衣裙",
    "skirt": "裙子",
    "shirt": "衬衫",
    "jacket": "夹克",
    "coat": "外套",
    "gloves": "手套",
    "boots": "靴子",
    "high_heels": "高跟鞋",
    "uniform": "制服",
    "military_uniform": "军装",
    "school_uniform": "校服",
    "swimsuit": "泳装",
    "bikini": "比基尼",
    "lingerie": "内衣",
    "nude": "裸体",
    "breasts": "胸部",
    "large_breasts": "大胸",
    "small_breasts": "小胸",
    "cleavage": "乳沟",
    "nipples": "乳头",
    "indoors": "室内",
    "outdoors": "室外",
    "simple_background": "简洁背景",
    "white_background": "白色背景",
    "black_background": "黑色背景",
    "night": "夜晚",
    "sunset": "日落",
    "backlighting": "逆光",
    "rim_light": "轮廓光",
    "depth_of_field": "景深",
    "from_above": "俯视",
    "from_below": "仰视",
    "from_side": "侧面视角",
    "front_view": "正面视角",
    "profile": "侧脸",
    "masterpiece": "杰作质量",
    "best_quality": "最佳质量",
    "very_aesthetic": "高审美",
    "watermark": "水印",
    "text": "文字",
    "signature": "签名",
    "username": "用户名",
    "lowres": "低分辨率",
    "blurry": "模糊",
    "jpeg_artifacts": "JPEG 压缩痕迹",
}

TOKEN_TRANSLATIONS_ZH = {
    "adult": "成年",
    "aesthetic": "审美",
    "arm": "手臂",
    "arms": "手臂",
    "back": "背面",
    "black": "黑色",
    "blonde": "金色",
    "blue": "蓝色",
    "body": "身体",
    "brown": "棕色",
    "closed": "闭合",
    "coat": "外套",
    "dark": "深色",
    "dress": "连衣裙",
    "eyes": "眼睛",
    "face": "脸部",
    "female": "女性",
    "from": "从",
    "full": "全身",
    "girl": "女孩",
    "green": "绿色",
    "grey": "灰色",
    "hair": "头发",
    "hand": "手",
    "hands": "手",
    "high": "高",
    "jacket": "夹克",
    "light": "光线",
    "long": "长",
    "looking": "看向",
    "male": "男性",
    "medium": "中等",
    "mouth": "嘴",
    "open": "张开",
    "pink": "粉色",
    "purple": "紫色",
    "quality": "质量",
    "red": "红色",
    "short": "短",
    "shirt": "衬衫",
    "side": "侧面",
    "silver": "银色",
    "skirt": "裙子",
    "upper": "上半身",
    "very": "非常",
    "view": "视角",
    "viewer": "观众",
    "white": "白色",
    "yellow": "黄色",
}

_REVERSE_TRANSLATIONS = {value.casefold(): key for key, value in TAG_TRANSLATIONS_ZH.items()}
_TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_()'./:+\- ]*$")


class TagLocaleError(ValueError):
    pass


def resolve_canonical_tag(value: str) -> str:
    clean = value.strip()
    if not clean:
        return ""
    translated = _REVERSE_TRANSLATIONS.get(clean.casefold())
    if translated:
        return translated
    if _contains_cjk(clean):
        message = f"无法确认中文标签“{clean}”对应的标准英文 tag"
        raise TagLocaleError(message)
    if not _TAG_PATTERN.fullmatch(clean):
        message = f"标签包含不支持的字符: {clean}"
        raise TagLocaleError(message)
    return clean


def localize_tag(value: str, *, language: str = "zh") -> dict[str, Any]:
    canonical = resolve_canonical_tag(value)
    zh, known = _translate_zh(canonical)
    display = canonical if language == "en" else f"{zh} ({canonical})" if zh else canonical
    return {
        "tag": canonical,
        "en": canonical,
        "zh": zh,
        "display": display,
        "known": known,
    }


def localize_tags(values: Iterable[str], *, language: str = "zh") -> list[dict[str, Any]]:
    if language not in {"zh", "en"}:
        message = "标签显示语言只支持 zh 或 en"
        raise TagLocaleError(message)
    result = []
    seen: set[str] = set()
    for value in values:
        localized = localize_tag(str(value), language=language)
        canonical = str(localized["tag"])
        key = canonical.casefold()
        if not canonical or key in seen:
            continue
        seen.add(key)
        result.append(localized)
    return result


def tag_catalog(*, language: str = "zh") -> list[dict[str, Any]]:
    """Return curated common tags while retaining their canonical English values."""
    return localize_tags(sorted(TAG_TRANSLATIONS_ZH), language=language)


def _translate_zh(canonical: str) -> tuple[str, bool]:
    normalized = canonical.casefold().replace(" ", "_")
    exact = TAG_TRANSLATIONS_ZH.get(normalized)
    if exact:
        return exact, True
    tokens = [token for token in normalized.split("_") if token]
    translated = [TOKEN_TRANSLATIONS_ZH.get(token, "") for token in tokens]
    if tokens and all(translated):
        return "".join(translated), True
    return "", False


def _contains_cjk(value: str) -> bool:
    return any("\u3400" <= character <= "\u9fff" for character in value)
