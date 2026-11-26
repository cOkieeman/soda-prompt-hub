from __future__ import annotations

import base64
import hashlib
import json
import re
import tempfile
import time
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.request import Request

from PIL import Image

from prompt_hub.dataset_workspace import _near_duplicate_groups, _phash
from prompt_hub.studio_export import native_moss_export
from prompt_hub.studio_prompts import prepare_batch
from prompt_hub.studio_providers import (
    ImageProviderStore,
    multipart,
    novelai_images,
    openai_images,
    read_response,
    reference_options,
)
from prompt_hub.studio_store import StudioError, StudioStore, now, wildcard_v2_active, write_json
from prompt_hub.studio_workflows import compile_graph, infer_bindings, set_input, source_values
from prompt_hub.windows_worker_core import ComfyUIClient, WorkerError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from prompt_hub.background_jobs import JobContext
    from prompt_hub.workflow_profiles import WorkflowProfileStore


def request_evidence(value: Any) -> Any:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
    if isinstance(value, dict):
        return {
            key: "[redacted]"
            if re.search(
                r"(?:api[_-]?key|authorization|access[_-]?token|password|secret)",
                key,
                re.IGNORECASE,
            )
            else request_evidence(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [request_evidence(item) for item in value]
    return value


def _comfy_failure(status: dict[str, Any]) -> str:
    for event in reversed(status.get("messages") or []):
        match event:
            case ["execution_error" | "execution_interrupted" as name, dict() as detail]:
                pass
            case _:
                continue
        node = " ".join(
            str(detail[key])[:120] for key in ("node_id", "node_type") if detail.get(key)
        )
        reason = " · ".join(
            str(detail[key]).strip()[:1200]
            for key in ("exception_type", "exception_message")
            if detail.get(key)
        )
        return " · ".join(filter(None, ("ComfyUI 執行失敗", node, reason or name)))
    return "ComfyUI 執行失敗，歷史記錄未提供節點詳情"


class StudioService:
    def __init__(
        self,
        store: StudioStore,
        providers: ImageProviderStore,
        workflows: WorkflowProfileStore,
    ) -> None:
        self.store = store
        self.providers = providers
        self.workflows = workflows

    def prepare(
        self,
        project_id: str,
        count: int | None = None,
        *,
        recipe: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if recipe is None:
            recipe = self.store.require_project(project_id)["studio"]
        if count is not None:
            recipe = {**recipe, "count": count}
        config = self.providers.public()
        if (
            wildcard_v2_active(recipe)
            and recipe["wildcard_v2"]["style_mode"] == "preset"
            and recipe["workflow_id"]
        ):
            graph = self.workflows.read_graph(recipe["workflow_id"])
            bindings = recipe["bindings"] or infer_bindings(graph)
            for name in ("style", "prefix"):
                keys = bindings.get(name)
                if keys:
                    explicit = source_values(
                        graph, {name: [keys] if isinstance(keys, str) else keys}
                    )
                    if explicit.get(name):
                        config["wildcard_v2_workflow_style"] = str(explicit[name])
                        break
        return prepare_batch(self.store, recipe, config)

    def exports(self, project_id: str) -> list[dict[str, Any]]:
        root = self.store.settings.dataset_exports_root / "studio" / project_id
        result = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(root.glob("dataset-*.json"), reverse=True)
        ]
        return sorted(result, key=lambda item: item.get("created_at", ""), reverse=True)

    def duplicate_candidates(self, project_id: str) -> list[dict[str, Any]]:
        records = []
        for image in self.store.images(project_id, "candidate"):
            if image["review"] == "excluded":
                continue
            cache = self.store.root / "hashes" / (image["sha256"] + ".json")
            if cache.is_file():
                value = json.loads(cache.read_text(encoding="utf-8"))
            else:
                with Image.open(self.store.image_path(project_id, image["item_id"])) as opened:
                    value = _phash(opened)
                write_json(cache, value)
            records.append(
                {"relative_path": image["item_id"], "sha256": image["sha256"], "phash": value}
            )
        return _near_duplicate_groups(records)

    def generation_job(self, payload: Mapping[str, Any], context: JobContext) -> dict[str, Any]:  # noqa: C901, PLR0912 - protocol validation and dispatch stay together
        payload = dict(payload)
        project_id = payload["project_id"]
        recipe = deepcopy(payload["recipe"])
        prompt = payload["prompt"]
        execution = self.store.execution(context.job_id)
        if execution and execution["state"] == "completed":
            return {"item_ids": execution["request"].get("item_ids", [])}
        references = [
            (item["role"], self.store.image_path(project_id, item["item_id"]))
            for item in payload.get("references", [])
        ]
        recipe["_reference_options"] = reference_options(recipe, payload.get("references", []))
        context.update(0, 1, "正在準備生成任務")
        if recipe["backend"] == "comfyui":
            images = self._comfy_images(payload, recipe, prompt, references, context, execution)
        else:
            response_path = self.store.root / "responses" / f"{context.job_id}.json"
            if response_path.is_file():
                images = [
                    base64.b64decode(value) for value in json.loads(response_path.read_text())
                ]
                request_path = response_path.with_suffix(".request.json")
                if request_path.is_file():
                    recipe["_effective_request"] = json.loads(
                        request_path.read_text(encoding="utf-8")
                    )
            else:
                if execution and execution["state"] == "submitting":
                    msg = "上次請求的服務端狀態待核對，請先檢查供應商記錄，避免重複生成"
                    raise StudioError(msg)
                provider = self.providers.require(recipe["provider_id"], recipe["backend"])
                self.store.save_execution(context.job_id, project_id, payload, state="submitting")
                try:
                    if recipe["backend"] == "novelai":
                        context.update(0, 1, "正在等候 NovelAI 回傳圖片")
                        images = novelai_images(provider, recipe, prompt, references)
                    else:
                        context.update(0, 1, "正在等候圖片 API 回傳圖片")
                        images = openai_images(provider, recipe, prompt, references)
                except StudioError as error:
                    cause = error.__cause__
                    if getattr(cause, "code", 0) in {400, 401, 403, 404, 422, 429}:
                        self.store.save_execution(
                            context.job_id, project_id, payload, state="rejected"
                        )
                    raise
                write_json(response_path, [base64.b64encode(raw).decode() for raw in images])
                write_json(
                    response_path.with_suffix(".request.json"),
                    request_evidence(recipe.get("_effective_request", {})),
                )
        if not images:
            msg = "服務沒有返回圖片，請檢查工作流的保存節點"
            raise StudioError(msg)
        item_ids = []
        for index, raw in enumerate(images):
            image = self.store.add_image(
                project_id,
                raw,
                f"generated-{context.job_id}-{index}.png",
                provenance={
                    "job_id": context.job_id,
                    "created_at": now(),
                    "recipe": request_evidence(
                        {key: value for key, value in recipe.items() if not key.startswith("_")}
                    ),
                    "prompt": prompt,
                    "backend": recipe["backend"],
                    "references": [
                        {
                            **reference,
                            "asset_id": self.store.image(project_id, reference["item_id"])[
                                "asset_id"
                            ],
                        }
                        for reference in payload.get("references", [])
                    ],
                    "parent_item_id": recipe.get("repair_parent", ""),
                    "request": request_evidence(recipe.get("_effective_request", {})),
                },
            )
            if image["title"].startswith("generated-"):
                self.store.gallery.update_asset(
                    image["asset_id"],
                    {
                        "title": str(prompt.get("body") or prompt.get("positive") or "生成圖片")[
                            :120
                        ]
                    },
                )
            item_ids.append(image["item_id"])
        self.store.save_execution(
            context.job_id, project_id, {**payload, "item_ids": item_ids}, state="completed"
        )
        context.update(1, 1, "圖片已加入專案")
        return {"item_ids": item_ids}

    def _comfy_images(  # noqa: C901, PLR0913, PLR0917 - protocol validation and dispatch stay together
        self,
        payload: dict[str, Any],
        recipe: dict[str, Any],
        prompt: dict[str, Any],
        references: list[tuple[str, Path]],
        context: JobContext,
        execution: dict[str, Any] | None,
    ) -> list[bytes]:
        client = ComfyUIClient(recipe["comfy_url"], timeout=30)
        if execution and execution["state"] == "submitting":
            msg = "上次 ComfyUI 提交狀態待核對，請先查看 ComfyUI 佇列"
            raise StudioError(msg)
        prompt_id = (
            execution["provider_task_id"] if execution and execution["state"] != "failed" else ""
        )
        if execution and execution["request"].get("effective_request"):
            recipe["_effective_request"] = execution["request"]["effective_request"]
        if not prompt_id:
            digest = payload["graph_digest"]
            if not re.fullmatch(r"[a-f0-9]{64}", digest):
                msg = "工作流快照識別有誤"
                raise StudioError(msg)
            snapshot_path = self.store.root / "graphs" / f"{digest}.json"
            original = json.loads(snapshot_path.read_text(encoding="utf-8"))
            graph = compile_graph(original, recipe, prompt)
            for reference, (_, path) in zip(
                payload.get("references", []), references, strict=False
            ):
                binding = recipe["reference_bindings"].get(reference["item_id"])
                if not binding:
                    msg = "請為每張啟用的參考圖選擇工作流輸入欄位"
                    raise StudioError(msg)
                body, content_type = multipart(
                    {"type": "input", "overwrite": "false"}, [("image", path)]
                )
                raw = read_response(
                    Request(  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
                        recipe["comfy_url"].rstrip("/") + "/upload/image",
                        data=body,
                        headers={"Content-Type": content_type},
                        method="POST",
                    ),
                    timeout=30,
                )
                result = json.loads(raw)
                name = "/".join(
                    part for part in (result.get("subfolder", ""), result["name"]) if part
                )
                set_input(graph, binding, name)
            recipe["_effective_request"] = {"graph": graph, "graph_digest": payload["graph_digest"]}
            payload = {
                **payload,
                "effective_request": request_evidence(recipe["_effective_request"]),
            }
            self.store.save_execution(
                context.job_id, payload["project_id"], payload, state="submitting"
            )
            try:
                prompt_id = client.queue_prompt(graph, client_id="soda-prompt-hub-studio")
            except WorkerError as error:
                if getattr(error.__cause__, "code", 0) in {
                    400,
                    401,
                    403,
                    404,
                    422,
                    429,
                } or "校验失败" in str(error):
                    self.store.save_execution(
                        context.job_id, payload["project_id"], payload, state="rejected"
                    )
                raise
            self.store.save_execution(
                context.job_id, payload["project_id"], payload, prompt_id, "accepted"
            )
        deadline = time.monotonic() + 7200
        while time.monotonic() < deadline:
            context.update(0, 1, "ComfyUI 正在排隊或生成，關閉頁面後可繼續查看")
            record = client.history(prompt_id)
            if record:
                status = record.get("status", {})
                if status.get("status_str") == "error":
                    msg = _comfy_failure(status)
                    self.store.save_execution(
                        context.job_id,
                        payload["project_id"],
                        {**payload, "provider_error": msg},
                        prompt_id,
                        "failed",
                    )
                    raise StudioError(msg)
                results = [
                    image
                    for output in record.get("outputs", {}).values()
                    for image in output.get("images", [])
                    if image.get("type", "output") == "output"
                ]
                if status.get("completed", bool(results)):
                    return [client.download_output(image) for image in results]
            time.sleep(1)
        msg = "ComfyUI 任務超過等候時間，服務端任務識別已保存"
        raise StudioError(msg)

    def export(self, project_id: str, output_format: str) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915 - protocol validation and dispatch stay together
        project = self.store.require_project(project_id)
        images = [
            image
            for image in self.store.images(project_id, "candidate")
            if image["review"] == "approved"
        ]
        if not images:
            msg = "請先在挑圖頁採用需要匯出的圖片"
            raise StudioError(msg)
        if output_format not in {"txt", "json", "both", "gbc"}:
            msg = "匯出格式有誤"
            raise StudioError(msg)
        if output_format == "gbc" and project["target_profile"] != "moss":
            msg = "原生 GBC 交付包適用於 MOSS 專案"
            raise StudioError(msg)
        missing = [
            image["title"]
            for image in images
            if not image["caption_confirmed"] or not str(image["caption"].get("long", "")).strip()
        ]
        if missing:
            msg = f"有 {len(missing)} 張圖片需要完成標注並確認"
            raise StudioError(msg)
        from uuid import uuid4  # noqa: PLC0415 - optional dependency

        version = f"dataset-{uuid4().hex}"
        root = self.store.settings.dataset_exports_root / "studio" / project_id
        root.mkdir(parents=True, exist_ok=True)
        temporary = root / f".{version}.tmp"
        archive_path = root / f"{version}.zip"
        manifest: dict[str, Any] = {
            "format": "soda-studio-dataset-v1",
            "project_id": project_id,
            "target": project["target_profile"],
            "title": project["title"],
            "version": version,
            "created_at": now(),
            "project_revision": project["revision"],
            "items": [],
        }
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                for index, image in enumerate(images, 1):
                    path = self.store.image_path(project_id, image["item_id"])
                    filename = f"{index:05d}-{image['asset_id'][-8:]}"
                    image_name = filename + path.suffix.lower()
                    raw = path.read_bytes()
                    archive.writestr(f"images/{image_name}", raw)
                    caption = dict(image["caption"])
                    caption["trigger"] = project["studio"].get("trigger", "")
                    text = caption["long"].strip()
                    if project["target_profile"] == "anima" and caption.get("tags"):
                        text = ", ".join(caption["tags"])
                    trigger = caption["trigger"].strip()
                    if trigger and not text.startswith(trigger):
                        text = f"{trigger}\n\n{text}"
                    if output_format in {"txt", "both", "gbc"}:
                        archive.writestr(f"images/{filename}.txt", text)
                    if output_format in {"json", "both", "gbc"}:
                        archive.writestr(
                            f"images/{filename}.json",
                            json.dumps(caption, ensure_ascii=False, indent=2),
                        )
                    manifest["items"].append(
                        {
                            "file": image_name,
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "item_id": image["item_id"],
                            "caption": caption,
                            "provenance": image["provenance"],
                        }
                    )
                archive.writestr(
                    "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
                )
                if output_format == "gbc":
                    with tempfile.TemporaryDirectory(prefix="studio-moss-", dir=root) as directory:
                        native_root = Path(directory)
                        native_moss_export(self.store, project, images, native_root)
                        for path in sorted(native_root.rglob("*")):
                            if path.is_file():
                                archive.write(path, path.relative_to(native_root).as_posix())
            temporary.replace(archive_path)
        finally:
            temporary.unlink(missing_ok=True)
        result = {
            "version": version,
            "image_count": len(images),
            "download_url": f"/api/studio/projects/{project_id}/exports/{version}.zip",
            "created_at": manifest["created_at"],
        }
        write_json(root / f"{version}.json", result)
        return result
