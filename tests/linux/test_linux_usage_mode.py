"""Linux must behave as a single-machine ("local") install, not as a remote Mac.

Upstream only had `windows_local` and `mac_remote`; on Linux the Core used to fall
back to the macOS remote mode, which asks for an SMB share and a second machine.
Linux runs Core and the Compute Worker on the same box, so it gets `linux_local`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from prompt_hub.desktop_connection import connection_summary
from prompt_hub.usage_modes import (
    LINUX_LOCAL,
    LOCAL_USAGE_MODES,
    MAC_REMOTE,
    USAGE_MODES,
    local_service_manager,
    platform_usage_mode,
)
from prompt_hub.web import render_index_html

if TYPE_CHECKING:
    from pathlib import Path


def test_platform_usage_mode_covers_the_three_platforms() -> None:
    assert platform_usage_mode("win32") == "windows_local"
    assert platform_usage_mode("linux") == LINUX_LOCAL
    assert platform_usage_mode("linux2") == LINUX_LOCAL
    assert platform_usage_mode("darwin") == MAC_REMOTE
    assert sorted(USAGE_MODES) == ["linux_local", "mac_remote", "windows_local"]
    assert sorted(LOCAL_USAGE_MODES) == ["linux_local", "windows_local"]


def test_linux_render_declares_linux_local_and_linux_paths() -> None:
    markup = render_index_html("QA device", usage_mode=LINUX_LOCAL)
    assert 'data-usage-mode="linux_local"' in markup
    assert 'data-usage-only="linux_local"' in markup
    assert 'placeholder="~/Pictures/my-dataset"' in markup
    assert 'placeholder="~/models/vision_model.onnx"' in markup
    assert "window.isPromptHubLocal" in markup
    assert "本机任务目录暂不可用。请检查本机服务" in markup


def test_linux_is_not_described_as_mac_remote() -> None:
    markup = render_index_html("QA device", usage_mode=LINUX_LOCAL)
    assert "Linux 本机模式" in markup
    assert "Mac 连接" in markup  # 仍随包发布, 但由 CSS 在 Linux 模式下隐藏


def test_default_render_follows_the_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prompt_hub.web.platform_usage_mode", lambda: LINUX_LOCAL)
    assert 'data-usage-mode="linux_local"' in render_index_html("QA device")


@pytest.mark.parametrize("state", ["not_configured", "mount_missing", "bridge_read_only"])
def test_linux_connection_errors_do_not_request_smb_pairing(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    monkeypatch.setattr("prompt_hub.desktop_connection.sys", SimpleNamespace(platform="linux"))
    store = Mock()
    store.list_nodes.return_value = [
        {"node_id": "local", "role": "compute_5060ti", "enabled": True}
    ]
    store.diagnostics.return_value = {"state": state, "mount_exists": False}
    result = connection_summary(store)
    assert result["mode"] == LINUX_LOCAL
    assert "deploy/linux 安装脚本" in result["detail"]
    assert "Finder" not in result["detail"]
    assert "共享" not in result["detail"]
    assert result["reconnect_url"] == ""


def test_linux_heartbeat_reports_local_worker_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("prompt_hub.desktop_connection.sys", SimpleNamespace(platform="linux"))
    store = Mock()
    store.list_nodes.return_value = [
        {"node_id": "local", "role": "compute_5060ti", "enabled": True}
    ]
    store.diagnostics.return_value = {
        "state": "ready",
        "mount_exists": True,
        "bridge_root": str(tmp_path),
    }
    monkeypatch.setattr(
        "prompt_hub.desktop_connection._read_json",
        lambda *_args, **_kwargs: {},
    )
    result = connection_summary(store)
    assert result["label"] == "本机 Worker 待确认"
    assert "deploy/linux 安装脚本" in result["detail"]


def test_linux_stale_heartbeat_names_the_linux_service_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("prompt_hub.desktop_connection.sys", SimpleNamespace(platform="linux"))
    store = Mock()
    store.list_nodes.return_value = [
        {"node_id": "local", "role": "compute_5060ti", "enabled": True}
    ]
    store.diagnostics.return_value = {
        "state": "ready",
        "mount_exists": True,
        "bridge_root": str(tmp_path),
    }
    checked_at = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    monkeypatch.setattr(
        "prompt_hub.desktop_connection._read_json",
        lambda *_args, **_kwargs: {"checked_at": checked_at, "running": True},
    )
    result = connection_summary(store)
    assert result["state"] == "stale"
    assert "deploy/linux 安装脚本" in result["detail"]
    assert "启动器" not in result["detail"]


def test_local_service_manager_labels() -> None:
    assert "启动器" in local_service_manager("windows_local")
    assert "deploy/linux" in local_service_manager(LINUX_LOCAL)
