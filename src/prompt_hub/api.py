from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from prompt_hub.background_jobs import BackgroundJobRunner, BackgroundJobStore
from prompt_hub.comfy_results import ComfyResultStore
from prompt_hub.comfy_routes import create_comfy_router
from prompt_hub.compute_bridge import compute_contract
from prompt_hub.config import Settings
from prompt_hub.creative import (
    CreativeStore,
    apply_iteration_suggestions,
    apply_result_review,
    compile_prompt,
    export_project,
    iteration_context,
    next_iteration_values,
)
from prompt_hub.database import PromptDatabase
from prompt_hub.dataset_curation import DatasetCurationStore
from prompt_hub.dataset_routes import create_dataset_router
from prompt_hub.dataset_workspace import DatasetWorkspaceStore
from prompt_hub.embedding_index import EmbeddingIndexStore
from prompt_hub.embedding_routes import create_embedding_router
from prompt_hub.hybrid_search import HybridSearchService
from prompt_hub.importers import import_all
from prompt_hub.local_model import (
    LocalModelError,
    analyze_result_image,
    draft_krea2_caption,
    expand_sourcing_queries,
    list_local_models,
    organize_slots,
)
from prompt_hub.local_visual import LocalVisualEncoder, LocalVisualIndexService
from prompt_hub.lora_projects import LoraProjectStore
from prompt_hub.lora_routes import create_lora_router
from prompt_hub.media import resolve_media_path
from prompt_hub.model_connections import CONNECTION_ID_PATTERN, ModelConnectionStore
from prompt_hub.model_routes import create_model_router
from prompt_hub.oc_manager import archive_import, parse_oc_manager_json
from prompt_hub.project_journey import ProjectJourneyServices, create_project_journey_router
from prompt_hub.remote_nodes import RemoteNodeStore
from prompt_hub.remote_routes import create_remote_router
from prompt_hub.result_assets import find_result_asset
from prompt_hub.result_media import ResultImageError, resolve_result_image, store_result_image
from prompt_hub.search_routes import create_search_router
from prompt_hub.source_routes import create_source_router
from prompt_hub.source_sync import SourceSyncService
from prompt_hub.sourcing import allowed_safety_levels, source_candidates
from prompt_hub.tag_locale import TagLocaleError, localize_tags, tag_catalog
from prompt_hub.visual_assets import VisualAssetCatalog
from prompt_hub.visual_routes import create_visual_router
from prompt_hub.web import INDEX_HTML
from prompt_hub.web_capture import WebCaptureService
from prompt_hub.workflow_profiles import WorkflowProfileStore
from prompt_hub.workflow_routes import create_workflow_router
from prompt_hub.workspace_routes import create_workspace_router

MAX_OC_IMPORT_BYTES = 25 * 1024 * 1024


class MarkUpdate(BaseModel):
    source_id: str = Field(min_length=1, max_length=120)
    external_id: str = Field(min_length=1, max_length=600)
    favorite: bool = False
    rating: int | None = Field(default=None, ge=1, le=5)
    note: str = Field(default="", max_length=1200)


class CreativeProjectInput(BaseModel):
    title: str = Field(default="未命名绘图项目", max_length=160)
    brief_zh: str = Field(default="", max_length=6000)
    safety_mode: Literal["sfw", "suggestive", "adult", "explicit-adult"] = "sfw"
    target_profile: Literal["anima", "krea2"] = "anima"
    character_id: str = Field(default="", max_length=300)
    slots: dict[str, str] = Field(default_factory=dict)
    slot_locks: dict[str, bool] = Field(default_factory=dict)
    references: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    generation: dict[str, Any] = Field(default_factory=dict)
    lineage: dict[str, Any] = Field(default_factory=dict)
    test_notes: str = Field(default="", max_length=6000)


class CreativeProjectUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    brief_zh: str | None = Field(default=None, max_length=6000)
    safety_mode: Literal["sfw", "suggestive", "adult", "explicit-adult"] | None = None
    target_profile: Literal["anima", "krea2"] | None = None
    character_id: str | None = Field(default=None, max_length=300)
    slots: dict[str, str] | None = None
    slot_locks: dict[str, bool] | None = None
    references: list[dict[str, Any]] | None = Field(default=None, max_length=100)
    generation: dict[str, Any] | None = None
    lineage: dict[str, Any] | None = None
    test_notes: str | None = Field(default=None, max_length=6000)


class CreativeCompileInput(CreativeProjectInput):
    profile_id: Literal["anima", "krea2"] | None = None


class RecipeInput(BaseModel):
    project_id: str = Field(min_length=1, max_length=160)
    name: str = Field(default="", max_length=160)
    favorite: bool = False


class LocalAssistInput(BaseModel):
    brief: str = Field(min_length=1, max_length=6000)
    slots: dict[str, str] = Field(default_factory=dict)
    slot_locks: dict[str, bool] = Field(default_factory=dict)
    model: str = Field(min_length=1, max_length=300)
    target_profile: Literal["anima", "krea2"] = "anima"


class CreativeSourcingInput(BaseModel):
    brief: str = Field(min_length=1, max_length=6000)
    slots: dict[str, str] = Field(default_factory=dict)
    slot_locks: dict[str, bool] = Field(default_factory=dict)
    safety_mode: Literal["sfw", "suggestive", "adult", "explicit-adult"] = "sfw"
    query_hints: dict[str, list[str]] = Field(default_factory=dict)
    limit_per_slot: int = Field(default=6, ge=2, le=10)


class CreativeSourcingExpandInput(BaseModel):
    brief: str = Field(min_length=1, max_length=6000)
    slots: dict[str, str] = Field(default_factory=dict)
    slot_locks: dict[str, bool] = Field(default_factory=dict)
    model: str = Field(min_length=1, max_length=300)


class CreativeImageAnalysisInput(BaseModel):
    model: str = Field(min_length=1, max_length=300)


class CreativeReviewApplyInput(BaseModel):
    analysis: dict[str, Any]
    fill_empty_slots: bool = False


class CreativeReviewBranchInput(BaseModel):
    analysis: dict[str, Any]


class TagLocaleInput(BaseModel):
    tags: list[str] = Field(min_length=1, max_length=500)
    language: Literal["zh", "en"] = "zh"


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings.from_environment()
    model_connections = ModelConnectionStore(active_settings)

    def krea2_captioner(
        image_path: Path,
        model: str,
        existing_caption: str,
    ) -> dict[str, Any]:
        if not CONNECTION_ID_PATTERN.fullmatch(model):
            return DatasetCurationStore._default_krea2_captioner(  # noqa: SLF001
                image_path,
                model,
                existing_caption,
            )
        return draft_krea2_caption(
            image_path=image_path,
            model=model,
            existing_caption=existing_caption,
            connections=model_connections,
        )

    database = PromptDatabase(active_settings.database_path)
    creative_store = CreativeStore(active_settings.database_path)
    job_store = BackgroundJobStore(active_settings.database_path)
    workspace_store = DatasetWorkspaceStore(active_settings)
    curation_store = DatasetCurationStore(
        active_settings,
        workspace_store,
        krea2_captioner=krea2_captioner,
    )
    lora_store = LoraProjectStore(active_settings.lora_projects_root)
    comfy_store = ComfyResultStore(active_settings.comfy_results_root)
    embedding_store = EmbeddingIndexStore(active_settings.embedding_index_root)
    source_sync = SourceSyncService(active_settings, database)
    web_capture = WebCaptureService(active_settings, database)
    remote_store = RemoteNodeStore(active_settings.remote_nodes_root)
    workflow_store = WorkflowProfileStore(active_settings.workflow_profiles_root)
    hybrid_search = HybridSearchService(database, embedding_store, remote_store)
    visual_catalog = VisualAssetCatalog(
        active_settings,
        database,
        workspace_store,
        creative_store,
        comfy_store,
        remote_store,
        web_capture,
    )
    visual_encoder = LocalVisualEncoder(
        active_settings.models_root / "clip" / "clip-vit-base-patch32"
    )
    local_visual = LocalVisualIndexService(embedding_store, visual_catalog, visual_encoder)
    job_runner = BackgroundJobRunner(
        job_store,
        {
            "dataset_scan": workspace_store.scan_job,
            "dataset_wd14": curation_store.tag_job,
            "dataset_krea2_vlm": curation_store.krea2_vlm_job,
            "source_sync": source_sync.job,
            "local_visual_index": local_visual.job,
        },
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        active_settings.ensure_directories()
        model_connections.initialize()
        database.initialize()
        creative_store.initialize()
        job_store.initialize()
        workspace_store.initialize()
        curation_store.initialize()
        lora_store.initialize()
        comfy_store.initialize()
        embedding_store.initialize()
        remote_store.initialize()
        workflow_store.initialize()
        job_runner.start()
        try:
            yield
        finally:
            job_runner.stop()

    application = FastAPI(
        title="Soda Prompt Hub",
        version="0.1.3",
        description="Local-first prompt, style, tag, and workflow archive.",
        lifespan=lifespan,
    )
    application.include_router(create_dataset_router(active_settings, creative_store))
    application.include_router(
        create_workspace_router(
            workspace_store,
            curation_store,
            job_store,
            job_runner,
            remote_store,
        )
    )
    application.include_router(
        create_lora_router(lora_store, workspace_store, curation_store, database)
    )
    application.include_router(create_comfy_router(active_settings, comfy_store, creative_store))
    application.include_router(create_embedding_router(embedding_store, workspace_store))
    application.include_router(create_search_router(hybrid_search))
    application.include_router(create_remote_router(remote_store))
    application.include_router(create_model_router(model_connections))
    application.include_router(create_source_router(source_sync, job_runner, web_capture))
    application.include_router(create_visual_router(local_visual, embedding_store, job_runner))
    application.include_router(
        create_workflow_router(
            active_settings,
            workflow_store,
            creative_store,
            comfy_store,
            remote_store,
        )
    )
    application.include_router(
        create_project_journey_router(
            ProjectJourneyServices(
                settings=active_settings,
                creative_store=creative_store,
                workspace_store=workspace_store,
                curation_store=curation_store,
                job_store=job_store,
                job_runner=job_runner,
                remote_store=remote_store,
            )
        )
    )

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return INDEX_HTML

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "database": str(active_settings.database_path)}

    @application.get("/api/compute/contract")
    def get_compute_contract() -> dict[str, Any]:
        return compute_contract()

    @application.post("/api/tags/localize")
    def get_localized_tags(payload: TagLocaleInput) -> dict[str, Any]:
        try:
            items = localize_tags(payload.tags, language=payload.language)
        except TagLocaleError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"language": payload.language, "items": items}

    @application.get("/api/tags/catalog")
    def get_tag_catalog(
        language: Literal["zh", "en"] = "zh",
    ) -> dict[str, Any]:
        return {"language": language, "items": tag_catalog(language=language)}

    @application.get("/api/stats")
    def stats() -> dict[str, Any]:
        return database.stats()

    @application.get("/api/sources")
    def sources() -> list[dict[str, Any]]:
        return database.list_sources()

    @application.get("/api/search")
    def search(
        query: str = "",
        kind: str = "",
        source_id: str = "",
        model_family: str = "",
        safety: str = "",
        favorites_only: bool = False,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
    ) -> dict[str, Any]:
        results = database.search(
            query,
            kind=kind,
            source_id=source_id,
            model_family=model_family,
            safety=safety,
            favorites_only=favorites_only,
            limit=limit,
        )
        _attach_visual_urls(results, safety)
        return {"query": query, "count": len(results), "results": results}

    @application.put("/api/marks")
    def save_mark(update: MarkUpdate) -> dict[str, Any]:
        return _save_mark(database, update)

    @application.get("/api/creative/projects")
    def list_creative_projects(
        limit: Annotated[int, Query(ge=1, le=100)] = 30,
    ) -> list[dict[str, Any]]:
        return creative_store.list_projects(limit=limit)

    @application.post("/api/creative/projects", status_code=201)
    def create_creative_project(payload: CreativeProjectInput) -> dict[str, Any]:
        return creative_store.create_project(payload.model_dump())

    @application.get("/api/creative/projects/{project_id}")
    def get_creative_project(project_id: str) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        return project

    @application.get("/api/creative/projects/{project_id}/iteration")
    def get_creative_iteration(project_id: str) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        parent_id = str(project.get("lineage", {}).get("parent_project_id", "")).strip()
        parent = creative_store.get_project(parent_id) if parent_id else None
        return iteration_context(project, parent)

    @application.post("/api/creative/projects/{project_id}/iteration/apply")
    def apply_creative_iteration(project_id: str) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        proposal = apply_iteration_suggestions(project)
        applied_slots = proposal.pop("applied_slots")
        if applied_slots:
            project = creative_store.update_project(project_id, proposal)
        parent_id = str(project.get("lineage", {}).get("parent_project_id", "")).strip()
        parent = creative_store.get_project(parent_id) if parent_id else None
        return {
            "project": project,
            "applied_slots": applied_slots,
            "iteration": iteration_context(project, parent),
        }

    @application.put("/api/creative/projects/{project_id}")
    def update_creative_project(
        project_id: str,
        payload: CreativeProjectUpdate,
    ) -> dict[str, Any]:
        values = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if value is not None
        }
        try:
            return creative_store.update_project(project_id, values)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Creative project not found") from error

    @application.post("/api/creative/compile")
    def compile_creative_prompt(payload: CreativeCompileInput) -> dict[str, Any]:
        values = payload.model_dump(exclude={"profile_id"})
        return compile_prompt(values, payload.profile_id)

    @application.get("/api/creative/projects/{project_id}/export")
    def export_creative_project(project_id: str) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        return export_project(project)

    @application.post("/api/creative/projects/{project_id}/results", status_code=201)
    async def upload_creative_result(
        project_id: str,
        request: Request,
        filename: Annotated[str, Query(min_length=1, max_length=180)] = "result.png",
    ) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        try:
            asset = store_result_image(
                active_settings,
                project_id=project_id,
                filename=filename,
                raw=await request.body(),
                safety_mode=str(project["safety_mode"]),
            )
        except ResultImageError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        generation = dict(project.get("generation", {}))
        current_assets = generation.get("result_assets", [])
        assets = list(current_assets) if isinstance(current_assets, list) else []
        assets.append(asset)
        generation["result_assets"] = assets
        updated = creative_store.update_project(project_id, {"generation": generation})
        return {"asset": asset, "project": updated}

    @application.post("/api/creative/projects/{project_id}/results/{asset_id}/analyze")
    def analyze_creative_result(
        project_id: str,
        asset_id: str,
        payload: CreativeImageAnalysisInput,
    ) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        asset = find_result_asset(project, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Result image not found")
        path = resolve_result_image(
            active_settings,
            project_id=project_id,
            variant="original",
            stored_name=str(asset.get("original_name", "")),
        )
        if path is None:
            raise HTTPException(status_code=404, detail="Result image file not found")
        try:
            return analyze_result_image(
                image_path=path,
                project=project,
                model=payload.model,
                connections=model_connections,
            )
        except LocalModelError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @application.post("/api/creative/projects/{project_id}/results/{asset_id}/apply")
    def apply_creative_result_review(
        project_id: str,
        asset_id: str,
        payload: CreativeReviewApplyInput,
    ) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        if find_result_asset(project, asset_id) is None:
            raise HTTPException(status_code=404, detail="Result image not found")
        values = apply_result_review(
            project,
            payload.analysis,
            fill_empty_slots=payload.fill_empty_slots,
        )
        return creative_store.update_project(project_id, values)

    @application.post(
        "/api/creative/projects/{project_id}/results/{asset_id}/branch",
        status_code=201,
    )
    def branch_creative_result_review(
        project_id: str,
        asset_id: str,
        payload: CreativeReviewBranchInput,
    ) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        asset = find_result_asset(project, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Result image not found")
        values = next_iteration_values(project, asset, payload.analysis)
        return creative_store.create_project(values)

    @application.get("/api/creative/recipes")
    def list_creative_recipes(
        limit: Annotated[int, Query(ge=1, le=100)] = 30,
    ) -> list[dict[str, Any]]:
        return creative_store.list_recipes(limit=limit)

    @application.post("/api/creative/recipes", status_code=201)
    def save_creative_recipe(payload: RecipeInput) -> dict[str, Any]:
        try:
            return creative_store.save_recipe(
                payload.project_id,
                payload.name,
                favorite=payload.favorite,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Creative project not found") from error

    @application.get("/api/local-models")
    def local_models() -> dict[str, Any]:
        try:
            return {"available": True, "models": list_local_models()}
        except LocalModelError as error:
            return {"available": False, "models": [], "message": str(error)}

    @application.post("/api/creative/assist")
    def assist_creative_project(payload: LocalAssistInput) -> dict[str, Any]:
        try:
            return organize_slots(
                brief=payload.brief,
                slots=payload.slots,
                locks=payload.slot_locks,
                model=payload.model,
                target_profile=payload.target_profile,
                connections=model_connections,
            )
        except LocalModelError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @application.post("/api/creative/source")
    def source_creative_materials(payload: CreativeSourcingInput) -> dict[str, Any]:
        result = source_candidates(
            database,
            brief=payload.brief,
            safety_mode=payload.safety_mode,
            slots=payload.slots,
            locks=payload.slot_locks,
            query_hints=payload.query_hints,
            limit_per_slot=payload.limit_per_slot,
        )
        _attach_sourcing_visuals(result, payload.safety_mode)
        return result

    @application.post("/api/creative/source/expand")
    def expand_creative_sourcing(payload: CreativeSourcingExpandInput) -> dict[str, Any]:
        try:
            return expand_sourcing_queries(
                brief=payload.brief,
                slots=payload.slots,
                locks=payload.slot_locks,
                model=payload.model,
                connections=model_connections,
            )
        except LocalModelError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @application.post("/api/oc-manager/import")
    async def import_oc_manager_json(
        request: Request,
        filename: Annotated[str, Query(min_length=1, max_length=180)] = "oc-manager-export.json",
    ) -> dict[str, Any]:
        raw = await request.body()
        return _import_oc_manager(active_settings, database, filename, raw)

    @application.get("/api/oc-manager/characters")
    def search_oc_characters(
        query: str = "",
        world: str = "",
        limit: Annotated[int, Query(ge=1, le=50)] = 30,
    ) -> dict[str, Any]:
        results = database.search_oc_characters(query, world=world, limit=limit)
        return {"query": query, "count": len(results), "results": results}

    @application.get("/api/oc-manager/characters/{character_id}")
    def get_oc_character(character_id: str) -> dict[str, Any]:
        result = database.get_oc_character(character_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Character not found")
        return result

    @application.get("/api/oc-manager/worlds")
    def list_oc_worlds() -> list[dict[str, Any]]:
        return database.list_oc_worlds()

    @application.get("/api/oc-manager/lore")
    def search_oc_lore(
        query: str = "",
        world: str = "",
        limit: Annotated[int, Query(ge=1, le=20)] = 10,
    ) -> dict[str, Any]:
        results = database.search_oc_lore(query, world=world, limit=limit)
        return {"query": query, "count": len(results), "results": results}

    @application.get(
        "/media/{source_id}/{variant}/{relative_path:path}",
        response_class=FileResponse,
        include_in_schema=False,
    )
    def media(source_id: str, variant: str, relative_path: str) -> FileResponse:
        return _media_response(active_settings, source_id, variant, relative_path)

    @application.get(
        "/result-media/{project_id}/{variant}/{asset_id}",
        response_class=FileResponse,
        include_in_schema=False,
    )
    def result_media(project_id: str, variant: str, asset_id: str) -> FileResponse:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Result image not found")
        asset = find_result_asset(project, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Result image not found")
        stored_key = "original_name" if variant == "original" else "thumbnail_name"
        path = resolve_result_image(
            active_settings,
            project_id=project_id,
            variant=variant,
            stored_name=str(asset.get(stored_key, "")),
        )
        if path is None:
            raise HTTPException(status_code=404, detail="Result image not found")
        return FileResponse(path)

    @application.post("/api/import")
    def rebuild_index() -> dict[str, Any]:
        results = import_all(active_settings, database)
        return {"status": "imported", "sources": results, "stats": database.stats()}

    return application


def _visual_urls(result: dict[str, Any], safety_filter: str = "") -> list[dict[str, str]]:
    metadata = result.get("metadata", {})
    refs = metadata.get("image_refs", [])
    if not isinstance(refs, list):
        return []
    source_id = str(result.get("source_id", ""))
    visuals = []
    for ref in refs[:3]:
        if not isinstance(ref, dict):
            continue
        path = ref.get("path")
        safety = str(ref.get("safety", result.get("safety", "sfw")))
        if not isinstance(path, str) or (safety_filter and safety != safety_filter):
            continue
        visuals.append(
            {
                "thumbnail_url": f"/media/{source_id}/thumbnail/{quote(path, safe='/')}",
                "original_url": f"/media/{source_id}/original/{quote(path, safe='/')}",
                "safety": safety,
            }
        )
    return visuals


def _save_mark(database: PromptDatabase, update: MarkUpdate) -> dict[str, Any]:
    try:
        return database.save_mark(
            source_id=update.source_id,
            external_id=update.external_id,
            favorite=update.favorite,
            rating=update.rating,
            note=update.note,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Entry not found") from error


def _import_oc_manager(
    settings: Settings,
    database: PromptDatabase,
    filename: str,
    raw: bytes,
) -> dict[str, Any]:
    if len(raw) > MAX_OC_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="OC Manager JSON exceeds 25 MiB")
    try:
        bundle = parse_oc_manager_json(raw)
        archived_path, digest = archive_import(settings.library_root, filename, raw)
        result = database.import_oc_manager(
            bundle,
            source_file=str(archived_path),
            import_hash=digest,
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"status": "imported", **result}


def _media_response(
    settings: Settings,
    source_id: str,
    variant: str,
    relative_path: str,
) -> FileResponse:
    path = resolve_media_path(settings, source_id, variant, relative_path)
    if path is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return FileResponse(path)


def _attach_visual_urls(results: list[dict[str, Any]], safety_filter: str = "") -> None:
    for result in results:
        result["visuals"] = _visual_urls(result, safety_filter)


def _attach_sourcing_visuals(result: dict[str, Any], safety_mode: str) -> None:
    allowed = allowed_safety_levels(safety_mode)
    groups = result.get("slots", {})
    if not isinstance(groups, dict):
        return
    for group in groups.values():
        if not isinstance(group, dict):
            continue
        candidates = group.get("candidates", [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if isinstance(candidate, dict):
                candidate["visuals"] = [
                    visual for visual in _visual_urls(candidate) if visual["safety"] in allowed
                ]


app = create_app()
