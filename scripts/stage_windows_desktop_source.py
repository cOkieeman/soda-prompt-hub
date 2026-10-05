from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path

ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
SOURCE_DIRECTORIES = (
    "deploy/desktop-ui",
    "deploy/windows-desktop",
    "deploy/windows-installer",
    "deploy/windows-shell",
    "deploy/windows-worker",
    "src/prompt_hub",
    "tests/git-runtime-regression",
    "tests/desktop-host-regression",
    "tests/installer-payload-regression",
)
SOURCE_FILES = (
    "LICENSE",
    "README.md",
    "RELEASE.json",
    "pyproject.toml",
    "uv.lock",
    "scripts/package_windows_desktop_release.py",
    "scripts/stage_windows_desktop_source.py",
)


def stage_source(repository_root: Path, output_root: Path) -> dict[str, object]:
    repository = repository_root.resolve()
    version = _project_version(repository / "pyproject.toml")
    package_name = f"Soda-Prompt-Hub-Desktop-Source-{version}"
    package_root = output_root.resolve() / package_name
    archive = output_root.resolve() / f"{package_name}.zip"
    if package_root.exists():
        shutil.rmtree(package_root)
    if archive.exists():
        archive.unlink()

    for relative in SOURCE_DIRECTORIES:
        source = repository / relative
        target = package_root / relative
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns(
                "dist", "bin", "obj", ".venv", "__pycache__", "worker-config.json"
            ),
        )
    for relative in SOURCE_FILES:
        source = repository / relative
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    # Windows PowerShell 5.1 otherwise decodes UTF-8 scripts as the ANSI code page.
    # Normalize before hashing so the manifest describes the exact build inputs.
    for script in package_root.rglob("*.ps1"):
        content = script.read_text(encoding="utf-8-sig")
        script.write_text(content, encoding="utf-8-sig")

    manifest = [
        {
            "path": path.relative_to(package_root).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    ]
    manifest_path = package_root / "SOURCE_MANIFEST.json"
    manifest_payload = {
        "format": "soda-windows-desktop-source-v1",
        "version": version,
        "files": manifest,
    }
    manifest_path.write_text(
        f"{json.dumps(manifest_payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8"
    )
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(item for item in package_root.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(
                f"{package_name}/{path.relative_to(package_root).as_posix()}",
                date_time=ZIP_TIMESTAMP,
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())
    return {
        "format": "soda-windows-desktop-source-v1",
        "version": version,
        "directory": str(package_root),
        "archive": str(archive),
        "archive_sha256": _sha256(archive),
        "file_count": len(manifest) + 1,
    }


def _project_version(path: Path) -> str:
    with path.open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage Soda Prompt Hub Windows Desktop source")
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = stage_source(args.repository_root, args.output_dir)
    sys.stdout.write(f"{json.dumps(result, ensure_ascii=False, indent=2)}\n")


if __name__ == "__main__":
    main()
