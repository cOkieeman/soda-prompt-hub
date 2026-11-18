from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from prompt_hub.studio_store import StudioError

MAX_SCRIPT_ARGUMENTS = 100


def package_path(name: str) -> str:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or ":" in normalized or not path.parts:
        msg = "插件檔案路徑無效"
        raise StudioError(msg)
    return path.as_posix()


def client_entry(package: dict[str, Any]) -> str:
    if package["kind"] != "dsh":
        return ""
    manifest = json.loads(package["files"].get("package.json", "{}"))
    exports = manifest.get("exports", {})
    entry = exports.get("./client", "client.js") if isinstance(exports, dict) else "client.js"
    if not isinstance(entry, str):
        return ""
    entry = package_path(entry)
    return entry if entry in package["files"] else ""


class AgentPackageRuntime:
    def __init__(self, root: Path) -> None:
        self.root = root

    def materialize(self, package: dict[str, Any]) -> Path:
        root = self.root / "runtime" / package["id"]
        for name, text in package["files"].items():
            path = root / package_path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = text.encode("utf-8")
            if not path.is_file() or path.read_bytes() != raw:
                path.write_bytes(raw)
        return root

    def node(self) -> str:
        bundled = Path(sys.executable).parent.parent / "node" / "node.exe"
        executable = str(bundled) if bundled.is_file() else shutil.which("node")
        if not executable:
            msg = "找不到 Node.js，請在工具環境安裝 Node.js"
            raise StudioError(msg)
        return executable

    def dsh(self, package: dict[str, Any], **request: Any) -> dict[str, Any]:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
        root = self.materialize(package)
        manifest_path = root / "package.json"
        if not manifest_path.is_file():
            source = package["files"].get("index.js", "")
            module_type = "commonjs" if "module.exports" in source else "module"
            manifest_path.write_text(json.dumps({"type": module_type}), encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = package_path(str(manifest.get("main") or "index.js"))
        if not (root / entry).is_file():
            candidates = [name for name in package["files"] if name.endswith((".js", ".mjs"))]
            if len(candidates) != 1:
                msg = "插件缺少主入口，請在 package.json 填寫 main"
                raise StudioError(msg)
            entry = candidates[0]
        data = {"root": str(root), "entry": entry, "operation": "describe", **request}
        output = self.run(
            [self.node(), str(Path(__file__).with_name("agent_dsh_host.mjs"))],
            root,
            json.dumps(data, ensure_ascii=False),
        )
        if output["returncode"]:
            raise StudioError("插件執行失敗 " + output["stderr"][:1000])
        try:
            return json.loads(output["stdout"])
        except ValueError as error:
            msg = "插件未返回有效 JSON"
            raise StudioError(msg) from error

    def script(
        self, package: dict[str, Any], values: dict[str, Any], *, python: str = ""
    ) -> dict[str, Any]:
        entry = package_path(str(values.get("entrypoint", "")))
        if entry not in package["tool_files"]:
            msg = "工具不屬於這個已安裝的插件"
            raise StudioError(msg)
        arguments = values.get("arguments", [])
        if (
            not isinstance(arguments, list)
            or len(arguments) > MAX_SCRIPT_ARGUMENTS
            or any(not isinstance(value, str) for value in arguments)
        ):
            msg = "工具參數需要字串列表"
            raise StudioError(msg)
        root = self.materialize(package)
        executable = (python or sys.executable) if entry.endswith(".py") else self.node()
        return self.run(
            [executable, str(root / entry), *arguments], root, str(values.get("stdin", ""))
        )

    def run(self, command: list[str], cwd: Path, stdin: str) -> dict[str, Any]:
        environment = {**os.environ, "PYTHONUTF8": "1", "CUDA_VISIBLE_DEVICES": ""}
        try:
            result = subprocess.run(  # noqa: S603 - local configured executable, argument list and no shell
                command,
                input=stdin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=cwd,
                env=environment,
                timeout=120,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            msg = "插件工具啟動失敗或執行逾時"
            raise StudioError(msg) from error
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-60000:],
            "stderr": result.stderr[-8000:],
        }
