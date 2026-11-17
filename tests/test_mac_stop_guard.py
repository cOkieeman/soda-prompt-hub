# ruff: noqa: S603
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# All subprocess targets are the compiled guard or a temporary fixture process.

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS process identity")


@pytest.fixture(scope="module")
def guard_binary(tmp_path_factory):
    directory = tmp_path_factory.mktemp("core-stop-guard")
    source = (
        Path(__file__).resolve().parents[1]
        / "deploy/mac/portable-launcher/SodaPromptHubLauncher.swift"
    ).read_text()
    guard = source[
        source.index("enum CoreProcessGuard {") : source.index("private let launcherName")
    ]
    harness = """
let pid = Int32(CommandLine.arguments[1])!
let port = Int(CommandLine.arguments[2])!
if let value = CoreProcessGuard.identity(pid: pid, port: port) {
    let expected = CommandLine.arguments.count > 3 ? "stale-identity" : value
    print(CoreProcessGuard.terminate(pid: pid, port: port, expected: expected))
} else { print("refused") }
"""
    main = directory / "main.swift"
    main.write_text("import Foundation\nimport Darwin\n" + guard + harness)
    binary = directory / "guard-test"
    subprocess.run(["/usr/bin/swiftc", str(main), "-o", str(binary)], check=True)
    return binary


def test_reused_core_stops_but_unrelated_wrong_port_and_stale_identity_do_not(
    guard_binary, tmp_path
):
    # A standalone fixture process, not the user's actual Core or GUI.
    module = tmp_path / "prompt_hub.py"
    module.write_text("import time\ntime.sleep(60)\n")
    with subprocess.Popen(
        [sys.executable, "-m", "prompt_hub", "serve", "--port", "19876"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
    ) as child:
        try:
            for port, extra, expected in [(19875, [], "refused"), (19876, ["stale"], "false")]:
                result = subprocess.run(
                    [str(guard_binary), str(child.pid), str(port), *extra],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                assert result.stdout.strip() == expected
                assert child.poll() is None
            result = subprocess.run(
                [str(guard_binary), str(child.pid), "19876"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout.strip() == "true"
            child.wait(timeout=5)
        finally:
            if child.poll() is None:
                child.terminate()
    result = subprocess.run(
        [str(guard_binary), str(os.getpid()), "19876"], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "refused"
