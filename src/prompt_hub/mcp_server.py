from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from prompt_hub.config import Settings
from prompt_hub.database import PromptDatabase


def create_mcp_server(settings: Settings | None = None) -> MCPServer:
    active_settings = settings or Settings.from_environment()
    database = PromptDatabase(active_settings.database_path)
    database.initialize()
    server = MCPServer(
        name="soda-prompt-hub",
        title="Soda Prompt Hub",
        description="Search local prompt, style, tag, OC character, and world-lore knowledge.",
        instructions=(
            "Search before composing image prompts. Preserve source attribution and model-family "
            "boundaries. Results may include legal adult material when explicitly requested."
        ),
        version="0.1.3",
    )

    @server.tool(description="Search all local prompt-library entries with optional filters.")
    def search_prompts(
        query: str,
        kind: str = "",
        source_id: str = "",
        model_family: str = "",
        safety: str = "",
        favorites_only: bool = False,
        limit: int = 8,
    ) -> dict[str, Any]:
        results = database.search(
            query,
            kind=kind,
            source_id=source_id,
            model_family=model_family,
            safety=safety,
            favorites_only=favorites_only,
            limit=limit,
        )
        return {"query": query, "count": len(results), "results": results}

    @server.tool(description="Search long-form style prompts and short style modifiers.")
    def search_styles(
        query: str,
        model_family: str = "",
        favorites_only: bool = False,
        limit: int = 8,
    ) -> dict[str, Any]:
        styles = database.search(
            query,
            kind="style",
            model_family=model_family,
            favorites_only=favorites_only,
            limit=limit,
        )
        modifiers = database.search(
            query,
            kind="modifier",
            favorites_only=favorites_only,
            limit=limit,
        )
        results = (styles + modifiers)[:limit]
        return {"query": query, "count": len(results), "results": results}

    @server.tool(description="Search canonical tags and image-caption tag references.")
    def search_tags(
        query: str,
        safety: str = "",
        favorites_only: bool = False,
        limit: int = 12,
    ) -> dict[str, Any]:
        results = database.search(
            query,
            kind="tag",
            safety=safety,
            favorites_only=favorites_only,
            limit=limit,
        )
        return {"query": query, "count": len(results), "results": results}

    @server.tool(description="Search imported OC Manager characters and character-card text.")
    def search_characters(
        query: str = "",
        world: str = "",
        limit: int = 8,
    ) -> dict[str, Any]:
        results = database.search_oc_characters(query, world=world, limit=limit)
        return {"query": query, "count": len(results), "results": results}

    @server.tool(description="Return one imported OC Manager character with its full profile.")
    def get_character_profile(character_id: str) -> dict[str, Any]:
        result = database.get_oc_character(character_id)
        return {"found": result is not None, "character": result}

    @server.tool(description="Return saved prompts belonging to one OC Manager character.")
    def get_character_prompts(character_id: str) -> dict[str, Any]:
        prompts = database.get_oc_character_prompts(character_id)
        return {"character_id": character_id, "count": len(prompts), "prompts": prompts}

    @server.tool(description="Search imported OC Manager world-lore records.")
    def search_world_lore(
        query: str = "",
        world: str = "",
        limit: int = 6,
    ) -> dict[str, Any]:
        results = database.search_oc_lore(query, world=world, limit=limit)
        return {"query": query, "count": len(results), "results": results}

    @server.tool(description="Return local prompt-library counts and source status.")
    def library_stats() -> dict[str, Any]:
        return {"stats": database.stats(), "sources": database.list_sources()}

    return server


def main() -> None:
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
