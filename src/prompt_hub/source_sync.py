from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Any, Protocol

from prompt_hub.importers import SourceSpec, discover_sources, import_report

if TYPE_CHECKING:
    from pathlib import Path

    from prompt_hub.config import Settings
    from prompt_hub.database import PromptDatabase

Reindexer = Callable[[], Mapping[str, int]]

GIT_TIMEOUT_SECONDS = 120.0
CLONE_TIMEOUT_SECONDS = 1800.0


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
        self._reindexer = reindexer

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
        clone_missing = bool(payload.get("clone_missing", False))
        results = []
        for index, spec in enumerate(sources, start=1):
            context.update(
                index - 1, len(sources) + 1, _progress_label(spec, clone_missing=clone_missing)
            )
            results.append(self._sync_one(spec, clone_missing=clone_missing))
            context.update(index, len(sources) + 1, f"已处理 {index}/{len(sources)} 个资料源")
        context.update(len(sources), len(sources) + 1, "重建本地资料索引")
        report = (
            {"sources": dict(self._reindexer()), "failed": [], "skipped": []}
            if self._reindexer is not None
            else import_report(self.settings, self.database)
        )
        context.update(len(sources) + 1, len(sources) + 1, "资料检查结束，请查看各来源结果")
        return {
            "sources": results,
            "updated": sum(item["status"] == "updated" for item in results),
            "unchanged": sum(item["status"] == "unchanged" for item in results),
            "cloned": sum(item["status"] == "cloned" for item in results),
            "skipped": sum(
                str(item["status"]).startswith("skipped") or item["status"] == "not_git"
                for item in results
            ),
            "missing": sum(item["status"] == "missing" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
            "entry_counts": report["sources"],
            "index_failed": report["failed"],
            "index_skipped": report["skipped"],
        }

    def configured_source_ids(self) -> set[str]:
        return {spec.source_id for spec in self._configured_sources()}

    def _configured_sources(self) -> list[SourceSpec]:
        return list(self._sources) if self._sources is not None else discover_sources(self.settings)

    def _source_status(self, spec: SourceSpec) -> dict[str, Any]:
        if spec.local_error:
            return _result(spec, "failed", message=spec.local_error)
        if spec.local_only:
            return _result(
                spec,
                "local" if spec.path.is_dir() else "missing",
                message="本地只读映射。不会联网拉取或修改资料目录。",
            )
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

    def clone(self, source_id: str) -> dict[str, Any]:
        """Fetch one configured source that is not present on this Mac yet."""
        spec = next(
            (item for item in self._configured_sources() if item.source_id == source_id), None
        )
        if spec is None:
            msg = "资料源不在预设清单中"
            raise ValueError(msg)
        return self._clone_one(spec)

    def _clone_one(self, spec: SourceSpec) -> dict[str, Any]:
        if spec.local_only:
            return _result(
                spec, "skipped_local", message="本地映射不会下载。请检查共享目录是否已挂载。"
            )
        return self._clone_git(spec)

    def _clone_git(self, spec: SourceSpec) -> dict[str, Any]:
        root = self.settings.git_sources_root
        if not spec.path.is_relative_to(root):
            return _result(spec, "failed", message="资料源路径不在本地来源目录内，已拒绝拉取")
        target_preexisting = spec.path.exists()
        if spec.path.exists() and (not spec.path.is_dir() or any(spec.path.iterdir())):
            return _result(spec, "failed", message="本地目录已存在且不为空，未覆盖")
        root.mkdir(parents=True, exist_ok=True)
        try:
            _git(
                root,
                "clone",
                "--",
                spec.url,
                str(spec.path),
                timeout=CLONE_TIMEOUT_SECONDS,
            )
        except SourceSyncError as error:
            if not target_preexisting:
                shutil.rmtree(spec.path, ignore_errors=True)
            return _result(spec, "failed", message=str(error))
        except subprocess.TimeoutExpired:
            if not target_preexisting:
                shutil.rmtree(spec.path, ignore_errors=True)
            return _result(spec, "failed", message="拉取超时，请检查网络后重试")
        cloned = self._source_status(spec)
        if cloned["status"] in {"missing", "not_git", "failed"}:
            return {
                **cloned,
                "status": "failed",
                "message": f"拉取结束但本地仓库不可用：{cloned['message'] or cloned['status']}",
            }
        return {**cloned, "status": "cloned", "message": "已拉取到本地"}

    def _sync_one(self, spec: SourceSpec, *, clone_missing: bool = False) -> dict[str, Any]:
        current = self._source_status(spec)
        if spec.local_only:
            return (
                current
                if current["status"] in {"failed", "missing"}
                else {
                    **current,
                    "status": "skipped_local",
                    "message": "已复用本地资料。仅重建索引。",
                }
            )
        return self._sync_git(spec, current, clone_missing=clone_missing)

    def _sync_git(
        self, spec: SourceSpec, current: dict[str, Any], *, clone_missing: bool
    ) -> dict[str, Any]:
        if current["status"] == "missing" and clone_missing:
            return self._clone_one(spec)
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


def _git(
    path: Path,
    *arguments: str,
    check: bool = True,
    timeout: float = GIT_TIMEOUT_SECONDS,
) -> str:
    executable = shutil.which("git")
    if executable is None:
        raise SourceSyncError("找不到 Git 可执行文件")
    try:
        result = subprocess.run(  # noqa: S603
            [executable, *arguments],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        operation = arguments[0] if arguments else "操作"
        msg = f"Git {operation} 超时（{timeout:g} 秒），请检查网络后重试"
        raise SourceSyncError(msg) from error
    if result.returncode and check:
        detail = (result.stderr or result.stdout).strip()[:600]
        raise SourceSyncError(detail or f"Git 命令失败：{' '.join(arguments)}")
    return result.stdout.strip() if result.returncode == 0 else ""


def _progress_label(spec: SourceSpec, *, clone_missing: bool) -> str:
    if clone_missing and not spec.path.is_dir():
        return f"正在拉取 {spec.name}，首次下载可能需要几分钟"
    return f"检查并更新 {spec.name}（Git 单步最长等待 {GIT_TIMEOUT_SECONDS:g} 秒）"


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
