from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi import Request as WebRequest
from fastapi.responses import FileResponse, HTMLResponse, Response

from prompt_hub.agent_package_runtime import AgentPackageRuntime, client_entry, package_path
from prompt_hub.studio_providers import ImageProviderStore, validate_provider_recipe
from prompt_hub.studio_routes import read_limited
from prompt_hub.studio_store import StudioError, StudioStore, now, write_json
from prompt_hub.web_resources import read_web_asset

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner
    from prompt_hub.model_connections import ModelConnectionStore
    from prompt_hub.studio_service import StudioService


MAX_ARCHIVE_NESTING = 2
MAX_ATTACHMENTS = 4
MAX_ATTACHMENT_BYTES = 8_000_000
MAX_CHAT_CHARS = 32000
MAX_CHAT_RESPONSE_BYTES = 4_000_000
MAX_PACKAGE_BYTES = 16_000_000
MAX_PACKAGE_FILES = 2000


class AgentWorkbench:
    """Persistent conversations, prompt packages, and installed package tools."""

    def __init__(self, root: Path, models: ModelConnectionStore, studio: StudioStore) -> None:
        self.root = root / "agent"
        self.models = models
        self.studio = studio
        self.lock = RLock()
        self.busy: set[str] = set()
        self.runtime = AgentPackageRuntime(self.root)
        self.providers = ImageProviderStore(root)

    def path(self, identifier: str) -> Path:
        if not re.fullmatch(r"chat-[a-f0-9]{32}", identifier):
            msg = "對話不存在"
            raise StudioError(msg)
        return self.root / "chats" / f"{identifier}.json"

    def read(self, identifier: str) -> dict[str, Any]:
        path = self.path(identifier)
        if not path.is_file():
            msg = "對話不存在"
            raise StudioError(msg)
        chat = json.loads(path.read_text(encoding="utf-8"))
        if chat.get("pending") and identifier not in self.busy:
            chat["pending"] = False
            chat["error"] = "上次回覆已中斷。訊息已保存，可以重試。"
            write_json(path, chat)
        return chat

    def create(self) -> dict[str, Any]:
        chat = {
            "id": "chat-" + uuid4().hex,
            "title": "新對話",
            "messages": [],
            "model": "",
            "packages": [],
            "updated_at": now(),
        }
        write_json(self.path(chat["id"]), chat)
        return chat

    def packages(self) -> list[dict[str, Any]]:
        packages = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.root / "packages").glob("*.json"))
        ]
        for package in packages:
            if package["kind"] == "dsh" and package["status"] == "adapter_required":
                self.configure_package(package)
            package["has_client"] = bool(client_entry(package))
            if package["has_client"] and "initial_projections" not in package:
                self.configure_package(package)
        return packages

    def configure_package(self, package: dict[str, Any]) -> None:
        if package["kind"] == "dsh":
            try:
                description = self.runtime.dsh(package)
                package.update(
                    status="ready",
                    instructions="\n\n".join(description["sections"]),
                    tools=description["tools"],
                    initial_projections=description["projections"],
                )
                package.pop("runtime_error", None)
            except StudioError as error:
                package.update(status="runtime_error", runtime_error=str(error))
        write_json(self.root / "packages" / (package["id"] + ".json"), package)

    def archive_files(self, raw: bytes, depth: int = 0) -> dict[str, str]:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if (
                len(entries) > MAX_PACKAGE_FILES
                or sum(item.file_size for item in entries) > MAX_PACKAGE_BYTES
            ):
                msg = "插件解壓後超過大小限制"
                raise StudioError(msg)
            nested = [item for item in entries if item.filename.lower().endswith(".zip")]
            if (
                not any(Path(item.filename).name.upper() == "SKILL.MD" for item in entries)
                and len(nested) == 1
                and depth < MAX_ARCHIVE_NESTING
            ):
                return self.archive_files(archive.read(nested[0]), depth + 1)
            files = {}
            for item in entries:
                if item.is_dir():
                    continue
                name = item.filename
                if not item.flag_bits & 0x800:
                    with contextlib.suppress(UnicodeEncodeError, UnicodeDecodeError):
                        name = name.encode("cp437").decode("gb18030")
                name = package_path(name)
                if Path(name).suffix.lower() not in {
                    ".md",
                    ".txt",
                    ".json",
                    ".js",
                    ".mjs",
                    ".py",
                    ".yml",
                    ".yaml",
                }:
                    continue
                content = archive.read(item)
                try:
                    files[name] = content.decode("utf-8-sig")
                except UnicodeDecodeError:
                    files[name] = content.decode("gb18030")
            skill = [name for name in files if Path(name).name.upper() == "SKILL.MD"]
            if len(skill) == 1:
                prefix = str(Path(skill[0]).parent).replace("\\", "/") + "/"
            else:
                roots = {name.split("/")[0] for name in files}
                prefix = (
                    next(iter(roots)) + "/"
                    if len(roots) == 1 and all("/" in name for name in files)
                    else ""
                )
            return {
                name.removeprefix(prefix): value
                for name, value in files.items()
                if not skill or name.startswith(prefix) or prefix == "./"
            }

    def install(self, raw: bytes, filename: str) -> dict[str, Any]:  # noqa: C901 - protocol validation and dispatch stay together
        suffix = Path(filename).suffix.lower()
        files: dict[str, str] = {}
        if suffix == ".zip":
            try:
                files = self.archive_files(raw)
            except zipfile.BadZipFile as error:
                msg = "無法讀取插件壓縮包"
                raise StudioError(msg) from error
        else:
            files[Path(filename).name] = raw.decode("utf-8-sig")
            if suffix in {".js", ".mjs"}:
                files["index" + suffix] = files.pop(Path(filename).name)
        skill_paths = [name for name in files if Path(name).name.upper() == "SKILL.MD"]
        markdown = skill_paths or [name for name in files if name.endswith((".md", ".txt"))]
        kind = "skill" if skill_paths else "preset"
        text = "\n\n".join(files[name] for name in markdown)
        if suffix == ".json":
            try:
                data = json.loads(raw)
                text = str(data.get("system_prompt") or data.get("content") or "")
                if not text and isinstance(data.get("prompts"), list):
                    text = "\n\n".join(
                        str(p.get("content", ""))
                        for p in data["prompts"]
                        if isinstance(p, dict) and p.get("enabled", True)
                    )
            except (ValueError, AttributeError) as error:
                msg = "預設 JSON 格式無效"
                raise StudioError(msg) from error
        if any(name.endswith((".js", ".mjs")) for name in files) and not skill_paths:
            kind = "dsh"
        if not text and kind != "dsh":
            msg = "未找到 SKILL.md 或可用的預設內容"
            raise StudioError(msg)
        title = Path(filename).stem
        match = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
        if match:
            title = match.group(1).strip("\"' ")
        package = {
            "id": "package-" + uuid4().hex,
            "title": title[:160],
            "kind": kind,
            "status": "ready",
            "instructions": text[:160000],
            "files": files,
            "installed_at": now(),
            "tool_files": [name for name in files if name.endswith((".py", ".js", ".mjs"))],
        }
        if "package.json" in files and kind == "dsh":
            manifest = json.loads(files["package.json"])
            package["title"] = manifest.get("dsh", {}).get("name") or manifest.get("name") or title
        self.configure_package(package)
        return package

    def chat(self, identifier: str, values: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if identifier in self.busy:
                raise HTTPException(409, "這個對話正在等待回覆")
            self.busy.add(identifier)
        try:
            return self._chat(identifier, values)
        finally:
            with self.lock:
                self.busy.discard(identifier)

    def package_tool(
        self, packages: list[dict[str, Any]], name: str, args: dict[str, Any], assets: list[str]
    ) -> Any:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
        package = next((item for item in packages if item["id"] == args.get("package_id")), None)
        if package is None:
            msg = "請先勾選這個插件"
            raise StudioError(msg)
        if name == "package_read_file":
            path = package_path(str(args.get("path", "")))
            text = package["files"].get(path)
            if text is None:
                msg = "插件檔案不存在"
                raise StudioError(msg)
            offset = max(0, int(args.get("offset", 0)))
            return {
                "path": path,
                "text": text[offset : offset + 32000],
                "next_offset": offset + 32000 if len(text) > offset + 32000 else None,
            }
        raw_arguments = args.get("arguments", [])
        if not isinstance(raw_arguments, list):
            msg = "工具參數需要字串列表"
            raise StudioError(msg)
        arguments = []
        for raw_argument in raw_arguments:
            argument = raw_argument
            if isinstance(argument, str) and argument.startswith("@image:"):
                try:
                    index = int(argument.split(":", 1)[1])
                    if index < 0:
                        raise IndexError  # noqa: TRY301 - validation uses the surrounding recovery and error normalization
                    image = self.studio.gallery.resolve_asset_path(assets[index])
                    if image is None:
                        msg = "附件原圖已離線"
                        raise StudioError(msg)
                    argument = str(image)
                except (IndexError, ValueError) as error:
                    msg = "圖片附件不存在"
                    raise StudioError(msg) from error
            arguments.append(argument)
        python = self.providers.public().get("caption_worker", {}).get("python", "")
        return self.runtime.script(package, {**args, "arguments": arguments}, python=python)

    def tool_catalog(
        self, packages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, tuple[dict[str, Any], str]]]:
        definitions = [
            {
                "name": "image_request",
                "description": "Propose image generation for explicit execution",
                "parameters": {
                    "type": "object",
                    "properties": {"prompt": {"type": "string"}, "negative": {"type": "string"}},
                    "required": ["prompt"],
                },
            },
        ]
        if packages:
            definitions.extend(
                [
                    {
                        "name": "package_read_file",
                        "description": (
                            "Read an installed package reference or source file. Use next_offs"
                            "et for longer files."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "package_id": {"type": "string"},
                                "path": {"type": "string"},
                                "offset": {"type": "integer", "minimum": 0},
                            },
                            "required": ["package_id", "path"],
                        },
                    },
                    {
                        "name": "package_run_script",
                        "description": (
                            "Run a script supplied by a selected package on CPU. Pass CLI argu"
                            "ments as strings. Use @image:0 for the first current image attach"
                            "ment. stdout, stderr and returncode are returned."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "package_id": {"type": "string"},
                                "entrypoint": {"type": "string"},
                                "arguments": {"type": "array", "items": {"type": "string"}},
                                "stdin": {"type": "string"},
                            },
                            "required": ["package_id", "entrypoint"],
                        },
                    },
                ]
            )
        native = {}
        for index, package in enumerate(packages):
            if package["kind"] != "dsh":
                continue
            for tool in package.get("tools", []):
                name = ("plugin_" + str(index) + "_" + re.sub(r"[^a-zA-Z0-9_]", "_", tool["name"]))[
                    :64
                ]
                definitions.append({**tool, "name": name})
                native[name] = (package, tool["name"])
        return [{"type": "function", "function": definition} for definition in definitions], native

    def _chat(self, identifier: str, values: dict[str, Any]) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915 - protocol validation and dispatch stay together
        chat = self.read(identifier)
        if (
            values.get("retry")
            and chat.get("error")
            and chat["messages"]
            and chat["messages"][-1]["role"] == "user"
        ):
            failed = chat["messages"].pop()
            values = {**values, "assets": failed.get("assets", [])}
        connection = self.models.resolve(str(values.get("model", "")))
        if connection is None:
            msg = "請先在設定接入並啟用聊天模型"
            raise StudioError(msg)
        text = str(values.get("text", "")).strip()
        if not text or len(text) > MAX_CHAT_CHARS:
            msg = "請填寫不超過 32000 字的訊息"
            raise StudioError(msg)
        selected = values.get("packages", [])
        packages = [p for p in self.packages() if p["id"] in selected and p["status"] == "ready"]
        system = (
            "You are Soda's image creation assistant. Help write, revise and analyze prompts. "
            "Respect the user's chosen image model. Return copyable prompts. "
            "When asked to generate an image, provide an image_request tool call. "
            "This proposes a task; the user executes it with a visible button. "
            "Never claim an image was generated before a tool result exists.\n\n"
        ) + "\n\n".join(p["instructions"] for p in packages)
        system += (
            "\nInstalled package files follow. Read the referenced guides before using a skill. "
            + json.dumps(
                [
                    {
                        "package_id": package["id"],
                        "title": package["title"],
                        "files": list(package["files"]),
                        "scripts": package["tool_files"],
                    }
                    for package in packages
                ],
                ensure_ascii=False,
            )
        )
        attachments = values.get("assets", [])
        if not isinstance(attachments, list) or len(attachments) > MAX_ATTACHMENTS:
            msg = "每次最多加入四張圖片"
            raise StudioError(msg)
        if attachments and not connection.supports_vision:
            msg = "所選模型未啟用看圖能力"
            raise StudioError(msg)
        user: dict[str, Any] = {"role": "user", "content": text, "assets": attachments}
        chat["messages"].append(user)
        chat.update(
            model=connection.connection_id, packages=[p["id"] for p in packages], updated_at=now()
        )
        if len(chat["messages"]) == 1:
            chat["title"] = text[:48]
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for item in chat["messages"][-40:]:
            content: Any = item["content"]
            if item.get("tools"):
                content += "\nPackage tool results\n" + json.dumps(
                    item["tools"], ensure_ascii=False
                )
            if item.get("assets"):
                content = [{"type": "text", "text": content}]
                for asset_id in item["assets"]:
                    path = self.studio.gallery.resolve_asset_path(str(asset_id))
                    if path is None:
                        msg = "附件原圖已離線"
                        raise StudioError(msg)
                    if path.stat().st_size > MAX_ATTACHMENT_BYTES:
                        msg = "聊天附件需要小於 8 MB"
                        raise StudioError(msg)
                    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(
                        path.suffix.lower(), "image/png"
                    )
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,"
                                + base64.b64encode(path.read_bytes()).decode()
                            },
                        }
                    )
            messages.append({"role": item["role"], "content": content})
        tools, native_tools = self.tool_catalog(packages)
        payload = {
            "model": connection.model_name,
            "messages": messages,
            "stream": False,
            "tools": tools,
        }
        headers = {"Content-Type": "application/json"}
        if connection.api_key:
            headers["Authorization"] = "Bearer " + connection.api_key
        chat["pending"] = True
        write_json(self.path(identifier), chat)
        try:
            proposals = []
            executed = []
            for _ in range(12):
                request = Request(  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
                    connection.base_url.rstrip("/") + "/chat/completions",
                    data=json.dumps(payload).encode(),
                    headers=headers,
                )
                with urlopen(request, timeout=180) as response:  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
                    raw = response.read(4_000_001)
                if len(raw) > MAX_CHAT_RESPONSE_BYTES:
                    msg = "模型回覆超過大小限制"
                    raise StudioError(msg)  # noqa: TRY301 - validation uses the surrounding recovery and error normalization
                reply = json.loads(raw)["choices"][0]["message"]
                calls = reply.get("tool_calls", [])
                if not calls:
                    break
                assistant_message = {
                    "role": "assistant",
                    "content": reply.get("content"),
                    "tool_calls": calls,
                }
                if reply.get("reasoning_content") is not None:
                    assistant_message["reasoning_content"] = reply["reasoning_content"]
                messages.append(assistant_message)
                only_images = True
                for call in calls:
                    name = call.get("function", {}).get("name", "")
                    args = {}
                    if name != "image_request":
                        only_images = False
                    try:
                        args = json.loads(call["function"]["arguments"])
                        if not isinstance(args, dict):
                            msg = "工具參數需要 JSON 物件"
                            raise StudioError(msg)  # noqa: TRY301 - validation uses the surrounding recovery and error normalization
                        if name == "image_request":
                            if not isinstance(args.get("prompt"), str):
                                msg = "生圖提案缺少提示詞"
                                raise StudioError(msg)  # noqa: TRY301 - validation uses the surrounding recovery and error normalization
                            proposal = {
                                "prompt": args["prompt"][:32000],
                                "negative": str(args.get("negative", ""))[:32000],
                            }
                            if proposal not in proposals:
                                proposals.append(proposal)
                            result = {"status": "proposal_ready", "execution": "user_button"}
                        elif name in native_tools:
                            only_images = False
                            package, tool_name = native_tools[name]
                            result = self.runtime.dsh(
                                package, operation="execute", tool=tool_name, arguments=args
                            )["result"]
                        elif name in {"package_read_file", "package_run_script"}:
                            only_images = False
                            result = self.package_tool(packages, name, args, attachments)
                        else:
                            msg = "工具不存在"
                            raise StudioError(msg)  # noqa: TRY301 - validation uses the surrounding recovery and error normalization
                    except (StudioError, ValueError, KeyError, TypeError) as error:
                        result = {"error": str(error)}
                    if name != "image_request":
                        executed.append({"name": name, "arguments": args, "result": result})
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                if only_images:
                    break
            else:
                reply = {"content": "工具執行記錄已保存，可繼續下一則訊息。"}
            chat["messages"].append(
                {
                    "role": "assistant",
                    "content": str(reply.get("content") or ""),
                    "proposals": proposals,
                    "tools": executed,
                }
            )
            chat["plugin_states"] = []
            events = [
                {
                    "type": item["role"] + "/message",
                    "data": {"message": {"content": [{"type": "text", "text": item["content"]}]}},
                }
                for item in chat["messages"][-40:]
            ]
            for package in packages:
                if package["kind"] == "dsh":
                    try:
                        description = self.runtime.dsh(package, events=events)
                        chat["plugin_states"].append(
                            {
                                "package_id": package["id"],
                                "title": package["title"],
                                "projections": description["projections"],
                            }
                        )
                    except StudioError as error:
                        chat["plugin_states"].append(
                            {"title": package["title"], "error": str(error)}
                        )
            chat.pop("error", None)
        except Exception as error:
            chat["error"] = "模型請求失敗。訊息已保存，請檢查連線後重試。"
            raise StudioError(chat["error"]) from error
        finally:
            chat["pending"] = False
            chat["updated_at"] = now()
            write_json(self.path(identifier), chat)
        return chat

    def prepare_image(
        self, service: StudioService, identifier: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve a visible proposal once; re-clicks return the same persisted jobs."""
        with self.lock:
            chat = self.read(identifier)
            try:
                index = int(values["message_index"])
                proposal_index = int(values["proposal_index"])
                if min(index, proposal_index) < 0:
                    raise IndexError  # noqa: TRY301 - validation uses the surrounding recovery and error normalization
                message = chat["messages"][index]
                if message["role"] != "assistant":
                    raise IndexError  # noqa: TRY301 - validation uses the surrounding recovery and error normalization
                proposal = message["proposals"][proposal_index]
            except (ValueError, TypeError, KeyError, IndexError) as error:
                msg = "生圖提案不存在"
                raise StudioError(msg) from error
            if proposal.get("job_ids"):
                return {"job_ids": proposal["job_ids"]}
            provider_id = str(values.get("provider_id", ""))
            public = next(
                (p for p in service.providers.public()["providers"] if p["id"] == provider_id), None
            )
            if public is None:
                msg = "請先接入圖片 API"
                raise StudioError(msg)
            provider = service.providers.require(provider_id, public["kind"])
            draft = service.store.generation_draft("agent-" + provider["kind"])
            recipe = {
                **draft["studio"],
                "body": proposal["prompt"],
                "prefix": "",
                "suffix": "",
                "negative": proposal.get("negative", ""),
                "provider_id": provider_id,
                "model": provider["model"],
                "text_mode": "manual",
                "count": 1,
                "locks": {},
                "prefix_rows": [],
                "creation_origin": "agent",
                "agent_chat_id": identifier,
            }
            attachments = next(
                (
                    m.get("assets", [])
                    for m in reversed(chat["messages"][:index])
                    if m["role"] == "user"
                ),
                [],
            )
            if provider["kind"] == "openai":
                recipe.update(width=1024, height=1536)
            elif attachments:
                recipe["novelai_mode"] = "img2img"
            references = []
            for asset_id in attachments:
                path = service.store.gallery.resolve_asset_path(asset_id)
                if path is None:
                    msg = "附件原圖已離線"
                    raise StudioError(msg)
                image = service.store.add_image(
                    draft["project_id"],
                    path.read_bytes(),
                    path.name,
                    kind="reference",
                    role="identity",
                )
                references.append({"item_id": image["item_id"], "role": "identity"})
            validate_provider_recipe(
                provider,
                recipe,
                [
                    (item["role"], service.store.image_path(draft["project_id"], item["item_id"]))
                    for item in references
                ],
            )
            service.store.save_project(draft["project_id"], {"studio": recipe})
            prompt = service.prepare(draft["project_id"])[0]
            preview_id = (
                "preview-"
                + hashlib.sha256(f"{identifier}:{index}:{proposal_index}".encode()).hexdigest()[:32]
            )
            jobs = service.store.enqueue_batch(
                preview_id,
                draft["project_id"],
                [
                    {
                        "project_id": draft["project_id"],
                        "recipe": recipe,
                        "prompt": prompt,
                        "references": references,
                        "graph_digest": "",
                        "preview_id": preview_id,
                    }
                ],
            )
            proposal["job_ids"] = jobs
            proposal["provider_id"] = provider_id
            write_json(self.path(identifier), chat)
            return {"job_ids": jobs}


def create_agent_router(  # noqa: C901 - FastAPI route registration aggregates nested handlers
    agent: AgentWorkbench,
    providers: ImageProviderStore,
    service: StudioService,
    runner: BackgroundJobRunner,
) -> APIRouter:
    router = APIRouter(prefix="/api/agent")
    catalog = {
        "fujiang": {"title": "富江", "repository": "c3cvld7aag/fujiang-dsh"},
        "nai5": {"title": "NAI5 Prompt Expert", "repository": "moudanji/NAI5-SKILL"},
        "anima": {"title": "Anima Tagger", "repository": "Vincent54122/anima-tagger"},
    }

    @router.get("/bootstrap")
    def bootstrap() -> dict[str, Any]:
        chats = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (agent.root / "chats").glob("*.json")
        ]
        return {
            "chats": [
                {key: c[key] for key in ("id", "title", "updated_at")}
                for c in sorted(chats, key=lambda c: c["updated_at"], reverse=True)
            ],
            "packages": [
                {
                    key: p.get(key)
                    for key in (
                        "id",
                        "title",
                        "kind",
                        "status",
                        "tool_files",
                        "runtime_error",
                        "tools",
                        "has_client",
                        "initial_projections",
                    )
                }
                for p in agent.packages()
            ],
            "models": agent.models.list_model_options(),
            "providers": providers.public()["providers"],
            "catalog": [{"id": key, **value} for key, value in catalog.items()],
        }

    @router.get("/client-react.js")
    def client_react() -> FileResponse:
        return FileResponse(
            Path(__file__).parent / "web_assets/agent_react.js", media_type="application/javascript"
        )

    def client_package(identifier: str) -> tuple[dict[str, Any], str]:
        package = next((item for item in agent.packages() if item["id"] == identifier), None)
        if package is None or not client_entry(package):
            raise HTTPException(404, "插件沒有前端入口")
        return package, client_entry(package)

    @router.get("/packages/{identifier}/client")
    def client_panel(identifier: str) -> HTMLResponse:
        client_package(identifier)
        page = read_web_asset("agent_client.html").replace(
            "__CLIENT_SOURCE__", "/api/agent/packages/" + identifier + "/client-code"
        )
        return HTMLResponse(
            page,
            headers={
                "Content-Security-Policy": (
                    "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src "
                    "'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'non"
                    "e'"
                )
            },
        )

    @router.get("/packages/{identifier}/client-code")
    def client_code(identifier: str) -> Response:
        package, entry = client_package(identifier)
        return Response(package["files"][entry], media_type="application/javascript")

    @router.post("/packages/catalog/{name}", status_code=201)
    def install_catalog(name: str) -> dict[str, Any]:
        if name not in catalog:
            raise HTTPException(404, "預設不存在")
        existing = next(
            (package for package in agent.packages() if package.get("catalog_id") == name), None
        )
        if existing:
            return {
                key: value
                for key, value in existing.items()
                if key not in {"files", "instructions"}
            }
        repository = catalog[name]["repository"]
        request = Request(
            "https://api.github.com/repos/" + repository + "/zipball/HEAD",
            headers={"User-Agent": "Soda-Prompt-Hub"},
        )
        try:
            with urlopen(request, timeout=60) as response:  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
                raw = response.read(16_000_001)
            if len(raw) > MAX_PACKAGE_BYTES:
                msg = "插件壓縮包超過大小限制"
                raise StudioError(msg)
            package = agent.install(raw, name + ".zip")
        except OSError as error:
            msg = "預設下載失敗，請稍後重試"
            raise StudioError(msg) from error
        package.update(catalog_id=name, source_url="https://github.com/" + repository)
        write_json(agent.root / "packages" / (package["id"] + ".json"), package)
        return {
            key: value for key, value in package.items() if key not in {"files", "instructions"}
        }

    @router.post("/packages/{identifier}/tools")
    def execute_package_tool(identifier: str, values: dict[str, Any]) -> dict[str, Any]:
        package = next(
            (package for package in agent.packages() if package["id"] == identifier), None
        )
        if not package or package["status"] != "ready":
            msg = "插件尚未就緒"
            raise StudioError(msg)
        if package["kind"] == "dsh":
            return {
                "result": agent.runtime.dsh(
                    package,
                    operation="execute",
                    tool=values.get("tool", ""),
                    arguments=values.get("arguments", {}),
                )["result"]
            }
        return agent.package_tool(
            [package], "package_run_script", {**values, "package_id": identifier}, []
        )

    @router.post("/chats", status_code=201)
    def create() -> dict[str, Any]:
        return agent.create()

    @router.get("/chats/{identifier}")
    def get(identifier: str) -> dict[str, Any]:
        return agent.read(identifier)

    @router.post("/chats/{identifier}/messages")
    def message(identifier: str, values: dict[str, Any]) -> dict[str, Any]:
        return agent.chat(identifier, values)

    @router.post("/chats/{identifier}/generate", status_code=202)
    def generate(identifier: str, values: dict[str, Any]) -> dict[str, Any]:
        result = agent.prepare_image(service, identifier, values)
        runner.wake()
        return result

    @router.post("/packages", status_code=201)
    async def install(request: WebRequest, filename: str = "SKILL.md") -> dict[str, Any]:
        package = agent.install(await read_limited(request, 16_000_000), filename)
        return {
            key: value for key, value in package.items() if key not in {"files", "instructions"}
        }

    return router
