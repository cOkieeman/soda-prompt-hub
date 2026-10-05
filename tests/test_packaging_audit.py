from __future__ import annotations

import codecs
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from scripts.build_mac_commercial_release import _copy_product
from scripts.package_windows_desktop_release import (
    REQUIRED_PATHS as DESKTOP_REQUIRED,
)
from scripts.package_windows_desktop_release import (
    PublishedVersionMismatchError as DesktopPublishedVersionMismatchError,
)
from scripts.package_windows_desktop_release import (
    package_release as package_desktop,
)
from scripts.package_windows_shell_release import (
    REQUIRED_PATHS as WORKER_REQUIRED,
)
from scripts.package_windows_shell_release import (
    PublishedVersionMismatchError as WorkerPublishedVersionMismatchError,
)
from scripts.package_windows_shell_release import (
    package_release as package_worker,
)
from scripts.stage_windows_desktop_source import stage_source as stage_desktop
from scripts.stage_windows_shell_source import stage_source as stage_worker

from prompt_hub import __version__
from prompt_hub.windows_worker_support import WorkerConfig

GALLERY_RUNTIME_FILES = (
    "gallery.py",
    "gallery_routes.py",
    "gallery_web.py",
    "generation_evidence.py",
    "scene_planning.py",
    "scene_routes.py",
    "web_assets/gallery.css",
    "web_assets/gallery.js",
)


def _repository() -> Path:
    return Path(__file__).resolve().parents[1]


def _published(tmp_path: Path, required: tuple[str, ...]) -> Path:
    published = tmp_path / "published"
    for relative in required:
        path = published / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"isolated test payload")
    for relative, field in (
        ("core/RELEASE.json", "product_version"),
        ("worker/RELEASE.json", "worker_version"),
    ):
        path = published / relative
        if path.exists():
            path.write_text(json.dumps({field: __version__}))
    return published


def test_windows_source_manifest_covers_gallery_modules_and_assets(tmp_path: Path) -> None:
    report = stage_desktop(_repository(), tmp_path)
    archive_root = f"Soda-Prompt-Hub-Desktop-Source-{__version__}/"
    with zipfile.ZipFile(str(report["archive"])) as bundle:
        manifest = json.loads(bundle.read(f"{archive_root}SOURCE_MANIFEST.json"))
        entries = {item["path"]: item for item in manifest["files"]}
        for relative in GALLERY_RUNTIME_FILES:
            source_path = f"src/prompt_hub/{relative}"
            content = bundle.read(f"{archive_root}{source_path}")
            assert entries[source_path]["sha256"] == hashlib.sha256(content).hexdigest()
            assert entries[source_path]["bytes"] == len(content)
        assert not any("prompt-library/" in item for item in entries)


def test_mac_product_copy_includes_gallery_assets_and_excludes_user_library(tmp_path: Path) -> None:
    product = tmp_path / "product"
    _copy_product(_repository(), product)
    for relative in GALLERY_RUNTIME_FILES:
        assert (product / "src/prompt_hub" / relative).read_bytes() == (
            _repository() / "src/prompt_hub" / relative
        ).read_bytes()
    assert not (product / "prompt-library").exists()
    assert not (product / ".planning").exists()


def test_worker_stage_normalizes_powershell_before_manifest_hashing(tmp_path: Path) -> None:
    report = stage_worker(_repository(), tmp_path)
    archive_root = f"Soda-Compute-Worker-Source-{__version__}/"
    with zipfile.ZipFile(str(report["archive"])) as bundle:
        manifest = json.loads(bundle.read(f"{archive_root}SOURCE_MANIFEST.json"))
        scripts = [item for item in manifest["files"] if item["path"].endswith(".ps1")]
        assert scripts
        for entry in scripts:
            content = bundle.read(f"{archive_root}{entry['path']}")
            assert content.startswith(codecs.BOM_UTF8)
            assert content.decode("utf-8-sig") == (_repository() / entry["path"]).read_text(
                encoding="utf-8-sig"
            )
            assert hashlib.sha256(content).hexdigest() == entry["sha256"]


@pytest.mark.parametrize(
    ("relative", "field"),
    [("core/RELEASE.json", "product_version"), ("worker/RELEASE.json", "worker_version")],
)
def test_desktop_packager_rejects_old_payload_before_replacing_output(
    tmp_path: Path, relative: str, field: str
) -> None:
    published = _published(tmp_path, DESKTOP_REQUIRED)
    (published / relative).write_text(json.dumps({field: "0.0.0-old"}))
    output = tmp_path / "output"
    package = output / f"Soda-Prompt-Hub-Desktop-{__version__}-win-x64"
    package.mkdir(parents=True)
    sentinel = package / "keep.txt"
    sentinel.write_text("previous package")
    with pytest.raises(DesktopPublishedVersionMismatchError):
        package_desktop(_repository(), published, output)
    assert sentinel.read_text() == "previous package"


def test_worker_packager_rejects_old_or_malformed_payload(tmp_path: Path) -> None:
    published = _published(tmp_path, WORKER_REQUIRED)
    for text in (json.dumps({"worker_version": "0.0.0-old"}), "invalid json"):
        (published / "worker/RELEASE.json").write_text(text)
        with pytest.raises(WorkerPublishedVersionMismatchError):
            package_worker(_repository(), published, tmp_path / "output")


def test_native_version_fallbacks_use_bundle_metadata_and_lifecycle_is_versioned() -> None:
    root = _repository()
    for relative in (
        "deploy/windows-desktop/SodaPromptHub/DesktopHost.cs",
        "deploy/windows-shell/SodaComputeWorker/WorkerHost.cs",
    ):
        content = (root / relative).read_text()
        assert "Assembly.GetName().Version?.ToString(3)" in content
        assert '"1.1.1"' not in content
    launcher = (root / "deploy/mac/portable-launcher/SodaPromptHubLauncher.swift").read_text()
    assert '"CFBundleShortVersionString"' in launcher
    assert '"1.1.1"' not in launcher
    lifecycle = (root / "deploy/windows-installer/test-lifecycle.ps1").read_text(
        encoding="utf-8-sig"
    )
    assert "$release.product_version" in lifecycle
    assert '"Soda-Prompt-Hub-Desktop-$version-Setup.exe"' in lifecycle
    assert '"Soda-Compute-Worker-$version-Setup.exe"' in lifecycle
    assert "$health.version -ne $version" in lifecycle


def test_worker_reads_8190_and_preserves_original_model_files(tmp_path: Path) -> None:
    models = tmp_path / "read-only-models"
    loras = tmp_path / "read-only-loras"
    models.mkdir()
    loras.mkdir()
    model = models / "anonymous-base.safetensors"
    lora = loras / "anonymous-style.safetensors"
    model.write_bytes(b"original model")
    lora.write_bytes(b"original lora")
    config = tmp_path / "worker-config.json"
    config.write_text(
        json.dumps(
            {
                "bridge_root": str(tmp_path / "bridge"),
                "comfyui_url": "http://127.0.0.1:8190/",
                "worker_id": "isolated-worker",
                "role": "compute_5060ti",
                "lora_roots": [{"root_id": "style-root", "path": str(loras)}],
                "model_roots": [
                    {"root_id": "base-root", "asset_type": "checkpoint", "path": str(models)}
                ],
            }
        )
    )
    before = config.read_bytes()
    loaded = WorkerConfig.load(config)
    assert loaded.comfyui_url == "http://127.0.0.1:8190"
    assert loaded.lora_roots[0].path == loras
    assert loaded.model_roots[0].path == models
    assert config.read_bytes() == before
    assert model.read_bytes() == b"original model"
    assert lora.read_bytes() == b"original lora"


def test_windows_installer_verifies_payload_before_copying_or_resealing() -> None:
    content = (_repository() / "deploy/windows-installer/build.ps1").read_text(encoding="utf-8-sig")
    for validation in (
        "$actualHash -ne $expectedHash",
        "$covered.Add($file)",
        "$covered.Contains($file.FullName)",
        "$file.StartsWith($prefix",
        "[IO.Path]::IsPathRooted($relative)",
        "[IO.FileAttributes]::ReparsePoint",
    ):
        assert validation in content
    assert content.index("Assert-CleanPayload -Root $desktopSource") < content.index(
        "Copy-Item -LiteralPath $desktopSource"
    )
    assert content.index("Assert-CleanPayload -Root $workerSource") < content.index(
        "prepare-runtime.ps1"
    )


def test_windows_payload_verifier_native_regressions_when_powershell_is_available() -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is unavailable; native verifier has a staged Windows test runner")
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-File",
            str(_repository() / "tests/installer-payload-regression/run.ps1"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report == {"status": "passed", "cases": 12, "installation_performed": False}


def test_runtime_selftest_python_flags_leave_manifest_source_tree_unchanged(tmp_path: Path) -> None:
    script = (_repository() / "deploy/windows-installer/prepare-runtime.ps1").read_text(
        encoding="utf-8-sig"
    )
    invocations = re.findall(r'& \$embeddedPython(.*?) -c "', script)
    assert len(invocations) == 2
    for index, flags in enumerate(invocations):
        source = tmp_path / str(index)
        source.mkdir()
        module = source / "anonymous_fixture.py"
        module.write_text("VALUE = 1\n")
        before = {
            file.relative_to(source): file.read_bytes()
            for file in source.rglob("*")
            if file.is_file()
        }
        subprocess.run(
            [
                sys.executable,
                *flags.split(),
                "-c",
                (
                    "import importlib,sys;sys.path.insert(0,sys.argv[1]);"
                    "importlib.import_module('anonymous_fixture')"
                ),
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        after = {
            file.relative_to(source): file.read_bytes()
            for file in source.rglob("*")
            if file.is_file()
        }
        assert before == after


def test_runtime_wheel_install_and_cleanup_happen_before_final_manifest() -> None:
    runtime = (_repository() / "deploy/windows-installer/prepare-runtime.ps1").read_text(
        encoding="utf-8-sig"
    )
    installs = re.findall(r"--no-deps ([^\n]+)--requirement", runtime)
    assert len(installs) == 2
    assert all("--no-compile" in flags for flags in installs)
    assert '$sourceUrl.StartsWith("file:"' in runtime
    assert 'Get-ChildItem -LiteralPath $Payload -Filter "*.pyc"' in runtime
    assert 'Get-ChildItem -LiteralPath $Payload -Filter "__pycache__"' in runtime
    assert runtime.index("Remove-RuntimeBuildArtifacts -Payload $payload") < runtime.index(
        "$manifestPath = Join-Path $payload"
    )


def test_optional_verification_payload_is_fresh_and_validated_after_runtime_preparation() -> None:
    build = (_repository() / "deploy/windows-installer/build.ps1").read_text(encoding="utf-8-sig")
    assert '[string]$VerificationOutputRoot = ""' in build
    assert "if (Test-Path -LiteralPath $verificationOutput)" in build
    assert "$verificationOutput.StartsWith($sourcePrefix" in build
    runtime_finished = build.index('throw "Worker Python runtime')
    desktop_check = build.index("Assert-CleanPayload -Root $desktopStage")
    worker_check = build.index("Assert-CleanPayload -Root $workerStage")
    desktop_copy = build.index(
        "Copy-Item -LiteralPath $desktopStage -Destination (Join-Path $verificationOutput"
    )
    assert runtime_finished < desktop_check < desktop_copy
    assert runtime_finished < worker_check < desktop_copy
