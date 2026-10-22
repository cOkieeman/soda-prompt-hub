from __future__ import annotations

import multiprocessing
from pathlib import Path
from threading import Event, Thread

import pytest
from soda_storyboard.server.common import APIError

from prompt_hub.storyboard import StoryboardConflictError, StoryboardStore
from prompt_hub.storyboard_editor_server import SafeEditorStore
from prompt_hub.storyboard_lock import project_file_lock


def _editor_process(root_text, locked, release, results):
    root = Path(root_text)
    try:
        with project_file_lock(root.parent.parent / "locks" / f"{root.name}.lock"):
            editor = SafeEditorStore(root)
            current = editor.page("one")
            current["page"]["description"] = "编辑器中的人工修改"
            locked.set()
            if not release.wait(10):
                results.put("release timed out")
                return
            editor.save("one", current["page"], current["version"])
        results.put("saved")
    except (ValueError, TypeError, OSError, APIError) as error:
        results.put(repr(error))


def test_editor_process_and_hub_share_lock_and_reject_stale_confirmation(settings):
    store = StoryboardStore(settings)
    store.initialize()
    store.create_project("并发测试", "race")
    before = store.create_page("race", {"id": "one"})
    context = multiprocessing.get_context("spawn")
    locked = context.Event()
    release = context.Event()
    results = context.Queue()
    process = context.Process(
        target=_editor_process,
        args=(str(store.project_path("race")), locked, release, results),
    )
    process.start()
    completed = Event()
    observed = []

    def confirm_preview():
        try:
            store.save_page(
                "race",
                "one",
                {**before["page"], "description": "过期的 AI 方案"},
                before["version"],
            )
        except StoryboardConflictError:
            observed.append("conflict")
        finally:
            completed.set()

    thread = Thread(target=confirm_preview)
    try:
        assert locked.wait(10)
        thread.start()
        assert not completed.wait(0.15)
        release.set()
        assert completed.wait(10)
        process.join(timeout=10)
        assert process.exitcode == 0
        assert results.get(timeout=2) == "saved"
        assert observed == ["conflict"]
        assert store.get_page("race", "one")["page"]["description"] == "编辑器中的人工修改"
    finally:
        release.set()
        if thread.ident is not None:
            thread.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        results.close()


def test_project_lock_is_reentrant_and_outside_core_project(settings):
    store = StoryboardStore(settings)
    store.initialize()
    store.create_project("可重入锁", "nested")
    with store.project_lock("nested"), store.project_lock("nested"):
        store.create_page("nested", {"id": "one"})
        assert store.get_project("nested")["pages"][0]["id"] == "one"
    assert (store.root / "locks" / "nested.lock").is_file()
    assert not list(store.project_path("nested").rglob("*.lock"))
    store.delete_project("nested")
    assert (store.root / "locks" / "nested.lock").is_file()


def test_lock_rejects_hardlinked_sidecar(tmp_path):
    source = tmp_path / "ordinary.lock"
    source.write_bytes(b"\0")
    target = tmp_path / "linked.lock"
    try:
        target.hardlink_to(source)
    except OSError:
        pytest.skip("hardlinks unavailable")
    with pytest.raises(ValueError, match="普通非链接"), project_file_lock(target):
        pytest.fail("linked lock should not be acquired")
