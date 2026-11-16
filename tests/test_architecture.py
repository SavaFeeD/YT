"""Enforce dependency direction so future changes cannot reintroduce UI/service cycles."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src" / "yt"


@pytest.mark.parametrize(
    "layer,forbidden",
    [
        (
            "domain",
            (
                "yt.application",
                "yt.infrastructure",
                "yt.presentation",
                "tkinter",
                "pygame",
                "yt_dlp",
                "mutagen",
                "requests",
            ),
        ),
        (
            "application",
            (
                "yt.infrastructure",
                "yt.presentation",
                "yt.bootstrap",
                "tkinter",
                "pygame",
                "yt_dlp",
                "mutagen",
                "requests",
            ),
        ),
        (
            "presentation",
            ("yt.infrastructure", "yt.bootstrap", "pygame", "yt_dlp", "mutagen", "requests"),
        ),
    ],
)
def test_dependency_direction(layer, forbidden):
    for path in (ROOT / layer).rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                assert not any(
                    module == prefix or module.startswith(prefix + ".") for prefix in forbidden
                ), (path, module)
