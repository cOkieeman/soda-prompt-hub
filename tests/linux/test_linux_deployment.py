"""deploy/linux 的行为测试, 仅 Linux 运行。

用一个隔离的 HOME 与 XDG 路径执行真实的安装 / 启停 / 状态流程,
不触碰开发机上已安装的服务与用户数据。
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_LINUX = REPO_ROOT / "deploy" / "linux"

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux 部署脚本的行为测试")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _run(
    script: str, *args: str, env: dict[str, str], timeout: int = 180
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - 固定脚本路径与参数
        [str(DEPLOY_LINUX / script), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )


def _wait_health(port: int, timeout: float = 30.0) -> dict[str, object] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2.0)
            if response.status_code == 200:
                return response.json()
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return None


def _install_no_service(
    env: dict[str, str], port: int, library: Path, *extra: str
) -> subprocess.CompletedProcess[str]:
    return _run(
        "install.sh",
        "--no-service",
        "--port",
        str(port),
        "--library-root",
        str(library),
        *extra,
        env=env,
    )


def _recorded_env(env: dict[str, str]) -> str:
    """读取 install.env, 并把 printf %q 转义的空格还原成可读形式。"""
    path = Path(env["XDG_DATA_HOME"]) / "soda-prompt-hub" / "install.env"
    assert path.is_file(), f"缺少安装记录 {path}"
    return path.read_text(encoding="utf-8").replace("\\ ", " ")


@pytest.fixture
def isolated(tmp_path: Path) -> dict[str, str]:
    """隔离的 HOME / XDG 环境, 保证不碰到开发机上真实的安装与服务。"""
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    data = tmp_path / "xdg-data"
    config = tmp_path / "xdg-config"
    runtime = tmp_path / "xdg-runtime"
    for directory in (data, config, runtime):
        directory.mkdir(parents=True, exist_ok=True)
    runtime.chmod(0o700)

    env = dict(os.environ)
    env["HOME"] = str(home)
    env["XDG_DATA_HOME"] = str(data)
    env["XDG_CONFIG_HOME"] = str(config)
    env["XDG_RUNTIME_DIR"] = str(runtime)
    # 保留真实缓存, 避免隔离 HOME 之后 uv 重新下载依赖
    env.setdefault("UV_CACHE_DIR", str(Path.home() / ".cache" / "uv"))
    return env


def test_help_flags_exit_cleanly(isolated: dict[str, str]) -> None:
    for script in ("install.sh", "update.sh", "uninstall.sh"):
        result = _run(script, "--help", env=isolated, timeout=60)
        assert result.returncode == 0, f"{script} --help 退出码 {result.returncode}"
        assert "用法" in result.stdout


def test_commands_report_missing_installation(isolated: dict[str, str]) -> None:
    for script in ("start.sh", "stop.sh", "status.sh"):
        result = _run(script, env=isolated, timeout=60)
        assert result.returncode != 0, f"{script} 在未安装时不应成功"
        assert "install.sh" in (result.stderr + result.stdout)


def test_install_start_stop_cycle_keeps_program_and_data_separate(
    tmp_path: Path, isolated: dict[str, str]
) -> None:
    library = tmp_path / "library with space"
    port = _free_port()

    install = _run(
        "install.sh",
        "--no-service",
        "--port",
        str(port),
        "--library-root",
        str(library),
        env=isolated,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    recorded = _recorded_env(isolated)
    assert f"SPH_PORT={port}" in recorded
    assert str(library) in recorded
    assert "SPH_SERVICE=no" in recorded

    start = _run("start.sh", env=isolated)
    assert start.returncode == 0, start.stdout + start.stderr
    stop: subprocess.CompletedProcess[str] | None = None
    try:
        health = _wait_health(port)
        assert health is not None, "服务未在 30 秒内通过健康检查"
        assert health["status"] == "ok"
        assert str(library) in str(health["database"])

        status = _run("status.sh", env=isolated)
        assert status.returncode == 0
        assert f"127.0.0.1:{port}" in status.stdout
        assert "健康检查: ok" in status.stdout
    finally:
        stop = _run("stop.sh", env=isolated)

    assert stop is not None
    assert stop.returncode == 0, stop.stdout + stop.stderr
    assert _wait_health(port, timeout=3.0) is None, "停止后端口仍在响应"

    # 程序与用户数据分离: 数据由安装参数决定, 便利命令装进隔离的 HOME
    assert (library / "database" / "prompt-library.sqlite").is_file()
    assert (Path(isolated["HOME"]) / ".local" / "bin" / "soda-prompt-hub").is_file()
    desktop_entry = Path(isolated["XDG_DATA_HOME"]) / "applications" / "soda-prompt-hub.desktop"
    desktop_icon = (
        Path(isolated["XDG_DATA_HOME"])
        / "icons"
        / "hicolor"
        / "256x256"
        / "apps"
        / "soda-prompt-hub.png"
    )
    assert desktop_entry.is_file()
    assert desktop_icon.is_file()


def test_launcher_starts_opens_and_then_reuses_service(
    tmp_path: Path, isolated: dict[str, str]
) -> None:
    library = tmp_path / "launcher library"
    port = _free_port()
    install = _install_no_service(isolated, port, library)
    assert install.returncode == 0, install.stdout + install.stderr
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    capture = tmp_path / "opened-url.txt"
    opener = fake_bin / "xdg-open"
    opener.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$1" > "$PROMPT_HUB_LAUNCHER_CAPTURE"\n',
        encoding="utf-8",
    )
    opener.chmod(0o755)
    launch_env = {
        **isolated,
        "PATH": f"{fake_bin}{os.pathsep}{isolated['PATH']}",
        "PROMPT_HUB_LAUNCHER_CAPTURE": str(capture),
    }
    try:
        launch = _run("launch.sh", env=launch_env)
        assert launch.returncode == 0, launch.stdout + launch.stderr
        assert capture.read_text(encoding="utf-8").strip() == f"http://127.0.0.1:{port}"
        log = Path(isolated["XDG_DATA_HOME"]) / "soda-prompt-hub" / "logs" / "launcher.log"
        assert log.is_file()
        assert "服务未就绪\uff0c开始启动" in log.read_text(encoding="utf-8")

        reuse_env = {**isolated, "PROMPT_HUB_LAUNCHER_SKIP_OPEN": "1"}
        reuse = _run("launch.sh", env=reuse_env)
        assert reuse.returncode == 0, reuse.stdout + reuse.stderr
        assert f"http://127.0.0.1:{port}" in reuse.stdout
        assert "复用已运行的服务" in log.read_text(encoding="utf-8")
    finally:
        _run("stop.sh", env=isolated)


def test_uninstall_removes_desktop_integration_but_keeps_data(
    tmp_path: Path, isolated: dict[str, str]
) -> None:
    library = tmp_path / "library kept after uninstall"
    port = _free_port()
    install = _install_no_service(isolated, port, library)
    assert install.returncode == 0, install.stdout + install.stderr

    launcher = Path(isolated["HOME"]) / ".local" / "bin" / "soda-prompt-hub"
    entry = Path(isolated["XDG_DATA_HOME"]) / "applications" / "soda-prompt-hub.desktop"
    icon = (
        Path(isolated["XDG_DATA_HOME"])
        / "icons"
        / "hicolor"
        / "256x256"
        / "apps"
        / "soda-prompt-hub.png"
    )
    assert launcher.is_file()
    assert entry.is_file()
    assert icon.is_file()

    uninstall = _run("uninstall.sh", env=isolated)
    assert uninstall.returncode == 0, uninstall.stdout + uninstall.stderr
    assert not launcher.exists()
    assert not entry.exists()
    assert not icon.exists()
    assert library.is_dir(), "默认卸载不应删除资料库"


def test_chinese_and_utf8_library_root(tmp_path: Path, isolated: dict[str, str]) -> None:
    """主任务书 §12: Linux 路径、UTF-8 路径、空格路径、中文路径。"""
    library = tmp_path / "资料库 测试-émoji"
    port = _free_port()

    install = _install_no_service(isolated, port, library)
    assert install.returncode == 0, install.stdout + install.stderr
    assert str(library) in _recorded_env(isolated)

    start = _run("start.sh", env=isolated)
    assert start.returncode == 0, start.stdout + start.stderr
    try:
        health = _wait_health(port)
        assert health is not None, "中文 + UTF-8 + 空格路径下服务未就绪"
        assert health["status"] == "ok"
        assert str(library) in str(health["database"])
    finally:
        _run("stop.sh", env=isolated)

    assert (library / "database" / "prompt-library.sqlite").is_file()


def test_models_root_is_created_and_recorded(tmp_path: Path, isolated: dict[str, str]) -> None:
    """主任务书 §12: PROMPT_HUB_MODELS_ROOT 必须真的被部署层接管。"""
    library = tmp_path / "library"
    models = tmp_path / "models root 模型"
    port = _free_port()

    install = _install_no_service(isolated, port, library, "--models-root", str(models))
    assert install.returncode == 0, install.stdout + install.stderr
    assert models.is_dir(), "--models-root 指定的目录未被创建"

    recorded = _recorded_env(isolated)
    assert f"SPH_MODELS_ROOT={models}" in recorded

    unit_placeholder = (REPO_ROOT / "deploy" / "linux" / "soda-prompt-hub.service").read_text(
        encoding="utf-8"
    )
    assert "Environment=__SPH_MODELS_ENV__" in unit_placeholder


def test_library_data_is_written_and_survives_restart(
    tmp_path: Path, isolated: dict[str, str]
) -> None:
    """主任务书 §12: 创建 Library、读取 Library、写入数据。"""
    library = tmp_path / "library"
    port = _free_port()

    install = _install_no_service(isolated, port, library)
    assert install.returncode == 0, install.stdout + install.stderr
    assert (library / "database").is_dir(), "安装未创建资料库目录"

    start = _run("start.sh", env=isolated)
    assert start.returncode == 0, start.stdout + start.stderr
    assert _wait_health(port) is not None

    # 写入
    marker = library / "private" / "personal-prompts" / "写入测试.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("内容 with UTF-8 ✓", encoding="utf-8")

    # 重启服务
    assert _run("stop.sh", env=isolated).returncode == 0
    restart = _run("start.sh", env=isolated)
    assert restart.returncode == 0, restart.stdout + restart.stderr
    try:
        assert _wait_health(port) is not None
        # 读取: 数据仍在, 内容一致
        assert marker.is_file()
        assert marker.read_text(encoding="utf-8") == "内容 with UTF-8 ✓"
        assert (library / "database" / "prompt-library.sqlite").stat().st_size > 0
    finally:
        _run("stop.sh", env=isolated)


def test_localhost_hostname_also_serves_health(tmp_path: Path, isolated: dict[str, str]) -> None:
    """主任务书 §12: localhost 与 127.0.0.1 都应可访问。"""
    library = tmp_path / "library"
    port = _free_port()

    install = _install_no_service(isolated, port, library)
    assert install.returncode == 0, install.stdout + install.stderr
    start = _run("start.sh", env=isolated)
    assert start.returncode == 0, start.stdout + start.stderr
    try:
        assert _wait_health(port) is not None
        response = httpx.get(f"http://localhost:{port}/api/health", timeout=5.0)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    finally:
        _run("stop.sh", env=isolated)
