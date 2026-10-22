"""Run the packaged core editor with Hub resource boundaries and Worker routing."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Never

from soda_storyboard.models import Page, Project
from soda_storyboard.server import app as core_app
from soda_storyboard.server.common import APIError
from soda_storyboard.server.store import Store as CoreStore

from prompt_hub.storyboard_lock import project_file_lock
from prompt_hub.storyboard_safety import audit_tree, json_document, local_path, page_limits


class SafeEditorStore(CoreStore):
    def path(self, relative: str) -> Path:
        audit_tree(self.root)
        return local_path(self.root, relative)

    def checked(self, value: dict[str, Any]) -> tuple[Page, dict[str, Any]]:
        value = json_document(value)
        page_limits(value, self.root)
        return super().checked(value)

    def patch_project(self, fields: dict[str, Any]) -> dict[str, Any]:
        fields = json_document(fields)
        project = Project.from_dict({**self.project()["project"], **fields})
        page_limits(
            {
                "id": "defaults",
                "canvas_width": project.default_canvas_width,
                "canvas_height": project.default_canvas_height,
            },
            self.root,
        )
        return super().patch_project(fields)

    def render_page(self, page_id: str, *, raw: dict[str, Any] | None = None) -> Page:
        value = raw if raw is not None else self.page(page_id)["page"]
        page_limits(json_document(value), self.root)
        return super().render_page(page_id, raw=raw)

    def save_character(
        self,
        value: dict[str, Any],
        character_id: str | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        return super().save_character(json_document(value), character_id, version)


class SafeEditorHandler(core_app.Handler):
    def route(self, path: str, query: dict[str, Any], body: dict[str, Any]) -> None:
        # Core handles SSE before route(); never hold this lock for an event stream.
        if path == "/api/health" and self.command == "GET":
            super().route(path, query, body)
            return
        root = self.server.store.root
        lock_path = local_path(root.parent.parent, f"locks/{root.name}.lock")
        with project_file_lock(lock_path):
            super().route(path, query, body)

    def guards(self) -> None:
        super().guards()
        origin = self.headers.get("Origin")
        if origin is not None and origin != f"http://{self.headers.get('Host', '')}":
            raise APIError(403, "编辑器只接受同源请求")

    def body(self) -> dict[str, Any]:
        return json_document(super().body())


def worker_only() -> Never:
    raise APIError(409, "请返回 Hub 分镜页面，通过 Worker 出图和选择结果")


def create_server(root: Path, port: int = 0) -> core_app.Server:
    """Adapt core services only; the editor static assets remain inside its wheel."""
    audit_tree(root)
    vars(core_app)["Store"] = SafeEditorStore
    vars(core_app)["Handler"] = SafeEditorHandler
    vars(core_app)["production"] = worker_only
    return core_app.Server(root, port=port, host="127.0.0.1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--instance-id", required=True)
    args = parser.parse_args()
    server = create_server(args.project_dir, args.port)
    server.instance_id = args.instance_id
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
