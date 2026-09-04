from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from prompt_hub.local_model import LocalModelError, list_local_models
from prompt_hub.model_connections import ModelConnectionError, ModelConnectionStore


class ModelConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connection_id: str = Field(default="", max_length=80)
    label: str = Field(default="", max_length=160)
    provider: Literal["openai_compatible"] = "openai_compatible"
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: str = Field(default="", max_length=12000)
    model_name: str = Field(min_length=1, max_length=300)
    supports_vision: bool = False


class ModelDiscoveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(min_length=1, max_length=2048)
    api_key: str = Field(default="", max_length=12000)


def create_model_router(store: ModelConnectionStore) -> APIRouter:  # noqa: C901
    router = APIRouter()

    @router.get("/api/models")
    def list_models() -> dict[str, object]:
        local_available = True
        local_message = ""
        try:
            local_models = [
                {**model, "provider": "lm_studio", "source": "local"}
                for model in list_local_models()
            ]
        except LocalModelError as error:
            local_available = False
            local_message = str(error)
            local_models = []
        try:
            external_models = store.list_model_options()
        except ModelConnectionError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        models = [*local_models, *external_models]
        return {
            "available": bool(models),
            "models": models,
            "local_available": local_available,
            "local_message": local_message,
            "local_count": len(local_models),
            "external_count": len(external_models),
        }

    @router.get("/api/model-connections")
    def list_model_connections() -> list[dict[str, object]]:
        try:
            return store.list_public()
        except ModelConnectionError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/api/model-connections/discover")
    def discover_models(payload: ModelDiscoveryInput) -> dict[str, object]:
        try:
            models = store.discover(payload.base_url, payload.api_key)
        except ModelConnectionError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"models": [{"id": model, "name": model} for model in models]}

    @router.post("/api/model-connections", status_code=status.HTTP_201_CREATED)
    def save_model_connection(payload: ModelConnectionInput) -> dict[str, object]:
        try:
            return store.save(payload.model_dump())
        except ModelConnectionError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.delete("/api/model-connections/{connection_id}")
    def delete_model_connection(connection_id: str) -> dict[str, object]:
        try:
            return store.delete(connection_id)
        except ModelConnectionError as error:
            code = 404 if "不存在" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    return router
