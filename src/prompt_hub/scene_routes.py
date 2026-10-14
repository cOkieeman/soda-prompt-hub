from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from prompt_hub.creative import CreativeProjectConflictError, scene_input_fingerprint
from prompt_hub.local_model import LocalModelError
from prompt_hub.remote_nodes import RemoteNodeError
from prompt_hub.result_assets import find_result_asset, result_asset_path
from prompt_hub.scene_planning import (
    ScenePlanError,
    apply_scene_plan,
    apply_style_advice,
    build_style_evidence,
    generate_scene_plans,
    generate_scene_review,
    generate_style_advice,
)
from prompt_hub.workflow_profiles import WorkflowProfileError

if TYPE_CHECKING:
    from prompt_hub.config import Settings
    from prompt_hub.creative import CreativeStore
    from prompt_hub.gallery import GalleryStore
    from prompt_hub.model_connections import ModelConnectionStore
    from prompt_hub.remote_nodes import RemoteNodeStore
    from prompt_hub.scene_planning import ScenePlanStore
    from prompt_hub.workflow_profiles import WorkflowProfileStore

MAX_REFERENCE_ASSETS = 12


class SceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=400)
    instruction: str = Field(default="", max_length=6000)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=12)
    canvas_locked: bool = False
    width: int = Field(default=1024, ge=256, le=4096, strict=True)
    height: int = Field(default=1024, ge=256, le=4096, strict=True)


class SceneApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int | None = Field(default=None, ge=1)
    apply_resolution: bool = True
    replace_slots: bool = False
    branch: bool = False


class StyleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=400)
    goal_zh: str = Field(default="", max_length=6000)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=12)
    candidate_lora_ids: list[str] = Field(default_factory=list, max_length=80)
    workflow_profile_id: str = Field(default="", max_length=160)


class StyleApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int | None = Field(default=None, ge=1)
    suggestion_id: str = Field(min_length=1, max_length=160)
    workflow_profile_id: str = Field(min_length=1, max_length=160)


class SceneReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=400)


def create_scene_router(
    settings: Settings,
    store: ScenePlanStore,
    creative_store: CreativeStore,
    remote_store: RemoteNodeStore,
    workflow_store: WorkflowProfileStore,
    gallery_store: GalleryStore,
    model_connections: ModelConnectionStore,
) -> APIRouter:
    router = APIRouter()

    def project_or_404(project_id: str, expected_revision: int | None = None) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        if expected_revision is not None and project["revision"] != expected_revision:
            raise HTTPException(status_code=409, detail="项目已改变; 请重新读取后再采用建议")
        return project

    def reference_context(
        project: Mapping[str, Any],
        asset_ids: list[str],
    ) -> list[dict[str, Any]]:
        references = []
        for asset_id in dict.fromkeys(asset_ids):
            asset = gallery_store.get_asset(asset_id)
            if asset is None:
                raise HTTPException(status_code=404, detail="Gallery reference not found")
            if asset.get("availability") != "online":
                raise HTTPException(status_code=409, detail="参考图离线或已改变，请重新扫描后重试")
            analysis = asset.get("analysis", {})
            confirmed = (
                analysis
                if isinstance(analysis, Mapping)
                and analysis.get("confirmed") is True
                and not analysis.get("stale")
                and not asset.get("analysis_stale")
                else {}
            )
            purposes = {
                item.get("purpose", "all")
                for item in project.get("references", [])
                if isinstance(item, Mapping) and item.get("gallery_asset_id") == asset_id
            } or {"all"}
            references.extend(
                [
                    {
                        **{
                            key: asset.get(key, "") for key in ("asset_id", "title", "note", "tags")
                        },
                        "source_sha256": asset.get("sha256", ""),
                        "purpose": purpose,
                        "analysis": _purpose_analysis(confirmed, purpose),
                    }
                    for purpose in sorted(str(value) for value in purposes)
                ]
            )
        return references

    def check_current(project: Mapping[str, Any]) -> None:
        current = project_or_404(str(project["project_id"]))
        if scene_input_fingerprint(current) != scene_input_fingerprint(project):
            raise HTTPException(status_code=409, detail="请求期间项目已改变，请重新生成建议")

    def check_references(project: Mapping[str, Any], snapshot: Mapping[str, Any]) -> None:
        asset_ids = snapshot.get("asset_ids", [])
        if not isinstance(asset_ids, list) or len(asset_ids) > MAX_REFERENCE_ASSETS:
            raise HTTPException(status_code=409, detail="参考快照无效，请重新生成建议")
        current = _reference_snapshot(reference_context(project, asset_ids))
        if current != snapshot:
            raise HTTPException(
                status_code=409, detail="相关参考图或已确认分析已改变，请重新生成建议"
            )

    @router.get("/api/creative/projects/{project_id}/scene-plans")
    def list_plans(project_id: str) -> dict[str, Any]:
        project = project_or_404(project_id)
        selected = project.get("generation", {}).get("scene_plan", {})
        selected = selected if isinstance(selected, Mapping) else {}
        plans = store.list_plans(project_id)
        plans = [
            dict(selected) if plan["plan_id"] == selected.get("plan_id") else plan for plan in plans
        ]
        if selected.get("plan_id") and not any(
            plan["plan_id"] == selected["plan_id"] for plan in plans
        ):
            plans.insert(0, dict(selected))
        fingerprint = scene_input_fingerprint(project)
        return {
            "plans": [
                {
                    **plan,
                    "stale": (
                        plan.get("input_fingerprint", plan.get("source_fingerprint")) != fingerprint
                    ),
                }
                for plan in plans
            ],
            "selected_plan_id": selected.get("plan_id", ""),
        }

    @router.post("/api/creative/projects/{project_id}/scene-plans")
    def suggest_scenes(project_id: str, payload: SceneRequest) -> dict[str, Any]:
        project = project_or_404(project_id)
        references = reference_context(project, payload.reference_asset_ids)
        snapshot = _reference_snapshot(references)
        try:
            response = generate_scene_plans(
                project,
                model=payload.model,
                instruction=payload.instruction,
                references=references,
                canvas_locked=payload.canvas_locked,
                width=payload.width,
                height=payload.height,
                connections=model_connections,
            )
            check_current(project)
            check_references(project, snapshot)
            for plan in response["plans"]:
                plan["reference_snapshot"] = snapshot
            store.save_plans(project, response["plans"])
        except LocalModelError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ScenePlanError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if any(not reference.get("analysis") for reference in references):
            response["warnings"].append("部分参考图尚未确认 AI 分析，本次仅使用标题、备注和标签。")
        return response

    @router.post("/api/creative/projects/{project_id}/scene-plans/{plan_id}/apply")
    def apply_scene(project_id: str, plan_id: str, payload: SceneApplyRequest) -> dict[str, Any]:
        project = project_or_404(project_id, payload.expected_revision)
        try:
            plan = store.get_plan(project_id, plan_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Scene plan not found") from error
        try:
            if isinstance(plan.get("reference_snapshot"), Mapping):
                check_references(project, plan["reference_snapshot"])
            values, warnings = apply_scene_plan(
                project,
                plan,
                apply_resolution=payload.apply_resolution,
                replace_slots=payload.replace_slots,
                branch=payload.branch,
            )
            updated = (
                creative_store.create_project(values)
                if payload.branch
                else creative_store.update_project(
                    project_id,
                    {"slots": values["slots"], "generation": values["generation"]},
                    preserve_results=True,
                    expected_revision=int(project["revision"]),
                )
            )
        except (ScenePlanError, CreativeProjectConflictError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"project": updated, "plan": plan, "warnings": warnings}

    @router.post("/api/creative/projects/{project_id}/style-advice")
    def suggest_style(project_id: str, payload: StyleRequest) -> dict[str, Any]:
        project = project_or_404(project_id)
        references = reference_context(project, payload.reference_asset_ids)
        snapshot = _reference_snapshot(references)
        try:
            workflow = (
                workflow_store.get_profile(payload.workflow_profile_id)
                if payload.workflow_profile_id
                else None
            )
            if workflow and workflow["model_family"] != project["target_profile"]:
                raise ScenePlanError("工作流模型族与项目目标不一致")
            candidates = (
                [
                    remote_store.get_lora(lora_id)
                    for lora_id in dict.fromkeys(payload.candidate_lora_ids)
                ]
                if payload.candidate_lora_ids
                else remote_store.search_loras(limit=80)
            )
            works = gallery_store.list_assets(kind="work", limit=30)["items"]
            notes = {}
            for asset in works:
                linked_id = str(asset.get("project_id", ""))
                linked = creative_store.get_project(linked_id) if linked_id else None
                if linked:
                    notes[linked_id] = str(linked.get("test_notes", ""))
            outcomes = build_style_evidence(works, candidates, project_notes=notes)
            response = generate_style_advice(
                project,
                model=payload.model,
                goal_zh=payload.goal_zh,
                candidates=candidates,
                workflow=workflow,
                references=references,
                recorded_outcomes=outcomes,
                connections=model_connections,
            )
            check_current(project)
            check_references(project, snapshot)
            response["reference_snapshot"] = snapshot
            store.save_advice(project_id, response)
        except LocalModelError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except (ScenePlanError, RemoteNodeError, WorkflowProfileError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return response

    @router.post("/api/creative/projects/{project_id}/style-advice/{advice_id}/apply")
    def apply_style(project_id: str, advice_id: str, payload: StyleApplyRequest) -> dict[str, Any]:
        project = project_or_404(project_id, payload.expected_revision)
        try:
            advice = store.get_advice(project_id, advice_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Style advice not found") from error
        try:
            if isinstance(advice.get("reference_snapshot"), Mapping):
                check_references(project, advice["reference_snapshot"])
            values, warnings = apply_style_advice(
                project,
                advice,
                suggestion_id=payload.suggestion_id,
                profile_id=payload.workflow_profile_id,
                remote_store=remote_store,
                workflow_store=workflow_store,
            )
            if isinstance(advice.get("reference_snapshot"), Mapping):
                check_references(project, advice["reference_snapshot"])
            updated = creative_store.update_project(
                project_id,
                values,
                preserve_results=True,
                expected_revision=int(project["revision"]),
            )
        except (
            ScenePlanError,
            CreativeProjectConflictError,
            RemoteNodeError,
            WorkflowProfileError,
        ) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"project": updated, "warnings": warnings}

    @router.post("/api/creative/projects/{project_id}/scene-review/{asset_id}")
    def review_scene(project_id: str, asset_id: str, payload: SceneReviewRequest) -> dict[str, Any]:
        project = project_or_404(project_id)
        asset = find_result_asset(project, asset_id)
        path = (
            result_asset_path(settings, project_id, asset)
            if asset
            else gallery_store.resolve_asset_path(asset_id, "original")
        )
        if path is None:
            raise HTTPException(status_code=404, detail="Result image not found or offline")
        try:
            return generate_scene_review(
                project,
                image_path=path,
                model=payload.model,
                connections=model_connections,
            )
        except LocalModelError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ScenePlanError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return router


def _purpose_analysis(analysis: object, purpose: str) -> dict[str, Any]:
    if not isinstance(analysis, Mapping) or not analysis:
        return {}
    observed = analysis.get("observed_slots", {})
    observed = observed if isinstance(observed, Mapping) else {}
    allowed = ("character", "outfit", "action", "composition", "scene", "lighting", "style")
    if purpose != "all":
        if purpose not in allowed or not isinstance(observed.get(purpose), str):
            return {}
        return {"observed_slots": {purpose: observed[purpose][:4000]}, "confirmed": True}
    return {
        "summary_zh": str(analysis.get("summary_zh", ""))[:2400],
        "observed_slots": {slot: str(observed.get(slot, ""))[:4000] for slot in allowed},
        "confirmed": True,
    }


def _reference_snapshot(references: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        references, key=lambda reference: (reference["asset_id"], reference["purpose"])
    )
    serialized = json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "asset_ids": sorted({str(reference["asset_id"]) for reference in references}),
        "fingerprint": hashlib.sha256(serialized.encode()).hexdigest(),
    }
