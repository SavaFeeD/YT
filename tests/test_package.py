"""Entry points must work without starting Tk, audio, or network services."""

import subprocess
import sys
from pathlib import Path


def test_version_command_works_outside_the_checkout(tmp_path):
    expected = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
    result = subprocess.run(
        [sys.executable, "-m", "yt", "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"YT {expected}"


def test_domain_import_does_not_load_gui_audio_or_network_adapters(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import yt.domain.music, sys; assert not {'tkinter', 'pygame', 'yt_dlp', 'requests', 'mutagen'} & sys.modules.keys()",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
