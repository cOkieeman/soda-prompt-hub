from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

import uvicorn

from prompt_hub.config import Settings
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import import_all
from prompt_hub.mcp_server import main as run_mcp
from prompt_hub.wd14 import WD14Error, tag_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prompt-hub", description="Local-first prompt library")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Create directories and initialize the database")
    subparsers.add_parser("import", help="Rebuild indexes from local source repositories")
    subparsers.add_parser("stats", help="Show database and source counts")
    subparsers.add_parser("sources", help="List indexed sources")

    search = subparsers.add_parser("search", help="Search the local library")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--kind", default="")
    search.add_argument("--source", default="")
    search.add_argument("--model-family", default="")
    search.add_argument("--safety", default="")
    search.add_argument("--limit", type=int, default=10)

    serve = subparsers.add_parser("serve", help="Run the local Prompt Hub web service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    tag = subparsers.add_parser("tag-image", help="Tag one local image with WD SwinV2 V3")
    tag.add_argument("image")
    tag.add_argument("--model-root", default="")
    tag.add_argument("--general-threshold", type=float, default=0.35)
    tag.add_argument("--character-threshold", type=float, default=0.85)
    tag.add_argument("--limit", type=int, default=80)
    tag.add_argument("--provider", choices=("auto", "coreml", "cpu"), default="auto")
    subparsers.add_parser("mcp", help="Run the MCP server over stdio")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings = Settings.from_environment()
    settings.ensure_directories()
    database = PromptDatabase(settings.database_path)

    if args.command == "init":
        database.initialize()
        _print_json({"status": "initialized", "database": str(settings.database_path)})
    elif args.command == "import":
        results = import_all(settings, database)
        _print_json({"status": "imported", "sources": results, "stats": database.stats()})
    elif args.command == "stats":
        database.initialize()
        _print_json(database.stats())
    elif args.command == "sources":
        database.initialize()
        _print_json(database.list_sources())
    elif args.command == "search":
        database.initialize()
        _print_json(
            database.search(
                args.query,
                kind=args.kind,
                source_id=args.source,
                model_family=args.model_family,
                safety=args.safety,
                limit=args.limit,
            )
        )
    elif args.command == "serve":
        uvicorn.run("prompt_hub.api:app", host=args.host, port=args.port, reload=False)
    elif args.command == "tag-image":
        model_root = args.model_root or settings.wd14_model_root
        try:
            result = tag_image(
                args.image,
                model_root=model_root,
                general_threshold=args.general_threshold,
                character_threshold=args.character_threshold,
                limit=args.limit,
                provider=args.provider,
            )
        except WD14Error as error:
            raise SystemExit(str(error)) from error
        _print_json(result)
    elif args.command == "mcp":
        run_mcp()


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
