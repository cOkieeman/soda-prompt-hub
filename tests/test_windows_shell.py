from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from scripts.package_windows_shell_release import package_release
from scripts.stage_windows_shell_source import ZIP_TIMESTAMP, stage_source

from prompt_hub import __version__, windows_worker


def _repository() -> Path:
    return Path(__file__).resolve().parents[1]


def test_windows_shell_version_and_shared_assets_match_release() -> None:
    repository = _repository()
    shell_root = repository / "deploy" / "windows-shell"
    project = (shell_root / "SodaComputeWorker" / "SodaComputeWorker.csproj").read_text(
        encoding="utf-8"
    )
    release = json.loads((repository / "deploy" / "windows-worker" / "RELEASE.json").read_text())

    assert f"<Version>{__version__}</Version>" in project
    assert release["worker_version"] == __version__
    assert "..\\..\\desktop-ui\\**\\*" in project
    assert "..\\..\\windows-worker\\**\\*" in project
    assert "Microsoft.Web.WebView2" in project
    assert "<OutputType>WinExe</OutputType>" in project
    assert "<ApplicationHighDpiMode>PerMonitorV2</ApplicationHighDpiMode>" in project

    shell = (shell_root / "SodaComputeWorker" / "ShellForm.cs").read_text(encoding="utf-8")
    assert "AutoScaleDimensions = new SizeF(96F, 96F);" in shell
    assert "AutoScaleMode = AutoScaleMode.Dpi;" in shell
    assert "ClientSize = ScaleForDpi(DesignClientSize, DeviceDpi);" in shell
    assert "eventArgs.DeviceDpiNew" in shell
    assert "exitRequested" in shell
    assert "statusTimer.Stop();" in shell
    assert "Task.Delay(TimeSpan.FromSeconds(3))" in shell
    assert "Application.ExitThread();" in shell


def test_windows_shell_bridge_is_allowlisted_and_worker_safe() -> None:
    source = (
        _repository() / "deploy" / "windows-shell" / "SodaComputeWorker" / "ShellForm.cs"
    ).read_text(encoding="utf-8")
    cases = set(re.findall(r'case "([A-Za-z]+)":', source))

    assert cases == {
        "getStatus",
        "startWorker",
        "stopWorker",
        "selfTestWorker",
        "openLogs",
        "exportDiagnostics",
        "openDataFolder",
        "openConfig",
        "getWorkerConfig",
        "getPairingInfo",
        "openShareFolder",
        "copyPairingAddress",
        "chooseFolder",
        "saveWorkerConfig",
        "hideWindow",
    }
    assert "CoreWebView2HostResourceAccessKind.DenyCors" in source
    assert 'string.Equals(uri.Host, "soda.local"' in source
    assert "任务正在执行" in source
    assert "未停止 Worker" in source
    assert "CoreWebView2Environment.CreateAsync" in source
    assert "SystemIcons.Application" not in source

    host_source = (
        _repository() / "deploy" / "windows-shell" / "SodaComputeWorker" / "WorkerHost.cs"
    ).read_text(encoding="utf-8")
    assert '"worker-config.backup.json"' in host_source
    assert "File.Move(temporaryPath, configPath, overwrite: true)" in host_source
    assert "Worker 运行时不能修改配置" in host_source
    assert 'Path.Combine(AppRoot, "INSTALL_MODE.json")' in host_source
    assert 'Path.Combine(StateRoot, "worker-config.json")' in host_source
    assert 'Path.Combine(AppRoot, "runtime", "python", "python.exe")' in host_source

    icon_source = (
        _repository() / "deploy" / "windows-shell" / "SodaComputeWorker" / "BrandIcon.cs"
    ).read_text(encoding="utf-8")
    assert 'GetManifestResourceStream("PromptHub.AppIcon")' in icon_source
    assert "icon.Clone()" in icon_source


def test_windows_shell_install_preserves_real_config() -> None:
    script = (_repository() / "deploy" / "windows-shell" / "install-to-worker.ps1").read_text(
        encoding="utf-8"
    )

    assert "$_ .Name" not in script
    assert '"worker-config.json",' in script
    assert '"PACKAGE_MANIFEST.sha256",' in script
    assert '$_.Name -ne "worker-config.json"' in script
    assert "Get-FileHash -LiteralPath $configPath" in script
    assert "Copy-Item" in script

    build_script = (_repository() / "deploy" / "windows-shell" / "build.ps1").read_text(
        encoding="utf-8"
    )
    assert "Write-HashManifest" in build_script
    assert '"PACKAGE_MANIFEST.sha256"' in build_script
    assert "--self-contained true" in build_script


def test_worker_supports_detached_utf8_log_file(tmp_path) -> None:
    log_path = tmp_path / "worker.log"
    missing_config = tmp_path / "missing.json"

    assert windows_worker.main(["--config", str(missing_config), "--log-file", str(log_path)]) == 2
    assert "worker 无法启动" in log_path.read_text(encoding="utf-8")


def test_windows_shell_source_stage_is_complete_and_private_free(tmp_path) -> None:
    result = stage_source(_repository(), tmp_path)
    archive = Path(str(result["archive"]))
    root = f"Soda-Compute-Worker-Source-{__version__}/"

    assert result["version"] == __version__
    assert archive.is_file()
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert f"{root}deploy/windows-shell/build.ps1" in names
        assert f"{root}deploy/windows-shell/SodaComputeWorker/SodaComputeWorker.csproj" in names
        assert f"{root}deploy/desktop-ui/index.html" in names
        assert f"{root}deploy/windows-installer/worker.iss" in names
        assert f"{root}deploy/windows-installer/prepare-runtime.ps1" in names
        assert f"{root}deploy/windows-worker/prompt_hub_worker.py" in names
        assert f"{root}pyproject.toml" in names
        assert f"{root}scripts/package_windows_shell_release.py" in names
        assert f"{root}LICENSE" in names
        assert not any(name.endswith("worker-config.json") for name in names)
        assert not any("/__pycache__/" in name for name in names)
        assert not any(name.endswith(".pyc") for name in names)
        assert {item.date_time for item in bundle.infolist()} == {ZIP_TIMESTAMP}


def test_windows_shell_release_package_has_manifests_and_no_private_config(
    tmp_path,
) -> None:
    repository = _repository()
    published = tmp_path / "published"
    output = tmp_path / "output"
    required = {
        "Soda Compute Worker.exe": b"fake-pe",
        "desktop-ui/index.html": b"html",
        "desktop-ui/desktop.css": b"css",
        "desktop-ui/desktop.js": b"js",
        "worker/prompt_hub_worker.py": b"worker",
        "worker/__pycache__/prompt_hub_worker.cpython-312.pyc": b"cache",
        "worker/RELEASE.json": json.dumps({"worker_version": __version__}).encode(),
        "worker/worker-config.json": b"private",
        "worker/debug.pdb": b"debug",
        "校验桌面包.ps1": b"verify",
        "LICENSE.txt": b"license",
    }
    for relative, payload in required.items():
        target = published / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    result = package_release(repository, published, output)
    package_root = Path(str(result["directory"]))
    archive = Path(str(result["archive"]))

    assert (package_root / "PACKAGE_MANIFEST.sha256").is_file()
    assert (package_root / "worker" / "MANIFEST.sha256").is_file()
    assert not (package_root / "worker" / "worker-config.json").exists()
    assert not (package_root / "worker" / "debug.pdb").exists()
    assert not (package_root / "worker" / "__pycache__").exists()
    assert result["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
