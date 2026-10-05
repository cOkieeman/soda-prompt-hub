"""deploy/linux 部署层的静态契约检查, 跨平台可运行。

这些用例只读取文件, 不执行脚本, 因此在 Windows / macOS 上同样有效:
Linux 适配最容易犯的错 (CRLF, 硬编码路径, 默认监听 0.0.0.0, sudo, 777 权限)
都可以在这里拦住。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_LINUX = REPO_ROOT / "deploy" / "linux"
UNIT_TEMPLATE = DEPLOY_LINUX / "soda-prompt-hub.service"
WORKER_UNIT_TEMPLATE = DEPLOY_LINUX / "soda-worker.service"

# 主任务书 §5 要求的最小脚本集合, 外加便利命令
SHELL_SCRIPTS = (
    "lib.sh",
    "install.sh",
    "uninstall.sh",
    "update.sh",
    "start.sh",
    "stop.sh",
    "status.sh",
    "launch.sh",
    "soda-prompt-hub.sh",
    "soda-worker.sh",
)

# lib.sh 是被 source 的函数库, 本身不设置 shell 选项
STANDALONE_SCRIPTS = tuple(name for name in SHELL_SCRIPTS if name != "lib.sh")


def _text(name: str) -> str:
    return (DEPLOY_LINUX / name).read_text(encoding="utf-8")


def test_deploy_linux_layout_exists() -> None:
    extra = (
        "soda-prompt-hub.service",
        "soda-prompt-hub.desktop",
        "soda-prompt-hub.png",
        "soda-worker.service",
        "worker-config.example.json",
    )
    missing = [name for name in (*SHELL_SCRIPTS, *extra) if not (DEPLOY_LINUX / name).is_file()]
    assert not missing, f"deploy/linux 缺少文件: {missing}"


def test_desktop_icon_uses_a_standard_hicolor_size() -> None:
    with Image.open(DEPLOY_LINUX / "soda-prompt-hub.png") as icon:
        assert icon.size == (256, 256)
        assert icon.mode == "RGBA"


def test_scripts_declare_strict_mode_and_ignore_cwd() -> None:
    for name in STANDALONE_SCRIPTS:
        text = _text(name)
        assert text.startswith("#!/usr/bin/env bash"), f"{name} 缺少 bash shebang"
        assert "set -Eeuo pipefail" in text, f"{name} 未开启严格模式"
        assert "BASH_SOURCE" in text, f"{name} 未按脚本自身位置解析路径, 会依赖当前工作目录"


def test_scripts_never_escalate_and_never_widen_permissions() -> None:
    for name in SHELL_SCRIPTS:
        text = _text(name)
        assert not re.search(r"(?m)^\s*sudo\b", text), f"{name} 直接调用了 sudo"
        for pattern in ("chmod 777", "chmod -R 777", "chmod 0777", "chmod -R 0777"):
            assert pattern not in text, f"{name} 出现 {pattern}"


def test_scripts_never_pipe_remote_content_into_a_shell() -> None:
    # 主任务书 §25: 安装脚本不得执行来源不明的远程脚本
    for name in SHELL_SCRIPTS:
        text = _text(name)
        assert "| sh" not in text, f"{name} 把远程内容管道给 sh"
        assert "| bash" not in text, f"{name} 把远程内容管道给 bash"


def test_defaults_never_expose_the_service() -> None:
    lib = _text("lib.sh")
    assert 'SPH_DEFAULT_HOST="127.0.0.1"' in lib
    assert 'SPH_DEFAULT_PORT="8765"' in lib
    assert 'HOST="${SPH_DEFAULT_HOST}"' in _text("install.sh")
    for name in (*SHELL_SCRIPTS, UNIT_TEMPLATE.name):
        assert "0.0.0.0" not in _text(name), f"{name} 出现全接口监听地址"  # noqa: S104


def test_linux_layer_does_not_remove_other_platforms() -> None:
    # 守住不破坏 macOS / Windows 的底线: 其他平台目录必须仍在
    for directory in (
        "mac",
        "windows-desktop",
        "windows-installer",
        "windows-shell",
        "windows-worker",
    ):
        assert (REPO_ROOT / "deploy" / directory).is_dir(), f"deploy/{directory} 不应被删除"
    assert (REPO_ROOT / "src" / "prompt_hub" / "windows_worker.py").is_file()


def test_systemd_unit_is_a_user_service_with_restart_policy() -> None:
    unit = _text(UNIT_TEMPLATE.name)
    for directive in (
        "Restart=on-failure",
        "RestartSec=5",
        "WantedBy=default.target",
        "NoNewPrivileges=yes",
        "KillSignal=SIGINT",
        "WorkingDirectory=__SPH_REPO__",
        "Environment=__SPH_LIBRARY_ENV__",
        "Environment=__SPH_MODELS_ENV__",
    ):
        assert directive in unit, f"unit 缺少 {directive}"
    assert "User=root" not in unit
    expected_exec = "ExecStart=__SPH_CORE_EXEC__ serve --host __SPH_HOST__ --port __SPH_PORT__"
    assert expected_exec in unit


def test_installer_and_updater_share_systemd_renderers() -> None:
    lib = _text("lib.sh")
    install = _text("install.sh")
    update = _text("update.sh")
    for function_name in ("sph_write_core_unit", "sph_write_worker_unit"):
        assert f"{function_name}()" in lib
        assert function_name in install
        assert function_name in update


@pytest.mark.skipif(sys.platform != "linux", reason="GNU realpath and systemd are Linux contracts")
def test_safe_purge_path_resolves_dotdot_and_symlinks(tmp_path: Path) -> None:
    home = tmp_path / "home"
    allowed = home / "library"
    outside = tmp_path / "outside"
    allowed.mkdir(parents=True)
    outside.mkdir()
    (home / "escape").symlink_to(outside, target_is_directory=True)

    bash = shutil.which("bash")
    assert bash is not None

    def resolve(candidate: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - fixed shell and sourced project file
            [
                bash,
                "-c",
                'source "$1"; sph_safe_purge_path "$2"',
                "bash",
                str(DEPLOY_LINUX / "lib.sh"),
                str(candidate),
            ],
            env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            check=False,
        )

    accepted = resolve(allowed)
    assert accepted.returncode == 0
    assert accepted.stdout == str(allowed.resolve())
    assert resolve(home / ".." / "outside").returncode != 0
    assert resolve(home / "escape" / "data").returncode != 0


@pytest.mark.skipif(
    sys.platform != "linux" or shutil.which("systemd-analyze") is None,
    reason="systemd-analyze is required for unit verification",
)
def test_rendered_systemd_units_support_spaces_and_percent(tmp_path: Path) -> None:
    repo = tmp_path / "repo 100% ready"
    library = tmp_path / "library 100% ready"
    models = tmp_path / "models 100% ready"
    config = tmp_path / "config 100% ready" / "worker.json"
    core_exec = repo / ".venv" / "bin" / "prompt-hub"
    worker_python = repo / ".venv" / "bin" / "python"
    for executable in (core_exec, worker_python):
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)
    library.mkdir()
    models.mkdir()
    config.parent.mkdir()
    config.write_text("{}\n", encoding="utf-8")
    core_unit = tmp_path / "soda-prompt-hub.service"
    worker_unit = tmp_path / "soda-worker.service"

    bash = shutil.which("bash")
    assert bash is not None
    render = subprocess.run(  # noqa: S603 - fixed shell and sourced project file
        [
            bash,
            "-c",
            (
                'source "$1"; '
                'sph_write_core_unit "$2" "$3" "$4" "$5" "$6" "$7" "$8"; '
                'sph_write_worker_unit "$9" "${10}" "$4" "${11}"'
            ),
            "bash",
            str(DEPLOY_LINUX / "lib.sh"),
            str(UNIT_TEMPLATE),
            str(core_unit),
            str(repo),
            str(library),
            str(models),
            "127.0.0.1",
            "8765",
            str(WORKER_UNIT_TEMPLATE),
            str(worker_unit),
            str(config),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert render.returncode == 0, render.stderr
    systemd_analyze = shutil.which("systemd-analyze")
    assert systemd_analyze is not None
    verify = subprocess.run(  # noqa: S603 - resolved system utility and generated files
        [systemd_analyze, "verify", str(core_unit), str(worker_unit)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stderr


def test_data_directories_follow_xdg_and_env_vars() -> None:
    lib = _text("lib.sh")
    assert "XDG_DATA_HOME" in lib
    assert "XDG_CONFIG_HOME" in lib
    install = _text("install.sh")
    assert 'LIBRARY_ROOT="${DATA_HOME}/library"' in install
    # 部署层通过环境变量接管路径, 不改核心默认值 (实现计划 D3/D4)
    assert "PROMPT_HUB_LIBRARY_ROOT" in install
    assert "PROMPT_HUB_MODELS_ROOT" in install
    assert "PROMPT_HUB_LIBRARY_ROOT" in _text("start.sh")
    assert "PROMPT_HUB_MODELS_ROOT" in _text("start.sh")


def test_desktop_launcher_starts_health_checks_and_opens_loopback_url() -> None:
    launch = _text("launch.sh")
    assert '"${SCRIPT_DIR}/start.sh"' in launch
    assert "sph_health_ok" in launch
    assert "xdg-open" in launch
    assert "gio open" in launch
    assert "notify-send" in launch
    assert "PROMPT_HUB_LAUNCHER_SKIP_OPEN" in launch
    assert 'APP_URL="$(sph_app_url)"' in launch

    command = _text("soda-prompt-hub.sh")
    assert "soda-prompt-hub open" in command
    assert "run_deploy launch.sh" in command


def test_desktop_entry_is_installed_updated_and_removed() -> None:
    template = _text("soda-prompt-hub.desktop")
    for field in (
        "Type=Application",
        "Exec=__SPH_LAUNCHER_EXEC__ open",
        "Icon=soda-prompt-hub",
        "Terminal=false",
        "StartupNotify=true",
    ):
        assert field in template

    assert "sph_install_desktop_integration" in _text("install.sh")
    assert "sph_install_desktop_integration" in _text("update.sh")
    uninstall = _text("uninstall.sh")
    assert "sph_desktop_entry_path" in uninstall
    assert "sph_desktop_icon_path" in uninstall


def test_rendered_desktop_entry_escapes_exec_field_codes(tmp_path: Path) -> None:
    launcher = tmp_path / "home 100% $soda" / ".local" / "bin" / "soda-prompt-hub"
    output = tmp_path / "soda-prompt-hub.desktop"
    bash = shutil.which("bash")
    assert bash is not None
    render = subprocess.run(  # noqa: S603 - fixed shell and sourced project file
        [
            bash,
            "-c",
            'source "$1"; sph_write_desktop_entry "$2" "$3" "$4"',
            "bash",
            str(DEPLOY_LINUX / "lib.sh"),
            str(DEPLOY_LINUX / "soda-prompt-hub.desktop"),
            str(output),
            str(launcher),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert render.returncode == 0, render.stderr
    rendered = output.read_text(encoding="utf-8")
    expected = str(launcher).replace("$", r"\$").replace("%", "%%")
    assert f'Exec="{expected}" open' in rendered
    assert "__SPH_LAUNCHER_EXEC__" not in rendered


def test_client_urls_normalize_wildcard_and_ipv6_hosts() -> None:
    bash = shutil.which("bash")
    assert bash is not None

    def render(host: str) -> str:
        result = subprocess.run(  # noqa: S603 - fixed shell and sourced project file
            [
                bash,
                "-c",
                'source "$1"; SPH_HOST="$2"; SPH_PORT=8765; sph_app_url',
                "bash",
                str(DEPLOY_LINUX / "lib.sh"),
                host,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    assert render("127.0.0.1") == "http://127.0.0.1:8765"
    assert render("::") == "http://[::1]:8765"
    assert render("::1") == "http://[::1]:8765"


def test_update_is_fast_forward_only_and_data_safe() -> None:
    update = _text("update.sh")
    assert "--ff-only" in update, "更新必须只允许快进"
    assert "git status --porcelain" in update, "更新前必须检查工作区"
    assert "rm -rf" not in update, "更新脚本不得删除任何东西"
    assert "sph_data_usage" in update, "更新必须给出用户数据未改动的证据"
    assert 'is-active --quiet "soda-worker.service"' in update
    assert 'restart "soda-worker.service"' in update


def test_worker_config_and_private_data_home_are_owner_only() -> None:
    install = _text("install.sh")
    assert 'mkdir -p "${DATA_HOME}"' in install
    assert 'chmod 0700 "${DATA_HOME}"' in install
    assert 'chmod 0600 "${WORKER_CONFIG}"' in install


def test_uninstall_keeps_user_data_by_default() -> None:
    uninstall = _text("uninstall.sh")
    assert "--purge-data" in uninstall
    confirm_at = uninstall.index("if ((PURGE == 0))")
    delete_at = uninstall.index("rm -rf -- ")
    assert confirm_at < delete_at, "默认分支必须排在删除逻辑之前"
    assert 'sph_safe_purge_path "${target}"' in uninstall, "删除目标必须经过规范化白名单检查"
    assert 'rm -rf -- "$(sph_worker_share_root)"' not in uninstall


def test_scripts_are_lf_utf8_without_local_paths() -> None:
    for name in SHELL_SCRIPTS:
        raw = (DEPLOY_LINUX / name).read_bytes()
        assert b"\r\n" not in raw, f"{name} 含 CRLF, shebang 会在 Linux 上失效"
        text = raw.decode("utf-8")
        assert "/home/voldm" not in text, f"{name} 含开发者本机路径"
        assert "C:\\" not in text, f"{name} 含 Windows 盘符路径"


def test_gitattributes_pins_shell_scripts_to_lf() -> None:
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attributes
    assert "deploy/linux/* text eol=lf" in attributes


def test_shell_scripts_pass_bash_syntax_check() -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available")
    for name in SHELL_SCRIPTS:
        result = subprocess.run(  # noqa: S603 - 固定命令与文件参数
            [bash, "-n", str(DEPLOY_LINUX / name)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{name} 语法错误: {result.stderr}"


def test_environment_checker_covers_required_signals() -> None:
    checker = (REPO_ROOT / "scripts" / "linux" / "check-env.sh").read_text(encoding="utf-8")
    for signal in ("Linux", "systemctl --user", "uv", "python3", "PROMPT_HUB_LIBRARY_ROOT"):
        assert signal in checker


def test_linux_worker_packaging_is_complete() -> None:
    """Linux Compute Worker 的配置模板、便利命令与 systemd 单元都要齐备。"""
    unit = _text("soda-worker.service")
    assert "WorkingDirectory=__SPH_REPO__" in unit
    assert "ExecStart=__SPH_WORKER_PYTHON__ -m prompt_hub.windows_worker" in unit
    assert "--config __SPH_WORKER_CONFIG__" in unit
    assert "Restart=on-failure" in unit
    assert "WantedBy=default.target" in unit
    assert "User=root" not in unit

    example = _text("worker-config.example.json")
    assert "__SPH_WORKER_BRIDGE_ROOT__" in example
    assert "comfyui_url" in example, "ComfyUI 地址必须可配置"
    assert '"role"' in example

    install = _text("install.sh")
    assert "--with-worker" in install
    assert "sph_write_worker_unit" in install
    assert "${WORKER_JSON//__SPH_WORKER_BRIDGE_ROOT__/" in install

    launcher = _text("soda-worker.sh")
    assert "prompt_hub.windows_worker" in launcher
    assert "self-test" in launcher


def _workflow(name: str) -> str:
    return (REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_linux_workflow_runs_existing_checks_and_deployment_smoke() -> None:
    """主任务书 §13: 执行项目既有的检查命令, 并跑 Linux 专用测试与部署冒烟。"""
    workflow = _workflow("linux.yml")
    for command in (
        "uv sync --locked",
        "uv run ruff format --check .",
        "uv run ruff check .",
        "uv run ty check src/",
        "uv run pytest",
    ):
        assert command in workflow, f"linux.yml 缺少 {command}"
    assert "ubuntu-22.04" in workflow
    assert "ubuntu-24.04" in workflow
    assert "./deploy/linux/install.sh --no-service" in workflow
    assert "./deploy/linux/start.sh" in workflow
    assert "./deploy/linux/stop.sh" in workflow
    assert "systemctl --user status soda-prompt-hub" in workflow
    # 主任务书 §13: 不要擅自引入新的 lint 工具
    for forbidden in ("flake8", "pylint", "mypy", "eslint"):
        assert forbidden not in workflow, f"linux.yml 引入了新工具 {forbidden}"


def test_default_branch_only_automation_is_not_shipped_on_linux_branch() -> None:
    workflows = REPO_ROOT / ".github" / "workflows"
    assert not (workflows / "upstream-sync.yml").exists()
    assert not (workflows / "release-linux.yml").exists()
