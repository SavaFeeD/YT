"""Run each desktop scenario in a fresh process to isolate Windows Tcl/SDL state."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCENARIOS = [
    node.name
    for parent in ast.parse(
        Path(__file__).with_name("ui_scenarios.py").read_text(encoding="utf-8")
    ).body
    if isinstance(parent, ast.ClassDef)
    for node in parent.body
    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
]


@pytest.mark.desktop
@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop integration tests")
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_desktop_scenario(scenario):
    result = subprocess.run(
        [sys.executable, "-m", "unittest", f"tests.ui_scenarios.InterfaceTests.{scenario}"],
        env={**os.environ, "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
