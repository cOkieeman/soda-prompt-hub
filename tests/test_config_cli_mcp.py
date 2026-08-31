from __future__ import annotations

import asyncio
import json

from prompt_hub.cli import main
from prompt_hub.config import Settings
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import import_all
from prompt_hub.mcp_server import create_mcp_server


def test_settings_from_environment(tmp_path, monkeypatch) -> None:
    root = tmp_path / "custom-library"
    monkeypatch.setenv("PROMPT_HUB_LIBRARY_ROOT", str(root))
    settings = Settings.from_environment()
    settings.ensure_directories()
    assert settings.library_root == root
    assert settings.database_path == root / "database" / "prompt-library.sqlite"
    assert settings.git_sources_root.exists()


def test_cli_init_stats_and_search(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "cli-library"
    monkeypatch.setenv("PROMPT_HUB_LIBRARY_ROOT", str(root))
    main(["init"])
    initialized = json.loads(capsys.readouterr().out)
    assert initialized["status"] == "initialized"

    main(["stats"])
    assert json.loads(capsys.readouterr().out)["entries"] == 0

    main(["search", "gothic", "--limit", "2"])
    assert json.loads(capsys.readouterr().out) == []


def test_cli_tag_image_uses_personal_model_root(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "cli-library"
    monkeypatch.setenv("PROMPT_HUB_LIBRARY_ROOT", str(root))
    captured = {}

    def fake_tag_image(image, **kwargs):
        captured["image"] = image
        captured.update(kwargs)
        return {"tag_string": "1girl, solo"}

    monkeypatch.setattr("prompt_hub.cli.tag_image", fake_tag_image)
    main(["tag-image", "sample.png", "--limit", "12"])

    assert json.loads(capsys.readouterr().out)["tag_string"] == "1girl, solo"
    assert captured["image"] == "sample.png"
    assert captured["model_root"] == tmp_path / "models" / "wd14" / "wd-swinv2-tagger-v3"
    assert captured["limit"] == 12


def test_mcp_server_lists_expected_tools(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    server = create_mcp_server(source_tree)

    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "get_character_profile",
        "get_character_prompts",
        "library_stats",
        "search_characters",
        "search_prompts",
        "search_styles",
        "search_tags",
        "search_world_lore",
    }
