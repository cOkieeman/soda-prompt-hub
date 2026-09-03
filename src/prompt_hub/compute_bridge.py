from __future__ import annotations

from typing import Any

COMPUTE_PROTOCOL_VERSION = "soda-compute-bridge-v2"


def compute_contract() -> dict[str, Any]:
    return {
        "protocol_version": COMPUTE_PROTOCOL_VERSION,
        "transport": "smb-shared-folder-v1",
        "directories": ["outbox", "inbox", "processing", "completed", "failed"],
        "task_states": [
            "recorded",
            "queued",
            "claimed",
            "running",
            "returned",
            "completed",
            "failed",
            "canceled",
        ],
        "task_envelope": {
            "required": [
                "task_id",
                "task_type",
                "target_role",
                "created_at",
                "payload",
                "manifest",
            ],
            "optional": [
                "project_id",
                "workspace_id",
                "run_id",
                "attempt",
                "priority",
                "retry_of",
            ],
            "integrity": "sha256 manifest; results must echo task_id and source hashes",
        },
        "result_envelope": {
            "required": [
                "task_id",
                "task_type",
                "worker_id",
                "status",
                "started_at",
                "finished_at",
                "source_hashes",
                "outputs",
            ],
            "status": ["completed", "failed", "canceled"],
            "integrity": "Mac verifies every echoed source hash and output sha256 before import",
        },
        "task_types": {
            "comfyui_generate": {
                "target_role": "compute_5060ti",
                "payload_required": ["generation_package", "workflow_id", "output_profile"],
                "generation_package_format": {
                    "format": "soda-comfyui-package-v1",
                    "required": ["workflow_id", "api_prompt"],
                    "api_prompt": "ComfyUI workflow exported in API Format, not UI workflow JSON",
                    "must_be_in_manifest": True,
                },
                "outputs": ["images", "comfyui_png_metadata", "workflow", "run_log"],
            },
            "lora_train": {
                "target_role": "compute_5060ti",
                "payload_required": ["run_id", "frozen_dataset", "training_config"],
                "outputs": ["checkpoints", "sample_images", "metrics", "run_log"],
            },
            "embedding_batch": {
                "target_role": "compute_5060ti",
                "payload_required": ["model_id", "model_revision", "items"],
                "item_required": ["asset_id", "relative_path", "sha256"],
                "outputs": [
                    "asset_id",
                    "source_sha256",
                    "vector",
                    "dimension",
                    "model_id",
                    "model_revision",
                ],
                "mac_import_endpoint": "/api/embedding-indexes/import",
            },
            "vlm_caption_batch": {
                "target_role": "compute_5060ti",
                "payload_required": ["workspace_id", "model_id", "profile_id", "items"],
                "constraints": {"profile_id": "krea2", "language": "en", "result": "draft"},
                "outputs": [
                    "relative_path",
                    "source_sha256",
                    "caption_draft",
                    "observations",
                    "model_id",
                ],
                "mac_import_endpoint": ("/api/dataset-workspaces/{workspace_id}/krea2-vlm/import"),
            },
            "lora_catalog_snapshot": {
                "target_role": "compute_5060ti",
                "payload_required": ["source_manager", "lora_roots"],
                "constraints": {
                    "read_only": True,
                    "copy_weights_to_mac": False,
                    "read_weight_contents": False,
                    "lora_roots": "root_id values from Windows Worker configuration",
                    "paths": "relative_to_configured_windows_root",
                },
                "item_required": ["lora_id", "relative_path"],
                "item_optional": [
                    "sha256",
                    "size_bytes",
                    "base_model",
                    "model_family",
                    "trigger_words",
                    "tags",
                    "preview_relative_path",
                    "metadata",
                ],
                "mac_import_endpoint": "/api/windows-loras/import",
            },
        },
        "worker_registration": {
            "required": ["worker_id", "role", "protocol_version", "capabilities"],
            "optional": ["hostname", "gpu", "vram_mib", "software_versions"],
            "credentials": "outside task JSON; use SMB mount or OS credential store",
        },
        "roles": {
            "mac_hub": {
                "owns": ["projects", "indexes", "review", "versions", "task_orchestration"],
                "capabilities": ["dataset_scan", "wd14_cpu", "caption_review", "export"],
            },
            "compute_5060ti": {
                "owns": [],
                "capabilities": [
                    "comfyui_generate",
                    "workflow_test",
                    "result_metadata",
                    "wd14_batch",
                    "embedding_batch",
                    "vlm_caption_batch",
                    "lora_smoke_test",
                    "lora_train",
                    "checkpoint_test",
                    "lora_catalog_snapshot",
                ],
            },
        },
        "security": {
            "credentials_in_tasks": False,
            "weights_copied_to_mac_by_default": False,
            "source_of_truth": "mac_hub",
            "reject_source_hash_mismatch": True,
            "model_outputs_require_review": True,
        },
    }
