from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from prompt_hub import source_sync
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


def _publish_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    author = tmp_path / "author"
    executable = shutil.which("git")
    assert executable is not None
    subprocess.run([executable, "init", "--bare", str(remote)], check=True, capture_output=True)  # noqa: S603 - local configured executable, argument list and no shell
    author.mkdir()
    _git(author, "init", "-b", "main")
    (author / "prompts.txt").write_text("first\n", encoding="utf-8")
    _commit(author, "initial")
    _git(author, "remote", "add", "origin", str(remote))
    _git(author, "push", "-u", "origin", "main")
    _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    return remote


def _service(settings, spec: SourceSpec, reindexes: list[bool]) -> SourceSyncService:
    return SourceSyncService(
        settings,
        PromptDatabase(settings.database_path),
        sources=[spec],
        reindexer=lambda: reindexes.append(True) or {"demo": 1},
    )


def _spec(url: str, path: Path) -> SourceSpec:
    return SourceSpec(
        source_id="demo",
        name="Demo prompts",
        url=url,
        path=path,
        license_name="test-only",
        notes="",
        importer="wildcards",
    )


def test_missing_source_is_cloned_only_when_explicitly_requested(settings, tmp_path) -> None:
    remote = _publish_remote(tmp_path)
    target = settings.git_sources_root / "demo"
    spec = _spec(str(remote), target)
    reindexes: list[bool] = []
    service = _service(settings, spec, reindexes)

    untouched = service.job({}, _Context())
    assert untouched["sources"][0]["status"] == "missing"
    assert untouched["missing"] == 1
    assert not target.exists()

    cloned = service.job({"clone_missing": True}, _Context())
    assert cloned["cloned"] == 1
    assert cloned["sources"][0]["status"] == "cloned"
    assert (target / "prompts.txt").read_text(encoding="utf-8") == "first\n"
    assert len(reindexes) == 2

    unchanged = service.job({"clone_missing": True}, _Context())
    assert unchanged["cloned"] == 0
    assert unchanged["unchanged"] == 1


def test_clone_that_checks_out_nothing_is_reported_as_failed(settings, tmp_path) -> None:
    remote = _publish_remote(tmp_path)
    _git(remote, "symbolic-ref", "HEAD", "refs/heads/does-not-exist")
    target = settings.git_sources_root / "demo"
    service = _service(settings, _spec(str(remote), target), [])

    result = service.clone("demo")

    assert result["status"] == "failed"
    assert "不可用" in result["message"]


def test_clone_refuses_to_overwrite_an_existing_non_empty_directory(settings, tmp_path) -> None:
    remote = _publish_remote(tmp_path)
    target = settings.git_sources_root / "demo"
    target.mkdir(parents=True)
    (target / "personal.txt").write_text("keep me\n", encoding="utf-8")
    service = _service(settings, _spec(str(remote), target), [])

    result = service.clone("demo")

    assert result["status"] == "failed"
    assert (target / "personal.txt").read_text(encoding="utf-8") == "keep me\n"


def test_failed_clone_removes_only_the_new_incomplete_directory(settings, monkeypatch) -> None:
    target = settings.git_sources_root / "demo"

    def interrupted_clone(_path, *_arguments, **_options) -> str:
        target.mkdir(parents=True)
        (target / "partial.pack").write_text("incomplete", encoding="utf-8")
        raise subprocess.TimeoutExpired(cmd="git clone", timeout=1)

    monkeypatch.setattr("prompt_hub.source_sync._git", interrupted_clone)
    service = _service(settings, _spec("https://example.invalid/demo", target), [])

    result = service.clone("demo")

    assert result["status"] == "failed"
    assert "超时" in result["message"]
    assert not target.exists()


def test_clone_rejects_a_target_outside_the_local_source_root(settings, tmp_path) -> None:
    remote = _publish_remote(tmp_path)
    outside = tmp_path / "outside"
    service = _service(settings, _spec(str(remote), outside), [])

    result = service.clone("demo")

    assert result["status"] == "failed"
    assert not outside.exists()


def test_source_sync_fast_forwards_and_skips_dirty_tree(settings, tmp_path) -> None:
    remote = tmp_path / "remote.git"
    author = tmp_path / "author"
    source = tmp_path / "source"
    executable = shutil.which("git")
    assert executable is not None
    subprocess.run([executable, "init", "--bare", str(remote)], check=True, capture_output=True)  # noqa: S603 - local configured executable, argument list and no shell
    author.mkdir()
    _git(author, "init", "-b", "main")
    (author / "prompts.txt").write_text("first\n", encoding="utf-8")
    _commit(author, "initial")
    _git(author, "remote", "add", "origin", str(remote))
    _git(author, "push", "-u", "origin", "main")
    subprocess.run(  # noqa: S603 - test controls the temporary repository path
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


def test_git_timeout_is_reported_as_source_failure(settings, monkeypatch) -> None:
    monkeypatch.setattr(source_sync.shutil, "which", lambda _: "git")

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="git fetch", timeout=120)

    monkeypatch.setattr(source_sync.subprocess, "run", timeout)
    target = settings.git_sources_root / "demo"
    (target / ".git").mkdir(parents=True)
    service = _service(settings, _spec("https://example.invalid/demo", target), [])
    result = service.job({}, _Context())
    assert result["failed"] == 1
    assert "超时" in result["sources"][0]["message"]


def test_default_reindex_failure_is_not_hidden(settings, monkeypatch) -> None:
    spec = _spec("https://example.invalid/demo", settings.git_sources_root / "demo")
    service = SourceSyncService(settings, PromptDatabase(settings.database_path), sources=[spec])
    failure = {"source_id": "demo", "name": "Demo", "message": "invalid source data"}
    monkeypatch.setattr(
        source_sync,
        "import_report",
        lambda *_: {
            "sources": {},
            "failed": [failure],
            "skipped": [],
        },
    )
    result = service.job({}, _Context())
    assert result["missing"] == 1
    assert result["entry_counts"] == {}
    assert result["index_failed"] == [failure]
