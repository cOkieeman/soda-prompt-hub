from __future__ import annotations

import json
import platform
import shutil
import sys
from dataclasses import dataclass
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any

import numpy as np

from prompt_hub.config import TAGGER_MODELS
from prompt_hub.local_visual import (
    MODEL_FILENAME,
    MODEL_ID,
    MODEL_REVISION,
    MODEL_SHA256,
    MODEL_SIZE_BYTES,
    validate_custom_visual_model,
    write_model_info,
)
from prompt_hub.optional_model_download import download_file
from prompt_hub.studio_providers import ImageProviderStore
from prompt_hub.studio_store import write_json
from prompt_hub.visual_model import (
    DOWNLOAD_JOB_TYPE,
    VisualModelError,
    download_bundled_visual_model,
)
from prompt_hub.wd14 import WD14Tagger
from prompt_hub.web_resources import read_web_asset

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from prompt_hub.background_jobs import BackgroundJobStore, JobContext, JobHandler
    from prompt_hub.config import Settings


@dataclass(frozen=True)
class ModelFile:
    name: str
    size: int
    sha256: str
    remote_name: str = ""


@dataclass(frozen=True)
class OptionalModel:
    id: str
    title: str
    purpose: str
    repository: str
    revision: str
    directory: str
    files: tuple[ModelFile, ...]
    caption_key: str = ""

    @property
    def job_type(self) -> str:
        return (
            DOWNLOAD_JOB_TYPE if self.id == "clip-vit-base-patch32" else f"optional_model_{self.id}"
        )

    @property
    def size(self) -> int:
        return sum(file.size for file in self.files)


OPTIONAL_MODELS = (
    OptionalModel(
        "wd-swinv2-tagger-v3",
        "WD14 · 二次元打标",
        "为动漫、插画生成 Booru 标签草稿；安装后仍需人工审核。",
        "SmilingWolf/wd-swinv2-tagger-v3",
        "627aef95638667ddcaa3ac8ae625e88ea5b02f51",
        "wd14/wd-swinv2-tagger-v3",
        (
            ModelFile(
                "model.onnx",
                467460978,
                "e6774bff34d43bd49f75a47db4ef217dce701c9847b546523eb85ff6dbba1db1",
            ),
            ModelFile(
                "selected_tags.csv",
                308468,
                "298633d94d0031d2081c0893f29c82eab7f0df00b08483ba8f29d1e979441217",
            ),
        ),
    ),
    OptionalModel(
        "idolsankaku-swinv2-tagger-v1",
        "真人／摄影打标",
        "为真人、摄影素材生成标签草稿；可在数据集工作区选择，不替换默认 WD14。",
        "deepghs/idolsankaku-swinv2-tagger-v1",
        "dae1ee73f9ed0fa758d194af2a33763e09f1d0f3",
        "tagger/idolsankaku-swinv2-tagger-v1",
        (
            ModelFile(
                "model.onnx",
                420267904,
                "37e7f4c66ba73cdbae5a1c3d125f35173fbca45096b1bd459b63119d16b553fd",
            ),
            ModelFile(
                "selected_tags.csv",
                12693,
                "8ac5e135d099f05ca3eae962f4bed26aa0a78b7b51d1d442ad6c53d289e0dd08",
            ),
        ),
    ),
    OptionalModel(
        "clip-vit-base-patch32",
        "CLIP · 相似图检索",
        "为图片建立视觉特征，支持以图找图；安装后还需建立或更新图片索引。",
        MODEL_ID,
        MODEL_REVISION,
        "clip/clip-vit-base-patch32",
        (ModelFile(MODEL_FILENAME, MODEL_SIZE_BYTES, MODEL_SHA256, f"onnx/{MODEL_FILENAME}"),),
    ),
)

CAPTION_MODEL_KEYS = {
    "pixai-tagger-v1.0": "pixai_model",
    "sam3-litetext-l": "detector_model",
    "all-MiniLM-L6-v2": "embedder_model",
}
OPTIONAL_MODELS += tuple(
    OptionalModel(
        **{key: value for key, value in entry.items() if key != "files"},
        files=tuple(ModelFile(**file) for file in entry["files"]),
        caption_key=CAPTION_MODEL_KEYS[entry["id"]],
    )
    for entry in json.loads(read_web_asset("caption_models.json"))
)


class OptionalModelInstaller:
    def __init__(self, settings: Settings, store: BackgroundJobStore) -> None:
        self.settings = settings
        self.store = store
        self.models = {model.id: model for model in OPTIONAL_MODELS}

    def model(self, model_id: str) -> OptionalModel:
        if model_id not in self.models:
            raise VisualModelError("未知的可选模型")
        return self.models[model_id]

    def root(self, model: OptionalModel) -> Path:
        base = self.settings.models_root.resolve()
        root = base / model.directory
        for target in (root, *(root / file.name for file in model.files)):
            for path in (target, *target.parents):
                if path == base:
                    break
                if path.is_symlink():
                    raise VisualModelError("安装目录不能经过符号链接")
        if not root.resolve().is_relative_to(base):
            raise VisualModelError("安装目录必须位于模型目录内")
        return root

    def status(self) -> dict[str, Any]:
        return {
            "host": "Windows"
            if platform.system() == "Windows"
            else "Mac"
            if platform.system() == "Darwin"
            else platform.system(),
            "models_root": str(self.settings.models_root),
            "models": [self.model_status(model) for model in self.models.values()],
            "onboarding": self.onboarding(),
            "caption_runtime_available": find_spec("kohakugbc") is not None,
        }

    def onboarding(self) -> dict[str, Any]:
        path = self.settings.library_root / "private" / "model-onboarding.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return {
                "completed": bool(value.get("completed")),
                "selected": value.get("selected", []),
            }
        except (OSError, ValueError, AttributeError):
            return {"completed": False, "selected": []}

    def complete_onboarding(self, selected: list[str]) -> dict[str, Any]:
        value = {"completed": True, "selected": list(dict.fromkeys(selected))}
        write_json(self.settings.library_root / "private" / "model-onboarding.json", value)
        return value

    def model_status(self, model: OptionalModel) -> dict[str, Any]:
        state, reason = "missing", "未安装，用到时再装即可"
        root = self.settings.models_root / model.directory
        try:
            root = self.root(model)
            stamps = _file_stamps(root, model)
            receipt = _read_receipt(root)
            if (
                stamps
                and receipt.get("revision") == model.revision
                and receipt.get("files") == stamps
            ):
                state, reason = (
                    "ready",
                    (
                        "文件校验通过，已接入打标工作器"
                        if model.caption_key
                        else "文件校验和本机推理自检通过"
                    ),
                )
            elif stamps:
                state, reason = "unverified", "发现已有文件，需校验并进行本机自检"
            elif any((root / file.name).exists() for file in model.files):
                state, reason = "partial", "模型文件不完整，可继续安装；不会覆盖不同版本的已有文件"
        except (OSError, VisualModelError):
            state, reason = "blocked", "模型目录不可访问或含符号链接，请检查路径与权限"
        jobs = self.store.list_jobs(job_type=model.job_type, limit=1)
        job = jobs[0] if jobs else None
        return {
            "id": model.id,
            "title": model.title,
            "purpose": model.purpose,
            "size_bytes": model.size,
            "path": str(root),
            "repository": model.repository,
            "source_url": f"https://huggingface.co/{model.repository}/tree/{model.revision}",
            "revision": model.revision,
            "files": [file.name for file in model.files],
            "state": state,
            "reason": reason,
            "job": job,
            "caption_key": model.caption_key,
        }

    def handlers(self) -> dict[str, JobHandler]:
        return {model.job_type: self._handler(model) for model in self.models.values()}

    def _handler(self, model: OptionalModel) -> JobHandler:
        def run(_payload: Mapping[str, Any], context: JobContext) -> dict[str, Any]:
            return self.install(model, context)

        return run

    def install(self, model: OptionalModel, context: JobContext) -> dict[str, Any]:
        root = self.root(model)
        root.mkdir(parents=True, exist_ok=True)
        metadata_names = ("model-info.json", "optional-install.json", "optional-install.json.tmp")
        if any((root / name).is_symlink() for name in metadata_names):
            raise VisualModelError("模型校验记录不能是符号链接")
        context.update(0, model.size, "正在检查磁盘空间……")
        needed = 0
        for file in model.files:
            if (root / file.name).is_file():
                continue
            part = root / (file.name + ".part")
            downloaded = part.stat().st_size if part.is_file() and not part.is_symlink() else 0
            needed += max(0, file.size - min(downloaded, file.size))
        if shutil.disk_usage(root).free < needed + 16 * 1024 * 1024:
            raise VisualModelError("磁盘空间不足，请至少释放模型大小加 16 MB 的空间后重试")
        if model.id == "clip-vit-base-patch32" and not (root / MODEL_FILENAME).exists():
            if any(
                (root / name).is_symlink() for name in (MODEL_FILENAME + ".part", "model-info.json")
            ):
                raise VisualModelError("模型路径不能是符号链接")
            download_bundled_visual_model(root, {}, context)
        else:
            completed = 0
            for file in model.files:
                url = (
                    f"https://huggingface.co/{model.repository}/resolve/"
                    f"{model.revision}/{file.remote_name or file.name}"
                )
                (root / file.name).parent.mkdir(parents=True, exist_ok=True)
                download_file(
                    root / file.name,
                    url,
                    file.size,
                    file.sha256,
                    context,
                    completed=completed,
                    total=model.size,
                )
                completed += file.size
        context.update(model.size, model.size, "文件完整性校验通过，正在检查模型结构……")
        self_check(model, root)
        context.raise_if_cancelled()
        if model.id == "clip-vit-base-patch32":
            write_model_info(root, sha256=MODEL_SHA256)
        receipt = {"revision": model.revision, "files": _file_stamps(root, model)}
        target = root / "optional-install.json"
        temporary = root / "optional-install.json.tmp"
        if target.is_symlink() or temporary.is_symlink():
            raise VisualModelError("模型校验记录不能是符号链接")
        temporary.write_text(json.dumps(receipt), encoding="utf-8")
        temporary.replace(target)
        self._configure_worker(model, root)
        return {"installed": True, "model_id": model.repository, "self_test": "passed"}

    def _configure_worker(self, model: OptionalModel, root: Path) -> None:
        if not model.caption_key:
            return
        defaults = {model.caption_key: str(root), "device": "cpu"}
        if find_spec("kohakugbc") is not None:
            defaults["python"] = sys.executable
        ImageProviderStore(self.settings.library_root).fill_caption_worker(defaults)


def _file_stamps(root: Path, model: OptionalModel) -> dict[str, Any]:
    stamps = {}
    for file in model.files:
        path = root / file.name
        if path.is_symlink() or not path.is_file():
            return {}
        stat = path.stat()
        if stat.st_size != file.size:
            return {}
        stamps[file.name] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    return stamps


def _read_receipt(root: Path) -> dict[str, Any]:
    try:
        data = json.loads((root / "optional-install.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def self_check(model: OptionalModel, root: Path) -> None:
    try:
        if model.caption_key:
            config = json.loads((root / "config.json").read_text(encoding="utf-8"))
            if not config.get("model_type"):
                raise ValueError("模型配置缺少类型")
        elif model.id == "clip-vit-base-patch32":
            validate_custom_visual_model(
                root / MODEL_FILENAME,
                model_id=model.repository,
                model_revision=model.revision,
                dimension=512,
                input_size=224,
            )
        else:
            config = TAGGER_MODELS[model.id]
            tagger = WD14Tagger(
                model_root=root,
                model_name=config.model_name,
                general_threshold=config.general_threshold,
                character_threshold=config.character_threshold,
            )
            output = tagger.session.run(
                [tagger.output_meta.name],
                {
                    tagger.input_meta.name: np.zeros(
                        (1, tagger.target_size, tagger.target_size, 3), dtype=np.float32
                    )
                },
            )[0]
            if (
                not isinstance(output, np.ndarray)
                or output.shape != (1, len(tagger.labels))
                or not np.isfinite(output).all()
            ):
                raise ValueError("模型输出与标签表不匹配")
    except Exception as error:
        raise VisualModelError(
            "文件已下载，但本机推理自检未通过。请检查运行库与可用内存，再点击校验重试。"
        ) from error
