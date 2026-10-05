from __future__ import annotations

from pathlib import Path


def _repository() -> Path:
    return Path(__file__).resolve().parents[1]


def test_windows_installers_are_per_user_and_preserve_user_data() -> None:
    root = _repository() / "deploy" / "windows-installer"
    for name in ("desktop.iss", "worker.iss"):
        source = (root / name).read_text(encoding="utf-8")
        assert "PrivilegesRequired=lowest" in source
        assert "{localappdata}\\Programs" in source
        assert "ArchitecturesAllowed=x64compatible" in source
        assert "MicrosoftEdgeWebview2Setup.exe" in source
        assert "worker-config.json" not in source
        assert "Documents\\Soda Prompt Hub" not in source
        assert "if not UninstallSilent then" in source

    desktop = (root / "desktop.iss").read_text(encoding="utf-8")
    worker = (root / "worker.iss").read_text(encoding="utf-8")
    assert "{app}\\.venv" in desktop
    assert "{app}\\core\\src\\prompt_hub\\__pycache__" in desktop
    assert "[UninstallDelete]" not in worker
    assert "资料库、数据库、日志和备份仍保留" in desktop
    assert "Worker 配置、日志和任务目录仍保留" in worker


def test_windows_runtime_builder_is_pinned_and_offline_for_end_users() -> None:
    root = _repository() / "deploy" / "windows-installer"
    runtime = (root / "prepare-runtime.ps1").read_text(encoding="utf-8")
    build = (root / "build.ps1").read_text(encoding="utf-8")

    assert (root / "prepare-runtime.ps1").read_bytes().startswith(b"\xef\xbb\xbf")
    assert (root / "build.ps1").read_bytes().startswith(b"\xef\xbb\xbf")

    assert '$pythonVersion = "3.12.10"' in runtime
    assert "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3" in runtime
    assert "UvExecutable" in runtime
    assert "& $uvPath export --frozen --no-default-groups" in runtime
    assert "& $uvPath build --wheel --out-dir $wheels" in runtime
    assert "--no-create-gitignore $repository" in runtime
    assert "$uvBuildExitCode = $LASTEXITCODE" in runtime
    assert "if ($uvBuildExitCode -ne 0)" in runtime
    assert 'Get-ChildItem -LiteralPath $wheels -Filter "prompt_hub-*.whl"' in runtime
    assert '$ErrorActionPreference = "Continue"' in runtime
    assert "$pipExitCode = $LASTEXITCODE" in runtime
    assert "if ($pipExitCode -ne 0)" in runtime
    assert "--no-deps --no-compile --only-binary=:all:" in runtime
    assert "--only-binary=:all:" in runtime
    assert '"..\\..\\core\\src"' in runtime
    assert runtime.index('$pthLines += "..\\..\\core\\src"') < runtime.index(
        '$pthLines += "Lib\\site-packages"'
    )
    assert "prompt_hub.__file__" in runtime
    assert "prompt_hub.__version__" in runtime
    assert 'Path.Combine(AppRoot, "runtime", "python", "python.exe")' in (
        _repository() / "deploy" / "windows-desktop" / "SodaPromptHub" / "DesktopHost.cs"
    ).read_text(encoding="utf-8")
    assert 'info.Environment["PYTHONDONTWRITEBYTECODE"] = "1";' in (
        _repository() / "deploy" / "windows-desktop" / "SodaPromptHub" / "DesktopHost.cs"
    ).read_text(encoding="utf-8")
    assert 'info.Environment["PYTHONDONTWRITEBYTECODE"] = "1";' in (
        _repository() / "deploy" / "windows-shell" / "SodaComputeWorker" / "WorkerHost.cs"
    ).read_text(encoding="utf-8")
    assert "Get-AuthenticodeSignature" in build
    assert 'SignerCertificate.Subject -notmatch "Microsoft"' in build
    assert "COMMERCIAL_RELEASE.json" in build
    assert 'Join-Path $env:LOCALAPPDATA "Programs\\Inno Setup 6\\ISCC.exe"' in build
    assert 'Join-Path ([IO.Path]::GetTempPath()) ("SB-" + $stagingId)' in build
    assert "Remove-Item -LiteralPath $installerOutput -Recurse -Force" in build
    assert "Remove-Item -LiteralPath $staging -Recurse -Force" in build


def test_installed_worker_state_is_outside_program_directory() -> None:
    host = (
        _repository() / "deploy" / "windows-shell" / "SodaComputeWorker" / "WorkerHost.cs"
    ).read_text(encoding="utf-8")

    assert 'Path.Combine(AppRoot, "INSTALL_MODE.json")' in host
    assert 'Path.Combine(StateRoot, "worker-config.json")' in host
    assert 'localDesktop ? "Desktop Worker" : "Compute Worker"' in host


def test_windows_diagnostics_are_explicitly_private_and_bounded() -> None:
    repository = _repository()
    diagnostic = (
        repository / "deploy" / "windows-shell" / "SodaComputeWorker" / "DiagnosticBundle.cs"
    ).read_text(encoding="utf-8")
    desktop_shell = (
        repository / "deploy" / "windows-desktop" / "SodaPromptHub" / "ShellForm.cs"
    ).read_text(encoding="utf-8")
    worker_shell = (
        repository / "deploy" / "windows-shell" / "SodaComputeWorker" / "ShellForm.cs"
    ).read_text(encoding="utf-8")

    assert "MaxLogBytes = 512 * 1024" in diagnostic
    assert "MaxLogFiles = 8" in diagnostic
    assert 'Directory.EnumerateFiles(logsRoot, "*.log"' in diagnostic
    assert "worker-config.json" in diagnostic
    assert "databases" in diagnostic
    assert "SecretPattern().Replace" in diagnostic
    assert "BearerPattern().Replace" in diagnostic
    assert 'case "exportDiagnostics"' in desktop_shell
    assert 'case "exportDiagnostics"' in worker_shell


def test_windows_commercial_lifecycle_script_preserves_user_state() -> None:
    script = (_repository() / "deploy" / "windows-installer" / "test-lifecycle.ps1").read_text(
        encoding="utf-8"
    )

    assert "Prompt Hub Core is not using the bundled Python runtime" in script
    assert 'Join-Path $desktopRoot ".venv"' in script
    assert "desktop_program_removed" in script
    assert "worker_program_removed" in script
    assert "worker_config_preserved" in script
    assert "desktop_data_reused" in script
    assert "worker_data_reused" in script
    assert "Installed Desktop reported unexpected version" in script
    assert "Installed Desktop reported unexpected release channel" in script
    assert "Remove-OwnedMarker $desktopMarker" in script
    assert "Remove-OwnedMarker $workerMarker" in script
    assert "Remove-Item -LiteralPath $desktopData" not in script
    assert "Remove-Item -LiteralPath $workerData" not in script
