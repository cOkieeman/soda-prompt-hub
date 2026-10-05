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
SKIPPED_SUFFIXES = {".pdb", ".pyc", ".xml"}
REQUIRED_PATHS = (
    "Soda Prompt Hub.exe",
    "desktop-ui/index.html",
    "desktop-ui/desktop.css",
    "desktop-ui/desktop.js",
    "core/pyproject.toml",
    "core/RELEASE.json",
    "core/src/prompt_hub/__init__.py",
    "worker/prompt_hub_worker.py",
    "worker/RELEASE.json",
    "校验桌面包.ps1",
    "LICENSE.txt",
    "runtime/git/cmd/git.exe",
    "runtime/git/mingw64/bin/git.exe",
    "runtime/git/mingw64/bin/git-remote-https.exe",
    "runtime/git/mingw64/etc/ssl/certs/ca-bundle.crt",
    "runtime/git/LICENSE.txt",
    "GIT_RUNTIME.json",
)


class WindowsDesktopPackageError(ValueError):
    pass


class MissingPublishedFileError(WindowsDesktopPackageError):
    def __init__(self, relative: str) -> None:
        super().__init__(f"publish output missing: {relative}")


class DesktopVersionMismatchError(WindowsDesktopPackageError):
    def __init__(self) -> None:
        super().__init__("Desktop release version does not match project version")


class PublishedVersionMismatchError(WindowsDesktopPackageError):
    def __init__(self, relative: str, expected: str) -> None:
        super().__init__(f"Published release metadata {relative} does not match version {expected}")


def package_release(
    repository_root: Path,
    published_root: Path,
    output_root: Path,
    *,
    runtime: str = "win-x64",
) -> dict[str, object]:
    repository = repository_root.resolve()
    published = published_root.resolve()
    output = output_root.resolve()
    version = _project_version(repository / "pyproject.toml")
    _validate_release_version(repository, version)
    for relative in REQUIRED_PATHS:
        if not (published / relative).is_file():
            raise MissingPublishedFileError(relative)
    _validate_published_versions(published, version)

    package_name = f"Soda-Prompt-Hub-Desktop-{version}-{runtime}"
    package_root = output / package_name
    archive = output / f"{package_name}.zip"
    if package_root.exists():
        shutil.rmtree(package_root)
    if archive.exists():
        archive.unlink()
    package_root.mkdir(parents=True)

    for source in sorted(path for path in published.rglob("*") if path.is_file()):
        relative = source.relative_to(published)
        if source.suffix.casefold() in SKIPPED_SUFFIXES and relative.parts[:2] != (
            "runtime",
            "git",
        ):
            continue
        if source.name in {
            "worker-config.json",
            "MANIFEST.sha256",
            "PACKAGE_MANIFEST.sha256",
        }:
            continue
        if ".venv" in relative.parts or "__pycache__" in relative.parts:
            continue
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    _prioritize_bundled_core(package_root)
    _write_manifest(package_root / "core", "MANIFEST.sha256")
    _write_manifest(package_root / "worker", "MANIFEST.sha256")
    _write_manifest(package_root, "PACKAGE_MANIFEST.sha256")
    files = sorted(path for path in package_root.rglob("*") if path.is_file())
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            info = zipfile.ZipInfo(
                f"{package_name}/{path.relative_to(package_root).as_posix()}",
                date_time=ZIP_TIMESTAMP,
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())
    return {
        "format": "soda-windows-desktop-release-v1",
        "version": version,
        "runtime": runtime,
        "directory": str(package_root),
        "archive": str(archive),
        "archive_sha256": _sha256(archive),
        "file_count": len(files),
    }


def _prioritize_bundled_core(package_root: Path) -> None:
    # Embedded Python ignores PYTHONPATH; an older installed wheel must not win.
    for path in (package_root / "runtime" / "python").glob("*._pth"):
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        core = "../../core/src"
        lines = [line for line in lines if line.strip().replace("\\", "/") != core]
        path.write_text("\n".join([core, *lines]) + "\n", encoding="utf-8")


def _write_manifest(root: Path, name: str) -> None:
    manifest = root / name
    lines = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path == manifest:
            continue
        lines.append(f"{_sha256(path)}  {path.relative_to(root).as_posix()}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validate_release_version(repository: Path, version: str) -> None:
    release = json.loads((repository / "RELEASE.json").read_text(encoding="utf-8"))
    if release.get("product_version") != version:
        raise DesktopVersionMismatchError


def _validate_published_versions(published: Path, version: str) -> None:
    for relative, field in (
        ("core/RELEASE.json", "product_version"),
        ("worker/RELEASE.json", "worker_version"),
    ):
        try:
            payload = json.loads((published / relative).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise PublishedVersionMismatchError(relative, version) from error
        if not isinstance(payload, dict) or payload.get(field) != version:
            raise PublishedVersionMismatchError(relative, version)


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
    parser = argparse.ArgumentParser(description="Package Soda Prompt Hub Windows Desktop")
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--published-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runtime", default="win-x64")
    args = parser.parse_args()
    result = package_release(
        args.repository_root,
        args.published_root,
        args.output_dir,
        runtime=args.runtime,
    )
    sys.stdout.write(f"{json.dumps(result, ensure_ascii=False, indent=2)}\n")


if __name__ == "__main__":
    main()
