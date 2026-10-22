from __future__ import annotations

import json
from http.client import HTTPConnection
from threading import Thread
from types import SimpleNamespace

import pytest
from soda_storyboard import edit
from soda_storyboard.server import app as core_app

from prompt_hub.storyboard import StoryboardStore
from prompt_hub.storyboard_editor import StoryboardEditorManager
from prompt_hub.storyboard_editor_server import (
    SafeEditorHandler,
    SafeEditorStore,
    create_server,
    worker_only,
)


@pytest.fixture
def editor_project(settings):
    store = StoryboardStore(settings)
    store.initialize()
    store.create_project("编辑器测试", "editor")
    store.create_page("editor", {"id": "first"})
    return store


def test_editor_manager_reuse_stop_and_cleanup(editor_project, monkeypatch):
    manager = StoryboardEditorManager(editor_project)
    root = editor_project.project_path("editor")
    info = {
        "service": "soda-storyboard",
        "project_dir": str(root),
        "instance_id": "unique",
        "pid": 999,
    }
    waits = []
    process = SimpleNamespace(wait=lambda **options: waits.append(options), poll=lambda: None)
    active = {}

    def launch(_root):
        active.update(info)
        return process, 8888, info

    def health(port):
        return dict(active) if port == 8888 else {}

    def stop(_root, state):
        active.clear()
        state.unlink(missing_ok=True)
        return {"stopped": True}

    monkeypatch.setattr(manager, "_launch", launch)
    monkeypatch.setattr(edit, "health", health)
    monkeypatch.setattr(edit, "stop", stop)
    started = manager.start("editor", "first")
    assert started["url"] == "http://127.0.0.1:8888/#page=first"
    assert started["reused"] is False
    assert manager.start("editor")["reused"] is True
    manager.close()
    assert not manager.instances
    assert waits == [{"timeout": 5}]
    assert manager.stop("editor") == {"stopped": False}


def test_editor_never_reuses_or_stops_foreign_instances(editor_project, monkeypatch):
    manager = StoryboardEditorManager(editor_project)
    root = editor_project.project_path("editor")
    foreign = {"project_dir": str(root), "instance_id": "foreign", "pid": 111}
    edit.write_state(root / ".soda" / "server.json", 8888, foreign)
    monkeypatch.setattr(edit, "health", lambda _port: foreign)
    with pytest.raises(ValueError, match="外部编辑器"):
        manager.start("editor")
    assert manager.stop("editor") == {"stopped": False}


def test_unreachable_health_preserves_live_handle_and_close_reaps_it(editor_project, monkeypatch):
    manager = StoryboardEditorManager(editor_project)
    root = editor_project.project_path("editor")
    info = {"project_dir": str(root), "instance_id": "owned", "pid": 999}
    running = [True]
    calls = []

    def terminate():
        calls.append("terminate")
        running[0] = False

    process = SimpleNamespace(
        poll=lambda: None if running[0] else 0,
        wait=lambda **_options: calls.append("wait"),
        terminate=terminate,
        kill=terminate,
    )

    def launch(_root):
        calls.append("launch")
        return process, 8888, info

    monkeypatch.setattr(manager, "_launch", launch)
    monkeypatch.setattr(edit, "health", lambda _port: {})
    manager.start("editor")
    with pytest.raises(ValueError, match="暂不可达"):
        manager.start("editor")
    assert manager.instances["editor"]["process"] is process
    assert calls == ["launch"]
    manager.close()
    assert calls == ["launch", "terminate", "wait"]
    assert manager.instances == {}


def test_mismatched_health_only_closes_owned_process_handle(editor_project, monkeypatch):
    manager = StoryboardEditorManager(editor_project)
    root = editor_project.project_path("editor")
    calls = []
    process = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: calls.append("terminate-owned"),
        wait=lambda **_options: calls.append("wait-owned"),
    )
    manager.instances["editor"] = {
        "port": 8888,
        "info": {"project_dir": str(root), "instance_id": "owned", "pid": 999},
        "process": process,
    }
    monkeypatch.setattr(
        edit,
        "health",
        lambda _port: {"project_dir": str(root), "instance_id": "foreign", "pid": 111},
    )

    def forbidden_stop(*_args):
        pytest.fail("must not signal a PID from mismatched health")

    monkeypatch.setattr(edit, "stop", forbidden_stop)
    assert manager.stop("editor") == {"stopped": False, "process_closed": True}
    assert calls == ["terminate-owned", "wait-owned"]
    assert manager.instances == {}


def test_safe_core_editor_serves_wheel_ui_and_rejects_unsafe_writes(editor_project, monkeypatch):
    root = editor_project.project_path("editor")
    # Restore module hooks after this in-process test; production runs in a subprocess.
    monkeypatch.setattr(core_app, "Store", core_app.Store)
    monkeypatch.setattr(core_app, "Handler", core_app.Handler)
    monkeypatch.setattr(core_app, "production", core_app.production)
    server = create_server(root)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        with editor_project.project_lock("editor"):
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            assert response.status == 200
            response.read()
        connection.request("GET", "/")
        response = connection.getresponse()
        assert response.status == 200
        assert b"<!doctype html" in response.read().lower()
        connection.request(
            "POST",
            "/api/pages",
            json.dumps({"id": "unsafe", "canvas_width": 999_999}),
            {"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        assert response.status == 400
        response.read()
        assert not (root / "pages" / "unsafe.json").exists()
        connection.close()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request("GET", "/api/project", headers={"Origin": "http://localhost:5173"})
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        assert core_app.Store is SafeEditorStore
        assert core_app.Handler is SafeEditorHandler
        assert core_app.production is worker_only
        with pytest.raises(core_app.APIError, match="Worker"):
            core_app.production()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_safe_editor_store_checks_unsaved_draft_and_project_limits(editor_project):
    store = SafeEditorStore(editor_project.project_path("editor"))
    with pytest.raises(ValueError, match="分镜画布"):
        store.patch_project({"default_canvas_width": 999_999})
    with pytest.raises(ValueError, match="分镜文件必须"):
        store.render_page(
            "first", raw={"id": "first", "production": {"selected_render": "../secret.png"}}
        )
    with pytest.raises(ValueError, match="分镜数字"):
        store.checked({"id": "invalid", "canvas_width": float("inf")})
