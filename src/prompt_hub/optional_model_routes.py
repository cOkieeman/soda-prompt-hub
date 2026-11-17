from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException

from prompt_hub.visual_model import VisualModelError

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner
    from prompt_hub.optional_models import OptionalModelInstaller


def create_optional_model_router(
    installer: OptionalModelInstaller, runner: BackgroundJobRunner
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/optional-models")
    def get_models() -> dict[str, Any]:
        return installer.status()

    @router.post("/api/optional-models/onboarding")
    def complete_onboarding(values: dict[str, Any]) -> dict[str, Any]:
        selected = values.get("selected", [])
        if not isinstance(selected, list) or any(
            not isinstance(identifier, str) or identifier not in installer.models
            for identifier in selected
        ):
            raise HTTPException(status_code=422, detail="请选择有效的模型")
        return installer.complete_onboarding(selected)

    @router.post("/api/optional-models/{model_id}/install", status_code=202)
    def install_model(model_id: str) -> dict[str, Any]:
        try:
            model = installer.model(model_id)
            installer.root(model)
        except VisualModelError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if installer.model_status(model)["state"] == "ready":
            return {"already_installed": True, "job": None}
        return {"job": runner.submit(model.job_type, {}, exclusive=True)}

    return router
