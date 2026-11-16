"""Resolve resources in a checkout, installed wheel, and PyInstaller bundle."""

import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", project_root()))


def icon_path() -> Path:
    candidate = resource_root() / "public" / "favicon.ico"
    return (
        candidate
        if candidate.is_file()
        else Path(sys.prefix) / "share" / "yt" / "public" / "favicon.ico"
    )


def settings_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "YT" / "settings.json"


def app_version() -> str:
    try:
        return version("yt-desktop")
    except PackageNotFoundError:
        path = resource_root() / "VERSION"
        return path.read_text(encoding="utf-8").strip() if path.is_file() else "development"


def ffmpeg_path() -> str:
    bundled = resource_root() / "bin" / "ffmpeg.exe"
    if not getattr(sys, "frozen", False):
        bundled = project_root() / "build" / "runtime" / "ffmpeg.exe"
    if bundled.is_file():
        return str(bundled)
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()
