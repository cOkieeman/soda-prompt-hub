from __future__ import annotations

import codecs
import hashlib
import json
import re
import zipfile
from importlib.machinery import PathFinder
from pathlib import Path

from scripts.package_windows_desktop_release import package_release
from scripts.stage_windows_desktop_source import ZIP_TIMESTAMP, stage_source

from prompt_hub import __version__


def _repository() -> Path:
    return Path(__file__).resolve().parents[1]


def test_windows_desktop_project_bundles_core_worker_and_shared_ui() -> None:
    repository = _repository()
    project = (
        repository / "deploy" / "windows-desktop" / "SodaPromptHub" / "SodaPromptHub.csproj"
    ).read_text(encoding="utf-8")

    assert f"<Version>{__version__}</Version>" in project
    assert "<AssemblyName>Soda Prompt Hub</AssemblyName>" in project
    assert "..\\..\\desktop-ui\\**\\*" in project
    assert "..\\..\\windows-worker\\**\\*" in project
    assert "..\\..\\..\\src\\prompt_hub\\**\\*" in project
    assert "WorkerHost.cs" in project
    assert "Microsoft.Web.WebView2" in project
    assert "<OutputType>WinExe</OutputType>" in project
    assert "<ApplicationHighDpiMode>PerMonitorV2</ApplicationHighDpiMode>" in project

    shell = (
        repository / "deploy" / "windows-desktop" / "SodaPromptHub" / "ShellForm.cs"
    ).read_text(encoding="utf-8")
    assert "AutoScaleDimensions = new SizeF(96F, 96F);" in shell
    assert "AutoScaleMode = AutoScaleMode.Dpi;" in shell
    assert "ClientSize = ScaleForDpi(DesignClientSize, DeviceDpi);" in shell
    assert "eventArgs.DeviceDpiNew" in shell
    assert "exitRequested" in shell
    assert "statusTimer.Stop();" in shell
    assert "Task.Delay(TimeSpan.FromSeconds(3))" in shell
    assert "Application.ExitThread();" in shell


def test_windows_desktop_bridge_is_allowlisted_and_process_safe() -> None:
    repository = _repository()
    source = (
        repository / "deploy" / "windows-desktop" / "SodaPromptHub" / "ShellForm.cs"
    ).read_text(encoding="utf-8")
    cases = set(re.findall(r'case "([A-Za-z]+)":', source))

    assert cases == {
        "getStatus",
        "openWorkspace",
        "retryCore",
        "restartCore",
        "openLogs",
        "exportDiagnostics",
        "openDataFolder",
        "toggleLocalWorker",
        "openConfig",
        "getWorkerConfig",
        "chooseFolder",
        "saveWorkerConfig",
        "hideWindow",
    }
    assert "CoreWebView2HostResourceAccessKind.DenyCors" in source
    assert 'string.Equals(uri.Host, "soda.local"' in source
    assert "退出启动器" in source
    assert "退出并停止本机服务" in source
    assert "未停止任何服务" in source

    host = (
        repository / "deploy" / "windows-desktop" / "SodaPromptHub" / "DesktopHost.cs"
    ).read_text(encoding="utf-8")
    assert '"soda-prompt-hub"' in host
    assert '"PROMPT_HUB_LIBRARY_ROOT"' in host
    assert '"ORT_DISABLE_TELEMETRY"' in host
    assert "Kill(entireProcessTree: true)" in host
    assert "不是由这个启动器启动" in host
    assert 'Path.Combine(LocalBridgeMount, "prompt-hub")' in host
    assert "/api/remote-nodes/compute-5060ti" in host
    assert 'Path.Combine(AppRoot, "runtime", "python", "python.exe")' in host


def test_shared_ui_has_distinct_windows_desktop_product() -> None:
    repository = _repository()
    html = (repository / "deploy" / "desktop-ui" / "index.html").read_text(encoding="utf-8")
    script = (repository / "deploy" / "desktop-ui" / "desktop.js").read_text(encoding="utf-8")

    assert 'class="desktop-only" id="computeAction"' in html
    assert 'class="compute-settings" id="configAction"' in html
    assert "WINDOWS DESKTOP / 03" in script
    assert 'product === "desktop"' in script
    assert "启动本机计算" in script


def test_windows_desktop_source_stage_is_complete_and_private_free(tmp_path: Path) -> None:
    result = stage_source(_repository(), tmp_path)
    archive = Path(str(result["archive"]))
    root = f"Soda-Prompt-Hub-Desktop-Source-{__version__}/"

    assert result["version"] == __version__
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert f"{root}deploy/windows-desktop/build.ps1" in names
        assert f"{root}deploy/windows-desktop/SodaPromptHub/DesktopHost.cs" in names
        assert f"{root}deploy/windows-shell/SodaComputeWorker/WorkerHost.cs" in names
        assert f"{root}deploy/windows-installer/desktop.iss" in names
        assert f"{root}deploy/windows-installer/build.ps1" in names
        assert f"{root}src/prompt_hub/__init__.py" in names
        assert f"{root}pyproject.toml" in names
        assert f"{root}uv.lock" in names
        assert f"{root}scripts/package_windows_desktop_release.py" in names
        assert not any(name.endswith("worker-config.json") for name in names)
        assert {item.date_time for item in bundle.infolist()} == {ZIP_TIMESTAMP}


def test_staged_powershell_scripts_have_explicit_utf8_and_matching_hashes(tmp_path: Path) -> None:
    result = stage_source(_repository(), tmp_path)
    root = f"Soda-Prompt-Hub-Desktop-Source-{__version__}/"
    with zipfile.ZipFile(str(result["archive"])) as bundle:
        manifest = json.loads(bundle.read(f"{root}SOURCE_MANIFEST.json"))
        scripts = [entry for entry in manifest["files"] if entry["path"].endswith(".ps1")]
        assert scripts
        for entry in scripts:
            content = bundle.read(f"{root}{entry['path']}")
            assert content.startswith(codecs.BOM_UTF8), entry["path"]
            original = (_repository() / entry["path"]).read_text(encoding="utf-8-sig")
            assert content.decode("utf-8-sig") == original
            assert hashlib.sha256(content).hexdigest() == entry["sha256"]


def test_windows_desktop_release_has_three_manifests_and_no_private_data(
    tmp_path: Path,
) -> None:
    repository = _repository()
    published = tmp_path / "published"
    output = tmp_path / "output"
    required = {
        "Soda Prompt Hub.exe": b"fake-pe",
        "desktop-ui/index.html": b"html",
        "desktop-ui/desktop.css": b"css",
        "desktop-ui/desktop.js": b"js",
        "core/pyproject.toml": b"project",
        "core/RELEASE.json": json.dumps({"product_version": __version__}).encode(),
        "core/src/prompt_hub/__init__.py": b"version",
        "worker/prompt_hub_worker.py": b"worker",
        "worker/RELEASE.json": json.dumps({"worker_version": __version__}).encode(),
        "worker/worker-config.json": b"private",
        "worker/debug.pdb": b"debug",
        ".venv/Scripts/python.exe": b"private-runtime",
        "校验桌面包.ps1": b"verify",
        "LICENSE.txt": b"license",
        "runtime/git/cmd/git.exe": b"git-proxy",
        "runtime/git/mingw64/bin/git.exe": b"git",
        "runtime/git/mingw64/bin/git-remote-https.exe": b"git-https",
        "runtime/git/mingw64/etc/ssl/certs/ca-bundle.crt": b"certificates",
        "runtime/git/LICENSE.txt": b"git-license",
        "GIT_RUNTIME.json": b"{}",
        "runtime/python/python312._pth": (
            b"python312.zip\n.\nLib\\site-packages\n..\\..\\core\\src\nimport site\n"
        ),
        "runtime/python/Lib/site-packages/prompt_hub/__init__.py": b"old_version",
    }
    for relative, payload in required.items():
        target = published / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    result = package_release(repository, published, output)
    package_root = Path(str(result["directory"]))
    archive = Path(str(result["archive"]))

    assert (package_root / "PACKAGE_MANIFEST.sha256").is_file()
    assert (package_root / "core" / "MANIFEST.sha256").is_file()
    assert (package_root / "worker" / "MANIFEST.sha256").is_file()
    assert not (package_root / "worker" / "worker-config.json").exists()
    assert not (package_root / ".venv").exists()
    assert result["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    runtime_root = package_root / "runtime" / "python"
    search_paths = [
        str((runtime_root / line.replace("\\", "/")).resolve())
        for line in (runtime_root / "python312._pth").read_text().splitlines()
        if line and not line.startswith(("#", "import "))
    ]
    spec = PathFinder.find_spec("prompt_hub", search_paths)
    assert spec is not None
    assert spec.origin == str(package_root / "core/src/prompt_hub/__init__.py")
