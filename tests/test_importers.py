from __future__ import annotations

import json

from prompt_hub.database import PromptDatabase
from prompt_hub.importers import discover_sources, import_all


def test_import_all_sources(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)

    results = import_all(source_tree, database)

    assert results["clio-style-preview"] == 1
    assert results["krea-open-prompts"] == 2
    assert results["sd-wildcards"] == 2
    assert results["kisegaeningyou"] > 2

    assert database.search("Gothic Ink", kind="style")[0]["model_family"] == "krea2"
    assert database.search("Gothic Ink", kind="style")[0]["metadata"]["image_paths"]
    assert database.search("red gown", kind="wildcard")[0]["category"] == "dress"
    assert database.search("underboob", kind="caption")[0]["safety"] == "suggestive"
    assert database.search("collared shirt", kind="tag")[0]["metadata"]["count"] == 1
    assert database.search("collared shirt", kind="tag")[0]["metadata"]["image_paths"]
    assert database.search("underboob", kind="tag")[0]["metadata"]["image_refs"][0]["safety"] == (
        "suggestive"
    )
    assert (source_tree.thumbnails_root / "kisegaeningyou" / "images" / "safe.webp").is_file()

    manifest = json.loads(
        (source_tree.library_root / "sources" / "manifest.json").read_text(encoding="utf-8")
    )
    assert len(manifest["sources"]) == 4
    assert all(source["commit_hash"] == "deadbeef" for source in manifest["sources"])


def test_discover_sources_uses_expected_roots(settings) -> None:
    specs = discover_sources(settings)
    assert {spec.source_id for spec in specs} == {
        "clio-style-preview",
        "krea-open-prompts",
        "sd-wildcards",
        "kisegaeningyou",
    }
    assert all(spec.path.is_relative_to(settings.git_sources_root) for spec in specs)
