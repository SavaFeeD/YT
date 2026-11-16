"""Filesystem and ID3 adapter for the local music library."""

import os
import re
from pathlib import Path

from mutagen.mp3 import MP3

from yt.application.cancellation import check_cancel
from yt.domain.music import Track


def scan_library(folder, excluded_ids=(), cancel=None):
    """Read headers/tags only; do not decode audio or access the network."""
    folder = Path(folder).expanduser()
    if not folder.exists():
        return [], 0
    if not folder.is_dir():
        raise ValueError("Выберите папку с музыкой.")
    tracks, unreadable = [], 0
    seen = set()
    excluded = set(excluded_ids)
    for path in folder.rglob("*"):
        if cancel is not None:
            check_cancel(cancel)
        if not path.is_file() or path.suffix.lower() != ".mp3":
            continue
        identity = os.path.normcase(str(path.resolve()))
        if identity in seen:
            continue
        seen.add(identity)
        match = re.search(r"\[([^\]]+)\]$", path.stem)
        if match and match[1] in excluded:
            continue
        try:
            audio = MP3(path)
            title = str(audio.tags.get("TIT2", "")) if audio.tags else ""
            artist = str(audio.tags.get("TPE1", "")) if audio.tags else ""
            fallback = re.sub(r"\s*\[[A-Za-z0-9_-]{11}\]$", "", path.stem)
            tracks.append(
                Track(path.resolve(), title or fallback, artist, float(audio.info.length))
            )
        except Exception:
            # Mutagen has several format-specific exception classes. A bad file must not hide the library.
            unreadable += 1
    tracks.sort(key=lambda track: (track.title.casefold(), track.artist.casefold(), track.key))
    return tracks, unreadable


class FileLibraryReader:
    def scan(self, folder, excluded, cancel):
        return scan_library(folder, excluded, cancel)
