"""Managed loopback editor subprocesses, using the core wheel's own UI."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from threading import RLock
from typing import TYPE_CHECKING, Any
from urllib.parse import quote
from uuid import uuid4

from soda_storyboard import edit

from prompt_hub.storyboard_safety import local_path

if TYPE_CHECKING:
    from pathlib import Path

    from prompt_hub.storyboard import StoryboardStore


class StoryboardEditorManager:
    def __init__(self, store: StoryboardStore) -> None:
        self.store = store
        self.lock = RLock()
        self.instances: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _finish_owned(registered: dict[str, Any]) -> None:
        process = registered["process"]
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _launch(self, root: Path) -> tuple[subprocess.Popen[bytes], int, dict[str, Any]]:
        for _ in range(3):
            port = edit.available_port(0)
            instance_id = uuid4().hex
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "prompt_hub.storyboard_editor_server",
                    str(root),
                    "--port",
                    str(port),
                    "--instance-id",
                    instance_id,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and process.poll() is None:
                info = edit.health(port)
                if (
                    edit.same_project(info, root.resolve())
                    and info.get("instance_id") == instance_id
                ):
                    return process, port, info
                time.sleep(0.05)
            process.terminate()
            process.wait(timeout=5)
        raise ValueError("分镜编辑器未能在本地端口启动")

    def start(self, project_id: str, page_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            root = self.store.project_path(project_id)
            if page_id is not None:
                self.store.get_page(project_id, page_id)
            state_path = local_path(root, ".soda/server.json")
            state = edit.read_state(state_path)
            registered = self.instances.get(project_id)
            port = registered["port"] if registered is not None else state.get("port", 0)
            info = edit.health(port)
            # Keep live owned handles when health is temporarily unavailable or mismatched.
            if registered is not None and not edit.matches(
                info, registered["info"], root.resolve()
            ):
                if registered["process"].poll() is None:
                    raise ValueError("分镜编辑器正在忙或状态暂不可达，请稍后重试")
                registered["process"].wait(timeout=5)
                self.instances.pop(project_id, None)
                registered = None
                port = state.get("port", 0)
                info = edit.health(port)
            reused = registered is not None and edit.matches(
                info, registered["info"], root.resolve()
            )
            if reused:
                port = registered["port"]
            else:
                if edit.same_project(info, root.resolve()):
                    raise ValueError("本项目已有外部编辑器，请先关闭该编辑器后再从 Hub 打开")
                process, port, info = self._launch(root)
                try:
                    edit.write_state(state_path, port, info)
                except (ValueError, OSError):
                    process.terminate()
                    process.wait(timeout=5)
                    raise
                self.instances[project_id] = {"port": port, "info": info, "process": process}
            suffix = f"#page={quote(page_id, safe='')}" if page_id else ""
            return {
                "url": f"http://127.0.0.1:{port}/{suffix}",
                "port": port,
                "pid": info["pid"],
                "reused": reused,
            }

    def stop(self, project_id: str) -> dict[str, Any]:
        with self.lock:
            root = self.store.project_path(project_id)
            registered = self.instances.get(project_id)
            if registered is None:
                return {"stopped": False}
            info = edit.health(registered["port"])
            if not edit.matches(info, registered["info"], root.resolve()):
                self._finish_owned(registered)
                self.instances.pop(project_id, None)
                return {"stopped": False, "process_closed": True}
            result = edit.stop(root.resolve(), local_path(root, ".soda/server.json"))
            if result["stopped"]:
                registered["process"].wait(timeout=5)
                self.instances.pop(project_id, None)
            else:
                self._finish_owned(registered)
                self.instances.pop(project_id, None)
                result["process_closed"] = True
            return result

    def close(self) -> None:
        with self.lock:
            for project_id in list(self.instances):
                try:
                    self.stop(project_id)
                except (ValueError, OSError, subprocess.TimeoutExpired):
                    # Cleanup only our own process handles; never trust a stale persisted PID.
                    registered = self.instances.get(project_id)
                    if registered:
                        self._finish_owned(registered)
                        self.instances.pop(project_id, None)
