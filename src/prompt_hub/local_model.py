from __future__ import annotations

import base64
import json
from contextlib import suppress
from io import BytesIO
from typing import IO, TYPE_CHECKING, Any, override
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from PIL import Image, ImageOps

from prompt_hub.creative import SLOT_LABELS, SLOT_ORDER
from prompt_hub.dataset_curation_support import (
    CaptionMode,
    normalize_caption_settings,
    normalize_caption_with_settings,
)
from prompt_hub.dataset_curation_support import (
    caption_mode_contract as _caption_mode_contract,
)
from prompt_hub.model_connections import MODEL_REF_PATTERN

if TYPE_CHECKING:
    from http.client import HTTPMessage
    from pathlib import Path

    from prompt_hub.model_connections import ModelConnection, ModelConnectionStore

DEFAULT_LM_STUDIO_URL = "http://127.0.0.1:1234/v1"
MAX_MODEL_RESPONSE_BYTES = 4 * 1024 * 1024


class LocalModelError(RuntimeError):
    pass


def caption_mode_contract() -> dict[str, Any]:
    return _caption_mode_contract()


class _NoRedirect(HTTPRedirectHandler):
    @override
    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> None:
        return None


def list_local_models(base_url: str = DEFAULT_LM_STUDIO_URL) -> list[dict[str, Any]]:
    server_root = base_url.rstrip("/").removesuffix("/v1")
    payload = _request_json(f"{server_root}/api/v1/models")
    rows = payload.get("models", []) if isinstance(payload, dict) else []
    return [
        {
            "id": str(row.get("key", "")),
            "name": str(row.get("display_name", row.get("key", ""))),
            "loaded": bool(row.get("loaded_instances")),
            "vision": bool(row.get("capabilities", {}).get("vision", False)),
            "params": str(row.get("params_string") or ""),
        }
        for row in rows
        if isinstance(row, dict) and row.get("key") and row.get("type") == "llm"
    ]


def organize_slots(
    *,
    brief: str,
    slots: dict[str, str],
    locks: dict[str, bool],
    model: str,
    target_profile: str,
    base_url: str = DEFAULT_LM_STUDIO_URL,
    connections: ModelConnectionStore | None = None,
) -> dict[str, Any]:
    editable = [slot for slot in SLOT_ORDER if not locks.get(slot, False)]
    locked = {slot: slots.get(slot, "") for slot in SLOT_ORDER if locks.get(slot, False)}
    instruction = (
        "你是 AI 绘图提示词整理助手。不要展示推理过程，把用户创作意图整理为七槽位 JSON。"
        "只输出一个 JSON 对象，不要 Markdown，不要解释。键必须是："
        + ", ".join(SLOT_ORDER)
        + "。保留具体人物、服装、动作、镜头、环境、灯光和画风信息。"
        f"目标模型是 {target_profile}；Anima 槽位优先简洁英文 Booru 标签，"
        "Krea 2 槽位优先连贯、具体的自然语言。"
        "合法成人向内容可照常整理，但不得添加未成年人性内容。"
        f"仅允许改写这些未锁定槽位：{', '.join(editable)}。"
    )
    user_payload = {
        "创作意图": brief,
        "已有槽位": slots,
        "锁定槽位_不可修改": locked,
        "槽位中文名": SLOT_LABELS,
    }
    external = _resolve_external_model(model, connections)
    request_model = external.model_name if external else model
    request_base_url = external.base_url if external else base_url
    payload = {
        "model": request_model,
        "messages": [
            {"role": "system", "content": instruction},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False) + "\n/no_think",
            },
        ],
        "temperature": 0.35,
        "max_tokens": 500,
        "stream": False,
    }
    response = _request_json(
        f"{request_base_url.rstrip('/')}/chat/completions",
        method="POST",
        payload=payload,
        timeout=90,
        api_key=external.api_key if external else "",
        allow_redirects=external is None,
        response_limit=MAX_MODEL_RESPONSE_BYTES if external else None,
        service_name="外部模型服务" if external else "LM Studio",
    )
    try:
        content = response["choices"][0]["message"]["content"]
        suggested = _extract_json_object(str(content))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise LocalModelError("本地模型没有返回可识别的七槽位 JSON") from error
    merged = {
        slot: slots.get(slot, "")
        if locks.get(slot, False)
        else str(suggested.get(slot, "")).strip()
        for slot in SLOT_ORDER
    }
    return {
        "model": model,
        "target_profile": target_profile,
        "suggested_slots": merged,
        "locked_slots": [slot for slot in SLOT_ORDER if locks.get(slot, False)],
    }


def expand_sourcing_queries(
    *,
    brief: str,
    slots: dict[str, str],
    locks: dict[str, bool],
    model: str,
    base_url: str = DEFAULT_LM_STUDIO_URL,
    connections: ModelConnectionStore | None = None,
) -> dict[str, Any]:
    editable = [slot for slot in SLOT_ORDER if not locks.get(slot, False)]
    instruction = (
        "你是本地 AI 绘图资料库的检索规划器。"
        "只输出 JSON 对象，不要解释，不要生成最终 Prompt。"
        "键必须是 character、outfit、action、composition、scene、lighting、style。"
        "每个值是最多 4 个简短英文检索词或短语的数组，"
        "适合搜索 Booru 标签、wildcard、画风和摄影资料。"
        "只提取用户明确表达或合理同义转换的概念，不增加新角色、新服装或新场景。"
        f"锁定槽位必须返回空数组；可检索槽位为：{', '.join(editable)}。"
    )
    external = _resolve_external_model(model, connections)
    request_model = external.model_name if external else model
    request_base_url = external.base_url if external else base_url
    payload = {
        "model": request_model,
        "messages": [
            {"role": "system", "content": instruction},
            {
                "role": "user",
                "content": json.dumps(
                    {"创作意图": brief, "当前槽位": slots, "锁定状态": locks},
                    ensure_ascii=False,
                )
                + "\n/no_think",
            },
        ],
        "temperature": 0.15,
        "max_tokens": 350,
        "stream": False,
    }
    response = _request_json(
        f"{request_base_url.rstrip('/')}/chat/completions",
        method="POST",
        payload=payload,
        timeout=90,
        api_key=external.api_key if external else "",
        allow_redirects=external is None,
        response_limit=MAX_MODEL_RESPONSE_BYTES if external else None,
        service_name="外部模型服务" if external else "LM Studio",
    )
    try:
        content = response["choices"][0]["message"]["content"]
        raw_queries = _extract_json_object(str(content))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise LocalModelError("本地模型没有返回可识别的检索词 JSON") from error
    queries = {}
    for slot in SLOT_ORDER:
        if locks.get(slot, False):
            queries[slot] = []
            continue
        raw_value = raw_queries.get(slot, [])
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        queries[slot] = _clean_query_values(values)
    return {"model": model, "queries": queries}


def analyze_result_image(
    *,
    image_path: Path,
    project: dict[str, Any],
    model: str,
    base_url: str = DEFAULT_LM_STUDIO_URL,
    connections: ModelConnectionStore | None = None,
) -> dict[str, Any]:
    instruction = (
        "你是 AI 绘图结果复盘助手。只输出一个 JSON 对象，不要 Markdown，不要解释。"
        "你要比较实际图片与用户创作意图，客观描述画面，并给出可执行的下一轮 Prompt 修改。"
        "JSON 必须包含：summary_zh 字符串；observed_slots 对象，键为 character、outfit、action、"
        "composition、scene、lighting、style；strengths、issues、improvements 三个字符串数组；"
        "reconstructed_prompts 对象，包含 anima_positive、anima_negative、krea2_positive、"
        "krea2_avoid；safety_warning 字符串。"
        "Anima 使用简洁英文 Booru 标签，Krea 2 使用具体自然语言。"
        "合法成年人的 SFW 或 NSFW 图片都可以如实分析，不要说教或因为成人内容省略服装、姿势、"
        "构图与灯光；若明确成人内容中的人物可能未成年，则填写 safety_warning，并省略露骨反推。"
        "不要猜测图片中不可见的身份或身体特征。summary_zh 最多 80 个中文字符；每个槽位一句；"
        "strengths、issues、improvements 各最多 3 条，每条最多 40 个中文字符；"
        "每段反推 Prompt 最多 300 个英文字符。必须简洁，禁止输出推理过程。"
    )
    context = {
        "创作意图": project.get("brief_zh", ""),
        "计划槽位": project.get("slots", {}),
        "项目分级": project.get("safety_mode", "sfw"),
        "目标Profile": project.get("target_profile", "anima"),
    }
    image_data_url = _image_data_url(image_path)
    payload = {
        "model": model,
        "system_prompt": instruction,
        "input": [
            {"type": "image", "data_url": image_data_url},
            {
                "type": "text",
                "content": "请复盘这张本地生成结果图。项目上下文："
                + json.dumps(context, ensure_ascii=False),
            },
        ],
        "temperature": 0.1,
        "max_output_tokens": 900,
        "reasoning": "off",
        "stream": False,
        "store": False,
    }
    external = _resolve_external_model(model, connections)
    if external:
        content = _external_vision_completion(
            connection=external,
            system_prompt=instruction,
            text_prompt="请复盘这张本地生成结果图。项目上下文："
            + json.dumps(context, ensure_ascii=False),
            image_data_url=image_data_url,
            temperature=0.1,
            max_tokens=900,
        )
    else:
        server_root = base_url.rstrip("/").removesuffix("/v1")
        response = _request_json(
            f"{server_root}/api/v1/chat",
            method="POST",
            payload=payload,
            timeout=180,
        )
        try:
            content = "\n".join(
                str(item.get("content", ""))
                for item in response["output"]
                if isinstance(item, dict) and item.get("type") == "message"
            )
        except (KeyError, TypeError) as error:
            raise LocalModelError("本地视觉模型没有返回可识别的复盘 JSON") from error
    try:
        raw = _extract_json_object(str(content))
    except json.JSONDecodeError as error:
        raise LocalModelError("视觉模型没有返回可识别的复盘 JSON") from error
    raw_slots = raw.get("observed_slots", {})
    slots = raw_slots if isinstance(raw_slots, dict) else {}
    raw_prompts = raw.get("reconstructed_prompts", {})
    prompts = raw_prompts if isinstance(raw_prompts, dict) else {}
    return {
        "model": model,
        "summary_zh": str(raw.get("summary_zh", "")).strip(),
        "observed_slots": {slot: str(slots.get(slot, "")).strip() for slot in SLOT_ORDER},
        "strengths": _clean_text_list(raw.get("strengths", [])),
        "issues": _clean_text_list(raw.get("issues", [])),
        "improvements": _clean_text_list(raw.get("improvements", [])),
        "reconstructed_prompts": {
            key: str(prompts.get(key, "")).strip()
            for key in ("anima_positive", "anima_negative", "krea2_positive", "krea2_avoid")
        },
        "safety_warning": str(raw.get("safety_warning", "")).strip(),
    }


def draft_krea2_caption(
    *,
    image_path: Path,
    model: str,
    existing_caption: str = "",
    mode: CaptionMode = "general",
    trigger: str = "",
    media_tags: bool = True,
    options: dict[str, bool] | None = None,
    max_tokens: int = 300,
    base_url: str = DEFAULT_LM_STUDIO_URL,
    connections: ModelConnectionStore | None = None,
) -> dict[str, Any]:
    settings = normalize_caption_settings(
        "krea2",
        {
            "mode": mode,
            "trigger": trigger,
            "media_tags": media_tags,
            "options": options or {},
            "max_tokens": max_tokens,
        },
    )
    instruction = (
        "You write concise English natural-language training captions for Krea 2 image datasets. "
        "Return one JSON object only, with keys caption, observations, and safety_warning. "
        "caption must be one fluent English paragraph describing only visible subject identity "
        "cues, "
        "appearance, outfit, pose, composition, setting, lighting, materials, and visual style. "
        "observations must be an object with short English values for subject, appearance, outfit, "
        "pose, composition, setting, lighting, and style. Do not output Booru tag lists. "
        "Legal adult SFW or NSFW images may be described objectively without moral commentary. "
        "If explicit sexual content may depict a minor, do not describe explicit details; set a "
        "clear safety_warning and keep the caption non-explicit. Do not infer invisible anatomy or "
        "identity. "
        f"Caption mode is {settings['mode']}. {_mode_instruction(settings['mode'], 'krea2')} "
        f"{_option_instruction(settings['options'])} "
        f"{_media_instruction(media_tags=settings['media_tags'], profile_id='krea2')} "
        f"{_trigger_instruction(settings['mode'], settings['trigger'], profile_id='krea2')} "
        "Use ASCII English only and do not reveal reasoning."
    )
    context = (
        f"Existing reviewed caption for reference only: {existing_caption[:1200]}"
        if existing_caption.strip()
        else "There is no existing reviewed caption."
    )
    image_data_url = _image_data_url(image_path)
    payload = {
        "model": model,
        "system_prompt": instruction,
        "input": [
            {"type": "image", "data_url": image_data_url},
            {
                "type": "text",
                "content": f"Draft a Krea 2 caption for this local dataset image. {context}",
            },
        ],
        "temperature": 0.15,
        "max_output_tokens": settings["max_tokens"],
        "reasoning": "off",
        "stream": False,
        "store": False,
    }
    external = _resolve_external_model(model, connections)
    if external:
        content = _external_vision_completion(
            connection=external,
            system_prompt=instruction,
            text_prompt=f"Draft a Krea 2 caption for this local dataset image. {context}",
            image_data_url=image_data_url,
            temperature=0.15,
            max_tokens=settings["max_tokens"],
        )
    else:
        server_root = base_url.rstrip("/").removesuffix("/v1")
        response = _request_json(
            f"{server_root}/api/v1/chat",
            method="POST",
            payload=payload,
            timeout=180,
        )
        try:
            content = "\n".join(
                str(item.get("content", ""))
                for item in response["output"]
                if isinstance(item, dict) and item.get("type") == "message"
            )
        except (KeyError, TypeError) as error:
            raise LocalModelError("本地视觉模型没有返回可识别的 Krea 2 草稿 JSON") from error
    try:
        raw = _extract_json_object(content)
    except json.JSONDecodeError as error:
        raise LocalModelError(_no_json_message(content)) from error
    caption = normalize_caption_with_settings(
        "krea2",
        " ".join(str(raw.get("caption", "")).split()),
        settings,
    )
    if not caption:
        raise LocalModelError("本地视觉模型返回了空的 Krea 2 草稿")
    if not caption.isascii():
        raise LocalModelError("Krea 2 草稿必须使用英文 ASCII 文本")
    raw_observations = raw.get("observations", {})
    observations = raw_observations if isinstance(raw_observations, dict) else {}
    return {
        "model": model,
        "draft": caption[:12000],
        "caption_settings": settings,
        "observations": {
            str(key)[:80]: " ".join(str(value).split())[:1000]
            for key, value in observations.items()
            if str(key).strip() and str(value).strip()
        },
        "safety_warning": " ".join(str(raw.get("safety_warning", "")).split())[:2000],
    }


def draft_anima_tags(
    *,
    image_path: Path,
    model: str,
    existing_tags: str = "",
    mode: CaptionMode = "general",
    trigger: str = "",
    media_tags: bool = True,
    options: dict[str, bool] | None = None,
    max_tokens: int = 300,
    base_url: str = DEFAULT_LM_STUDIO_URL,
    connections: ModelConnectionStore | None = None,
) -> dict[str, Any]:
    settings = normalize_caption_settings(
        "anima",
        {
            "mode": mode,
            "trigger": trigger,
            "media_tags": media_tags,
            "options": options or {},
            "max_tokens": max_tokens,
        },
    )
    instruction = (
        "You write concise Booru-style English tags for Anima image datasets. "
        "Return one JSON object only, with keys tags, rating, and safety_warning. "
        "tags must be an array of ASCII English Booru tags using underscores, ordered from "
        "the most important subject, count, appearance, outfit, pose, composition, setting, "
        "lighting, and style tags to less important details. Do not write a paragraph. "
        "Do not include artist names, copyrights, watermarks, or identity guesses unless they "
        "are visibly established by the image. Legal adult SFW or NSFW images may be tagged "
        "objectively. If explicit sexual content may depict a minor, set a clear safety_warning "
        "and omit explicit tags. "
        f"Caption mode is {settings['mode']}. {_mode_instruction(settings['mode'], 'anima')} "
        f"{_option_instruction(settings['options'])} "
        f"{_media_instruction(media_tags=settings['media_tags'], profile_id='anima')} "
        f"{_trigger_instruction(settings['mode'], settings['trigger'], profile_id='anima')} "
        "Do not reveal reasoning."
    )
    context = (
        f"Existing reviewed or draft Anima tags for reference only: {existing_tags[:1200]}"
        if existing_tags.strip()
        else "There are no existing Anima tags."
    )
    image_data_url = _image_data_url(image_path)
    text_prompt = f"Draft Anima Booru tags for this local dataset image. {context}"
    payload = {
        "model": model,
        "system_prompt": instruction,
        "input": [
            {"type": "image", "data_url": image_data_url},
            {"type": "text", "content": text_prompt},
        ],
        "temperature": 0.1,
        "max_output_tokens": settings["max_tokens"],
        "reasoning": "off",
        "stream": False,
        "store": False,
    }
    external = _resolve_external_model(model, connections)
    if external:
        content = _external_vision_completion(
            connection=external,
            system_prompt=instruction,
            text_prompt=text_prompt,
            image_data_url=image_data_url,
            temperature=0.1,
            max_tokens=settings["max_tokens"],
        )
        provider = "external"
    else:
        server_root = base_url.rstrip("/").removesuffix("/v1")
        response = _request_json(
            f"{server_root}/api/v1/chat",
            method="POST",
            payload=payload,
            timeout=180,
        )
        provider = "LM Studio"
        try:
            content = "\n".join(
                str(item.get("content", ""))
                for item in response["output"]
                if isinstance(item, dict) and item.get("type") == "message"
            )
        except (KeyError, TypeError) as error:
            raise LocalModelError("本地视觉模型没有返回可识别的 Anima 标签草稿 JSON") from error
    try:
        raw = _extract_json_object(content)
    except json.JSONDecodeError as error:
        raise LocalModelError("视觉模型没有返回可识别的 Anima 标签草稿 JSON") from error
    tags = normalize_caption_with_settings(
        "anima",
        ", ".join(_clean_anima_tags(raw.get("tags", []))),
        settings,
    ).split(", ")
    if not tags:
        raise LocalModelError("视觉模型返回了空的 Anima 标签草稿")
    rating_value = raw.get("rating", "")
    rating_tag = (
        str(rating_value.get("tag", "")).strip()
        if isinstance(rating_value, dict)
        else str(rating_value).strip()
    )
    rating: dict[str, Any] = {"tag": rating_tag or "unknown"}
    if isinstance(rating_value, dict):
        raw_score = rating_value.get("score")
        if raw_score is not None:
            with suppress(TypeError, ValueError):
                rating["score"] = float(raw_score)
    general_tags = [{"tag": tag} for tag in tags]
    return {
        "tagger": "model",
        "model": model,
        "provider": provider,
        "rating": rating,
        "general": general_tags,
        "characters": [],
        "tag_string": ", ".join(tags),
        "caption_settings": settings,
        "safety_warning": " ".join(str(raw.get("safety_warning", "")).split())[:2000],
    }


CAPTION_REVISION_SYSTEM_PROMPT = (
    "You revise English image captions used as LoRA training data. "
    "The user gives you the current English caption and a note written in Chinese. "
    "The note is one of two things. It may be a corrected Chinese rendering of the "
    "whole caption, in which case apply only the differences it introduces against "
    "the current caption. Or it may be an instruction describing what to change or add. "
    "Decide which it is from its content. "
    "Keep every detail the note does not touch, and keep the same descriptive register. "
    "Reply with only the revised English caption itself. One paragraph. "
    "No explanation, no quotes, no Chinese."
)
CAPTION_REVISION_MAX_TOKENS = 1200
CAPTION_REVISION_TIMEOUT = 120
MAX_REVISION_CAPTION_LENGTH = 12000
MAX_REVISION_NOTE_LENGTH = 4000


def revise_caption_with_model(
    caption: str,
    instruction: str,
    *,
    connections: ModelConnectionStore | None = None,
) -> str:
    """按修正意见改写英文说明。

    修正意见可以是整段改写后的中文。也可以是一句指示。两种都由模型自己
    判断。因为使用者在同一个输入框里两种都会用。

    失败一律抛错而不是回空字串。翻译回空是合理的 对照是辅助信息。
    没有就不显示 。但改写是使用者按下按钮主动要求的动作。静默不做
    会像按钮坏了。而且前端要靠这个错误来决定不要覆盖既有草稿。
    """
    text = caption.strip()
    note = instruction.strip()
    if not text:
        raise LocalModelError("草稿是空的，没有可改写的内容")
    if not note:
        raise LocalModelError("请先填写修正意见")
    if len(text) > MAX_REVISION_CAPTION_LENGTH or len(note) > MAX_REVISION_NOTE_LENGTH:
        raise LocalModelError("内容过长，无法改写")

    # 与翻译走同一个选择 使用者在模型服务里指定的那个。
    # 没有指定时退回第一个启用的连线。
    connection = connections.get_caption_assist() if connections else None
    if connection is None:
        rows = connections.list_connections() if connections else []
        if not rows:
            raise LocalModelError("没有可用的模型连接，无法改写")
        connection = rows[0]

    payload = {
        "model": connection.model_name,
        "messages": [
            {"role": "system", "content": CAPTION_REVISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Current caption:\n{text}\n\nNote (Chinese):\n{note}",
            },
        ],
        "temperature": 0.2,
        "max_tokens": CAPTION_REVISION_MAX_TOKENS,
        "stream": False,
    }
    response = _request_json(
        f"{connection.base_url.rstrip('/')}/chat/completions",
        method="POST",
        payload=payload,
        timeout=CAPTION_REVISION_TIMEOUT,
        api_key=connection.api_key,
        service_name="改写服务",
    )
    try:
        revised = str(response["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as error:
        raise LocalModelError("改写服务返回了无法解析的结果") from error
    if not revised:
        raise LocalModelError("改写服务返回了空结果")
    return revised


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 4,
    api_key: str = "",
    allow_redirects: bool = True,
    response_limit: int | None = None,
    service_name: str = "LM Studio",
) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=data, method=method, headers=headers)
    try:
        response_context = (
            urlopen(request, timeout=timeout)
            if allow_redirects
            else build_opener(_NoRedirect).open(request, timeout=timeout)
        )
        with response_context as response:
            body = (
                response.read(response_limit + 1) if response_limit is not None else response.read()
            )
        if response_limit is not None and len(body) > response_limit:
            raise LocalModelError(f"{service_name}响应超过安全上限")
        return json.loads(body)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace").strip()[:800]
        try:
            parsed_detail = json.loads(detail)
            detail = str(parsed_detail.get("error", {}).get("message") or detail)
        except (AttributeError, json.JSONDecodeError):
            pass
        message = f"{service_name}返回 HTTP {error.code}"
        if detail:
            message += f"：{detail}"
        raise LocalModelError(message) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise LocalModelError(f"无法连接{service_name}：{error}") from error


def _resolve_external_model(
    model: str,
    connections: ModelConnectionStore | None,
) -> ModelConnection | None:
    connection = connections.resolve(model) if connections else None
    if connection is None and MODEL_REF_PATTERN.fullmatch(model):
        raise LocalModelError("外部模型连接不存在或已删除，请重新选择模型")
    return connection


def _external_vision_completion(
    *,
    connection: ModelConnection,
    system_prompt: str,
    text_prompt: str,
    image_data_url: str,
    temperature: float,
    max_tokens: int,
) -> str:
    if not connection.supports_vision:
        raise LocalModelError("当前外部模型没有标记为视觉模型")
    payload = {
        "model": connection.model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                    {"type": "text", "text": text_prompt},
                ],
            },
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        # 思考型模型会先把 max_tokens 花在内部推理上。300 个 token 全部
        # 用完还没开始写答案。content 就是空的。finish_reason 是 length。
        # 两种写法都送。不同后端认的键不一样。
        # 已实测云端闸道会忽略不认得的键。本机 llama.cpp 认得其中之一。
        "enable_thinking": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    response = _request_json(
        f"{connection.base_url}/chat/completions",
        method="POST",
        payload=payload,
        timeout=180,
        api_key=connection.api_key,
        allow_redirects=False,
        response_limit=MAX_MODEL_RESPONSE_BYTES,
        service_name="外部模型服务",
    )
    try:
        choice = response["choices"][0]
        content = str(choice["message"]["content"] or "")
    except (KeyError, IndexError, TypeError) as error:
        raise LocalModelError("外部视觉模型返回格式错误") from error
    if content.strip():
        return content
    # 空内容配上 length。几乎总是被推理吃光了额度。
    # 只回「没有返回可识别的 JSON」的话。人会去怀疑提示词或模型能力。
    if str(choice.get("finish_reason", "")) == "length":
        raise LocalModelError(
            "模型把输出额度用在内部推理上，没有留下内容。请调高说明长度，或换一个不做长推理的模型"
        )
    raise LocalModelError("外部视觉模型返回了空内容")


def _image_data_url(path: Path) -> str:
    try:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, "JPEG", quality=88, optimize=True)
    except OSError as error:
        raise LocalModelError("无法为本地视觉模型读取结果图") from error
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _no_json_message(content: str) -> str:
    """模型回了散文而不是 JSON 时。把它说了什么带出来。

    只写「没有返回可识别的 JSON」的话。最常见的原因会被藏起来
    模型拒绝描述这张图。那不是技术故障。换一个愿意描述的模型就好。
    但看不到原文的人会一直去调提示词。
    """
    snippet = " ".join(content.split())[:160]
    if not snippet:
        return "视觉模型没有返回任何内容"
    return f"视觉模型没有返回可识别的草稿 JSON。它回了这段文字：{snippet}"


def _extract_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```")
        stripped = stripped.removesuffix("```").strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        raise json.JSONDecodeError("No JSON object", stripped, 0)
    result = json.loads(stripped[start : end + 1])
    if not isinstance(result, dict):
        raise json.JSONDecodeError("Expected JSON object", stripped, 0)
    return result


def _clean_query_values(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        clean = " ".join(str(value).strip().split())[:80]
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result[:4]


def _clean_text_list(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item).strip()][:8]


def _clean_anima_tags(value: Any) -> list[str]:
    values = value if isinstance(value, list) else str(value).replace("\n", ",").split(",")
    tags: list[str] = []
    seen: set[str] = set()
    for raw in values:
        tag = "_".join(str(raw).strip().replace(" ", "_").split())[:120]
        key = tag.casefold()
        if tag and tag.isascii() and key not in seen:
            seen.add(key)
            tags.append(tag)
    return tags[:120]


def _mode_instruction(mode: CaptionMode, profile_id: str) -> str:
    if mode == "general":
        return "Describe all visible caption-worthy details."
    if mode == "portrait":
        return (
            "Do not describe facial features; cover body, pose, scene, light, "
            "composition, and outfit."
        )
    if mode == "outfit":
        return (
            "Do not describe clothing or outfit details; cover subject, scene, light, "
            "composition, and action."
        )
    if profile_id == "anima":
        return (
            "Do not include style, color-grading, or lighting tags; cover subject, outfit, "
            "scene, composition, and action."
        )
    return (
        "Do not describe visual style, color grading, or lighting; cover subject, outfit, "
        "scene, composition, and action."
    )


def _option_instruction(options: dict[str, bool]) -> str:
    enabled = [key.replace("_", " ") for key, value in options.items() if value]
    if not enabled:
        return "All advanced switches are off."
    return "Advanced switches enabled: " + ", ".join(enabled) + "."


def _media_instruction(*, media_tags: bool, profile_id: str) -> str:
    if not media_tags:
        return "Do not describe or include the image medium, rendering medium, or medium tags."
    # Training captions keep the medium separate from the trigger word so later style prompts
    # can override it instead of inheriting a fixed photographic property.
    if profile_id == "anima":
        return (
            "Identify the visible medium and include only matching medium tags, such as photo, "
            "anime_coloring, illustration, or 3d_render. Never assume a photographic medium."
        )
    return (
        "Describe the visible image medium accurately when it is useful, such as photography, "
        "anime illustration, digital painting, or 3D rendering. Never assume photography."
    )


def _trigger_instruction(mode: CaptionMode, trigger: str, *, profile_id: str) -> str:
    if mode == "general" or not trigger:
        return "No trigger word should be inserted."
    if profile_id == "anima":
        return f"Prefix the trigger tag {trigger} before other tags while keeping count tags."
    return f"Use {trigger} as the subject name instead of a generic subject phrase."
