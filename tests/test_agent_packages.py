from __future__ import annotations

import io
import json
import zipfile

import pytest

from prompt_hub.agent_workbench import AgentWorkbench
from prompt_hub.background_jobs import BackgroundJobStore
from prompt_hub.creative import CreativeStore
from prompt_hub.gallery import GalleryStore
from prompt_hub.model_connections import ModelConnectionStore
from prompt_hub.studio_store import StudioError, StudioStore


@pytest.fixture
def store(settings):
    projects = CreativeStore(settings.database_path)
    projects.initialize()
    gallery = GalleryStore(settings)
    gallery.initialize()
    BackgroundJobStore(settings.database_path).initialize()
    result = StudioStore(settings, projects, gallery)
    result.initialize()
    return result


def archive(files):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)
    return raw.getvalue()


@pytest.mark.parametrize("ending", ["\n", "\r\n"])
def test_materialized_package_keeps_original_line_endings_and_repairs_old_copies(
    settings, store, ending
):
    agent = AgentWorkbench(settings.library_root, ModelConnectionStore(settings), store)
    original = ending.join(["第一行", "second line", ""])
    package = agent.install(archive({"SKILL.md": original}), "line-endings.zip")
    root = agent.runtime.materialize(package)
    target = root / "SKILL.md"
    assert target.read_bytes() == original.encode("utf-8")
    target.write_bytes(b"old materialized copy\r\n")
    agent.runtime.materialize(package)
    assert target.read_bytes() == original.encode("utf-8")


def test_nested_skill_archive_preserves_reference_paths(settings, store):
    agent = AgentWorkbench(settings.library_root, ModelConnectionStore(settings), store)
    nested = archive(
        {
            "外層/skill/SKILL.md": "---\nname: example\n---\nRead references/構圖.md",
            "外層/skill/references/構圖.md": "構圖指南",
        }
    )
    package = agent.install(
        archive({"repository/README.md": "readme", "repository/skill.zip": nested}), "repo.zip"
    )
    assert package["instructions"].endswith("Read references/構圖.md")
    result = agent.package_tool(
        [package],
        "package_read_file",
        {"package_id": package["id"], "path": "references/構圖.md"},
        [],
    )
    assert result["text"] == "構圖指南"


@pytest.mark.parametrize(
    "name", ["../outside.py", "/outside.py", "C:/outside.py", "folder/../../outside.py"]
)
def test_package_rejects_paths_outside_its_directory(settings, store, name):
    agent = AgentWorkbench(settings.library_root, ModelConnectionStore(settings), store)
    with pytest.raises(StudioError, match="路徑"):
        agent.install(archive({"SKILL.md": "test", name: "test"}), "bad.zip")


def test_skill_script_runs_on_request_and_returns_cpu_output(settings, store):
    agent = AgentWorkbench(settings.library_root, ModelConnectionStore(settings), store)
    package = agent.install(
        archive(
            {
                "SKILL.md": "---\nname: echo\n---\nUse tools/echo.py",
                "tools/echo.py": (
                    "import json, os, sys\n"
                    "print(json.dumps({'input':sys.stdin.read(),'args':sys.argv[1:],"
                    "'cuda':os.environ['CUDA_VISIBLE_DEVICES']}))"
                ),
            }
        ),
        "echo.zip",
    )
    assert not (agent.root / "runtime" / package["id"]).exists()
    result = agent.package_tool(
        [package],
        "package_run_script",
        {
            "package_id": package["id"],
            "entrypoint": "tools/echo.py",
            "arguments": ["one argument", "中文"],
            "stdin": "test",
        },
        [],
    )
    assert result["returncode"] == 0
    assert json.loads(result["stdout"]) == {
        "input": "test",
        "args": ["one argument", "中文"],
        "cuda": "",
    }
    with pytest.raises(StudioError, match="勾選"):
        agent.package_tool([], "package_run_script", {"package_id": package["id"]}, [])


def test_dsh_registers_sections_tools_and_session_projection(settings, store):
    agent = AgentWorkbench(settings.library_root, ModelConnectionStore(settings), store)
    package = agent.install(
        archive(
            {
                "plugin/package.json": json.dumps({"type": "module", "main": "index.js"}),
                "plugin/index.js": """
export function apply(ctx) {
  ctx.effect(()=>ctx.systemPrompt.section({name:'test',text:'Plugin instruction',order:10}));
  ctx.tools.register({name:'sum',parameters:{type:'object',properties:{number:{type:'number'}}},execute:args=>({total:args.number+1})});
  ctx.get('sessionProjections').register({key:'count',init:()=>0,apply:(state,event)=>state+1,wire:{view:state=>state}});
}
""",
            }
        ),
        "plugin.zip",
    )
    assert package["status"] == "ready"
    assert package["instructions"] == "Plugin instruction"
    assert package["tools"][0]["name"] == "sum"
    description = agent.runtime.dsh(
        package,
        operation="execute",
        tool="sum",
        arguments={"number": 4},
        events=[{"type": "user/message"}],
    )
    assert description["result"] == {"total": 5}
    assert description["projections"] == {"count": 1}


def test_chat_runs_package_tool_then_passes_result_back_to_the_model(settings, store, monkeypatch):
    models = ModelConnectionStore(settings)
    endpoint = models.save_endpoint(
        {
            "label": "test",
            "provider": "openai_compatible",
            "base_url": "https://example.test/v1",
            "api_key": "test-only",
        }
    )
    models.save_endpoint_models(endpoint["id"], [{"name": "test", "enabled": True}])
    agent = AgentWorkbench(settings.library_root, models, store)
    package = agent.install(
        archive({"SKILL.md": "Use tool.py", "tool.py": "print('verified CPU result')"}), "skill.zip"
    )
    requests = []

    def reply(request, **_kwargs):
        payload = json.loads(request.data)
        requests.append(payload)
        message = {"content": "Validated"}
        if len(requests) == 1:
            message = {
                "content": "",
                "reasoning_content": "Tool selection reasoning",
                "tool_calls": [
                    {
                        "id": "tool-1",
                        "type": "function",
                        "function": {
                            "name": "package_run_script",
                            "arguments": json.dumps(
                                {"package_id": package["id"], "entrypoint": "tool.py"}
                            ),
                        },
                    }
                ],
            }
        return io.BytesIO(json.dumps({"choices": [{"message": message}]}).encode())

    monkeypatch.setattr("prompt_hub.agent_workbench.urlopen", reply)
    chat = agent.create()
    result = agent.chat(
        chat["id"],
        {
            "text": "Run the validator",
            "model": models.list_model_options()[0]["id"],
            "packages": [package["id"]],
        },
    )
    assert len(requests) == 2
    assert requests[1]["messages"][-1]["role"] == "tool"
    assert requests[1]["messages"][-2]["reasoning_content"] == "Tool selection reasoning"
    assert "verified CPU result" in requests[1]["messages"][-1]["content"]
    assert result["messages"][-1]["content"] == "Validated"
    assert result["messages"][-1]["tools"][0]["result"]["returncode"] == 0
    assert agent.read(chat["id"])["messages"][-1]["tools"]


def test_chat_projection_receives_dsh_text_content_blocks(settings, store, monkeypatch):
    models = ModelConnectionStore(settings)
    endpoint = models.save_endpoint(
        {
            "label": "test",
            "provider": "openai_compatible",
            "base_url": "https://example.test/v1",
            "api_key": "test-only",
        }
    )
    models.save_endpoint_models(endpoint["id"], [{"name": "test", "enabled": True}])
    agent = AgentWorkbench(settings.library_root, models, store)
    package = agent.install(
        archive(
            {
                "plugin/package.json": json.dumps({"type": "module", "main": "index.js"}),
                "plugin/index.js": """
export function apply(ctx) {
  ctx.get('sessionProjections').register({key:'reply',init:()=>'',apply:(state,event)=>event.type==='assistant/message'?event.data.message.content[0].text:state,wire:{view:state=>state}});
}
""",
            }
        ),
        "plugin.zip",
    )
    monkeypatch.setattr(
        "prompt_hub.agent_workbench.urlopen",
        lambda *_args, **_kwargs: io.BytesIO(
            json.dumps({"choices": [{"message": {"content": "Completed"}}]}).encode()
        ),
    )
    chat = agent.create()
    result = agent.chat(
        chat["id"],
        {"text": "Run", "model": models.list_model_options()[0]["id"], "packages": [package["id"]]},
    )
    assert result["plugin_states"][0]["projections"] == {"reply": "Completed"}
