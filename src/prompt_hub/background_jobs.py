from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from prompt_hub.schema_migrations import record_schema_migration

JOB_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS background_jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'canceled')),
    payload_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    progress_current INTEGER NOT NULL DEFAULT 0,
    progress_total INTEGER NOT NULL DEFAULT 0,
    progress_message TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0, 1)),
    created_at TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_background_jobs_queue
ON background_jobs(status, created_at);
"""

JobResult = Mapping[str, Any] | None
JobHandler = Callable[[Mapping[str, Any], "JobContext"], JobResult]


class JobCancelledError(RuntimeError):
    pass


class JobInterruptedError(RuntimeError):
    pass


class BackgroundJobStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(JOB_SCHEMA)
            record_schema_migration(
                connection,
                "background_jobs",
                1,
                "Recoverable background job queue baseline",
            )
            connection.commit()

    def enqueue(
        self,
        job_type: str,
        payload: Mapping[str, Any],
        *,
        max_attempts: int = 1,
    ) -> dict[str, Any]:
        job_id = f"job-{uuid4().hex}"
        now = _now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO background_jobs (
                    job_id, job_type, status, payload_json, max_attempts,
                    created_at, updated_at
                ) VALUES (?, ?, 'queued', ?, ?, ?, ?)
                """,
                (job_id, job_type, _dump(payload), max(1, max_attempts), now, now),
            )
            connection.commit()
        job = self.get(job_id)
        if job is None:  # pragma: no cover - guarded by insert
            raise RuntimeError("Background job was not created")
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM background_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return _job_from_row(row) if row is not None else None

    def list_jobs(self, *, status: str = "", limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM background_jobs"
        values: list[Any] = []
        if status:
            query += " WHERE status = ?"
            values.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        values.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [_job_from_row(row) for row in rows]

    def recover_interrupted(self) -> int:
        now = _now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE background_jobs SET
                    status = 'queued',
                    max_attempts = MAX(max_attempts, attempts + 1),
                    progress_message = '服务重启后等待恢复',
                    started_at = '',
                    updated_at = ?
                WHERE status = 'running' AND cancel_requested = 0
                """,
                (now,),
            )
            connection.execute(
                """
                UPDATE background_jobs SET
                    status = 'canceled', finished_at = ?, updated_at = ?
                WHERE status = 'running' AND cancel_requested = 1
                """,
                (now, now),
            )
            connection.commit()
        return cursor.rowcount

    def claim_next(self, supported_types: set[str]) -> dict[str, Any] | None:
        if not supported_types:
            return None
        placeholders = ", ".join("?" for _ in supported_types)
        now = _now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"""
                SELECT * FROM background_jobs
                WHERE status = 'queued' AND cancel_requested = 0
                  AND job_type IN ({placeholders})
                ORDER BY created_at ASC
                LIMIT 1
                """,  # noqa: S608
                sorted(supported_types),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                """
                UPDATE background_jobs SET
                    status = 'running', attempts = attempts + 1,
                    started_at = ?, finished_at = '', updated_at = ?
                WHERE job_id = ?
                """,
                (now, now, row["job_id"]),
            )
            claimed = connection.execute(
                "SELECT * FROM background_jobs WHERE job_id = ?",
                (row["job_id"],),
            ).fetchone()
            connection.commit()
        return _job_from_row(claimed) if claimed is not None else None

    def update_progress(self, job_id: str, current: int, total: int, message: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE background_jobs SET
                    progress_current = ?, progress_total = ?,
                    progress_message = ?, updated_at = ?
                WHERE job_id = ? AND status = 'running'
                """,
                (max(0, current), max(0, total), message[:500], _now(), job_id),
            )
            connection.commit()

    def complete(self, job_id: str, result: Mapping[str, Any]) -> None:
        now = _now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE background_jobs SET
                    status = 'completed', result_json = ?, error = '',
                    progress_message = '已完成', finished_at = ?, updated_at = ?
                WHERE job_id = ? AND status = 'running'
                """,
                (_dump(result), now, now, job_id),
            )
            connection.commit()

    def fail(self, job_id: str, error: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        retrying = job["attempts"] < job["max_attempts"] and not job["cancel_requested"]
        status = "queued" if retrying else "failed"
        message = "失败，等待自动重试" if retrying else "失败"
        finished_at = "" if retrying else _now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE background_jobs SET
                    status = ?, error = ?, progress_message = ?,
                    finished_at = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, error[:4000], message, finished_at, _now(), job_id),
            )
            connection.commit()

    def requeue_interrupted(self, job_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE background_jobs SET
                    status = 'queued', max_attempts = MAX(max_attempts, attempts + 1),
                    progress_message = '服务停止，等待恢复', started_at = '', updated_at = ?
                WHERE job_id = ? AND status = 'running'
                """,
                (_now(), job_id),
            )
            connection.commit()

    def request_cancel(self, job_id: str) -> dict[str, Any] | None:
        job = self.get(job_id)
        if job is None:
            return None
        now = _now()
        queued = job["status"] == "queued"
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE background_jobs SET
                    cancel_requested = 1,
                    status = CASE WHEN status = 'queued' THEN 'canceled' ELSE status END,
                    progress_message = CASE
                        WHEN status = 'queued' THEN '已取消' ELSE '正在取消'
                    END,
                    finished_at = CASE WHEN status = 'queued' THEN ? ELSE finished_at END,
                    updated_at = ?
                WHERE job_id = ? AND status IN ('queued', 'running')
                """,
                (now, now, job_id),
            )
            connection.commit()
        return self.get(job_id) if queued or job["status"] == "running" else job

    def mark_canceled(self, job_id: str) -> None:
        now = _now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE background_jobs SET
                    status = 'canceled', cancel_requested = 1,
                    progress_message = '已取消', finished_at = ?, updated_at = ?
                WHERE job_id = ? AND status = 'running'
                """,
                (now, now, job_id),
            )
            connection.commit()

    def retry(self, job_id: str) -> dict[str, Any] | None:
        job = self.get(job_id)
        if job is None:
            return None
        if job["status"] not in {"failed", "canceled"}:
            return job
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE background_jobs SET
                    status = 'queued', result_json = '{}', error = '',
                    cancel_requested = 0, max_attempts = MAX(max_attempts, attempts + 1),
                    progress_current = 0, progress_total = 0,
                    progress_message = '等待重试', started_at = '', finished_at = '',
                    updated_at = ?
                WHERE job_id = ?
                """,
                (_now(), job_id),
            )
            connection.commit()
        return self.get(job_id)

    def is_cancel_requested(self, job_id: str) -> bool:
        job = self.get(job_id)
        return bool(job and job["cancel_requested"])


class JobContext:
    def __init__(self, store: BackgroundJobStore, job_id: str, stop_event: Event) -> None:
        self.store = store
        self.job_id = job_id
        self.stop_event = stop_event

    def update(self, current: int, total: int, message: str = "") -> None:
        self.raise_if_cancelled()
        self.store.update_progress(self.job_id, current, total, message)

    def raise_if_cancelled(self) -> None:
        if self.stop_event.is_set():
            raise JobInterruptedError
        if self.store.is_cancel_requested(self.job_id):
            raise JobCancelledError


class BackgroundJobRunner:
    def __init__(
        self,
        store: BackgroundJobStore,
        handlers: Mapping[str, JobHandler],
    ) -> None:
        self.store = store
        self.handlers = dict(handlers)
        self._stop_event = Event()
        self._wake_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.store.initialize()
        self.store.recover_interrupted()
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="prompt-hub-jobs", daemon=True)
        self._thread.start()

    def stop(self, *, timeout: float = 5) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def submit(
        self,
        job_type: str,
        payload: Mapping[str, Any],
        *,
        max_attempts: int = 1,
    ) -> dict[str, Any]:
        if job_type not in self.handlers:
            msg = f"Unsupported background job type: {job_type}"
            raise ValueError(msg)
        job = self.store.enqueue(job_type, payload, max_attempts=max_attempts)
        self._wake_event.set()
        return job

    def wake(self) -> None:
        self._wake_event.set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            job = self.store.claim_next(set(self.handlers))
            if job is None:
                self._wake_event.wait(timeout=0.25)
                self._wake_event.clear()
                continue
            self._execute(job)

    def _execute(self, job: Mapping[str, Any]) -> None:
        job_id = str(job["job_id"])
        context = JobContext(self.store, job_id, self._stop_event)
        try:
            result = self.handlers[str(job["job_type"])](job["payload"], context)
            context.raise_if_cancelled()
        except JobCancelledError:
            self.store.mark_canceled(job_id)
        except JobInterruptedError:
            self.store.requeue_interrupted(job_id)
        except Exception as error:  # noqa: BLE001
            self.store.fail(job_id, str(error))
        else:
            self.store.complete(job_id, dict(result or {}))


def _job_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "job_id": str(row["job_id"]),
        "job_type": str(row["job_type"]),
        "status": str(row["status"]),
        "payload": _load(str(row["payload_json"])),
        "result": _load(str(row["result_json"])),
        "error": str(row["error"]),
        "progress_current": int(row["progress_current"]),
        "progress_total": int(row["progress_total"]),
        "progress_message": str(row["progress_message"]),
        "attempts": int(row["attempts"]),
        "max_attempts": int(row["max_attempts"]),
        "cancel_requested": bool(row["cancel_requested"]),
        "created_at": str(row["created_at"]),
        "started_at": str(row["started_at"]),
        "finished_at": str(row["finished_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _dump(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load(value: str) -> dict[str, Any]:
    loaded = json.loads(value or "{}")
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
