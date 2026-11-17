from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from prompt_hub.novelai_auth import NovelAIAccounts
from prompt_hub.studio_annotations import import_annotations
from prompt_hub.studio_providers import validate_provider_recipe
from prompt_hub.studio_store import StudioError, write_json
from prompt_hub.studio_workflows import (
    infer_bindings,
    postprocess_nodes,
    scalar_inputs,
    source_values,
)
from prompt_hub.workflow_profiles import MAX_WORKFLOW_BYTES

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner, BackgroundJobStore
    from prompt_hub.model_connections import ModelConnectionStore
    from prompt_hub.studio_service import StudioService


async def read_limited(request: Request, maximum: int) -> bytes:
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > maximum:
            raise HTTPException(413, detail="檔案超過大小限制")
        chunks.extend(chunk)
    return bytes(chunks)


MAX_CAPTION_BATCH_SIZE = 200


def create_studio_router(  # noqa: C901, PLR0915 - FastAPI route registration aggregates nested handlers
    service: StudioService,
    jobs: BackgroundJobStore,
    runner: BackgroundJobRunner,
    models: ModelConnectionStore,
) -> APIRouter:
    router = APIRouter(prefix="/api/studio")
    store = service.store
    novelai_accounts = NovelAIAccounts(service.providers)

    @router.post("/novelai/login")
    def novelai_login(values: dict[str, Any]) -> dict[str, Any]:
        return novelai_accounts.login(values)

    @router.get("/novelai/session")
    def novelai_session(provider_id: str = "", *, refresh: bool = False) -> dict[str, Any]:
        return novelai_accounts.session(provider_id, refresh=refresh)

    @router.post("/novelai/logout")
    def novelai_logout(values: dict[str, Any]) -> dict[str, Any]:
        return novelai_accounts.logout(str(values.get("provider_id", "")))

    def project_jobs(project_id: str) -> list[dict[str, Any]]:
        keys = (
            "job_id",
            "job_type",
            "status",
            "error",
            "progress_current",
            "progress_total",
            "progress_message",
            "created_at",
            "updated_at",
            "result",
        )
        return [
            {key: job.get(key) for key in keys}
            for job in jobs.list_jobs(limit=500, project_id=project_id)
        ]

    def workflow_options() -> list[dict[str, Any]]:
        result = []
        for profile in service.workflows.list_profiles():
            graph = service.workflows.read_graph(profile["profile_id"])
            bindings = infer_bindings(graph)
            result.append(
                {
                    **profile,
                    "fields": scalar_inputs(graph),
                    "bindings": bindings,
                    "source_values": source_values(graph, bindings),
                    "postprocess": postprocess_nodes(graph),
                }
            )
        return result

    @router.get("/bootstrap")
    def bootstrap() -> dict[str, Any]:
        return {
            "projects": store.list_projects(),
            "workflows": workflow_options(),
            "connections": service.providers.public(),
            "wordlists": store.wordlists(),
            "vision_models": [item for item in models.list_model_options() if item.get("vision")],
        }

    @router.post("/projects", status_code=201)
    def create_project(values: dict[str, Any]) -> dict[str, Any]:
        return store.create_project(
            str(values.get("title", "未命名資料集")), str(values.get("target", "moss"))
        )

    @router.get("/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        return {
            "project": store.require_project(project_id),
            "images": store.images(project_id),
            "jobs": project_jobs(project_id),
            "exports": service.exports(project_id),
        }

    @router.put("/projects/{project_id}")
    def update_project(project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return store.save_project(project_id, values)

    @router.post("/projects/{project_id}/images", status_code=201)
    async def import_image(
        project_id: str,
        request: Request,
        filename: str = "image.png",
        kind: str = "candidate",
        role: str = "identity",
    ) -> dict[str, Any]:
        raw = await read_limited(request, 50 * 1024 * 1024)
        return store.add_image(
            project_id, raw, filename, kind=kind, role=role if kind == "reference" else ""
        )

    @router.put("/projects/{project_id}/images/{item_id}")
    def update_image(project_id: str, item_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return store.update_image(project_id, item_id, values)

    @router.get("/projects/{project_id}/jobs")
    def get_jobs(project_id: str) -> list[dict[str, Any]]:
        store.require_project(project_id)
        return project_jobs(project_id)

    @router.post("/projects/{project_id}/duplicates")
    def find_duplicates(project_id: str) -> dict[str, Any]:
        return {"groups": service.duplicate_candidates(project_id)}

    @router.post("/projects/{project_id}/images/{item_id}/repair")
    def prepare_repair(project_id: str, item_id: str) -> dict[str, Any]:
        image = store.image(project_id, item_id)
        project = store.require_project(project_id)
        reference = store.add_image(
            project_id,
            store.image_path(project_id, item_id).read_bytes(),
            image["title"] + ".png",
            kind="reference",
            role="identity",
            provenance={"parent_item_id": item_id},
        )
        if reference["review"] == "excluded":
            store.update_image(project_id, reference["item_id"], {"review": "pending"})
        recipe = project["studio"]
        recipe["repair_parent"] = item_id
        recipe["count"] = 1
        if recipe["backend"] == "novelai":
            recipe["novelai_mode"] = "img2img"
        saved = store.save_project(project_id, {"studio": recipe})
        return {"project": saved, "reference": reference}

    @router.post("/projects/{project_id}/preview")
    def preview(project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        project = store.require_project(project_id)
        count = values.get("count")
        if count is not None and count != 1:
            msg = "單次抽詞數量有誤"
            raise StudioError(msg)
        rows = service.prepare(project_id, count=count)
        identifier = f"preview-{uuid4().hex}"
        snapshot = {
            "project_id": project_id,
            "recipe": project["studio"],
            "rows": rows,
            "references": [
                item
                for item in store.images(project_id, "reference")
                if item["review"] != "excluded"
            ],
        }
        write_json(store.root / "previews" / f"{identifier}.json", snapshot)
        return {"preview_id": identifier, "rows": rows}

    @router.post("/projects/{project_id}/generate", status_code=202)
    def generate(project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        project = store.require_project(project_id)
        identifier = str(values.get("preview_id", ""))
        if not re.fullmatch(r"preview-[a-f0-9]{32}", identifier):
            msg = "請先預覽本批提示詞"
            raise StudioError(msg)
        path = store.root / "previews" / f"{identifier}.json"
        if not path.is_file():
            msg = "批次預覽不存在，請重新預覽"
            raise StudioError(msg)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if snapshot["project_id"] != project_id or snapshot["recipe"] != project["studio"]:
            msg = "生成設定已變更，請重新預覽後加入佇列"
            raise StudioError(msg)
        current_references = [
            item for item in store.images(project_id, "reference") if item["review"] != "excluded"
        ]
        current_reference_ids = [(item["item_id"], item["role"]) for item in current_references]
        snapshot_reference_ids = [
            (item["item_id"], item["role"]) for item in snapshot["references"]
        ]
        if current_reference_ids != snapshot_reference_ids:
            msg = "參考素材已變更，請重新預覽"
            raise StudioError(msg)
        recipe = snapshot["recipe"]
        graph_digest = ""
        if recipe["backend"] == "comfyui":
            graph = service.workflows.read_graph(recipe["workflow_id"])
            encoded = json.dumps(graph, ensure_ascii=False, sort_keys=True).encode()
            graph_digest = hashlib.sha256(encoded).hexdigest()
            write_json(store.root / "graphs" / f"{graph_digest}.json", graph)
        else:
            provider = service.providers.require(recipe["provider_id"], recipe["backend"])
            validate_provider_recipe(
                provider,
                recipe,
                [
                    (item["role"], store.image_path(project_id, item["item_id"]))
                    for item in current_references
                ],
            )
        payloads = [
            {
                "project_id": project_id,
                "recipe": recipe,
                "prompt": prompt,
                "references": [
                    {"item_id": item["item_id"], "role": item["role"]}
                    for item in current_references
                ],
                "graph_digest": graph_digest,
                "preview_id": identifier,
            }
            for prompt in snapshot["rows"]
        ]
        queued = store.enqueue_batch(identifier, project_id, payloads)
        runner.wake()
        return {"job_ids": queued}

    @router.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None or not job["job_type"].startswith("studio_"):
            raise HTTPException(404, detail="任務不存在")
        return jobs.request_cancel(job_id) or {}

    @router.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None or not job["job_type"].startswith("studio_"):
            raise HTTPException(404, detail="任務不存在")
        result = jobs.retry(job_id)
        runner.wake()
        return result or {}

    @router.post("/workflows", status_code=201)
    async def import_workflow(
        request: Request,
        label: str = "自訂工作流",
        filename: str = "workflow-api.json",
        target: str = "anima",
    ) -> dict[str, Any]:
        if target not in {"anima", "moss", "krea2", "h3"}:
            msg = "工作流訓練目標有誤"
            raise StudioError(msg)
        return service.workflows.import_generic(
            await read_limited(request, MAX_WORKFLOW_BYTES),
            label=label,
            filename=filename,
            model_family=target,
        )

    @router.put("/settings")
    def save_settings(values: dict[str, Any]) -> dict[str, Any]:
        return service.providers.save(values)

    @router.delete("/providers/{identifier}")
    def delete_provider(identifier: str) -> dict[str, Any]:
        return service.providers.delete(identifier)

    @router.post("/providers/models")
    def discover_provider_models(values: dict[str, Any]) -> dict[str, Any]:
        return {"models": service.providers.discover_models(values, models)}

    @router.put("/wordlists")
    def save_wordlist(values: dict[str, Any]) -> dict[str, Any]:
        return store.save_wordlist(str(values.get("name", "")), str(values.get("content", "")))

    @router.post("/projects/{project_id}/caption", status_code=202)
    def queue_caption(project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        store.require_project(project_id)
        identifiers = values.get("item_ids", [])
        if not isinstance(identifiers, list) or not 1 <= len(identifiers) <= MAX_CAPTION_BATCH_SIZE:
            msg = "請選擇 1 至 200 張圖片"
            raise StudioError(msg)
        for item_id in identifiers:
            store.image(project_id, item_id)
        return runner.submit(
            "studio_caption",
            {
                "project_id": project_id,
                "item_ids": identifiers,
                "model": str(values.get("model", "")),
                "method": values.get("method", "vision"),
            },
        )

    @router.post("/projects/{project_id}/annotations/import")
    async def import_caption_results(project_id: str, request: Request) -> dict[str, Any]:
        store.require_project(project_id)
        try:
            value = json.loads(await read_limited(request, 20 * 1024 * 1024))
        except ValueError as error:
            msg = "標注匯入 JSON 格式有誤"
            raise StudioError(msg) from error
        if not isinstance(value, dict) or not isinstance(value.get("records"), list):
            msg = "標注匯入需要 records 列表"
            raise StudioError(msg)
        return import_annotations(store, project_id, value["records"])

    @router.post("/projects/{project_id}/exports", status_code=201)
    def export_project(project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return service.export(project_id, str(values.get("format", "both")))

    @router.get("/projects/{project_id}/exports/{filename}")
    def download_export(project_id: str, filename: str) -> FileResponse:
        store.require_project(project_id)
        if not re.fullmatch(r"dataset-[a-f0-9]{32}\.zip", filename):
            raise HTTPException(404, detail="交付包不存在")
        path = store.settings.dataset_exports_root / "studio" / project_id / filename
        if not path.is_file():
            raise HTTPException(404, detail="交付包不存在")
        return FileResponse(path, filename=f"{project_id}-{filename}", media_type="application/zip")

    return router
