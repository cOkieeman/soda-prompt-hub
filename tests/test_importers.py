from __future__ import annotations

import json
import shutil

from prompt_hub.database import PromptDatabase
from prompt_hub.importers import discover_sources, import_all, import_report


def test_import_all_sources(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)

    results = import_all(source_tree, database)

    assert results["clio-style-preview"] == 1
    assert results["krea-open-prompts"] == 2
    assert results["sd-wildcards"] == 2
    assert results["kisegaeningyou"] > 2
    assert results["animadex"] == 3

    assert database.search("Gothic Ink", kind="style")[0]["model_family"] == "krea2"
    assert database.search("Gothic Ink", kind="style")[0]["metadata"]["image_paths"]
    assert database.search("red gown", kind="wildcard")[0]["category"] == "dress"
    assert database.search("underboob", kind="caption")[0]["safety"] == "suggestive"
    assert database.search("collared shirt", kind="tag")[0]["metadata"]["count"] == 1
    assert database.search("collared shirt", kind="tag")[0]["metadata"]["image_paths"]
    animadex = database.search("test hero", source_id="animadex")[0]
    assert animadex["kind"] == "character_reference"
    assert animadex["metadata"]["hair_colors"] == ["silver hair"]
    assert animadex["metadata"]["eye_colors"] == ["blue eyes"]
    assert database.search("underboob", kind="tag")[0]["metadata"]["image_refs"][0]["safety"] == (
        "suggestive"
    )
    assert (source_tree.thumbnails_root / "kisegaeningyou" / "images" / "safe.webp").is_file()

    manifest = json.loads(
        (source_tree.library_root / "sources" / "manifest.json").read_text(encoding="utf-8")
    )
    assert len(manifest["sources"]) == 5
    assert all(source["commit_hash"] == "deadbeef" for source in manifest["sources"])


def test_missing_source_directories_are_reported_not_silently_ignored(settings) -> None:
    database = PromptDatabase(settings.database_path)

    report = import_report(settings, database)

    assert report["sources"] == {}
    assert {item["source_id"] for item in report["skipped"]} == {
        "clio-style-preview",
        "krea-open-prompts",
        "sd-wildcards",
        "kisegaeningyou",
        "animadex",
        "krea2-style-explorer",
        "anima-style-explorer",
        "illustrious-style-explorer",
    }
    assert report["failed"] == []


def test_empty_scan_never_replaces_already_indexed_entries(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    before = database.stats()["entries"]
    shutil.rmtree(source_tree.git_sources_root / "sd-wildcards" / "wildcards")

    report = import_report(source_tree, database)

    assert "sd-wildcards" not in report["sources"]
    empty = next(item for item in report["failed"] if item["source_id"] == "sd-wildcards")
    assert empty["status"] == "empty_result"
    assert empty["previous_count"] == 2
    assert database.stats()["entries"] == before
    assert database.search("red gown", kind="wildcard")


def test_one_broken_source_does_not_abort_the_other_sources(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    (source_tree.git_sources_root / "clio-style-preview" / "styles.json").unlink()

    report = import_report(source_tree, database)

    broken = next(item for item in report["failed"] if item["source_id"] == "clio-style-preview")
    assert broken["status"] == "load_error"
    assert report["sources"]["sd-wildcards"] == 2
    assert report["sources"]["kisegaeningyou"] > 2
    assert report["sources"]["animadex"] == 3
    assert (source_tree.library_root / "sources" / "manifest.json").is_file()


def test_source_without_git_metadata_is_reported_without_crashing(source_tree) -> None:
    database = PromptDatabase(source_tree.database_path)

    report = import_report(source_tree, database)

    assert report["sources"] == {}
    assert {item["status"] for item in report["failed"]} == {"not_git"}


def test_discover_sources_uses_expected_roots(settings) -> None:
    specs = discover_sources(settings)
    assert {spec.source_id for spec in specs} == {
        "clio-style-preview",
        "krea-open-prompts",
        "sd-wildcards",
        "kisegaeningyou",
        "animadex",
        "krea2-style-explorer",
        "anima-style-explorer",
        "illustrious-style-explorer",
    }
    assert all(spec.path.is_relative_to(settings.git_sources_root) for spec in specs)
