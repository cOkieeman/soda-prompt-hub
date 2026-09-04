from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from prompt_hub.config import Settings
from prompt_hub.model_client import ModelConfig, UnifiedModelClient, load_model_configs

if TYPE_CHECKING:
    pass


_model_configs: dict[str, ModelConfig] | None = None




def get_config_path() -> Path:
    """统一解析 models.json 路径（library_root 优先，否则项目根目录）"""
    settings = Settings.from_environment()
    config_path = settings.library_root / "models.json"
    
    # 如果 library_root 不存在配置，尝试从项目根目录读取
    if not config_path.exists():
        from pathlib import Path
        project_config = Path(__file__).parent.parent.parent / "models.json"
        if project_config.exists():
            config_path = project_config
    return config_path


def get_model_configs() -> dict[str, ModelConfig]:
    """获取所有模型配置（带缓存）"""
    global _model_configs
    
    if _model_configs is None:
        settings = Settings.from_environment()
        config_path = settings.library_root / "models.json"
        
        # 如果 library_root 不存在配置，尝试从项目根目录读取
        if not config_path.exists():
            from pathlib import Path
            project_config = Path(__file__).parent.parent.parent / "models.json"
            if project_config.exists():
                config_path = project_config
        
        # 如果配置文件不存在，返回空字典（使用默认 LM Studio）
        if not config_path.exists():
            _model_configs = {}
        else:
            _model_configs = load_model_configs(config_path)
    
    return _model_configs


def get_model_client(model_id: str | None = None) -> UnifiedModelClient:
    """获取模型客户端
    
    Args:
        model_id: 模型 ID，如果为 None 则使用默认 LM Studio
    
    Returns:
        统一模型客户端
    """
    if model_id is None:
        # 向后兼容：使用默认 LM Studio
        config = ModelConfig.lm_studio_default()
        return UnifiedModelClient(config)
    
    configs = get_model_configs()
    
    if model_id in configs:
        return UnifiedModelClient(configs[model_id])
    
    # 如果找不到配置，尝试作为 LM Studio 模型名
    config = ModelConfig.lm_studio_default(model_name=model_id)
    return UnifiedModelClient(config)


def list_available_models() -> list[dict[str, Any]]:
    """列出所有可用模型（配置文件 + LM Studio）
    
    Returns:
        模型列表，每个模型包含 id、name、provider、supports_vision
    """
    results = []
    
    # 从配置文件加载
    configs = get_model_configs()
    for config in configs.values():
        results.append({
            "id": config.id,
            "name": f"{config.model_name} ({config.provider})",
            "provider": config.provider,
            "supports_vision": config.supports_vision,
            "max_tokens": config.max_tokens,
        })
    
    # 未配置任何模型时，返回空列表（让前端显示"还未添加模型"提示）
    return results


def organize_slots_unified(
    *,
    model_id: str,
    brief: str,
    slots: dict[str, str],
    locks: dict[str, bool],
    target_profile: str,
) -> dict[str, Any]:
    """使用统一接口整理槽位
    
    这是新接口，支持所有提供商的模型
    """
    from prompt_hub.creative import SLOT_LABELS, SLOT_ORDER
    
    client = get_model_client(model_id)
    
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
    
    messages = [
        {"role": "system", "content": instruction},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False) + "\n/no_think",
        },
    ]
    
    content = client.chat_completion(messages, temperature=0.35, max_tokens=500)
    
    # 提取 JSON
    from prompt_hub.local_model import _extract_json_object
    suggested = _extract_json_object(content)
    
    merged = {
        slot: slots.get(slot, "")
        if locks.get(slot, False)
        else str(suggested.get(slot, "")).strip()
        for slot in SLOT_ORDER
    }
    
    return {
        "model": model_id,
        "target_profile": target_profile,
        "slots": merged,
        "suggested": suggested,
        "locked": locked,
    }


def expand_sourcing_queries_unified(
    *,
    model_id: str,
    brief: str,
    slots: dict[str, str],
    locks: dict[str, bool],
    target_profile: str,
) -> dict[str, list[str]]:
    """使用统一接口扩展检索词"""
    from prompt_hub.creative import SLOT_LABELS, SLOT_ORDER
    
    client = get_model_client(model_id)
    
    editable = [slot for slot in SLOT_ORDER if not locks.get(slot, False)]
    
    instruction = (
        "你是检索词生成助手。从创作意图提取关键概念，每个未锁定槽位返回 0-4 个英文检索短语。"
        "只输出 JSON 对象，键是槽位名（"
        + ", ".join(SLOT_ORDER)
        + "），值是字符串数组。不增加新元素，只转换已有概念。锁定槽位返回空数组。"
        f"仅为这些未锁定槽位生成检索词：{', '.join(editable)}。"
    )
    
    user_payload = {
        "创作意图": brief,
        "已有槽位": slots,
        "锁定槽位": [slot for slot in SLOT_ORDER if locks.get(slot, False)],
        "槽位中文名": SLOT_LABELS,
    }
    
    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]
    
    content = client.chat_completion(messages, temperature=0.15, max_tokens=400)
    
    from prompt_hub.local_model import _extract_json_object
    result = _extract_json_object(content)
    
    return {slot: result.get(slot, []) for slot in SLOT_ORDER}


def analyze_result_image_unified(
    *,
    model_id: str,
    image_path: Path,
    brief: str,
    slots: dict[str, str],
    target_profile: str,
    safety_level: str,
) -> dict[str, Any]:
    """使用统一接口分析结果图"""
    from prompt_hub.creative import SLOT_LABELS, SLOT_ORDER
    from prompt_hub.local_model import _image_data_url
    
    client = get_model_client(model_id)
    
    # 确保模型支持视觉
    if not client.config.supports_vision:
        raise ValueError(f"模型 {model_id} 不支持视觉任务")
    
    system_prompt = (
        "你是 AI 绘图结果复盘助手。比较实际图片与用户创作意图，客观描述画面。"
        "合法成年人的 SFW 或 NSFW 图片都可以如实分析；"
        "若人物可能未成年，填写 safety_warning 并省略露骨反推。"
        "JSON 必须包含：summary_zh（总结，最多 80 个中文字符），"
        "observed_slots（七个槽位的实际观察），strengths（优点，最多 3 条，每条 40 字符），"
        "issues（问题，最多 3 条），improvements（改进建议，最多 3 条），"
        "reconstructed_prompts（反推 Prompt，包含 anima_positive、anima_negative、krea2_positive、krea2_avoid），"
        "safety_warning（安全警告，若无则为空字符串）。"
    )
    
    user_prompt_data = {
        "原始意图": brief,
        "预期槽位": slots,
        "目标模型": target_profile,
        "安全等级": safety_level,
        "槽位中文名": SLOT_LABELS,
    }
    
    text_prompt = "请复盘这张本地生成结果图。项目上下文：\n" + json.dumps(
        user_prompt_data, ensure_ascii=False
    )
    
    # 生成 data URL
    image_data_url = _image_data_url(image_path)
    
    content = client.vision_completion(
        image_data_url=image_data_url,
        text_prompt=text_prompt,
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=900,
    )
    
    from prompt_hub.local_model import _extract_json_object
    analysis = _extract_json_object(content)
    
    return {
        "model": model_id,
        "summary_zh": analysis.get("summary_zh", ""),
        "observed_slots": analysis.get("observed_slots", {}),
        "strengths": analysis.get("strengths", []),
        "issues": analysis.get("issues", []),
        "improvements": analysis.get("improvements", []),
        "reconstructed_prompts": analysis.get("reconstructed_prompts", ),
        "safety_warning": analysis.get("safety_warning", ""),
    }
