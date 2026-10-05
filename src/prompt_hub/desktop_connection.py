"""Read-only, freshness-aware summary for desktop connection indicators."""

from __future__ import annotations

import re
import sys

# ruff: noqa: RUF001
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from prompt_hub.release_info import worker_compatibility
from prompt_hub.remote_nodes_support import _read_json
from prompt_hub.usage_modes import (
    is_local_platform,
    local_service_manager,
    platform_usage_mode,
)

HEARTBEAT_MAX_AGE = 25
MAX_CLOCK_SKEW = 15

if TYPE_CHECKING:
    from prompt_hub.remote_nodes import RemoteNodeStore


def connection_summary(store: RemoteNodeStore, node_id: str | None = None) -> dict[str, Any]:  # noqa: PLR0911, C901
    local = is_local_platform(sys.platform)
    mode = platform_usage_mode(sys.platform)
    manager = local_service_manager(mode)
    nodes = [node for node in store.list_nodes() if node.get("role") == "compute_5060ti"]
    if node_id is not None:
        nodes = [node for node in nodes if node.get("node_id") == node_id]
    enabled = [node for node in nodes if node.get("enabled")]
    node = next((node for node in enabled if node.get("node_id") == "compute-5060ti"), None)
    node = node or next(iter(enabled), None) or next(iter(nodes), None)
    result: dict[str, Any] = {
        "state": "not_configured",
        "label": "本机服务尚未配置" if local else "未配置计算设备",
        "detail": f"请先启动本机服务（{manager}），无需配对其他设备。"
        if local
        else "本机资料库可以独立使用，需要计算时再添加设备。",
        "device": str((node or {}).get("label", "计算设备")),
        "share_connected": False,
        "worker_online": False,
        "can_compute": False,
        "checked_at": datetime.now(UTC).isoformat(),
        "heartbeat_age_seconds": None,
        "mode": mode if local else "mac_remote",
        "reconnect_url": "" if local else reconnect_url(node or {}),
    }
    if not node:
        return result
    if not node.get("enabled"):
        return {
            **result,
            "state": "disabled",
            "label": "设备未启用",
            "detail": f"请先启动本机服务（{manager}）后再检查。"
            if local
            else "在设备设置中启用这台设备后再检查。",
        }
    diagnostic = store.diagnostics(node["node_id"])
    messages = {
        "not_configured": ("设备配置不完整", "请在设备设置中填写主机地址和共享目录。"),
        "mount_missing": ("共享目录未连接", "在 Finder 连接 Windows 共享目录，然后重新检查。"),
        "mount_ready_bridge_unprepared": ("共享已连接 · 尚未准备", "在设备设置中准备任务目录。"),
        "bridge_read_only": ("共享已连接 · 无写入权限", "请检查共享目录的写入权限。"),
    }
    if local:
        messages = {
            "not_configured": (
                "本机配置未完成",
                f"请重新启动本机服务（{manager}），完成初始化。",
            ),
            "mount_missing": (
                "本机任务目录不可用",
                f"请检查本机服务（{manager}）的运行状态及本机任务目录是否存在。",
            ),
            "mount_ready_bridge_unprepared": (
                "本机任务目录待准备",
                f"请先启动本机服务（{manager}），会自动准备任务目录。",
            ),
            "bridge_read_only": (
                "本机任务目录不可写",
                f"请核对本机任务目录（由 {manager} 使用），确认当前账号有写入权限。",
            ),
        }
    result["share_connected"] = diagnostic["mount_exists"]
    state = diagnostic["state"]
    if state in messages:
        return {**result, "state": state, "label": messages[state][0], "detail": messages[state][1]}
    heartbeat = _read_json(Path(diagnostic["bridge_root"]) / "worker-heartbeat.json", {})
    if not isinstance(heartbeat, dict) or not heartbeat:
        return {
            **result,
            "state": "unconfirmed",
            "label": "本机 Worker 待确认" if local else "共享已连接 · Worker 待确认",
            "detail": f"尚未收到本机 Worker 心跳，请检查本机服务（{manager}）。"
            if local
            else "未收到实时心跳，请启动支持连接状态的新版 Worker。",
        }
    try:
        checked = datetime.fromisoformat(str(heartbeat.get("checked_at", "")))
        age = (datetime.now(UTC) - checked).total_seconds()
    except (ValueError, TypeError):
        age = float("inf")
    result["heartbeat_age_seconds"] = round(max(0, age)) if age != float("inf") else None
    if age < -MAX_CLOCK_SKEW or age > HEARTBEAT_MAX_AGE:
        return {
            **result,
            "state": "stale",
            "label": "Worker 连接中断",
            "detail": (
                f"本机 Worker 心跳已过期，请检查本机服务（{manager}）；电脑刚唤醒时可稍后刷新。"
                if local
                else "心跳已过期，请检查 Windows 是否休眠、Worker 是否仍在运行。"
            ),
        }
    if heartbeat.get("running") is not True:
        return {
            **result,
            "state": "stopped",
            "label": "Worker 已停止",
            "detail": f"请先启动本机服务（{manager}），无需另开独立 Worker。"
            if local
            else "共享目录仍可访问，在 Windows 启动 Worker 即可恢复。",
        }
    if (
        heartbeat.get("role") != node.get("role")
        or worker_compatibility(heartbeat).get("state") == "incompatible"
    ):
        return {
            **result,
            "state": "incompatible",
            "label": "Worker 需要更新",
            "detail": "设备协议不匹配，请使用与当前管理器配套的 Worker。",
        }
    result["worker_online"] = True
    if heartbeat.get("comfyui_reachable") is not True:
        return {
            **result,
            "state": "compute_unavailable",
            "label": "Worker 在线 · 计算未就绪",
            "detail": "设备已连接，但 ComfyUI 尚未启动或暂时无法访问。",
        }
    return {
        **result,
        "state": "connected",
        "label": "已连接 · 可以计算",
        "detail": "本机 Worker 与 ComfyUI 均正常，无需跨设备连接。"
        if local
        else "共享目录、Worker 心跳和 ComfyUI 均正常。",
        "can_compute": True,
    }


def reconnect_url(node: dict[str, Any]) -> str:
    """Build a credential-free SMB destination from the user's saved pairing."""
    host = str(node.get("host", "")).strip()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}", host):
        return ""
    share = str(node.get("smb_share", "")).strip()
    if not share:
        mount = Path(str(node.get("smb_mount", "")))
        if mount.parent == Path("/Volumes"):
            share = mount.name
    if not share or share in {".", ".."} or any(c in share for c in "/\\\x00"):
        return ""
    return f"smb://{host}/{quote(share, safe='')}"
