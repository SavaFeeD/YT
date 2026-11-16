"""Download requests and the playlist read model."""

from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class PlaylistEntry(TypedDict):
    key: str
    id: str | None
    title: str
    duration: float | None
    thumbnail: str | None
    available: bool


class Playlist(TypedDict):
    url: str
    title: str
    thumbnail: str | None
    entries: list[PlaylistEntry]


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    folder: Path
    quality: str = "192"
    concurrency: int = 3
    playlist: Playlist | None = None
    playlist_items: str | None = None

    def __post_init__(self) -> None:
        if self.quality not in {"128", "192", "256", "320"}:
            raise ValueError("Выберите поддерживаемое качество MP3.")
        if type(self.concurrency) is not int or not 1 <= self.concurrency <= 6:
            raise ValueError("Выберите от 1 до 6 одновременных загрузок.")
