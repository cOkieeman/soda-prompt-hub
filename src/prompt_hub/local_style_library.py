from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from prompt_hub.database_support import EntryInput
from prompt_hub.media import media_type_for
from prompt_hub.studio_store import write_json

if TYPE_CHECKING:
    from prompt_hub.database import PromptDatabase

CATALOGS = {"anima", "krea2", "moss", "qwen"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class LocalStyleLibrary:
    def __init__(self, library_root: Path, database: PromptDatabase) -> None:
        self.config_path = library_root / "local-style-library.json"
        self.database = database
        self.lock = RLock()

    def configuration(self) -> dict[str, Any]:
        if not self.config_path.is_file():
            return {"root": "", "node_root": "", "catalogs": []}
        values = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        return {**values, "catalogs": self.catalog_status(values)}

    def configure(self, values: dict[str, Any]) -> dict[str, Any]:
        root = Path(str(values.get("root", ""))).expanduser().resolve()
        nested = root / "90_备份与维护" / "comfyui-data" / "NeonsStyleExplorer"
        if not (root / "catalogs.json").is_file() and nested.is_dir():
            root = nested.resolve()
        node = Path(str(values.get("node_root", ""))).expanduser().resolve()
        if not (root / "catalogs.json").is_file() or not (root / "custom.json").is_file():
            msg = "請選擇畫風庫或包含 catalogs.json 的 Neons 使用者目錄"
            raise ValueError(msg)
        if not (node / "styles").is_dir():
            msg = "請選擇包含 styles 目錄的 Neons 節點"
            raise ValueError(msg)
        with self.lock:
            write_json(self.config_path, {"root": str(root), "node_root": str(node)})
        return self.configuration()

    def catalog_status(self, values: dict[str, Any]) -> list[dict[str, Any]]:
        root = Path(values["root"])
        result = []
        for catalog in sorted(CATALOGS):
            manifest = root / "catalogs" / catalog / "previews" / "manifest.json"
            if manifest.is_file():
                data = json.loads(manifest.read_text(encoding="utf-8-sig"))
                result.append({"id": catalog, "entries": len(data)})
        return result

    def media_path(self, catalog: str, filename: str) -> Path | None:
        if catalog not in CATALOGS or Path(filename).name != filename:
            return None
        if not self.config_path.is_file():
            return None
        config = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        root = (Path(config["root"]) / "catalogs" / catalog / "previews").resolve()
        candidate = (root / filename).resolve()
        if (
            candidate.is_relative_to(root)
            and candidate.suffix.lower() in IMAGE_SUFFIXES
            and candidate.is_file()
        ):
            return candidate
        return None

    def sync(self) -> dict[str, Any]:  # noqa: C901 - protocol validation and dispatch stay together
        with self.lock:
            config = self.configuration()
            if not config["root"]:
                msg = "先設定本地畫風庫目錄"
                raise ValueError(msg)
            root = Path(config["root"])
            styles: dict[str, dict[str, Any]] = {}
            for path in sorted((Path(config["node_root"]) / "styles").glob("*.json")):
                document = json.loads(path.read_text(encoding="utf-8-sig"))
                rows = document if isinstance(document, list) else document.get("styles", [])
                for row in rows:
                    if isinstance(row, dict) and row.get("id"):
                        styles[str(row["id"])] = row
            for row in json.loads((root / "custom.json").read_text(encoding="utf-8-sig")):
                if isinstance(row, dict) and row.get("id"):
                    styles[str(row["id"])] = row
            by_key: dict[str, list[dict[str, Any]]] = {}
            for style_id, row in styles.items():
                key = re.sub(r"[^A-Za-z0-9]+", "_", style_id.strip()).strip("_")[:140]
                by_key.setdefault(key, []).append(row)
            result = []
            for catalog in config["catalogs"]:
                name = catalog["id"]
                path = root / "catalogs" / name / "previews" / "manifest.json"
                records = json.loads(path.read_text(encoding="utf-8-sig"))
                entries = []
                skipped = 0
                for key, record in records.items():
                    candidates = by_key.get(key, [])
                    matches = [row for row in candidates if row.get("name") == record.get("name")]
                    row = (
                        matches[0]
                        if len(matches) == 1
                        else candidates[0]
                        if len(candidates) == 1
                        else None
                    )
                    if row is None or not str(row.get("nl", "")).strip():
                        skipped += 1
                        continue
                    shots = [
                        shot
                        for shot in record.get("shots", [])
                        if isinstance(shot, dict)
                        and self.media_path(name, str(shot.get("file", ""))) is not None
                    ]
                    if not shots:
                        skipped += 1
                        continue
                    cover = record.get("cover")
                    ordered = sorted(shots, key=lambda shot: shot["file"] != cover)
                    entries.append(
                        EntryInput(
                            source_id="neons-local-" + name,
                            external_id=str(row["id"]),
                            kind="style" if row.get("axis", "style") == "style" else "modifier",
                            title=str(row.get("name", record.get("name", key))),
                            content=str(row["nl"]),
                            negative_content=str(row.get("negative", "")),
                            category=str(row.get("family", "")),
                            model_family=name,
                            safety="unrated",
                            source_path=str(row["id"]),
                            metadata={
                                "prompt_syntax": "natural_language",
                                "compatibility": "local_preview",
                                "style_id": row["id"],
                                "catalog": name,
                                "tags": row.get("tags", []),
                                "image_refs": [
                                    {
                                        "path": name + "/" + shot["file"],
                                        "origin": "local-neons",
                                        "safety": "unrated",
                                        "preview_only": True,
                                    }
                                    for shot in ordered
                                ],
                                "preview_records": ordered,
                                "preview_prompt_limit": 600,
                            },
                        )
                    )
                source_id = "neons-local-" + name
                signature = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.database.connect() as connection:
                    self.database.upsert_source(
                        source_id=source_id,
                        name="Neons 本地 · " + name.upper(),
                        source_type="local",
                        url="",
                        local_path=str(path.parent),
                        commit_hash=signature,
                        license_name="Local materials",
                        notes="本地畫風正文與現有預覽；樣圖記錄按原清單保存。",
                        connection=connection,
                    )
                    connection.execute(
                        "CREATE TEMP TABLE local_style_keys (external_id TEXT PRIMARY KEY)"
                    )
                    for entry in entries:
                        self.database.upsert_entry(entry, connection=connection)
                        connection.execute(
                            "INSERT INTO local_style_keys VALUES (?)", (entry.external_id,)
                        )
                    connection.execute(
                        "DELETE FROM entries WHERE source_id=? AND external_id NOT IN "
                        "(SELECT external_id FROM local_style_keys)",
                        (source_id,),
                    )
                    connection.commit()
                result.append({"catalog": name, "entries": len(entries), "unmatched": skipped})
            return {"catalogs": result, "entries": sum(item["entries"] for item in result)}


def create_local_style_router(service: LocalStyleLibrary) -> APIRouter:
    router = APIRouter(prefix="/api/local-styles")

    @router.get("/settings")
    def settings() -> dict[str, Any]:
        return service.configuration()

    @router.put("/settings")
    def configure(values: dict[str, Any]) -> dict[str, Any]:
        try:
            return service.configure(values)
        except (ValueError, OSError) as error:
            raise HTTPException(400, str(error)) from error

    @router.post("/sync")
    def sync() -> dict[str, Any]:
        try:
            return service.sync()
        except (ValueError, OSError) as error:
            raise HTTPException(400, str(error)) from error

    @router.get("/media/{catalog}/{filename}")
    def media(catalog: str, filename: str) -> FileResponse:
        path = service.media_path(catalog, filename)
        if path is None:
            raise HTTPException(404, "預覽圖片不存在")
        return FileResponse(path, media_type=media_type_for(path))

    return router
