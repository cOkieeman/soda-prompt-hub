from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from prompt_hub.lora_projects import LoraProjectError


def freeze_lora_project(
    project: Mapping[str, Any],
    prepared: list[dict[str, Any]],
) -> dict[str, Any]:
    if not prepared:
        raise LoraProjectError("冻结前至少需要一张已保留或正则图片")
    families = list(project.get("target_families", []))
    trigger = str(project.get("trigger_word", ""))
    seen_hashes: set[str] = set()
    for item in prepared:
        digest = str(item["sha256"])
        if digest in seen_hashes:
            raise LoraProjectError("冻结集合含完全重复图片")
        seen_hashes.add(digest)
        for family in families:
            caption = item["captions"].get(family, {})
            if caption.get("status") != "reviewed":
                message = f"{family} caption 尚未人工审核: {item['relative_path']}"
                raise LoraProjectError(message)
            text = str(caption.get("current", ""))
            if not text or not text.isascii():
                message = f"{family} caption 必须是非空英文: {item['relative_path']}"
                raise LoraProjectError(message)
            if trigger not in text:
                message = f"caption 缺少 trigger {trigger}: {item['relative_path']}"
                raise LoraProjectError(message)

    version_id = f"freeze-{_timestamp()}-{uuid4().hex[:8]}"
    run_id = f"run-{uuid4().hex}"
    project_root = Path(str(project["project_path"]))
    export_root = project_root / "07_导出"
    version_root = export_root / version_id
    archive = export_root / f"{version_id}.zip"
    manifest_items = []
    try:
        version_root.mkdir(parents=True, exist_ok=False)
        for family in families:
            family_name = "Anima" if family == "anima" else "Krea2"
            family_root = version_root / family_name
            for group in ("train", "reg", "config"):
                (family_root / group).mkdir(parents=True)
            for index, item in enumerate(prepared, start=1):
                source = Path(str(item["source_path"]))
                if _sha256(source) != item["sha256"]:
                    message = f"来源图片在扫描后发生变化: {item['relative_path']}"
                    raise LoraProjectError(message)
                group = "reg" if item["status"] == "regularization" else "train"
                stem = f"{index:04d}-{_safe_stem(Path(item['relative_path']).stem)}"
                image_relative = Path(family_name) / group / f"{stem}{source.suffix.lower()}"
                caption_relative = image_relative.with_suffix(".txt")
                target_image = version_root / image_relative
                target_caption = version_root / caption_relative
                shutil.copy2(source, target_image)
                caption = str(item["captions"][family]["current"])
                target_caption.write_text(caption, encoding="utf-8")
                manifest_items.append(
                    {
                        "family": family,
                        "group": group,
                        "workspace_id": item["workspace_id"],
                        "source_relative_path": item["relative_path"],
                        "source_sha256": item["sha256"],
                        "image_path": image_relative.as_posix(),
                        "caption_path": caption_relative.as_posix(),
                        "caption_sha256": hashlib.sha256(caption.encode()).hexdigest(),
                    }
                )
            _write_config(family_root / "config" / "training-draft.yaml", project, family)
        manifest = {
            "format": "soda-prompt-hub-lora-freeze-v1",
            "version_id": version_id,
            "run_id": run_id,
            "project_id": project["project_id"],
            "concept_type": project["concept_type"],
            "trigger_word": trigger,
            "target_families": families,
            "training_node": project.get("training_node", "5060ti"),
            "training_resolution": project.get("training_resolution", 1024),
            "created_at": _now(),
            "items": manifest_items,
        }
        _write_json(version_root / "manifest.json", manifest)
        _write_json(
            version_root / "sample-prompts.json",
            {
                "trigger_only": trigger,
                "replacement_test": f"{trigger}, alternate outfit, different background",
                "checkpoint_plan": "compare early, middle, and late checkpoints with fixed seeds",
            },
        )
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(version_root.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(version_root).as_posix())
    except Exception:
        shutil.rmtree(version_root, ignore_errors=True)
        archive.unlink(missing_ok=True)
        raise
    return {
        "version_id": version_id,
        "run_id": run_id,
        "archive": str(archive),
        "archive_name": archive.name,
        "download_url": f"/api/lora/projects/{project['project_id']}/exports/{archive.name}",
        "image_count": len(prepared),
        "families": families,
        "created_at": manifest["created_at"],
        "manifest": manifest,
    }


def _write_config(path: Path, project: Mapping[str, Any], family: str) -> None:
    values = [
        f"model_family: {family}",
        f"concept_type: {project['concept_type']}",
        f"trigger_word: {project['trigger_word']}",
        f"resolution: {project.get('training_resolution', 1024)}",
        "trainer_version: VERIFY_ON_5060TI",
        "base_model: SET_ON_WINDOWS",
        "batch_size: 1",
        "grad_accum: 2",
        "rank: 32",
        "learning_rate: 0.0001",
        "smoke_test_steps: 10",
    ]
    if family == "krea2":
        values.extend(
            (
                "base_variant: raw_fp8",
                "text_encoder: qwen3_vl_fp8",
                "blocks_to_swap: 28",
                "grad_checkpoint: true",
                "mixed_precision: bf16",
                "text_encoder_cache: true",
                "timestep_sampling: krea2_shift",
                "attention_backend: none",
                "shuffle_caption: false",
                "keep_tokens: 0",
                "tag_dropout: 0.0",
            )
        )
    else:
        values.extend(("shuffle_caption: true", "keep_tokens: 2", "tag_dropout: 0.0"))
    path.write_text("\n".join(values) + "\n", encoding="utf-8")


def _safe_stem(value: str) -> str:
    clean = "".join(
        character if character.isalnum() or character in "-_" else "-" for character in value
    )
    return clean.strip("-")[:80] or "image"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
