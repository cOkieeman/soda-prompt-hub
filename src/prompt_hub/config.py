from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    library_root: Path
    database_path: Path
    git_sources_root: Path

    @classmethod
    def from_environment(cls) -> Settings:
        default_root = Path.home() / "Documents" / "Codex" / "soda-person" / "prompt-library"
        library_root = Path(os.environ.get("PROMPT_HUB_LIBRARY_ROOT", default_root)).expanduser()
        database_path = Path(
            os.environ.get(
                "PROMPT_HUB_DATABASE",
                library_root / "database" / "prompt-library.sqlite",
            )
        ).expanduser()
        return cls(
            library_root=library_root,
            database_path=database_path,
            git_sources_root=library_root / "sources" / "git",
        )

    def ensure_directories(self) -> None:
        directories = (
            self.database_path.parent,
            self.git_sources_root,
            self.library_root / "sources" / "web",
            self.library_root / "sources" / "api",
            self.library_root / "sources" / "imports",
            self.oc_imports_root,
            self.library_root / "normalized",
            self.library_root / "private" / "personal-prompts",
            self.library_root / "private" / "adult-prompts",
            self.library_root / "private" / "characters",
            self.library_root / "test-results",
            self.result_images_root,
            self.comfy_results_root,
            self.thumbnails_root,
            self.library_root / "exports",
            self.dataset_exports_root,
            self.dataset_workspaces_root,
            self.lora_projects_root,
            self.embedding_index_root,
            self.remote_nodes_root,
            self.workflow_profiles_root,
        )
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def thumbnails_root(self) -> Path:
        return self.library_root / "thumbnails"

    @property
    def oc_imports_root(self) -> Path:
        return self.library_root / "sources" / "imports" / "oc-manager"

    @property
    def result_images_root(self) -> Path:
        return self.library_root / "test-results" / "prompt-hub"

    @property
    def comfy_results_root(self) -> Path:
        return self.library_root / "test-results" / "comfyui-imports"

    @property
    def dataset_exports_root(self) -> Path:
        return self.library_root / "exports" / "datasets"

    @property
    def dataset_workspaces_root(self) -> Path:
        return self.library_root / "datasets" / "workspaces"

    @property
    def lora_projects_root(self) -> Path:
        return self.library_root / "lora-projects"

    @property
    def embedding_index_root(self) -> Path:
        return self.library_root / "indexes" / "embeddings"

    @property
    def remote_nodes_root(self) -> Path:
        return self.library_root / "remote-nodes"

    @property
    def workflow_profiles_root(self) -> Path:
        return self.library_root / "workflow-profiles"

    @property
    def models_root(self) -> Path:
        default_root = self.library_root.parent / "models"
        return Path(os.environ.get("PROMPT_HUB_MODELS_ROOT", default_root)).expanduser()

    @property
    def wd14_model_root(self) -> Path:
        return self.models_root / "wd14" / "wd-swinv2-tagger-v3"
