"""Run the installed Raffle text selector in an isolated CPU-only process."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


def main() -> None:
    request = json.load(sys.stdin)
    path = Path(request["root"]) / "custom_nodes" / "ComfyUI-Raffle" / "raffle.py"
    if not path.is_file():
        msg = "請在設定選擇已安裝 Raffle 的 ComfyUI 目錄"
        raise ValueError(msg)
    # Raffle imports this module for its host environment but does not use GPU APIs.
    sys.modules["folder_paths"] = types.ModuleType("folder_paths")
    specification = importlib.util.spec_from_file_location("studio_installed_raffle", path)
    if specification is None or specification.loader is None:
        msg = "Raffle 程式無法載入"
        raise ValueError(msg)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    # A fresh subprocess is created for every draw. The host's one-time migration
    # warning would otherwise abort every request, including explicit category choices.
    module.Raffle._critical_warning_shown = True  # noqa: SLF001 - upstream migration flag
    values = module.Raffle().process_tags(**request["options"])
    print(  # noqa: T201 - worker stdout carries JSON
        json.dumps(
            {"text": values[0], "unfiltered": values[1], "debug": values[2]}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
