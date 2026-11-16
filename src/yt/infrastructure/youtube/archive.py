"""Own the yt-dlp-compatible archive without modifying SDK instances at runtime."""

from pathlib import Path
from threading import Lock

from yt_dlp.utils import locked_file


class DownloadArchive:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        try:
            with locked_file(path, "r", encoding="utf-8") as stream:
                self._entries = {line.strip() for line in stream if line.strip()}
        except FileNotFoundError:
            self._entries = set()

    def snapshot(self) -> set[str]:
        with self._lock:
            return self._entries.copy()

    def record(self, video_id: str) -> None:
        entry = f"youtube {video_id}"
        with self._lock:
            if entry in self._entries:
                return
            with locked_file(self.path, "a", encoding="utf-8") as stream:
                stream.write(entry + "\n")
                stream.flush()
            self._entries.add(entry)
