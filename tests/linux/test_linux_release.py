from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path

import pytest
from scripts.build_linux_release import (
    InvalidArchitectureError,
    InvalidBuildDateError,
    build_release,
)

from prompt_hub import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_linux_release_contains_launcher_runtime_and_docs(tmp_path: Path) -> None:
    result = build_release(
        REPO_ROOT,
        tmp_path,
        architecture="amd64",
        build_date="20260915",
    )
    archive = Path(str(result["archive"]))
    assert archive.name == f"soda-prompt-hub-linux-x86_64-{__version__}-20260915.tar.gz"
    assert result["architecture"] == "x86_64"
    assert result["self_contained"] is False
    assert result["requires_uv"] is True

    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        names = {member.name for member in members}
        for required in (
            "soda-prompt-hub/LINUX_RELEASE.json",
            "soda-prompt-hub/deploy/linux/launch.sh",
            "soda-prompt-hub/deploy/linux/soda-prompt-hub.desktop",
            "soda-prompt-hub/deploy/linux/soda-prompt-hub.png",
            "soda-prompt-hub/src/prompt_hub/media.py",
            "soda-prompt-hub/docs/linux/INSTALL.md",
            "soda-prompt-hub/pyproject.toml",
            "soda-prompt-hub/scripts/build_linux_release.py",
            "soda-prompt-hub/uv.lock",
        ):
            assert required in names
        assert not any("/.git/" in name or "/tests/" in name for name in names)
        assert all(member.uid == 0 and member.gid == 0 and member.mtime == 0 for member in members)
        launcher = bundle.getmember("soda-prompt-hub/deploy/linux/launch.sh")
        assert launcher.mode == 0o755

    checksum = Path(str(result["checksums"])).read_text(encoding="utf-8")
    assert checksum == f"{_sha256(archive)}  {archive.name}\n"
    manifest = json.loads(Path(str(result["manifest"])).read_text(encoding="utf-8"))
    assert manifest["sha256"] == _sha256(archive)
    assert manifest["entrypoint"] == "deploy/linux/install.sh"


def test_linux_release_is_reproducible(tmp_path: Path) -> None:
    first = build_release(
        REPO_ROOT,
        tmp_path / "first",
        architecture="x64",
        build_date="20260915",
    )
    second = build_release(
        REPO_ROOT,
        tmp_path / "second",
        architecture="x86_64",
        build_date="20260915",
    )
    assert _sha256(Path(str(first["archive"]))) == _sha256(Path(str(second["archive"])))


@pytest.mark.parametrize("build_date", ["2026-09-15", "", "tomorrow"])
def test_linux_release_rejects_invalid_build_date(tmp_path: Path, build_date: str) -> None:
    with pytest.raises(InvalidBuildDateError):
        build_release(
            REPO_ROOT,
            tmp_path,
            architecture="x86_64",
            build_date=build_date,
        )


def test_linux_release_rejects_unsafe_architecture(tmp_path: Path) -> None:
    with pytest.raises(InvalidArchitectureError):
        build_release(
            REPO_ROOT,
            tmp_path,
            architecture="../../escape",
            build_date="20260915",
        )
