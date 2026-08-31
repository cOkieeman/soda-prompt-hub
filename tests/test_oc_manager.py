from __future__ import annotations

import json

import pytest

from prompt_hub.database import PromptDatabase
from prompt_hub.oc_manager import archive_import, parse_oc_manager_json


def _full_export() -> bytes:
    return json.dumps(
        {
            "version": 4,
            "format": "oc-manager-full-database",
            "characters": [
                {
                    "id": "char-luna",
                    "name": "露娜",
                    "world": "夜城",
                    "gender": "女",
                    "age": 24,
                    "race": "人类",
                    "identity": "调查员",
                    "story": "在哥特教堂调查失踪事件。",
                    "modules": [
                        {
                            "id": "appearance",
                            "type": "text-long",
                            "title": "外观",
                            "body": "黑金礼服, 银色长发",
                        }
                    ],
                    "prompts": [
                        {
                            "id": "prompt-1",
                            "label": "Anima 立绘",
                            "text": "adult woman, black and gold gothic dress",
                            "createdAt": "2026-08-30T00:00:00Z",
                        }
                    ],
                    "gallery": [{"id": "image-1", "url": "https://example.com/luna.png"}],
                    "createdAt": "2026-08-01T00:00:00Z",
                    "updatedAt": "2026-08-30T00:00:00Z",
                },
                {
                    "id": "char-noah",
                    "name": "诺亚",
                    "world": "夜城",
                    "gender": "男",
                    "age": "未知",
                    "race": "精灵",
                    "identity": "向导",
                    "story": "熟悉地下遗迹。",
                    "prompts": [],
                    "gallery": [],
                },
            ],
            "worlds": [
                {
                    "id": "world-night",
                    "name": "夜城",
                    "color": "#171815",
                    "system": "coc7",
                }
            ],
            "catalog": {},
            "lore": {
                "world-night": {
                    "locations": [
                        {
                            "id": "old-cathedral",
                            "name": "旧教堂",
                            "type": "遗迹",
                            "climate": "常年有雾",
                            "ruler": "",
                            "tags": ["哥特", "秘密通道"],
                        }
                    ],
                    "factions": [],
                    "rules": [],
                    "artifacts": [],
                    "history": [],
                    "races": [],
                }
            },
        },
        ensure_ascii=False,
    ).encode()


def test_parse_supported_oc_manager_formats() -> None:
    full = parse_oc_manager_json(_full_export())
    assert full.format_name == "oc-manager-full-database"
    assert [character["id"] for character in full.characters] == ["char-luna", "char-noah"]
    assert full.worlds[0]["name"] == "夜城"

    single = parse_oc_manager_json(
        json.dumps(
            {
                "format": "oc-manager-single-character",
                "character": {"id": "single", "name": "单卡"},
            },
            ensure_ascii=False,
        ).encode()
    )
    assert single.characters[0]["id"] == "single"

    folders = parse_oc_manager_json(
        json.dumps(
            {
                "format": "oc-manager-world-folders",
                "worlds": {"雾都": {"characters": [{"id": "fog", "name": "雾中人"}]}},
                "unassigned": [],
            },
            ensure_ascii=False,
        ).encode()
    )
    assert folders.characters[0]["world"] == "雾都"

    with pytest.raises(ValueError, match="requires id and name"):
        parse_oc_manager_json(b'[{"id":"missing-name"}]')
    with pytest.raises(ValueError, match="Invalid OC Manager JSON"):
        parse_oc_manager_json(b"not-json")


def test_archive_and_import_oc_manager_data(tmp_path) -> None:
    raw = _full_export()
    bundle = parse_oc_manager_json(raw)
    archived, digest = archive_import(tmp_path, "../My OC export.json", raw)
    archived_again, same_digest = archive_import(tmp_path, "duplicate.json", raw)
    assert archived.exists()
    assert archived.parent == tmp_path / "sources" / "imports" / "oc-manager"
    assert archived_again == archived
    assert same_digest == digest

    database = PromptDatabase(tmp_path / "database" / "prompt.sqlite")
    database.initialize()
    result = database.import_oc_manager(
        bundle,
        source_file=str(archived),
        import_hash=digest,
    )
    assert result["characters_imported"] == 2
    assert result["stats"] == {
        "characters": 2,
        "worlds": 1,
        "prompts": 1,
        "lore_worlds": 1,
        "imports": 1,
    }
    gothic = database.search_oc_characters("哥特", world="夜城")
    assert gothic[0]["character_id"] == "char-luna"
    assert gothic[0]["prompt_count"] == 1
    assert gothic[0]["gallery_count"] == 1
    profile = database.get_oc_character("char-luna")
    assert profile is not None
    assert profile["profile"]["modules"][0]["title"] == "外观"
    assert profile["prompts"][0]["label"] == "Anima 立绘"
    assert database.get_oc_character_prompts("missing") == []
    assert database.list_oc_worlds()[0]["has_lore"] is True
    lore = database.search_oc_lore("秘密通道")
    assert lore[0]["world_name"] == "夜城"
    assert lore[0]["lore"]["locations"][0]["name"] == "旧教堂"

    updated_raw = json.dumps(
        {
            "format": "oc-manager-single-character",
            "character": {
                "id": "char-luna",
                "name": "露娜·更新",
                "world": "夜城",
                "story": "更新后的故事",
                "prompts": [],
            },
        },
        ensure_ascii=False,
    ).encode()
    updated = parse_oc_manager_json(updated_raw)
    _, updated_digest = archive_import(tmp_path, "luna-update.json", updated_raw)
    database.import_oc_manager(
        updated,
        source_file="luna-update.json",
        import_hash=updated_digest,
    )
    assert database.search_oc_characters("露娜")[0]["name"] == "露娜·更新"
    assert database.get_oc_character_prompts("char-luna") == []
    assert database.get_oc_character("char-noah") is not None
    assert database.oc_stats()["characters"] == 2
