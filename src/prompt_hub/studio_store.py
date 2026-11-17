from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from prompt_hub.creative import CreativeStore, compile_prompt
from prompt_hub.schema_migrations import record_schema_migration

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    from prompt_hub.config import Settings
    from prompt_hub.gallery import GalleryStore

TARGETS = {"anima", "krea2", "moss", "h3"}
STEPS = {"references", "generate", "review", "caption", "export"}
REFERENCE_ROLES = {"identity", "outfit", "style", "pose", "depth", "composition", "mask"}
FIELDS = ("prefix", "body", "negative", "suffix")
MAX_IMAGE_BYTES = 50 * 1024 * 1024

STUDIO_SCHEMA = """
CREATE TABLE IF NOT EXISTS studio_images (
    item_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    review TEXT NOT NULL DEFAULT 'pending',
    caption_json TEXT NOT NULL DEFAULT '{}',
    caption_confirmed INTEGER NOT NULL DEFAULT 0,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id, asset_id, kind)
);
CREATE INDEX IF NOT EXISTS studio_images_project ON studio_images(project_id, created_at);
CREATE TABLE IF NOT EXISTS studio_executions (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    request_json TEXT NOT NULL DEFAULT '{}',
    provider_task_id TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'prepared',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS studio_batches (
    preview_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    job_ids_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS studio_caption_revisions (
    revision_id INTEGER PRIMARY KEY,
    item_id TEXT NOT NULL,
    caption_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


MAX_CAPTION_CHARS = 100000
MAX_CFG = 30
MAX_EDITOR_ROWS = 200
MAX_NAI_CHARACTERS = 6
MAX_OUTPAINT_EDGE = 2048
MAX_WILDCARD_CHARS = 500000
MAX_WILDCARD_NAME_CHARS = 180
REGION_BOX_COORDINATES = 4


class StudioError(ValueError):
    pass


def now() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, value: Any) -> None:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def recipe_defaults() -> dict[str, Any]:
    return {
        "prefix": "",
        "body": "",
        "negative": "",
        "suffix": "",
        "locks": {},
        "locked_values": {},
        "prefix_rows": [],
        "backend": "comfyui",
        "provider_id": "",
        "workflow_id": "",
        "comfy_url": "http://127.0.0.1:8190",
        "model": "",
        "width": 832,
        "height": 1216,
        "steps": 25,
        "cfg": 4.0,
        "seed": 1,
        "text_seed": 1,
        "seed_mode": "increment",
        "text_seed_mode": "increment",
        "text_mode": "wildcard",
        "batch_mode": "new_text",
        "count": 1,
        "bindings": {},
        "overrides": {},
        "branches": {},
        "reference_bindings": {},
        "trigger": "",
        "reference_modes": {},
        "novelai_mode": "vibe",
        "strength": 0.6,
        "noise": 0,
        "reference_strength": 0.6,
        "reference_information": 1.0,
        "characters": [],
        "character_position_mode": "ai",
        "sampler": "k_euler_ancestral",
        "noise_schedule": "karras",
        "cfg_rescale": 0.0,
        "smea": False,
        "smea_dyn": False,
        "decrisp": False,
        "variety": False,
        "outpaint": {"left": 0, "top": 0, "right": 0, "bottom": 0},
        "raffle": {
            "use_general": True,
            "use_questionable": False,
            "use_sensitive": False,
            "use_explicit": False,
            "taglists_must_include": "",
            "filter_out_tags": "",
            "exclude_taglists_containing": "",
            "exclude_tag_categories": "artist, character_name, copyright, meta",
        },
    }


def normalize_recipe(values: dict[str, Any]) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915 - protocol validation and dispatch stay together
    if not isinstance(values, dict):
        msg = "生圖設定需要 JSON 物件"
        raise StudioError(msg)
    recipe: dict[str, Any] = {**recipe_defaults(), **values}
    if "character_position_mode" not in values and values.get("characters"):
        recipe["character_position_mode"] = "custom"
    if recipe["character_position_mode"] not in ("ai", "custom"):
        msg = "角色位置模式有誤"
        raise StudioError(msg)
    for name in FIELDS:
        recipe[name] = str(recipe[name])[:32000]
    for name in (
        "locks",
        "locked_values",
        "bindings",
        "overrides",
        "branches",
        "reference_bindings",
        "reference_modes",
        "raffle",
    ):
        if not isinstance(recipe[name], dict):
            msg = f"{name} 設定格式有誤"
            raise StudioError(msg)
    rows = recipe["prefix_rows"]
    if (
        not isinstance(rows, list)
        or len(rows) > MAX_EDITOR_ROWS
        or any(
            not isinstance(row, dict) or not isinstance(row.get("text", ""), str) for row in rows
        )
    ):
        msg = "前綴分行格式有誤"
        raise StudioError(msg)
    if any(
        not isinstance(value, (str, list))
        or (isinstance(value, list) and any(not isinstance(key, str) for key in value))
        for value in recipe["bindings"].values()
    ):
        msg = "工作流欄位對應格式有誤"
        raise StudioError(msg)
    if any(
        name not in FIELDS or not isinstance(value, str)
        for name, value in recipe["locked_values"].items()
    ):
        msg = "鎖定結果格式有誤"
        raise StudioError(msg)
    if recipe["novelai_mode"] not in {"vibe", "precise", "mixed", "img2img", "infill", "outpaint"}:
        msg = "NovelAI 參考方式有誤"
        raise StudioError(msg)
    if not isinstance(recipe["characters"], list) or len(recipe["characters"]) > MAX_NAI_CHARACTERS:
        msg = "角色提示需要為至多六組的列表"
        raise StudioError(msg)
    for character in recipe["characters"]:
        if not isinstance(character, dict) or not isinstance(character.get("prompt", ""), str):
            msg = "角色提示格式有誤"
            raise StudioError(msg)
        if not isinstance(character.get("negative", ""), str):
            msg = "角色負面提示格式有誤"
            raise StudioError(msg)
        for axis in ("x", "y"):
            if (
                not isinstance(character.get(axis, 0.5), (int, float))
                or not 0 <= character.get(axis, 0.5) <= 1
            ):
                msg = "角色座標需要介於 0 和 1"
                raise StudioError(msg)
    for name in ("strength", "noise", "reference_strength", "reference_information", "cfg_rescale"):
        try:
            recipe[name] = float(recipe[name])
        except (ValueError, TypeError) as error:
            msg = "參考強度需要數字"
            raise StudioError(msg) from error
        if not 0 <= recipe[name] <= 1:
            msg = "參考強度需要介於 0 和 1"
            raise StudioError(msg)
    if recipe["backend"] not in {"comfyui", "openai", "novelai"}:
        msg = "請選擇可用的生圖後端"
        raise StudioError(msg)
    for name, lower, upper in (
        ("width", 64, 4096),
        ("height", 64, 4096),
        ("steps", 1, 200),
        ("count", 1, 200),
        ("seed", 0, 2**53 - 1),
        ("text_seed", 0, 2**53 - 1),
    ):
        try:
            recipe[name] = int(recipe[name])
        except (TypeError, ValueError) as error:
            msg = f"{name} 需要整數"
            raise StudioError(msg) from error
        if not lower <= recipe[name] <= upper:
            msg = f"{name} 超出可用範圍"
            raise StudioError(msg)
    try:
        recipe["cfg"] = float(recipe["cfg"])
    except (TypeError, ValueError) as error:
        msg = "CFG 需要數字"
        raise StudioError(msg) from error
    if not 0 <= recipe["cfg"] <= MAX_CFG:
        msg = "CFG 需要介於 0 和 30"
        raise StudioError(msg)
    for name in ("seed_mode", "text_seed_mode"):
        if recipe[name] not in {"fixed", "increment", "random"}:
            msg = "種子方式有誤"
            raise StudioError(msg)
    if recipe["batch_mode"] not in {"new_text", "same_text"}:
        msg = "批次方式有誤"
        raise StudioError(msg)
    if recipe["text_mode"] not in {"manual", "wildcard", "raffle"}:
        msg = "抽詞方式有誤"
        raise StudioError(msg)
    if not isinstance(recipe["outpaint"], dict):
        msg = "擴圖設定有誤"
        raise StudioError(msg)
    for name in ("left", "top", "right", "bottom"):
        value = recipe["outpaint"].get(name, 0)
        if not isinstance(value, int) or not 0 <= value <= MAX_OUTPAINT_EDGE or value % 64:
            msg = "擴圖邊距需要為 0 至 2048 的 64 倍數"
            raise StudioError(msg)
    for option in recipe["reference_modes"].values():
        if not isinstance(option, dict) or option.get("mode", "vibe") not in {"vibe", "precise"}:
            msg = "逐圖參考設定有誤"
            raise StudioError(msg)
        for name in ("strength", "information", "fidelity"):
            if (
                not isinstance(option.get(name, 1), (int, float))
                or not 0 <= option.get(name, 1) <= 1
            ):
                msg = "逐圖參考強度需要介於 0 和 1"
                raise StudioError(msg)
    return recipe


class StudioStore:
    def __init__(self, settings: Settings, projects: CreativeStore, gallery: GalleryStore) -> None:
        self.settings = settings
        self.projects = projects
        self.gallery = gallery
        self.root = settings.library_root / "studio"
        self.lock = RLock()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.projects.connect() as connection:
            connection.executescript(STUDIO_SCHEMA)
            connection.execute(
                "UPDATE gallery_assets SET image_json=json_set(image_json, '$.hub_"
                "generation', json((SELECT provenance_json FROM studio_images WHER"
                "E studio_images.asset_id=gallery_assets.asset_id AND json_extract"
                "(provenance_json,'$.job_id') IS NOT NULL ORDER BY created_at DESC"
                " LIMIT 1))) WHERE json_extract(image_json,'$.hub_generation') IS "
                "NULL AND EXISTS (SELECT 1 FROM studio_images WHERE studio_images."
                "asset_id=gallery_assets.asset_id AND json_extract(provenance_json"
                ",'$.job_id') IS NOT NULL)"
            )
            record_schema_migration(
                connection,
                "dataset_studio",
                1,
                "Dataset projects, images, captions and recoverable generation",
            )
            connection.commit()

    def require_project(self, project_id: str) -> dict[str, Any]:
        project = self.projects.get_project(project_id)
        if project is None:
            msg = "專案不存在"
            raise StudioError(msg)
        values = project["generation"].get("studio")
        if values is None:
            compiled = compile_prompt(project)
            values = {
                "body": compiled.get("positive", ""),
                "negative": compiled.get("negative", ""),
                "text_mode": "manual",
            }
        project["studio"] = normalize_recipe(values)
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        projects = self.projects.list_projects(limit=300)
        projects = [
            project
            for project in projects
            if project["generation"].get("workspace_role") != "generation"
        ]
        with self.projects.connect() as connection:
            rows = connection.execute(
                "SELECT project_id, kind, review, COUNT(*) AS total FROM studio_images "
                "GROUP BY project_id, kind, review"
            ).fetchall()
        for project in projects:
            counts = [row for row in rows if row["project_id"] == project["project_id"]]
            project["image_count"] = sum(
                row["total"] for row in counts if row["kind"] == "candidate"
            )
            project["approved_count"] = sum(
                row["total"]
                for row in counts
                if row["kind"] == "candidate" and row["review"] == "approved"
            )
            project["last_step"] = project["generation"].get("studio_step", "generate")
        return projects

    def generation_draft(self, backend: str) -> dict[str, Any]:
        if backend not in {"comfyui", "novelai", "openai", "agent-openai", "agent-novelai"}:
            msg = "生圖後端有誤"
            raise StudioError(msg)
        path = self.root / "generation-drafts.json"
        with self.lock:
            drafts = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            project_id = drafts.get(backend, "")
            if project_id and self.projects.get_project(project_id):
                return self.require_project(project_id)
            recipe = recipe_defaults()
            recipe["backend"] = backend.removeprefix("agent-")
            if backend.startswith("agent-"):
                recipe["creation_origin"] = "agent"
            project = self.projects.create_project(
                {
                    "title": {
                        "comfyui": "ComfyUI 創作",
                        "novelai": "NovelAI 創作",
                        "openai": "圖片 API 創作",
                        "agent-openai": "Agent 圖片 API",
                        "agent-novelai": "Agent NovelAI",
                    }[backend],
                    "target_profile": "anima",
                    "generation": {
                        "studio": recipe,
                        "workspace_role": "generation",
                        "studio_step": "generate",
                    },
                }
            )
            drafts[backend] = project["project_id"]
            write_json(path, drafts)
            return self.require_project(project["project_id"])

    def create_project(self, title: str, target: str) -> dict[str, Any]:
        if target not in TARGETS:
            msg = "請選擇訓練目標"
            raise StudioError(msg)
        project = self.projects.create_project(
            {
                "title": title[:160],
                "target_profile": target,
                "generation": {"studio": recipe_defaults(), "studio_step": "references"},
            }
        )
        return self.require_project(project["project_id"])

    def save_project(self, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self.require_project(project_id)
            generation = dict(project["generation"])
            if "studio" in values:
                generation["studio"] = normalize_recipe(values["studio"])
            if "step" in values:
                if values["step"] not in STEPS:
                    msg = "專案步驟有誤"
                    raise StudioError(msg)
                generation["studio_step"] = values["step"]
            update = {"generation": generation}
            for name in ("title", "target_profile"):
                if name in values:
                    update[name] = values[name]
            if update.get("target_profile", project["target_profile"]) not in TARGETS:
                msg = "訓練目標有誤"
                raise StudioError(msg)
            if all(project.get(name) == value for name, value in update.items()):
                return project
            self.projects.update_project(
                project_id,
                update,
                expected_revision=values.get("expected_revision", project["revision"]),
            )
        return self.require_project(project_id)

    def add_image(  # noqa: PLR0913 - matches the existing workflow or route contract
        self,
        project_id: str,
        raw: bytes,
        filename: str,
        *,
        kind: str = "candidate",
        role: str = "",
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.require_project(project_id)
        if kind not in {"candidate", "reference"} or (
            kind == "reference" and role not in REFERENCE_ROLES
        ):
            msg = "圖片用途有誤"
            raise StudioError(msg)
        if len(raw) > MAX_IMAGE_BYTES:
            msg = "圖片超過 50 MiB"
            raise StudioError(msg)
        asset = self.gallery.import_bytes(
            raw, filename=filename, kind="reference" if kind == "reference" else "work"
        )
        if provenance and provenance.get("job_id"):
            self.gallery.record_generation(asset["asset_id"], provenance)
        with self.projects.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO studio_images "
                "(item_id, project_id, asset_id, kind, role, provenance_json, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"image-{uuid4().hex}",
                    project_id,
                    asset["asset_id"],
                    kind,
                    role,
                    json.dumps(provenance or {}, ensure_ascii=False),
                    now(),
                    now(),
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM studio_images WHERE project_id=? AND asset_id=? AND kind=?",
                (project_id, asset["asset_id"], kind),
            ).fetchone()
        return self.decorate_image(row)

    def decorate_image(self, row: sqlite3.Row) -> dict[str, Any]:
        image = dict(row)
        image["caption"] = json.loads(image.pop("caption_json"))
        image["provenance"] = json.loads(image.pop("provenance_json"))
        image["caption_confirmed"] = bool(image["caption_confirmed"])
        asset = self.gallery.require_asset(image["asset_id"])
        image.update(
            {
                "thumbnail_url": asset["thumbnail_url"],
                "image_url": f"/api/gallery/assets/{image['asset_id']}/media/original",
                "title": asset["title"],
                "sha256": asset["sha256"],
            }
        )
        return image

    def images(self, project_id: str, kind: str = "") -> list[dict[str, Any]]:
        self.require_project(project_id)
        query = "SELECT * FROM studio_images WHERE project_id=?"
        values: list[Any] = [project_id]
        if kind:
            query += " AND kind=?"
            values.append(kind)
        query += " ORDER BY created_at, item_id"
        with self.projects.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self.decorate_image(row) for row in rows]

    def image(self, project_id: str, item_id: str) -> dict[str, Any]:
        with self.projects.connect() as connection:
            row = connection.execute(
                "SELECT * FROM studio_images WHERE project_id=? AND item_id=?",
                (project_id, item_id),
            ).fetchone()
        if row is None:
            msg = "圖片不存在"
            raise StudioError(msg)
        return self.decorate_image(row)

    def update_image(self, project_id: str, item_id: str, values: dict[str, Any]) -> dict[str, Any]:  # noqa: C901 - protocol validation and dispatch stay together
        with self.lock:
            image = self.image(project_id, item_id)
            if values.get("expected_updated_at", image["updated_at"]) != image["updated_at"]:
                msg = "標注已由其他操作更新，請重新載入圖片後核對"
                raise StudioError(msg)
            review = values.get("review", image["review"])
            role = values.get("role", image["role"])
            caption = values.get("caption", image["caption"])
            if review not in {"pending", "approved", "excluded"}:
                msg = "圖片狀態有誤"
                raise StudioError(msg)
            if image["kind"] == "reference" and role not in REFERENCE_ROLES:
                msg = "參考用途有誤"
                raise StudioError(msg)
            if not isinstance(caption, dict) or len(json.dumps(caption)) > MAX_CAPTION_CHARS:
                msg = "標注格式有誤或超過大小限制"
                raise StudioError(msg)
            for name in ("long", "medium", "short"):
                if name in caption and not isinstance(caption[name], str):
                    msg = "標注描述需要文字"
                    raise StudioError(msg)
            regions = caption.get("regions", [])
            if not isinstance(regions, list) or len(regions) > MAX_EDITOR_ROWS:
                msg = "標注區域需要列表"
                raise StudioError(msg)
            if "tags" in caption and (
                not isinstance(caption["tags"], list)
                or any(not isinstance(tag, str) for tag in caption["tags"])
            ):
                msg = "標籤需要文字列表"
                raise StudioError(msg)
            for region in regions:
                box = region.get("bbox", []) if isinstance(region, dict) else []
                if (
                    not isinstance(box, list)
                    or len(box) != REGION_BOX_COORDINATES
                    or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in box)
                    or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)
                ):
                    msg = "區域座標需要正規化的 [x0,y0,x1,y1]"
                    raise StudioError(msg)
            confirmed = bool(values.get("caption_confirmed", image["caption_confirmed"]))
            if "caption" in values and caption != image["caption"]:
                confirmed = bool(values.get("caption_confirmed", False))
            with self.projects.connect() as connection:
                if caption != image["caption"] and image["caption"]:
                    connection.execute(
                        (
                            "INSERT INTO studio_caption_revisions(item_id,caption_json,created"
                            "_at) VALUES(?,?,?)"
                        ),
                        (item_id, json.dumps(image["caption"], ensure_ascii=False), now()),
                    )
                connection.execute(
                    "UPDATE studio_images SET review=?, role=?, caption_json=?, "
                    "caption_confirmed=?, updated_at=? WHERE project_id=? AND item_id=?",
                    (
                        review,
                        role,
                        json.dumps(caption, ensure_ascii=False),
                        int(confirmed),
                        now(),
                        project_id,
                        item_id,
                    ),
                )
                connection.commit()
        return self.image(project_id, item_id)

    def enqueue_batch(
        self, preview_id: str, project_id: str, payloads: list[dict[str, Any]]
    ) -> list[str]:
        """Commit all jobs and their idempotency key in one SQLite transaction."""
        with self.projects.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT job_ids_json FROM studio_batches WHERE preview_id=? AND project_id=?",
                (preview_id, project_id),
            ).fetchone()
            if existing:
                return json.loads(existing[0])
            identifiers = []
            for payload in payloads:
                identifier = f"job-{uuid4().hex}"
                connection.execute(
                    "INSERT INTO background_jobs(job_id,job_type,status,payload_json,"
                    "created_at,updated_at) "
                    "VALUES(?,'studio_generate','queued',?,?,?)",
                    (identifier, json.dumps(payload, ensure_ascii=False), now(), now()),
                )
                identifiers.append(identifier)
            connection.execute(
                "INSERT INTO studio_batches VALUES(?,?,?)",
                (preview_id, project_id, json.dumps(identifiers)),
            )
            connection.commit()
        return identifiers

    def image_path(self, project_id: str, item_id: str) -> Path:
        image = self.image(project_id, item_id)
        path = self.gallery.resolve_asset_path(image["asset_id"])
        if path is None or not path.is_file():
            msg = "原圖暫時無法讀取"
            raise StudioError(msg)
        return path

    def execution(self, job_id: str) -> dict[str, Any] | None:
        with self.projects.connect() as connection:
            row = connection.execute(
                "SELECT * FROM studio_executions WHERE job_id=?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["request"] = json.loads(value.pop("request_json"))
        return value

    def save_execution(
        self,
        job_id: str,
        project_id: str,
        request: dict[str, Any],
        provider_task_id: str = "",
        state: str = "prepared",
    ) -> None:
        with self.projects.connect() as connection:
            connection.execute(
                "INSERT INTO studio_executions VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(job_id) DO UPDATE SET request_json=excluded.request_json, "
                "provider_task_id=excluded.provider_task_id, state=excluded.state, "
                "updated_at=excluded.updated_at",
                (
                    job_id,
                    project_id,
                    json.dumps(request, ensure_ascii=False),
                    provider_task_id,
                    state,
                    now(),
                ),
            )
            connection.commit()

    def wordlists(self) -> list[dict[str, Any]]:
        root = self.root / "wildcards"
        root.mkdir(parents=True, exist_ok=True)
        result = []
        for path in sorted(root.rglob("*.txt")):
            content = path.read_text(encoding="utf-8-sig")
            result.append(
                {
                    "name": path.relative_to(root).with_suffix("").as_posix(),
                    "content": content,
                    "count": sum(
                        bool(line.strip()) and not line.lstrip().startswith("#")
                        for line in content.splitlines()
                    ),
                }
            )
        return result

    def save_wordlist(self, name: str, content: str) -> dict[str, Any]:
        if not re.fullmatch(r"[\w-]+(?:/[\w-]+)*", name) or len(name) > MAX_WILDCARD_NAME_CHARS:
            msg = "詞庫名稱可使用文字、數字、底線和分類斜線"
            raise StudioError(msg)
        if len(content) > MAX_WILDCARD_CHARS:
            msg = "詞庫內容過長"
            raise StudioError(msg)
        path = self.root / "wildcards" / f"{name}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
        return {"name": name, "content": content}
