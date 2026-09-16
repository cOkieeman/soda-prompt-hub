from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prompt_hub.dataset_workspace as workspace_module
from prompt_hub.api import create_app
from prompt_hub.dataset_workspace import DatasetWorkspaceError, DatasetWorkspaceStore


@pytest.fixture
def store(settings) -> DatasetWorkspaceStore:
    return DatasetWorkspaceStore(settings)


@pytest.fixture
def scoped_home(monkeypatch, tmp_path) -> Path:
    home = tmp_path.resolve()
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    volumes = tmp_path / "Volumes"
    volumes.mkdir()
    roots = [home, *sorted((volumes / name).resolve() for name in ("Vol-A", "Vol-B"))]
    for root in roots[1:]:
        root.mkdir()
    monkeypatch.setattr("prompt_hub.dataset_workspace.browse_roots", lambda: roots)
    return tmp_path


def _image_files(directory: Path, count: int, suffix: str = ".jpg") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for number in range(count):
        (directory / f"img-{number:03d}{suffix}").write_bytes(b"x")


def test_browse_rejects_paths_outside_scope(store, scoped_home) -> None:
    with pytest.raises(DatasetWorkspaceError, match="浏览范围"):
        store.browse_directory("/")
    with pytest.raises(DatasetWorkspaceError, match="浏览范围"):
        store.browse_directory(scoped_home.parent)
    with pytest.raises(DatasetWorkspaceError, match="不存在"):
        store.browse_directory(scoped_home / "missing-dir")


def test_browse_roots_response_lists_home_and_volumes(store, scoped_home) -> None:
    payload = store.browse_directory(None)
    assert payload["path"] == ""
    assert payload["crumbs"] == []
    names = [entry["name"] for entry in payload["entries"]]
    assert names == [scoped_home.name, "Vol-A", "Vol-B"]
    quick_labels = [entry["label"] for entry in payload["quick"]]
    assert quick_labels[:1] == ["主目录"]
    assert "Vol-A" in quick_labels
    assert "Vol-B" in quick_labels
    home_entry = payload["entries"][0]
    assert home_entry["selectable"] is False
    assert "主目录" in home_entry["reason"]
    assert payload["entries"][1]["selectable"] is True


def test_home_shortcuts_skip_xdg_directories_disabled_as_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    config = home / ".config"
    config.mkdir(parents=True)
    (config / "user-dirs.dirs").write_text(
        'XDG_DESKTOP_DIR="$HOME/"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    assert workspace_module.home_shortcuts(home) == []


def test_browse_quick_entries_only_include_reachable_xdg_paths(
    store: DatasetWorkspaceStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    volume = tmp_path / "mounts" / "disk"
    mounted_pictures = volume / "pictures"
    outside = tmp_path / "outside-pictures"
    config = home / ".config"
    for directory in (mounted_pictures, outside, config):
        directory.mkdir(parents=True)
    user_dirs = config / "user-dirs.dirs"
    roots = [home.resolve(), volume.resolve()]
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.setattr(workspace_module, "browse_roots", lambda: roots)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    user_dirs.write_text(f'XDG_PICTURES_DIR="{outside}"\n', encoding="utf-8")
    outside_payload = store.browse_directory(None)
    assert "图片" not in {entry["label"] for entry in outside_payload["quick"]}

    user_dirs.write_text(f'XDG_PICTURES_DIR="{mounted_pictures}"\n', encoding="utf-8")
    mounted_payload = store.browse_directory(None)
    mounted_quick = {entry["label"]: entry for entry in mounted_payload["quick"]}
    assert mounted_quick["图片"]["path"] == str(mounted_pictures.resolve())


def test_browse_marks_imported_counts_and_reasons(store, scoped_home) -> None:
    trained = scoped_home / "trained"
    _image_files(trained, 3, ".png")
    store.register(trained, name="已导入集")
    (scoped_home / "misc").mkdir()
    pictures = scoped_home / "Pictures"
    pictures.mkdir()
    _image_files(pictures / "walk", 2)

    payload = store.browse_directory(scoped_home)
    entries = {entry["name"]: entry for entry in payload["entries"]}
    assert entries["trained"]["imported"] is True
    assert entries["trained"]["image_count"] == 3
    assert entries["trained"]["selectable"] is True
    assert entries["misc"]["selectable"] is True
    assert entries["misc"]["image_count"] == 0
    library = entries["prompt-library"]
    assert library["selectable"] is False
    assert "资料库根目录" in library["reason"]
    inside_library = store.browse_directory(store.settings.library_root)
    nested = {entry["name"]: entry for entry in inside_library["entries"]}
    datasets = nested["datasets"]
    assert datasets["selectable"] is False
    assert "工作区" in datasets["reason"]
    quick = {entry["label"]: entry for entry in payload["quick"]}
    assert quick["图片"]["path"] == str(pictures)
    assert quick["主目录"]["path"] == str(scoped_home)


def test_browse_breadcrumbs_and_parent(store, scoped_home) -> None:
    nested = scoped_home / "trained" / "sub"
    _image_files(nested, 1)
    payload = store.browse_directory(nested)
    crumbs = [(crumb["name"], crumb["path"]) for crumb in payload["crumbs"]]
    assert crumbs == [
        ("主目录", str(scoped_home)),
        ("trained", str(scoped_home / "trained")),
        ("sub", str(nested)),
    ]
    assert payload["parent"] == str(scoped_home / "trained")
    assert payload["selectable"] is True
    assert payload["image_count"] == 1


def test_browse_image_count_cap(store, scoped_home, monkeypatch) -> None:
    monkeypatch.setattr(workspace_module, "BROWSE_IMAGE_COUNT_LIMIT", 5)
    crowded = scoped_home / "crowded"
    _image_files(crowded, 8, ".png")
    (crowded / "note.txt").write_text("caption", encoding="utf-8")
    payload = store.browse_directory(scoped_home)
    entry = next(item for item in payload["entries"] if item["name"] == "crowded")
    assert entry["image_count"] == 5
    assert entry["image_count_capped"] is True


def test_browse_unreadable_subdir_is_skipped_not_fatal(store, scoped_home, monkeypatch) -> None:
    locked = scoped_home / "locked"
    _image_files(locked, 1)
    original_count = workspace_module._count_directory_images

    def counting(path, limit):
        if path.name == "locked":
            message = "permission denied"
            raise PermissionError(message)
        return original_count(path, limit)

    monkeypatch.setattr(workspace_module, "_count_directory_images", counting)
    payload = store.browse_directory(scoped_home)
    assert "locked" not in {entry["name"] for entry in payload["entries"]}
    skipped = next(item for item in payload["skipped"] if item["name"] == "locked")
    assert "权限" in skipped["reason"]


def test_browse_skips_symlink_directories(store, scoped_home) -> None:
    outside = scoped_home.parent / f"outside-{scoped_home.name}"
    outside.mkdir(exist_ok=True)
    (scoped_home / "link").symlink_to(outside)
    payload = store.browse_directory(scoped_home)
    assert "link" not in {entry["name"] for entry in payload["entries"]}
    skipped = next(item for item in payload["skipped"] if item["name"] == "link")
    assert "符号链接" in skipped["reason"]


def test_register_still_applies_shared_rejection_rules(store, scoped_home) -> None:
    with pytest.raises(DatasetWorkspaceError, match="主目录"):
        store.register(scoped_home)
    with pytest.raises(DatasetWorkspaceError, match="资料库根目录"):
        store.register(store.settings.library_root)


def test_browse_api_rejects_outside_and_lists_home(settings, monkeypatch, tmp_path) -> None:
    home = tmp_path.resolve()
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.setattr("prompt_hub.dataset_workspace.browse_roots", lambda: [home])
    with TestClient(create_app(settings)) as client:
        rejected = client.get("/api/dataset-workspaces/browse", params={"path": "/"})
        assert rejected.status_code == 422
        assert "浏览范围" in rejected.json()["detail"]
        listing = client.get("/api/dataset-workspaces/browse")
        assert listing.status_code == 200
        payload = listing.json()
        assert payload["path"] == ""
        assert payload["entries"][0]["path"] == str(tmp_path)
        assert "主目录" in payload["entries"][0]["reason"]
