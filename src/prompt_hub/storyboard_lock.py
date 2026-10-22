"""Reentrant project locks shared by Hub and its managed editor subprocesses."""

from __future__ import annotations

import os
import stat
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from typing import BinaryIO

LOCK_TIMEOUT_SECONDS = 15
LOCK_RETRY_SECONDS = 0.025
_guard = threading.Lock()
_locks: dict[str, threading.RLock] = {}
_held = threading.local()


def _acquire(stream: BinaryIO) -> None:
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if time.monotonic() >= deadline:
                raise ValueError("分镜项目正在另一个进程保存，请稍后重试") from None
            time.sleep(LOCK_RETRY_SECONDS)
        else:
            return


def _release(stream: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def project_file_lock(path: Path) -> Iterator[None]:
    """Keep the sidecar inode stable across replacements; never delete lock files."""
    key = os.path.normcase(str(path.resolve()))
    with _guard:
        lock = _locks.setdefault(key, threading.RLock())
    with lock:
        held = getattr(_held, "paths", None)
        if held is None:
            held = _held.paths = set()
        if key in held:
            yield
            return
        if path.is_symlink() or path.is_junction():
            raise ValueError("分镜锁文件不接受链接")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as stream:
            details = os.fstat(stream.fileno())
            if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
                raise ValueError("分镜锁文件必须是普通非链接文件")
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            _acquire(stream)
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
                _release(stream)
