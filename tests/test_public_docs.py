from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote


def test_public_document_layers_exist_and_readme_routes_users() -> None:
    repository = Path(__file__).resolve().parents[1]
    expected = {
        "QUICK_START.md",
        "WORKFLOWS.md",
        "MAC_GUIDE.md",
        "WINDOWS_WORKER.md",
        "OPTIONAL_MODELS.md",
        "DESKTOP_PRODUCT_PLAN.md",
        "DESKTOP_UI_SPEC.md",
        "ARCHITECTURE.md",
        "COMMERCIAL_RELEASE.md",
        "TROUBLESHOOTING.md",
        "RELEASES.md",
        "USER_MANUAL_DRAFT.md",
        "STYLE_SOURCES.md",
        "CREATIVE_AI_GUIDE.md",
    }
    assert {path.name for path in (repository / "docs").glob("*.md")} == expected

    readme = (repository / "README.md").read_text(encoding="utf-8")
    for name in expected:
        assert f"docs/{name}" in readme
    assert len(readme.splitlines()) < 140


def test_local_markdown_links_resolve() -> None:
    repository = Path(__file__).resolve().parents[1]
    missing: list[str] = []
    for source in repository.rglob("*.md"):
        if any(part in {".git", ".venv", "bin", "obj", "dist"} for part in source.parts):
            continue
        for target in re.findall(r"\[[^]]*\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
            normalized = target.strip().strip("<>")
            if not normalized or "://" in normalized or normalized.startswith(("#", "mailto:")):
                continue
            local = unquote(normalized.split("#", 1)[0])
            if local and not (source.parent / local).resolve().exists():
                missing.append(f"{source.relative_to(repository)} -> {normalized}")
    assert missing == []


def test_worker_offline_guide_uses_numbered_first_run_and_upgrade_flow() -> None:
    repository = Path(__file__).resolve().parents[1]
    guide = (repository / "deploy/windows-worker/README-WINDOWS.md").read_text(encoding="utf-8")

    assert "校验发行包.ps1" in guide
    assert "0-首次配置.bat" in guide
    assert "1-先自检.bat" in guide
    assert "2-启动Worker.bat" in guide
    assert "## 升级 Worker" in guide
    assert "worker-config.json" in guide
