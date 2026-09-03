from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Any, Protocol

from prompt_hub.importers import SourceSpec, discover_sources, import_all

if TYPE_CHECKING:
    from pathlib import Path

    from prompt_hub.config import Settings
    from prompt_hub.database import PromptDatabase

Reindexer = Callable[[], Mapping[str, int]]


class SyncProgress(Protocol):
    def update(self, current: int, total: int, message: str = "") -> None: ...


class SourceSyncService:
    def __init__(
        self,
        settings: Settings,
        database: PromptDatabase,
        *,
        sources: Iterable[SourceSpec] | None = None,
        reindexer: Reindexer | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self._sources = list(sources) if sources is not None else None
        self._reindexer = reindexer or (lambda: import_all(settings, database))

    def status(self) -> list[dict[str, Any]]:
        return [self._source_status(spec) for spec in self._configured_sources()]

    def job(self, payload: Mapping[str, Any], context: SyncProgress) -> dict[str, Any]:
        selected_value = payload.get("source_ids", [])
        selected = {
            str(value)
            for value in selected_value
            if isinstance(selected_value, list) and str(value).strip()
        }
        sources = [
            spec
            for spec in self._configured_sources()
            if not selected or spec.source_id in selected
        ]
        if not sources:
            msg = "没有可更新的资料源"
            raise ValueError(msg)
        results = []
        for index, spec in enumerate(sources, start=1):
            context.update(index - 1, len(sources) + 1, f"检查 {spec.name}")
            results.append(self._sync_one(spec))
            context.update(index, len(sources) + 1, f"已检查 {index}/{len(sources)} 个资料源")
        context.update(len(sources), len(sources) + 1, "重建本地资料索引")
        counts = dict(self._reindexer())
        context.update(len(sources) + 1, len(sources) + 1, "资料源与索引已更新")
        return {
            "sources": results,
            "updated": sum(item["status"] == "updated" for item in results),
            "unchanged": sum(item["status"] == "unchanged" for item in results),
            "skipped": sum(str(item["status"]).startswith("skipped") for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
            "entry_counts": counts,
        }

    def _configured_sources(self) -> list[SourceSpec]:
        return list(self._sources) if self._sources is not None else discover_sources(self.settings)

    def _source_status(self, spec: SourceSpec) -> dict[str, Any]:
        if not spec.path.is_dir():
            return _result(spec, "missing", message="本地仓库不存在")
        if not (spec.path / ".git").exists():
            return _result(spec, "not_git", message="本地目录不是 Git 仓库")
        try:
            dirty = bool(_git(spec.path, "status", "--porcelain"))
            commit = _git(spec.path, "rev-parse", "HEAD")
            branch = _git(spec.path, "branch", "--show-current")
            upstream = _git(spec.path, "rev-parse", "--abbrev-ref", "@{u}", check=False)
        except SourceSyncError as error:
            return _result(spec, "failed", message=str(error))
        return _result(
            spec,
            "ready" if upstream and not dirty else "dirty" if dirty else "no_upstream",
            before=commit,
            after=commit,
            branch=branch,
            upstream=upstream,
            dirty=dirty,
        )

    def _sync_one(self, spec: SourceSpec) -> dict[str, Any]:
        current = self._source_status(spec)
        if current["status"] in {"missing", "not_git", "failed"}:
            return current
        if current["dirty"]:
            return {**current, "status": "skipped_dirty", "message": "存在本地改动，已跳过"}
        if not current["upstream"]:
            return {**current, "status": "skipped_no_upstream", "message": "没有 upstream，已跳过"}
        try:
            _git(spec.path, "fetch", "--prune", "origin")
            _git(spec.path, "merge", "--ff-only", str(current["upstream"]))
            after = _git(spec.path, "rev-parse", "HEAD")
        except SourceSyncError as error:
            return {**current, "status": "failed", "message": str(error)}
        status = "updated" if after != current["before"] else "unchanged"
        return {
            **current,
            "status": status,
            "after": after,
            "message": "已更新" if status == "updated" else "已经是最新版本",
        }


class SourceSyncError(RuntimeError):
    pass


def _git(path: Path, *arguments: str, check: bool = True) -> str:
    executable = shutil.which("git")
    if executable is None:
        raise SourceSyncError("找不到 Git 可执行文件")
    result = subprocess.run(  # noqa: S603
        [executable, *arguments],
        cwd=path,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode and check:
        detail = (result.stderr or result.stdout).strip()[:600]
        raise SourceSyncError(detail or f"Git 命令失败：{' '.join(arguments)}")
    return result.stdout.strip() if result.returncode == 0 else ""


def _result(
    spec: SourceSpec,
    status: str,
    *,
    message: str = "",
    before: str = "",
    after: str = "",
    branch: str = "",
    upstream: str = "",
    dirty: bool = False,
) -> dict[str, Any]:
    return {
        "source_id": spec.source_id,
        "name": spec.name,
        "path": str(spec.path),
        "status": status,
        "message": message,
        "before": before,
        "after": after,
        "branch": branch,
        "upstream": upstream,
        "dirty": dirty,
        "license": spec.license_name,
        "url": spec.url,
    }
