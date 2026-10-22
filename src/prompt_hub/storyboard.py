"""Hub-owned index and filesystem wiring for unmodified core projects."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING, Any
from urllib.parse import quote
from uuid import uuid4

from soda_storyboard.bundle import BUNDLE_FORMAT, compile_bundle, export_bundle, load_bundle
from soda_storyboard.importers import import_storyboard
from soda_storyboard.models import Character, Page, Project
from soda_storyboard.preview import render_preview
from soda_storyboard.translations import apply_translations, translation_todo
from soda_storyboard.validation import validate_page

from prompt_hub.storyboard_lock import project_file_lock
from prompt_hub.storyboard_safety import (
    MAX_DOCUMENT_BYTES,
    audit_tree,
    identifier,
    json_document,
    local_path,
    page_limits,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from prompt_hub.config import Settings

INDEX_FORMAT = "soda-storyboard-hub-index-v1"


class StoryboardConflictError(ValueError):
    """An explicit edit conflicts with the current on-disk document."""


def _stamp() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError("分镜文件不能超过 16 MiB")
    return json_document(path.read_text(encoding="utf-8-sig"))


def _version(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    payload = json_document(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _import_content(
    source: dict[str, Any] | list[dict[str, Any]] | str,
) -> dict[str, Any] | str:
    if isinstance(source, str):
        if len(source.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError("分镜文件不能超过 16 MiB")
        text = source.lstrip("\ufeff").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            source = json.loads(text)
        except json.JSONDecodeError:
            if not re.search(r"(?m)^\s*(?:\d+[.)、]\s*|\|.+\|)", text):
                raise ValueError(
                    "请输入 JSON、Markdown 表格或编号分镜内容，不接受文件路径"
                ) from None
            return text
        except RecursionError as exc:
            raise ValueError("分镜 JSON 嵌套超过限制") from exc
    if isinstance(source, list):
        if len(source) > 256 or any(not isinstance(item, dict) for item in source):
            raise ValueError("分镜数组必须包含最多 256 个分镜对象")
        source = {"frames": source}
    return json_document(source)


class StoryboardStore:
    def __init__(self, settings: Settings) -> None:
        self.root = settings.library_root / "storyboards"
        self.lock = RLock()

    def initialize(self) -> None:
        with self.lock:
            audit_tree(self.root)
            for name in ("projects", "trash", "previews", "locks"):
                local_path(self.root, name).mkdir(parents=True, exist_ok=True)
            path = local_path(self.root, "index.json")
            if not path.exists():
                _write_json(path, {"format": INDEX_FORMAT, "projects": {}})
            elif _read_json(path).get("format") != INDEX_FORMAT:
                raise ValueError("分镜索引版本不受支持")

    def _metadata(self) -> dict[str, Any]:
        return _read_json(local_path(self.root, "index.json"))

    @contextmanager
    def project_lock(self, project_id: str) -> Iterator[None]:
        # Always acquire the local RLock before the OS lock, including nested callers.
        with self.lock:
            self.project_path(project_id)
            path = local_path(self.root, f"locks/{identifier(project_id)}.lock")
            with project_file_lock(path):
                yield

    def project_path(self, project_id: str) -> Path:
        root = local_path(self.root, f"projects/{identifier(project_id)}")
        if not local_path(root, "project.json").is_file():
            raise FileNotFoundError("分镜项目不存在")
        audit_tree(root)
        return root

    def page_path(self, project_id: str, page_id: str) -> Path:
        return local_path(self.project_path(project_id), f"pages/{identifier(page_id)}.json")

    def list_projects(self) -> list[dict[str, Any]]:
        with self.lock:
            metadata = self._metadata()["projects"]
            result = []
            for path in sorted(local_path(self.root, "projects").iterdir()):
                if not path.is_dir():
                    continue
                project_id = identifier(path.name)
                with self.project_lock(project_id):
                    root = self.project_path(project_id)
                    project = _read_json(local_path(root, "project.json"))
                    result.append(
                        {
                            "id": project_id,
                            "name": project.get("name", project_id),
                            "page_count": len(list(local_path(root, "pages").glob("*.json"))),
                            **metadata.get(project_id, {}),
                        }
                    )
            return result

    def create_project(
        self,
        name: str,
        project_id: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("项目名称必须为 1 到 200 个字符")
        project_id = identifier(project_id or uuid4().hex)
        raw = json_document(settings or {})
        raw["name"] = name.strip()
        project = Project.from_dict(raw)
        page_limits(
            {
                "id": "defaults",
                "canvas_width": project.default_canvas_width,
                "canvas_height": project.default_canvas_height,
            },
            self.root,
        )
        with self.lock:
            root = local_path(self.root, f"projects/{project_id}")
            if root.exists():
                raise StoryboardConflictError("分镜项目已存在")
            root.mkdir(parents=True)
            for directory in ("pages", "characters", "exports", "output"):
                local_path(root, directory).mkdir()
            _write_json(local_path(root, "project.json"), project.to_dict())
            metadata = self._metadata()
            metadata["projects"][project_id] = {"created_at": _stamp()}
            _write_json(local_path(self.root, "index.json"), metadata)
            return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            root = self.project_path(project_id)
            return {
                "id": project_id,
                "project": _read_json(local_path(root, "project.json")),
                "pages": self.list_pages(project_id),
                "characters": [card.to_dict() for card in self.characters(project_id).values()],
            }

    def delete_project(self, project_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            root = self.project_path(project_id)
            trash_id = f"{identifier(project_id)}-{uuid4().hex}"
            root.replace(local_path(self.root, f"trash/{trash_id}"))
            metadata = self._metadata()
            metadata["projects"].pop(project_id, None)
            _write_json(local_path(self.root, "index.json"), metadata)
            return {"id": project_id, "deleted": True, "trash_path": f"trash/{trash_id}"}

    def list_pages(self, project_id: str) -> list[dict[str, Any]]:
        with self.project_lock(project_id):
            root = self.project_path(project_id)
            result = []
            for path in sorted(local_path(root, "pages").glob("*.json")):
                page_id = identifier(path.stem)
                current = self.get_page(project_id, page_id)
                page = current["page"]
                result.append(
                    {
                        "id": page_id,
                        "title": page.get("title", page.get("name", page_id)),
                        "description": page.get("description", ""),
                        "panel_count": len(page.get("panels", [])),
                        "version": current["version"],
                        "preview_url": "/api/storyboard/projects/"
                        f"{quote(project_id, safe='')}/pages/{quote(page_id, safe='')}/preview.png",
                    }
                )
            return result

    def get_page(self, project_id: str, page_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            path = self.page_path(project_id, page_id)
            raw = _read_json(path)
            page_limits(raw, self.project_path(project_id))
            if raw.get("page_id", raw.get("id")) != page_id:
                raise ValueError("页面标识与文件名不一致")
            return {"page": raw, "version": _version(path)}

    def characters(self, project_id: str) -> dict[str, Character]:
        with self.project_lock(project_id):
            root = self.project_path(project_id)
            cards = {}
            for path in sorted(local_path(root, "characters").glob("*.json")):
                card = Character.from_dict(_read_json(path))
                if identifier(card.id) != path.stem:
                    raise ValueError("角色标识与文件名不一致")
                cards[card.id] = card
            return cards

    def save_character(self, project_id: str, raw: dict[str, Any]) -> dict[str, Any]:
        with self.project_lock(project_id):
            root = self.project_path(project_id)
            card = Character.from_dict(json_document(raw))
            path = local_path(root, f"characters/{identifier(card.id)}.json")
            if path.exists():
                raise StoryboardConflictError("角色已存在，请在核心编辑器中修改")
            _write_json(path, card.to_dict())
            return {"character": card.to_dict(), "version": _version(path)}

    def _envelope(self, project_id: str, raw: dict[str, Any]) -> dict[str, Any]:
        root = self.project_path(project_id)
        page_limits(raw, root)
        return {
            "format": BUNDLE_FORMAT,
            "project": _read_json(local_path(root, "project.json")),
            "page": raw,
            "characters": {
                key: card.to_dict() for key, card in self.characters(project_id).items()
            },
        }

    def create_page(self, project_id: str, raw: dict[str, Any]) -> dict[str, Any]:
        with self.project_lock(project_id):
            raw = json_document(raw)
            page_id = identifier(raw.get("page_id", raw.get("id")))
            path = self.page_path(project_id, page_id)
            if path.exists():
                raise StoryboardConflictError("分镜页已存在")
            raw.setdefault("format", "soda-storyboard-page-v1")
            page, _, _, warnings = load_bundle(self._envelope(project_id, raw))
            page_limits(page.to_dict(), self.project_path(project_id))
            _write_json(path, page.to_dict())
            return {**self.get_page(project_id, page_id), "warnings": warnings}

    def save_page(
        self,
        project_id: str,
        page_id: str,
        raw: dict[str, Any],
        expected_version: str | None = None,
    ) -> dict[str, Any]:
        with self.project_lock(project_id):
            current = self.get_page(project_id, page_id)
            if expected_version is not None and current["version"] != expected_version:
                raise StoryboardConflictError("分镜页已修改，请刷新预览后重试")
            raw = json_document(raw)
            if raw.get("page_id", raw.get("id")) != page_id:
                raise ValueError("页面标识与请求不一致")
            page, _, _, warnings = load_bundle(self._envelope(project_id, raw))
            if _version(self.page_path(project_id, page_id)) != current["version"]:
                raise StoryboardConflictError("分镜页已修改，请刷新预览后重试")
            _write_json(self.page_path(project_id, page_id), page.to_dict())
            return {**self.get_page(project_id, page_id), "warnings": warnings}

    def delete_page(self, project_id: str, page_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            source = self.page_path(project_id, page_id)
            if not source.is_file():
                raise FileNotFoundError("分镜页不存在")
            relative = f".trash/{identifier(page_id)}-{uuid4().hex}.json"
            target = local_path(self.project_path(project_id), relative)
            target.parent.mkdir(exist_ok=True)
            source.replace(target)
            return {"id": page_id, "deleted": True, "trash_path": relative}

    def validate_page(self, project_id: str, page_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            raw = self.get_page(project_id, page_id)["page"]
            page = Page.from_dict(raw)
            settings = Project.from_dict(self.get_project(project_id)["project"])
            page.lora_policy = settings.lora_policy
            return validate_page(page, self.characters(project_id)).to_dict()

    def compile_page(
        self, project_id: str, page_id: str, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with self.project_lock(project_id):
            options = options or {}
            unknown = options.keys() - {"dialogue_mode", "slant_mode", "include_triggers"}
            if unknown:
                raise ValueError("编译选项不受支持")
            return compile_bundle(
                self._envelope(project_id, self.get_page(project_id, page_id)["page"]),
                **options,
            )

    def translation_todo(self, project_id: str, page_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            page, cards, settings, _ = load_bundle(
                self._envelope(project_id, self.get_page(project_id, page_id)["page"])
            )
            return translation_todo(page, cards, Project.from_dict(settings).glossary)

    def apply_translations(
        self,
        project_id: str,
        page_id: str,
        payload: dict[str, Any] | list[dict[str, Any]],
        expected_version: str | None = None,
    ) -> dict[str, Any]:
        with self.project_lock(project_id):
            current = self.get_page(project_id, page_id)
            if expected_version is not None and current["version"] != expected_version:
                raise StoryboardConflictError("分镜页已修改，请重新获取翻译清单")
            page, cards, _, _ = load_bundle(self._envelope(project_id, current["page"]))
            entries = (
                payload.get("translations", payload.get("panels", []))
                if isinstance(payload, dict)
                else payload
            )
            checked = json_document({"translations": entries})["translations"]
            if not isinstance(checked, list):
                raise TypeError("翻译结果必须是数组")
            todo = {
                entry["panel_id"] for entry in self.translation_todo(project_id, page_id)["panels"]
            }
            known = {panel.id for panel in page.panels}
            eligible = []
            rejected = []
            for entry in checked:
                panel_id = entry.get("panel_id") if isinstance(entry, dict) else None
                if panel_id in known and panel_id not in todo:
                    rejected.append({"panel_id": panel_id, "reason": "translation_not_todo"})
                else:
                    eligible.append(entry)
            report = apply_translations(page, cards, eligible)
            report["rejected"].extend(rejected)
            # Core checks source_hash for each scene; unchanged valid translations survive.
            if report["applied"]:
                self.save_page(project_id, page_id, page.to_dict(), current["version"])
            return {**report, **self.get_page(project_id, page_id)}

    def _parse_import(
        self, source: dict[str, Any] | list[dict[str, Any]] | str, page_id: str | None = None
    ) -> tuple[Page, dict[str, Character], dict[str, Any], dict[str, Any]]:
        content = _import_content(source)
        if isinstance(content, str):
            page, report = import_storyboard(content, page_id=page_id)
            page_limits(json_document(page.to_dict()), self.root)
            return page, {}, {}, report
        raw = content
        if raw.get("format") == BUNDLE_FORMAT:
            page_raw = raw.get("page")
            if not isinstance(page_raw, dict):
                raise ValueError("分镜包缺少页面对象")
            page_limits(page_raw, self.root)
            cards_raw = raw.get("characters", {})
            if not isinstance(cards_raw, dict) or len(cards_raw) > 256:
                raise ValueError("分镜包角色卡数量超过限制")
            for card_id, card in cards_raw.items():
                identifier(card_id)
                if not isinstance(card, dict) or identifier(card.get("id")) != card_id:
                    raise ValueError("角色卡标识与分镜包键不一致")
            page, cards, settings, warnings = load_bundle(raw)
            if page_id is not None:
                page.page_id = identifier(page_id)
            return page, cards, settings, {"warnings": warnings, "guesses": []}
        page, report = import_storyboard(raw, page_id=page_id)
        page_limits(page.to_dict(), self.root)
        return page, {}, {}, report

    def import_project(
        self, source: dict[str, Any] | list[dict[str, Any]] | str, name: str | None = None
    ) -> dict[str, Any]:
        with self.lock:
            page, cards, settings, report = self._parse_import(source)
            project = self.create_project(
                name or settings.get("name") or page.id, settings=settings
            )
            project_id = project["id"]
            try:
                for card in cards.values():
                    self.save_character(project_id, card.to_dict())
                created = self.create_page(project_id, page.to_dict())
            except (ValueError, TypeError, OSError):
                self.delete_project(project_id)
                raise
            return {
                **self.get_project(project_id),
                "import_report": report,
                "page": created["page"],
            }

    def import_page(
        self,
        project_id: str,
        source: dict[str, Any] | list[dict[str, Any]] | str,
        page_id: str | None = None,
    ) -> dict[str, Any]:
        with self.project_lock(project_id):
            page, cards, _, report = self._parse_import(source, page_id)
            root = self.project_path(project_id)
            if self.page_path(project_id, page.id).exists():
                raise StoryboardConflictError("分镜页已存在，请为导入页指定新标识")
            existing = self.characters(project_id)
            for key, card in cards.items():
                if key in existing and existing[key].to_dict() != card.to_dict():
                    raise StoryboardConflictError("导入角色与项目中的同名角色冲突")
            # Validate the entire merged envelope before creating even one character file.
            envelope = self._envelope(project_id, page.to_dict())
            envelope["characters"].update({key: card.to_dict() for key, card in cards.items()})
            page_limits(page.to_dict(), root)
            load_bundle(envelope)
            added = []
            try:
                for key, card in cards.items():
                    if key not in existing:
                        self.save_character(project_id, card.to_dict())
                        added.append(key)
                return {**self.create_page(project_id, page.to_dict()), "import_report": report}
            except (ValueError, TypeError, OSError):
                for key in added:
                    local_path(root, f"characters/{identifier(key)}.json").unlink(missing_ok=True)
                raise

    def export_bundle(self, project_id: str, page_id: str | None = None) -> dict[str, Any]:
        with self.project_lock(project_id):
            if page_id is None:
                pages = self.list_pages(project_id)
                if len(pages) != 1:
                    raise ValueError("核心分镜包按页导出，请选择一个分镜页")
                page_id = pages[0]["id"]
            self.get_page(project_id, page_id)
            root = self.project_path(project_id)
            output = local_path(root, f"exports/{identifier(page_id)}.storyboard.json")
            report = export_bundle(self.page_path(project_id, page_id), output=output)
            return {
                **{key: value for key, value in report.items() if key != "path"},
                "filename": output.name,
                "bundle": _read_json(output),
            }

    def thumbnail(self, project_id: str, page_id: str) -> bytes:
        with self.project_lock(project_id):
            page, cards, _, _ = load_bundle(
                self._envelope(project_id, self.get_page(project_id, page_id)["page"])
            )
            relative = f"previews/{identifier(project_id)}-{uuid4().hex}.png"
            target = local_path(self.root, relative)
            try:
                render_preview(
                    page, target, cards, scale=min(384 / max(page.width, page.height), 1)
                )
                return target.read_bytes()
            finally:
                target.unlink(missing_ok=True)
