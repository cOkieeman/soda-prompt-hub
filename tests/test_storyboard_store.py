from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from soda_storyboard.bundle import export_bundle, load_bundle

from prompt_hub.storyboard import StoryboardConflictError, StoryboardStore
from prompt_hub.storyboard_safety import (
    audit_tree,
    identifier,
    json_document,
    local_path,
    page_limits,
    validate_paths,
)


@pytest.fixture
def storyboard_store(settings):
    store = StoryboardStore(settings)
    store.initialize()
    return store


@pytest.fixture
def pudding_bundle(tmp_path):
    source = Path(__file__).parent / "fixtures" / "storyboard_pudding"
    project = tmp_path / "pudding-copy"
    shutil.copytree(source, project)
    report = export_bundle(project / "pages" / "pudding.json")
    return json.loads(Path(report["path"]).read_text(encoding="utf-8"))


def test_pudding_import_validate_compile_export_roundtrip(storyboard_store, pudding_bundle):
    expected_page, expected_cards, expected_project, _ = load_bundle(pudding_bundle)
    project = storyboard_store.import_project(pudding_bundle)
    project_id = project["id"]
    assert project["project"]["name"] == "布丁争夺战"
    assert storyboard_store.validate_page(project_id, "pudding")["errors"] == []
    compiled = storyboard_store.compile_page(project_id, "pudding")
    assert compiled["width"] == 1024
    assert compiled["height"] == 1536
    assert compiled["moss"]["items"]
    exported = storyboard_store.export_bundle(project_id, "pudding")
    page, cards, project_settings, _ = load_bundle(exported["bundle"])
    assert page.to_dict() == expected_page.to_dict()
    assert {key: card.to_dict() for key, card in cards.items()} == {
        key: card.to_dict() for key, card in expected_cards.items()
    }
    for key, value in expected_project.items():
        assert project_settings[key] == value
    assert exported["filename"] == "pudding.storyboard.json"
    assert "path" not in exported
    assert storyboard_store.thumbnail(project_id, "pudding").startswith(b"\x89PNG")
    assert not list((storyboard_store.root / "previews").glob("*.png"))


def test_projects_pages_and_recycle_bin(storyboard_store):
    store = storyboard_store
    store.initialize()
    project = store.create_project("新故事", "story")
    assert store.list_projects()[0]["name"] == "新故事"
    page = store.create_page("story", {"id": "one"})
    assert page["page"]["panels"] == []
    assert store.list_pages("story")[0]["preview_url"].endswith("/one/preview.png")
    with pytest.raises(StoryboardConflictError):
        store.create_project("重复", "story")
    with pytest.raises(StoryboardConflictError):
        store.create_page("story", {"id": "one"})
    changed = {**page["page"], "description": "人工填写"}
    saved = store.save_page("story", "one", changed, page["version"])
    assert saved["page"]["description"] == "人工填写"
    with pytest.raises(StoryboardConflictError):
        store.save_page("story", "one", page["page"], page["version"])
    deleted = store.delete_page("story", "one")
    assert (store.project_path("story") / deleted["trash_path"]).is_file()
    assert not store.list_pages("story")
    with pytest.raises(FileNotFoundError):
        store.delete_page("story", "one")
    recycled = store.delete_project(project["id"])
    assert (store.root / recycled["trash_path"] / "project.json").is_file()
    assert store.list_projects() == []


def test_translation_source_hash_and_version(storyboard_store, pudding_bundle):
    store = storyboard_store
    project_id = store.import_project(pudding_bundle)["id"]
    page_id = "pudding"
    current = store.get_page(project_id, page_id)
    raw = current["page"]
    for panel in raw["panels"]:
        panel.pop("caption_auto_en", None)
    current = store.save_page(project_id, page_id, raw, current["version"])
    todo = store.translation_todo(project_id, page_id)
    assert todo["panels"]
    item = todo["panels"][0]
    translations = [
        {
            "panel_id": item["panel_id"],
            "source_hash": item["source_hash"],
            "text": "The sisters reach for a pudding cup.",
        }
    ]
    report = store.apply_translations(project_id, page_id, translations, current["version"])
    assert report["applied"] == [item["panel_id"]]
    with pytest.raises(StoryboardConflictError):
        store.apply_translations(project_id, page_id, translations, current["version"])
    rejected = store.apply_translations(
        project_id, page_id, [{**translations[0], "source_hash": "outdated"}]
    )
    assert rejected["rejected"][0]["reason"] == "translation_not_todo"


def test_fresh_and_manual_captions_are_never_replaced(storyboard_store, pudding_bundle):
    store = storyboard_store
    project_id = store.import_project(pudding_bundle)["id"]
    current = store.get_page(project_id, "pudding")
    raw = current["page"]
    raw["panels"][0]["caption_en"] = "User-approved caption"
    raw["panels"][0]["use_custom_caption"] = True
    store.save_page(project_id, "pudding", raw, current["version"])
    todo = store.translation_todo(project_id, "pudding")
    assert raw["panels"][0]["id"] not in {item["panel_id"] for item in todo["panels"]}
    before = store.get_page(project_id, "pudding")
    result = store.apply_translations(
        project_id,
        "pudding",
        [{"panel_id": raw["panels"][0]["id"], "source_hash": "unused", "text": "overwrite"}],
        before["version"],
    )
    assert result["applied"] == []
    assert result["rejected"][0]["reason"] == "translation_not_todo"
    assert store.get_page(project_id, "pudding") == before


@pytest.mark.parametrize(
    "content",
    [
        "1. 女孩推开窗户。\n2. 阳光照亮桌上的白花。",
        "| 格 | 画面 | 台词 |\n| --- | --- | --- |\n| 1 | 女孩推开窗户 | 天晴了。 |",
        '[{"description":"女孩推开窗户"},{"description":"阳光照亮白花"}]',
        '```json\n[{"description":"女孩推开窗户"}]\n```',
        [{"description": "女孩推开窗户"}],
    ],
)
def test_markdown_and_frame_arrays_delegate_to_core(storyboard_store, content):
    project = storyboard_store.import_project(content, "外来分镜")
    assert project["page"]["panels"]
    assert project["import_report"]["guesses"]
    project_id = project["id"]
    page_id = project["page"]["id"]
    page = storyboard_store.get_page(project_id, page_id)
    page["page"]["title"] = "第一页的标题"
    storyboard_store.save_page(project_id, page_id, page["page"], page["version"])
    assert storyboard_store.list_pages(project_id)[0]["title"] == "第一页的标题"


@pytest.mark.parametrize("content", ["../../private.json", "C:\\private.json", "1", "[1,2,3]"])
def test_import_content_never_reads_arbitrary_paths(storyboard_store, content):
    with pytest.raises((ValueError, TypeError)):
        storyboard_store.import_project(content)
    assert storyboard_store.list_projects() == []


def test_import_into_existing_project_never_overwrites(storyboard_store, pudding_bundle):
    store = storyboard_store
    store.create_project("现有项目", "existing")
    imported = store.import_page("existing", pudding_bundle)
    assert imported["page"]["id"] == "pudding"
    assert store.get_project("existing")["project"]["name"] == "现有项目"
    with pytest.raises(StoryboardConflictError):
        store.import_page("existing", pudding_bundle)
    store.import_page("existing", pudding_bundle, "second-page")
    with pytest.raises(ValueError, match="按页导出"):
        store.export_bundle("existing")
    card = store.characters("existing")["older"].to_dict()
    with pytest.raises(StoryboardConflictError):
        store.save_character("existing", card)
    conflicting = json.loads(json.dumps(pudding_bundle))
    conflicting["characters"]["older"]["display_name"] = "同名冲突角色"
    with pytest.raises(StoryboardConflictError):
        store.import_page("existing", conflicting, "third-page")
    assert len(store.list_pages("existing")) == 2


def test_moss_import_and_core_compile_delegation(storyboard_store, monkeypatch):
    store = storyboard_store
    moss = {
        "summary": {"caption": "A simple room"},
        "items": [{"type": "object", "caption": "a red cup", "bbox": [-100, -100, 100, 100]}],
        "bbox_format": "xyxy",
        "bbox_coord_space": "absolute",
    }
    project = store.import_project(moss, "MOSS 导入")
    page_id = project["pages"][0]["id"]
    expected = {"moss": {"items": []}, "width": 1024, "height": 1536, "lora": None, "warnings": []}
    calls = []

    def fake_compile(bundle, **options):
        calls.append((bundle, options))
        return expected

    monkeypatch.setattr("prompt_hub.storyboard.compile_bundle", fake_compile)
    assert store.compile_page(project["id"], page_id) == expected
    assert calls[0][0]["format"] == "soda-storyboard-bundle-v1"
    with pytest.raises(ValueError, match="编译选项"):
        store.compile_page(project["id"], page_id, {"output": "elsewhere.json"})


@pytest.mark.parametrize(
    "value", ["../escape", "C:\\escape", "CON", "one/other", "x\x00", ".", "last.", ""]
)
def test_identifiers_reject_path_forms(value):
    with pytest.raises(ValueError, match="分镜标识"):
        identifier(value)


@pytest.mark.parametrize(
    "path", ["../outside.png", "/outside.png", "C:/outside.png", "safe/../out", "safe:file.png"]
)
def test_local_paths_reject_escape(tmp_path, path):
    with pytest.raises(ValueError, match="分镜文件必须"):
        local_path(tmp_path, path)
    assert validate_paths({"production": {"renders": [{"path": path}]}}, tmp_path)


def test_json_limits_and_invalid_page_geometry(storyboard_store):
    assert json_document({"production": {"seed": 2**64 - 1}})["production"]["seed"] == 2**64 - 1
    for source in ('{"number": 1e999}', {"number": float("nan")}, {"wrong": object()}):
        with pytest.raises((ValueError, TypeError)):
            json_document(source)
    with pytest.raises(ValueError, match="有效的分镜 JSON"):
        json_document("not-a-file-path.json")
    with pytest.raises(TypeError):
        json_document([1])
    store = storyboard_store
    store.create_project("路径边界", "safe")
    for raw in (
        {"id": "../out"},
        {"id": "too-large", "canvas_width": 100_000},
        {"id": "bad-path", "production": {"selected_render": "../outside.png"}},
        {"id": "many", "panels": [{}] * 257},
        {"id": "invalid", "panels": [None]},
    ):
        with pytest.raises((ValueError, TypeError)):
            store.create_page("safe", raw)
    assert store.list_pages("safe") == []
    with pytest.raises(ValueError, match="分镜画布"):
        page_limits({"id": "safe", "canvas_height": True}, store.root)


def test_symlink_and_hardlink_boundaries(storyboard_store, tmp_path):
    store = storyboard_store
    store.create_project("链接边界", "linked")
    target = tmp_path / "outside.json"
    target.write_text('{"id":"external"}', encoding="utf-8")
    managed = store.project_path("linked") / "pages" / "external.json"
    try:
        managed.hardlink_to(target)
    except OSError:
        pytest.skip("hardlinks unavailable")
    with pytest.raises(ValueError, match="硬链接"):
        store.get_project("linked")
    managed.unlink()
    # Junction detection is tested without requiring the Windows symlink privilege.
    original = Path.is_junction

    def fake_junction(path):
        return path == managed.parent or original(path)

    with (
        patch.object(Path, "is_junction", fake_junction),
        pytest.raises(ValueError, match="目录联接"),
    ):
        audit_tree(store.root / "projects" / "linked")
