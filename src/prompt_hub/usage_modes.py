"""Usage modes shared by the UI and the connection layer.

The product has two shapes: the Core runs on the same machine as the Compute Worker
(single machine), or the Core runs elsewhere and reaches a worker over a share
(remote). Windows and Linux both use the single-machine shape; only macOS drives a
remote worker today.
"""

from __future__ import annotations

import sys

WINDOWS_LOCAL = "windows_local"
LINUX_LOCAL = "linux_local"
MAC_REMOTE = "mac_remote"

LOCAL_USAGE_MODES = frozenset({WINDOWS_LOCAL, LINUX_LOCAL})
USAGE_MODES = frozenset({WINDOWS_LOCAL, LINUX_LOCAL, MAC_REMOTE})

# 单机模式下"谁在管理本机服务"的说法随平台不同
LOCAL_SERVICE_MANAGER = {
    WINDOWS_LOCAL: "Windows 启动器",
    LINUX_LOCAL: "deploy/linux 安装脚本",
}


def platform_usage_mode(platform: str | None = None) -> str:
    """Return the usage mode implied by a platform string (defaults to sys.platform)."""
    current = sys.platform if platform is None else platform
    if current == "win32":
        return WINDOWS_LOCAL
    if current.startswith("linux"):
        return LINUX_LOCAL
    return MAC_REMOTE


def is_local_platform(platform: str | None = None) -> bool:
    """True when Core and the Compute Worker are expected on the same machine."""
    return platform_usage_mode(platform) in LOCAL_USAGE_MODES


def local_service_manager(mode: str) -> str:
    """Human-readable name of the thing that starts the local service."""
    return LOCAL_SERVICE_MANAGER.get(mode, LOCAL_SERVICE_MANAGER[WINDOWS_LOCAL])
