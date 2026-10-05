from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path

RELEASE_FORMAT = "soda-linux-source-release-v1"
SOURCE_DIRECTORIES = (
    "deploy/desktop-ui",
    "deploy/linux",
    "docs/linux",
    "scripts/linux",
    "src/prompt_hub",
)
SOURCE_FILES = (
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "RELEASE.json",
    "pyproject.toml",
    "scripts/build_linux_release.py",
    "uv.lock",
)
ROOT_DIRECTORY = "soda-prompt-hub"


class LinuxReleaseError(ValueError):
    """Raised when the Linux source release cannot be assembled safely."""


class InvalidBuildDateError(LinuxReleaseError):
    def __init__(self, value: str) -> None:
        super().__init__(f"Build date must use YYYYMMDD: {value}")


class InvalidArchitectureError(LinuxReleaseError):
    def __init__(self, value: str) -> None:
        super().__init__(f"Invalid Linux architecture: {value}")


class MissingReleaseInputError(FileNotFoundError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"Missing Linux release input: {path}")


def build_release(
    repository_root: Path,
    output_root: Path,
    *,
    architecture: str,
    build_date: str,
) -> dict[str, object]:
    repository = repository_root.resolve()
    output = output_root.resolve()
    architecture = _normalize_architecture(architecture)
    if re.fullmatch(r"\d{8}", build_date) is None:
        raise InvalidBuildDateError(build_date)

    version = _project_version(repository / "pyproject.toml")
    release = _read_json(repository / "RELEASE.json")
    if release.get("product_version") != version:
        msg = "Linux release version does not match project version"
        raise LinuxReleaseError(msg)

    for relative in (*SOURCE_DIRECTORIES, *SOURCE_FILES):
        source = repository / relative
        if not source.exists():
            raise MissingReleaseInputError(source)

    package_name = f"soda-prompt-hub-linux-{architecture}-{version}-{build_date}"
    archive = output / f"{package_name}.tar.gz"
    checksum_path = output / "SHA256SUMS"
    manifest_path = output / "LINUX_RELEASE.json"
    output.mkdir(parents=True, exist_ok=True)

    temporary = Path(tempfile.mkdtemp(prefix=".soda-linux-release-", dir=output))
    package_root = temporary / ROOT_DIRECTORY
    try:
        for relative in SOURCE_DIRECTORIES:
            shutil.copytree(
                repository / relative,
                package_root / relative,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
        for relative in SOURCE_FILES:
            target = package_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repository / relative, target)

        source_commit, source_dirty = _git_state(repository)
        internal_manifest = {
            "format": RELEASE_FORMAT,
            "product": "Soda Prompt Hub",
            "version": version,
            "platform": "linux",
            "architecture": architecture,
            "build_date": build_date,
            "source_commit": source_commit,
            "source_dirty": source_dirty,
            "self_contained": False,
            "requires_uv": True,
            "entrypoint": "deploy/linux/install.sh",
        }
        _write_json(package_root / "LINUX_RELEASE.json", internal_manifest)

        if archive.exists():
            archive.unlink()
        _write_deterministic_tar_gz(package_root, archive)
        archive_sha256 = _sha256(archive)
        checksum_path.write_text(f"{archive_sha256}  {archive.name}\n", encoding="utf-8")
        public_manifest = {
            **internal_manifest,
            "file": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": archive_sha256,
        }
        _write_json(manifest_path, public_manifest)
        return {
            **public_manifest,
            "archive": str(archive),
            "checksums": str(checksum_path),
            "manifest": str(manifest_path),
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def _normalize_architecture(value: str) -> str:
    aliases = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}
    normalized = aliases.get(value.strip().casefold(), value.strip().casefold())
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", normalized) is None:
        raise InvalidArchitectureError(value)
    return normalized


def _project_version(path: Path) -> str:
    with path.open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Expected a JSON object: {path}"
        raise TypeError(msg)
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")


def _git_state(repository: Path) -> tuple[str, bool]:
    git = shutil.which("git")
    if git is None:
        return "unknown", True
    try:
        commit = subprocess.run(  # noqa: S603
            [git, "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(  # noqa: S603
            [git, "-C", str(repository), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown", True
    return commit, bool(status.strip())


def _write_deterministic_tar_gz(package_root: Path, archive: Path) -> None:
    with (
        archive.open("wb") as raw_stream,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw_stream, mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as bundle,
    ):
        paths = [package_root, *sorted(package_root.rglob("*"))]
        for path in paths:
            relative = path.relative_to(package_root)
            archive_name = Path(ROOT_DIRECTORY) / relative
            info = bundle.gettarinfo(str(path), arcname=archive_name.as_posix())
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = 0
            info.mode = 0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644
            if path.is_file():
                with path.open("rb") as stream:
                    bundle.addfile(info, stream)
            else:
                bundle.addfile(info)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Linux source release archive")
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--architecture", default=platform.machine())
    parser.add_argument("--build-date", default=datetime.now(UTC).strftime("%Y%m%d"))
    args = parser.parse_args()
    result = build_release(
        args.repository_root,
        args.output_dir,
        architecture=args.architecture,
        build_date=args.build_date,
    )
    sys.stdout.write(f"{json.dumps(result, ensure_ascii=False, indent=2)}\n")


if __name__ == "__main__":
    main()
