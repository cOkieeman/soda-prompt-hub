from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field

from prompt_hub.local_model import LocalModelError
from prompt_hub.storyboard import StoryboardConflictError
from prompt_hub.storyboard_ai import StoryboardPreviewError

if TYPE_CHECKING:
    from prompt_hub.storyboard import StoryboardStore
    from prompt_hub.storyboard_ai import StoryboardAIService
    from prompt_hub.storyboard_editor import StoryboardEditorManager
    from prompt_hub.storyboard_generation import StoryboardGenerationService


class StoryboardRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def guarded(request: Request) -> Response:
            try:
                return await handler(request)
            except FileNotFoundError as error:
                raise HTTPException(status_code=404, detail="分镜项目或页面不存在") from error
            except (FileExistsError, StoryboardConflictError, StoryboardPreviewError) as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except (
                ValueError,
                TypeError,
                AttributeError,
                KeyError,
                OverflowError,
                RecursionError,
            ) as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            except LocalModelError as error:
                raise HTTPException(status_code=502, detail=str(error)) from error

        return guarded


class StoryboardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectInput(StoryboardInput):
    name: str = Field(default="未命名分镜", min_length=1, max_length=160)
    settings: dict[str, Any] | None = None


class PageInput(StoryboardInput):
    page: dict[str, Any] | None = None
    id: str = Field(default="", max_length=80)
    title: str = Field(default="", max_length=160)
    name: str = Field(default="", max_length=160)


class PageUpdate(StoryboardInput):
    page: dict[str, Any]
    expected_version: str


class ImportInput(StoryboardInput):
    content: dict[str, Any] | list[dict[str, Any]] | str
    name: str | None = Field(default=None, max_length=160)
    page_id: str | None = Field(default=None, max_length=80)


class AIPreviewInput(StoryboardInput):
    story: str = Field(min_length=1, max_length=12000)
    connection_id: str = Field(min_length=1, max_length=400)
    panel_count: int = Field(default=4, ge=1, le=12)


class TranslationPreviewInput(StoryboardInput):
    connection_id: str = Field(min_length=1, max_length=400)


class ApplyInput(StoryboardInput):
    preview_id: str = Field(default="", max_length=80)
    confirmed: bool = False
    candidate_index: int = Field(default=0, ge=0, le=12)
    expected_version: str | None = None
    translations: list[dict[str, Any]] | None = None


class CharacterInput(StoryboardInput):
    oc_id: str = Field(min_length=1, max_length=300)
    appearance_zh: str = Field(default="", max_length=6000)
    appearance_en: str = Field(default="", max_length=6000)
    outfit_zh: str = Field(default="", max_length=3000)
    outfit_en: str = Field(default="", max_length=3000)
    lora: dict[str, Any] | None = None
    connection_id: str = Field(default="", max_length=400)


class GenerationInput(StoryboardInput):
    node_id: str = Field(default="compute-5060ti", max_length=160)
    backend: Literal["minimal", "moss-soda-v2"] = "minimal"
    preset: str = Field(default="draft", max_length=80)
    seed: int = Field(default=0, ge=0, le=18446744073709551615)
    negative: str = Field(default="", max_length=12000)
    model: str | None = Field(default=None, max_length=400)
    workflow_profile_id: str = Field(default="moss-soda-v2", max_length=80)
    model_overrides: dict[str, str] | None = None
    priority: int = Field(default=50, ge=0, le=100)


class RefreshInput(StoryboardInput):
    node_id: str = Field(default="compute-5060ti", max_length=160)
    task_id: str = Field(min_length=1, max_length=160)


class PickInput(StoryboardInput):
    result_id: str = Field(min_length=1, max_length=160)


def create_storyboard_router(
    store: StoryboardStore,
    ai: StoryboardAIService,
    editors: StoryboardEditorManager,
    generation: StoryboardGenerationService,
) -> APIRouter:
    router = APIRouter(prefix="/api/storyboard", tags=["storyboard"], route_class=StoryboardRoute)

    @router.get("/projects")
    def projects() -> list[dict[str, Any]]:
        return store.list_projects()

    @router.post("/projects", status_code=201)
    def create_project(payload: ProjectInput) -> dict[str, Any]:
        return store.create_project(payload.name, settings=payload.settings)

    @router.get("/projects/{project_id}")
    def project(project_id: str) -> dict[str, Any]:
        return store.get_project(project_id)

    @router.delete("/projects/{project_id}")
    def delete_project(project_id: str) -> dict[str, Any]:
        editors.stop(project_id)
        return store.delete_project(project_id)

    @router.post("/import", status_code=201)
    def import_project(payload: ImportInput) -> dict[str, Any]:
        return store.import_project(payload.content, name=payload.name)

    @router.post("/projects/{project_id}/import", status_code=201)
    def import_page(project_id: str, payload: ImportInput) -> dict[str, Any]:
        return store.import_page(project_id, payload.content, page_id=payload.page_id)

    @router.get("/projects/{project_id}/export")
    def export(project_id: str, page_id: str | None = None) -> Response:
        bundle = store.export_bundle(project_id, page_id=page_id)["bundle"]
        return Response(
            content=json.dumps(bundle, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="storyboard-bundle.json"'},
        )

    @router.get("/projects/{project_id}/pages")
    def pages(project_id: str) -> list[dict[str, Any]]:
        return store.list_pages(project_id)

    @router.post("/projects/{project_id}/pages", status_code=201)
    def create_page(project_id: str, payload: PageInput) -> dict[str, Any]:
        raw = (
            payload.page
            if payload.page is not None
            else {
                "id": payload.id or f"page-{uuid4().hex[:12]}",
                "title": payload.title or payload.name or "未命名分镜页",
            }
        )
        return store.create_page(project_id, raw)

    @router.get("/projects/{project_id}/pages/{page_id}")
    def page(project_id: str, page_id: str) -> dict[str, Any]:
        return {
            **store.get_page(project_id, page_id),
            "results": generation.list_results(project_id, page_id),
            "last_task": generation.last_task(project_id, page_id),
        }

    @router.get("/projects/{project_id}/pages/{page_id}/results")
    def results(project_id: str, page_id: str) -> list[dict[str, Any]]:
        return generation.list_results(project_id, page_id)

    @router.put("/projects/{project_id}/pages/{page_id}")
    def update_page(project_id: str, page_id: str, payload: PageUpdate) -> dict[str, Any]:
        return store.save_page(
            project_id, page_id, payload.page, expected_version=payload.expected_version
        )

    @router.delete("/projects/{project_id}/pages/{page_id}")
    def delete_page(project_id: str, page_id: str) -> dict[str, Any]:
        editors.stop(project_id)
        return store.delete_page(project_id, page_id)

    @router.get("/projects/{project_id}/pages/{page_id}/preview.png")
    def preview(project_id: str, page_id: str) -> Response:
        return Response(content=store.thumbnail(project_id, page_id), media_type="image/png")

    @router.post("/projects/{project_id}/pages/{page_id}/validate")
    def validate(project_id: str, page_id: str) -> dict[str, Any]:
        return store.validate_page(project_id, page_id)

    @router.post("/projects/{project_id}/pages/{page_id}/compile")
    def compile_page(project_id: str, page_id: str) -> dict[str, Any]:
        return store.compile_page(project_id, page_id)

    @router.get("/projects/{project_id}/pages/{page_id}/translations/todo")
    @router.post("/projects/{project_id}/pages/{page_id}/translations/todo")
    def translations(project_id: str, page_id: str) -> dict[str, Any]:
        return store.translation_todo(project_id, page_id)

    @router.post("/projects/{project_id}/pages/{page_id}/ai/preview")
    def ai_preview(project_id: str, page_id: str, payload: AIPreviewInput) -> dict[str, Any]:
        return ai.preview_page(
            project_id,
            page_id,
            story=payload.story,
            model=payload.connection_id,
            panel_count=payload.panel_count,
        )

    @router.post("/projects/{project_id}/pages/{page_id}/ai/apply")
    def ai_apply(project_id: str, page_id: str, payload: ApplyInput) -> dict[str, Any]:
        return ai.apply(
            project_id,
            page_id,
            payload.preview_id,
            kind="page",
            confirmed=payload.confirmed,
            candidate=payload.candidate_index,
        )

    @router.post("/projects/{project_id}/pages/{page_id}/translations/preview")
    def translation_preview(
        project_id: str, page_id: str, payload: TranslationPreviewInput
    ) -> dict[str, Any]:
        return ai.preview_translations(project_id, page_id, model=payload.connection_id)

    @router.post("/projects/{project_id}/pages/{page_id}/translations/apply")
    def translation_apply(project_id: str, page_id: str, payload: ApplyInput) -> dict[str, Any]:
        if payload.preview_id:
            return ai.apply(
                project_id,
                page_id,
                payload.preview_id,
                kind="translations",
                confirmed=payload.confirmed,
            )
        if not payload.confirmed or payload.translations is None or not payload.expected_version:
            message = "手工翻译也须先核对并确认，提供页面版本"
            raise StoryboardPreviewError(message)
        return store.apply_translations(
            project_id,
            page_id,
            {"translations": payload.translations},
            expected_version=payload.expected_version,
        )

    @router.post("/projects/{project_id}/characters/preview")
    def character_preview(project_id: str, payload: CharacterInput) -> dict[str, Any]:
        return ai.preview_character(project_id, payload.model_dump())

    @router.post("/projects/{project_id}/characters/apply")
    def character_apply(project_id: str, payload: ApplyInput) -> dict[str, Any]:
        return ai.apply(
            project_id, "", payload.preview_id, kind="character", confirmed=payload.confirmed
        )

    @router.post("/projects/{project_id}/pages/{page_id}/editor/start")
    def start_editor(project_id: str, page_id: str) -> dict[str, Any]:
        return editors.start(project_id, page_id)

    @router.post("/projects/{project_id}/pages/{page_id}/editor/stop")
    def stop_editor(project_id: str, page_id: str) -> dict[str, Any]:
        store.page_path(project_id, page_id)
        return editors.stop(project_id)

    @router.post("/projects/{project_id}/pages/{page_id}/generate")
    def generate(project_id: str, page_id: str, payload: GenerationInput) -> dict[str, Any]:
        return generation.submit(
            project_id,
            page_id,
            node_id=payload.node_id,
            options=payload.model_dump(exclude={"node_id"}, exclude_none=True),
        )

    @router.post("/projects/{project_id}/pages/{page_id}/results/refresh")
    def refresh(project_id: str, page_id: str, payload: RefreshInput) -> dict[str, Any]:
        return generation.import_results(
            project_id, page_id, payload.task_id, node_id=payload.node_id
        )

    @router.post("/projects/{project_id}/pages/{page_id}/results/pick")
    def pick(project_id: str, page_id: str, payload: PickInput) -> dict[str, Any]:
        return generation.select_result(project_id, page_id, payload.result_id)

    return router
