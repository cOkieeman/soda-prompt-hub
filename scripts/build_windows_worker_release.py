from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any

RELEASE_FORMAT = "soda-windows-worker-release-v1"
PROTOCOL_VERSION = "soda-compute-bridge-v2"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
WORKER_FILES = (
    "0-首次配置.bat",
    "1-先自检.bat",
    "2-启动Worker.bat",
    "3-检查LoRAManager.ps1",
    "校验发行包.ps1",
    "prompt_hub_worker.py",
    "worker-config.example.json",
    "README-WINDOWS.md",
    "RELEASE.json",
    "examples/comfyui-smoke-empty-image-v1.json",
)
WORKER_SOURCE_FILES = (
    "src/prompt_hub/windows_worker_support.py",
    "src/prompt_hub/windows_worker_core.py",
    "src/prompt_hub/windows_worker.py",
)
STANDALONE_PREAMBLE = """from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from contextlib import AbstractContextManager, redirect_stderr, redirect_stdout, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path, PurePosixPath
from threading import Event, Thread
from typing import Any, BinaryIO, Self, TextIO
from uuid import uuid4
"""


class ReleaseBuildError(ValueError):
    pass


class InvalidWorkerReleaseFormatError(ReleaseBuildError):
    def __init__(self) -> None:
        super().__init__("Windows Worker RELEASE.json format is invalid")


class WorkerVersionMismatchError(ReleaseBuildError):
    def __init__(self) -> None:
        super().__init__("Windows Worker version does not match the application version")


class WorkerProtocolMismatchError(ReleaseBuildError):
    def __init__(self) -> None:
        super().__init__("Windows Worker protocol does not match the application protocol")


class MissingWorkerReleaseFileError(FileNotFoundError):
    def __init__(self, relative: str) -> None:
        super().__init__(f"Missing Worker release file: {relative}")


class MissingProjectVersionError(ReleaseBuildError):
    def __init__(self) -> None:
        super().__init__("pyproject.toml does not define project.version")


class InvalidReleaseJsonTypeError(TypeError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"Expected a JSON object: {path}")


def build_release(repository_root: Path, output_root: Path) -> dict[str, Any]:
    repository = repository_root.resolve()
    worker_root = repository / "deploy" / "windows-worker"
    version = _project_version(repository / "pyproject.toml")
    release = _read_json(worker_root / "RELEASE.json")
    if release.get("format") != RELEASE_FORMAT:
        raise InvalidWorkerReleaseFormatError
    if release.get("worker_version") != version:
        raise WorkerVersionMismatchError
    if release.get("protocol_version") != PROTOCOL_VERSION:
        raise WorkerProtocolMismatchError

    package_name = f"Soda-Prompt-Hub-Windows-Worker-{version}"
    staging = output_root.resolve() / package_name
    archive = output_root.resolve() / f"{package_name}.zip"
    if staging.exists():
        shutil.rmtree(staging)
    if archive.exists():
        archive.unlink()
    staging.mkdir(parents=True)
    try:
        for relative in WORKER_FILES:
            source = worker_root / relative
            if not source.is_file():
                raise MissingWorkerReleaseFileError(relative)
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_worker_release_file(repository, relative, source, target)
        shutil.copy2(repository / "LICENSE", staging / "LICENSE.txt")
        manifest = _manifest(staging)
        (staging / "MANIFEST.sha256").write_text(
            "".join(f"{item['sha256']}  {item['path']}\n" for item in manifest),
            encoding="utf-8",
        )
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(item for item in staging.rglob("*") if item.is_file()):
                archive_name = f"{package_name}/{path.relative_to(staging).as_posix()}"
                info = zipfile.ZipInfo(archive_name, date_time=ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, path.read_bytes())
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return {
        "format": RELEASE_FORMAT,
        "version": version,
        "protocol_version": PROTOCOL_VERSION,
        "archive": str(archive),
        "archive_sha256": _sha256(archive),
        "file_count": len(manifest) + 1,
    }


def _copy_worker_release_file(
    repository: Path,
    relative: str,
    source: Path,
    target: Path,
) -> None:
    if relative == "prompt_hub_worker.py":
        target.write_text(render_standalone_worker(repository), encoding="utf-8")
        return
    if source.suffix.casefold() == ".bat":
        payload = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        target.write_bytes(payload.replace(b"\n", b"\r\n"))
        return
    shutil.copy2(source, target)


def render_standalone_worker(repository_root: Path) -> str:
    repository = repository_root.resolve()
    parts = [STANDALONE_PREAMBLE]
    for relative in WORKER_SOURCE_FILES:
        source = repository / relative
        if not source.is_file():
            raise MissingWorkerReleaseFileError(relative)
        parts.append(_standalone_source_part(source.read_text(encoding="utf-8")))
    preamble, support, core, cli = (part.strip() for part in parts)
    return f"{preamble}\n\n{support}\n\n\n{core}\n\n\n{cli}\n"


def _standalone_source_part(source: str) -> str:
    lines = []
    omitting = False
    for line in source.splitlines():
        if line == "# standalone-bundle: omit-start":
            omitting = True
            continue
        if line == "# standalone-bundle: omit-end":
            omitting = False
            continue
        if omitting:
            continue
        if line == "from __future__ import annotations":
            continue
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the standalone Windows Worker ZIP")
    parser.add_argument("--repository-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", default="dist")
    args = parser.parse_args()
    result = build_release(Path(args.repository_root), Path(args.output_dir))
    sys.stdout.write(f"{json.dumps(result, ensure_ascii=False, indent=2)}\n")


def _project_version(path: Path) -> str:
    with path.open("rb") as stream:
        project = tomllib.load(stream).get("project", {})
    version = str(project.get("version", "")).strip()
    if not version:
        raise MissingProjectVersionError
    return version


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise InvalidReleaseJsonTypeError(path)
    return value


def _manifest(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
