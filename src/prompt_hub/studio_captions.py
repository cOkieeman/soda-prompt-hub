from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from prompt_hub.local_model import (
    _external_vision_completion,
    _extract_json_object,
    _image_data_url,
    draft_krea2_caption,
)
from prompt_hub.studio_annotations import PIXAI_TAG_THRESHOLD, normalize_annotation
from prompt_hub.studio_providers import ImageProviderStore
from prompt_hub.studio_store import StudioError, StudioStore
from prompt_hub.wd14 import tag_image

GBC_TAG_SEEDED_SUFFIX = ".gbc-tag-seeded.json"

if TYPE_CHECKING:
    from collections.abc import Mapping

    from prompt_hub.background_jobs import JobContext
    from prompt_hub.model_connections import ModelConnectionStore


class StudioCaptioner:
    def __init__(self, store: StudioStore, models: ModelConnectionStore) -> None:
        self.store = store
        self.models = models

    def job(self, payload: Mapping[str, Any], context: JobContext) -> dict[str, Any]:
        payload = dict(payload)
        project_id = payload["project_id"]
        project = self.store.require_project(project_id)
        identifiers = payload["item_ids"]
        if payload["method"] in {"pixai", "gbc", "pixai_gbc"}:
            return self.worker_job(payload, context)
        completed = []
        for index, item_id in enumerate(identifiers):
            context.update(index, len(identifiers), f"正在標注第 {index + 1} 張圖片")
            image = self.store.image(project_id, item_id)
            if image["caption_confirmed"]:
                continue
            path = self.store.image_path(project_id, item_id)
            if payload["method"] == "wd14":
                result = tag_image(
                    path,
                    model_root=self.store.settings.wd14_model_root,
                    general_threshold=self.store.settings.wd14_model_config.general_threshold,
                    character_threshold=self.store.settings.wd14_model_config.character_threshold,
                    model_name=self.store.settings.wd14_model_config.model_name,
                    provider="cpu",
                    limit=100,
                )
                general = result.get("general", [])
                tags = (
                    [str(item["tag"]) for item in general if isinstance(item, dict)]
                    if isinstance(general, list)
                    else []
                )
                caption = {"long": result.get("tag_string", ""), "tags": tags, "source": "wd14"}
            elif payload["method"] == "vision":
                model_id = payload["model"]
                if not model_id:
                    msg = "請在打標頁選擇已配置的視覺模型"
                    raise StudioError(msg)
                connection = self.models.resolve(model_id)
                if connection is not None:
                    instruction = (
                        f"Describe this image for a {project['target_profile']} training dataset. "
                        "Return JSON with long, medium, short, tags, regions, and visible_text. "
                        "Describe only visible people, clothing, pose, objects, "
                        "composition and style. "
                        "Preserve readable text verbatim in visible_text, including "
                        "its original language. "
                        "Use English for descriptive captions. Count visible subjects carefully. "
                        "Do not infer hidden anatomy, identity or unreadable text. "
                        "For Anima, also provide a list of precise Booru tags. "
                        "Regions may be an empty list. Any region must use normalized "
                        "bbox [x0,y0,x1,y1]. "
                        "Return no reasoning or Markdown."
                    )
                    content = _external_vision_completion(
                        connection=connection,
                        system_prompt=instruction,
                        text_prompt="Write the training annotation for this image.",
                        image_data_url=_image_data_url(path),
                        temperature=0.1,
                        max_tokens=1800,
                    )
                    caption = _extract_json_object(content)
                    caption["source"] = model_id
                else:
                    draft = draft_krea2_caption(
                        image_path=path,
                        model=model_id,
                        max_tokens=900,
                        connections=self.models,
                    )
                    caption = {"long": draft.get("caption", ""), "source": model_id}
                if not str(caption.get("long", "")).strip():
                    msg = "視覺模型沒有返回可用的描述，請查看模型設定後重試"
                    raise StudioError(msg)
            else:
                msg = "標注方式有誤"
                raise StudioError(msg)
            self.store.update_image(
                project_id,
                item_id,
                {
                    "caption": caption,
                    "caption_confirmed": False,
                    "expected_updated_at": image["updated_at"],
                },
            )
            completed.append(item_id)
        context.update(len(identifiers), len(identifiers), "標注草稿已保存，請逐圖審核")
        return {"item_ids": completed}

    def worker_job(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915 - protocol validation and dispatch stay together
        project_id = payload["project_id"]
        options = (
            ImageProviderStore(self.store.settings.library_root).public().get("caption_worker", {})
        )
        executable = Path(options.get("python", ""))
        if not executable.is_file():
            msg = "請在設定填寫已安裝 PixAI／KohakuGBC 的 Python 路徑"
            raise StudioError(msg)
        method = payload["method"]
        required = ["pixai_model"] if method == "pixai" else ["detector_model", "embedder_model"]
        if method == "pixai_gbc":
            required.append("pixai_model")
        if any(not Path(options.get(name, "")).exists() for name in required):
            msg = "請在設定填寫標注工作器所需的模型目錄"
            raise StudioError(msg)
        records = []
        for item_id in payload["item_ids"]:
            image = self.store.image(project_id, item_id)
            if not image["caption_confirmed"]:
                records.append(
                    {
                        "item_id": item_id,
                        "sha256": image["sha256"],
                        "updated_at": image["updated_at"],
                        "path": str(self.store.image_path(project_id, item_id)),
                    }
                )
        output = self.store.root / "caption-workers" / context.job_id
        output.mkdir(parents=True, exist_ok=True)
        request = {
            "options": options,
            "method": method,
            "images": records,
            "output": str(output),
            "pixai_tag_threshold": PIXAI_TAG_THRESHOLD,
        }
        if method != "pixai":
            connection = self.models.resolve(payload["model"])
            if connection is None or not connection.supports_vision:
                msg = "KohakuGBC 需要已接入的視覺模型 API"
                raise StudioError(msg)
            request["vision"] = {
                "model": connection.model_name,
                "base_url": connection.base_url,
                "api_key": connection.api_key,
            }
        command = [
            str(executable),
            "-X",
            "utf8",
            str(Path(__file__).with_name("studio_caption_worker.py")),
        ]
        process = subprocess.Popen(  # noqa: S603 - local configured executable, argument list and no shell
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        gbc_suffix = GBC_TAG_SEEDED_SUFFIX if method == "pixai_gbc" else ".gbc.json"
        try:
            if process.stdin is None:
                msg = "標注工作器的輸入管道無法開啟"
                raise StudioError(msg)
            process.stdin.write(json.dumps(request, ensure_ascii=False).encode("utf-8"))
            process.stdin.close()
            deadline = time.monotonic() + 24 * 3600
            while process.poll() is None:
                context.raise_if_cancelled()
                if time.monotonic() > deadline:
                    msg = "標注工作器超過等候時間，已完成的中間結果已保存"
                    raise StudioError(msg)
                completed = sum(
                    (
                        output
                        / (item["item_id"] + (".pixai.json" if method == "pixai" else gbc_suffix))
                    ).is_file()
                    for item in records
                )
                context.update(
                    completed, len(records), f"標注工作器已處理 {completed} / {len(records)}"
                )
                time.sleep(0.5)
            if process.returncode:
                msg = (
                    "標注工作器執行失敗，請檢查工作器 Python 依賴、模型目錄及視覺 API 設定。"
                    "重試會沿用已完成結果。"
                )
                raise StudioError(msg)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
        completed = []
        for item in records:
            current = self.store.image(project_id, item["item_id"])
            if current["caption_confirmed"]:
                continue
            caption = dict(current["caption"])
            for suffix in ("pixai", "gbc"):
                result_suffix = gbc_suffix if suffix == "gbc" else ".pixai.json"
                path = output / (item["item_id"] + result_suffix)
                if path.is_file():
                    part = normalize_annotation(json.loads(path.read_text(encoding="utf-8")))
                    if suffix == "pixai" and caption.get("long"):
                        part.pop("long", None)
                    if suffix == "gbc" and caption.get("tags"):
                        part["tags"] = caption["tags"]
                    caption.update(part)
            self.store.update_image(
                project_id,
                item["item_id"],
                {
                    "caption": caption,
                    "caption_confirmed": False,
                    "expected_updated_at": item["updated_at"],
                },
            )
            completed.append(item["item_id"])
        context.update(len(records), len(records), "標注草稿已保存，請逐圖審核")
        return {"item_ids": completed}
