from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException

from prompt_hub.database import PromptDatabase
from prompt_hub.database_support import EntryInput
from prompt_hub.dataset_workspace import DatasetWorkspaceStore, _collect_source_files
from prompt_hub.studio_annotations import normalize_annotation
from prompt_hub.studio_store import StudioError, StudioStore, write_json

if TYPE_CHECKING:
    from prompt_hub.gallery import GalleryStore


MAX_GALLERY_TRANSFER_IMAGES = 200


def create_workbench_router(  # noqa: C901, PLR0915 - FastAPI route registration aggregates nested handlers
    studio: StudioStore, workspaces: DatasetWorkspaceStore, gallery: GalleryStore
) -> APIRouter:
    router = APIRouter(prefix="/api/workbench")
    mapping_path = studio.root / "imported-workspaces.json"

    def imported_workspaces() -> dict[str, Any]:
        return (
            json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.is_file() else {}
        )

    @router.post("/drafts/{backend}")
    def draft(backend: str) -> dict[str, Any]:
        return studio.generation_draft(backend)

    @router.post("/characters/library")
    def save_character(values: dict[str, Any]) -> dict[str, str]:
        name = str(values.get("name", "")).strip()[:160]
        prompt = str(values.get("prompt", "")).strip()[:32000]
        negative = str(values.get("negative", ""))[:32000]
        identifier = str(values.get("id", "")).strip()[:100]
        if not name or not prompt or not identifier:
            msg = "請填寫角色名稱和提示詞"
            raise StudioError(msg)
        database = PromptDatabase(studio.settings.database_path)
        source_id = "local-novelai-characters"
        database.upsert_source(
            source_id=source_id,
            name="我的角色詞庫",
            source_type="local",
            url="",
            local_path="",
            commit_hash="",
            license_name="private",
            notes="",
        )
        thumbnail_id = str(values.get("thumbnail_asset_id", ""))
        if thumbnail_id:
            gallery.require_asset(thumbnail_id)
        database.upsert_entry(
            EntryInput(
                source_id=source_id,
                external_id=identifier,
                kind="character",
                title=name,
                content=prompt,
                negative_content=negative,
                model_family="novelai",
                category="角色",
                safety="unrated",
                metadata={
                    "gender": values.get("gender", "other"),
                    "thumbnail_asset_id": thumbnail_id,
                    "image_refs": [{"origin": "gallery", "path": thumbnail_id, "safety": "unrated"}]
                    if thumbnail_id
                    else [],
                },
            )
        )
        return {"source_id": source_id, "external_id": identifier}

    @router.get("/datasets")
    def datasets() -> list[dict[str, Any]]:
        result = [
            {
                "id": item["project_id"],
                "kind": "project",
                "name": item["title"],
                "image_count": item["image_count"],
                "target": item["target_profile"],
                "updated_at": item["updated_at"],
            }
            for item in studio.list_projects()
        ]
        imported = imported_workspaces()
        for item in workspaces.list_workspaces():
            record = imported.get(item["workspace_id"], {})
            if record.get("complete") and studio.projects.get_project(record["project_id"]):
                continue
            result.append(
                {
                    "id": item["workspace_id"],
                    "kind": "directory",
                    "name": item["name"],
                    "image_count": item.get("summary", {}).get("image_count", 0),
                    "source_path": item["source_path"],
                    "updated_at": item["updated_at"],
                }
            )
        return sorted(result, key=lambda item: item["updated_at"], reverse=True)

    @router.post("/workspaces/{workspace_id}/import")
    def import_workspace(workspace_id: str, values: dict[str, Any]) -> dict[str, Any]:  # noqa: C901 - protocol validation and dispatch stay together
        workspace = workspaces.get(workspace_id)
        if workspace is None:
            raise HTTPException(404, "資料集不存在")
        root = Path(workspace["source_path"]).resolve()
        if not root.is_dir():
            msg = "資料集原目錄離線"
            raise StudioError(msg)
        with studio.lock:
            mapping = imported_workspaces()
            project_id = mapping.get(workspace_id, {}).get("project_id")
            if not project_id or not studio.projects.get_project(project_id):
                project = studio.create_project(
                    workspace["name"], str(values.get("target", "moss"))
                )
                project_id = project["project_id"]
                mapping[workspace_id] = {"project_id": project_id, "complete": False}
                write_json(mapping_path, mapping)
            paths, _ = _collect_source_files(root)
            errors = []
            imported = 0
            for path in paths:
                if not path.resolve().is_relative_to(root):
                    continue
                try:
                    image = studio.add_image(
                        project_id,
                        path.read_bytes(),
                        path.name,
                        provenance={
                            "source": "directory",
                            "workspace_id": workspace_id,
                            "relative_path": path.relative_to(root).as_posix(),
                        },
                    )
                    if not image["caption"]:
                        caption = None
                        if path.with_suffix(".json").is_file():
                            caption = normalize_annotation(
                                json.loads(
                                    path.with_suffix(".json").read_text(encoding="utf-8-sig")
                                )
                            )
                        elif path.with_suffix(".txt").is_file():
                            caption = {
                                "long": path.with_suffix(".txt")
                                .read_text(encoding="utf-8-sig")
                                .strip(),
                                "source": "existing_sidecar",
                            }
                        if caption:
                            studio.update_image(
                                project_id,
                                image["item_id"],
                                {"caption": caption, "caption_confirmed": False},
                            )
                    imported += 1
                except (StudioError, ValueError, OSError) as error:
                    errors.append({"file": path.name, "error": str(error)})
            mapping[workspace_id] = {"project_id": project_id, "complete": not errors}
            write_json(mapping_path, mapping)
            return {"project_id": project_id, "imported": imported, "errors": errors}

    @router.post("/datasets/{project_id}/assets")
    def add_assets(project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        studio.require_project(project_id)
        asset_ids = values.get("asset_ids", [])
        if (
            not isinstance(asset_ids, list)
            or not 1 <= len(asset_ids) <= MAX_GALLERY_TRANSFER_IMAGES
        ):
            raise HTTPException(400, "請選擇 1 至 200 張圖片")
        kind = str(values.get("kind", "candidate"))
        role = str(values.get("role", "identity"))
        existing = {(item["asset_id"], item["kind"]) for item in studio.images(project_id)}
        assets = []
        for asset_id in dict.fromkeys(str(value) for value in asset_ids):
            asset = gallery.get_asset(asset_id)
            path = gallery.resolve_asset_path(asset_id) if asset else None
            if asset is None or path is None:
                raise HTTPException(404, "圖片不存在或原圖目錄離線")
            assets.append((asset, path))
        added = []
        with studio.lock:
            existing = {(item["asset_id"], item["kind"]) for item in studio.images(project_id)}
            for asset, path in assets:
                if (asset["asset_id"], kind) in existing:
                    continue
                item = studio.add_image(
                    project_id,
                    path.read_bytes(),
                    filename=path.name,
                    kind=kind,
                    role=role,
                    provenance={"gallery_asset_id": asset["asset_id"], "source": "gallery"},
                )
                added.append(item)
        return {"added": len(added), "images": added}

    return router
