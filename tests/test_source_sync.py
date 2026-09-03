from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from prompt_hub.database import PromptDatabase
from prompt_hub.importers import SourceSpec
from prompt_hub.source_sync import SourceSyncService

if TYPE_CHECKING:
    from pathlib import Path


class _Context:
    job_id = "job-source-sync"

    def __init__(self) -> None:
        self.updates: list[tuple[int, int, str]] = []

    def update(self, current: int, total: int, message: str = "") -> None:
        self.updates.append((current, total, message))


def _git(path: Path, *arguments: str) -> str:
    executable = shutil.which("git")
    assert executable is not None
    result = subprocess.run(  # noqa: S603 - test controls the local git arguments
        [executable, *arguments],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(path: Path, message: str) -> None:
    _git(path, "add", ".")
    _git(
        path,
        "-c",
        "user.name=Prompt Hub Test",
        "-c",
        "user.email=prompt-hub@example.invalid",
        "commit",
        "-m",
        message,
    )


def test_source_sync_fast_forwards_and_skips_dirty_tree(settings, tmp_path) -> None:
    remote = tmp_path / "remote.git"
    author = tmp_path / "author"
    source = tmp_path / "source"
    executable = shutil.which("git")
    assert executable is not None
    subprocess.run(  # noqa: S603 - test controls the temporary repository path
        [executable, "init", "--bare", str(remote)], check=True, capture_output=True
    )
    author.mkdir()
    _git(author, "init", "-b", "main")
    (author / "prompts.txt").write_text("first\n", encoding="utf-8")
    _commit(author, "initial")
    _git(author, "remote", "add", "origin", str(remote))
    _git(author, "push", "-u", "origin", "main")
    subprocess.run(  # noqa: S603 - test controls the temporary repository paths
        [executable, "clone", "--branch", "main", str(remote), str(source)],
        check=True,
        capture_output=True,
    )
    spec = SourceSpec(
        source_id="demo",
        name="Demo prompts",
        url="https://example.invalid/demo",
        path=source,
        license_name="test-only",
        notes="",
        importer="wildcards",
    )
    reindexes = []
    service = SourceSyncService(
        settings,
        PromptDatabase(settings.database_path),
        sources=[spec],
        reindexer=lambda: reindexes.append(True) or {"demo": 1},
    )
    first = service.job({}, _Context())
    assert first["unchanged"] == 1

    (author / "prompts.txt").write_text("first\nsecond\n", encoding="utf-8")
    _commit(author, "second")
    _git(author, "push")
    updated = service.job({}, _Context())
    assert updated["updated"] == 1
    assert (source / "prompts.txt").read_text(encoding="utf-8") == "first\nsecond\n"

    (source / "prompts.txt").write_text("local edit\n", encoding="utf-8")
    (author / "prompts.txt").write_text("third\n", encoding="utf-8")
    _commit(author, "third")
    _git(author, "push")
    skipped = service.job({}, _Context())
    assert skipped["sources"][0]["status"] == "skipped_dirty"
    assert (source / "prompts.txt").read_text(encoding="utf-8") == "local edit\n"
    assert len(reindexes) == 3
