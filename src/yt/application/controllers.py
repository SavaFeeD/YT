"""Asynchronous use cases independent of Tk and the concrete network/audio libraries."""

import logging
import threading
from pathlib import Path

from yt.application.ports import DownloadBackend, LibraryReader, PlaylistReader, ThumbnailReader
from yt.application.tasks import BackgroundTasks
from yt.domain.downloads import DownloadRequest, Playlist
from yt.domain.events import AppEvent, EventKind, EventSink

logger = logging.getLogger(__name__)


class DownloadController:
    def __init__(self, backend: DownloadBackend, tasks: BackgroundTasks, events: EventSink) -> None:
        self.backend, self.tasks, self.events = backend, tasks, events
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None

    def start(self, request: DownloadRequest) -> None:
        if self.worker and self.worker.is_alive():
            raise RuntimeError("A download is already running")
        self.cancel_event.clear()

        def work() -> None:
            try:
                self.backend.download(request, self.events, self.cancel_event)
            except Exception as error:
                logger.exception("Download backend failed")
                message = "Остановлено." if self.cancel_event.is_set() else f"Ошибка: {error}"
                self.events.put(AppEvent(EventKind.DONE, message))

        self.worker = self.tasks.start(work, name="downloads")

    def cancel(self) -> None:
        self.cancel_event.set()


class PlaylistController:
    def __init__(self, reader: PlaylistReader, tasks: BackgroundTasks, events: EventSink) -> None:
        self.reader, self.tasks, self.events = reader, tasks, events
        self.cancel_event = threading.Event()

    def load(self, url: str, token: int) -> None:
        self.cancel_event.set()
        cancel = self.cancel_event = threading.Event()

        def work() -> None:
            try:
                result, error = self.reader.fetch(url, cancel), None
            except Exception as exception:
                result, error = None, str(exception)
            if not cancel.is_set() and not self.tasks.closed.is_set():
                self.events.put(AppEvent(EventKind.PREVIEW, (token, result, error)))

        self.tasks.start(work, name="playlist-preview")


class LibraryController:
    def __init__(self, reader: LibraryReader, tasks: BackgroundTasks, events: EventSink) -> None:
        self.reader, self.tasks, self.events = reader, tasks, events
        self.cancel_event = threading.Event()

    def load(self, token: int, folder: str, excluded: list[str]) -> None:
        self.cancel_event.set()
        cancel = self.cancel_event = threading.Event()

        def work() -> None:
            try:
                tracks, unreadable = self.reader.scan(Path(folder), excluded, cancel)
                error = None
            except Exception as exception:
                tracks, unreadable, error = [], 0, str(exception)
            if not cancel.is_set() and not self.tasks.closed.is_set():
                self.events.put(
                    AppEvent(EventKind.LIBRARY, (token, folder, tracks, unreadable, error))
                )

        self.tasks.start(work, name="library-scan")


class ThumbnailController:
    def __init__(self, reader: ThumbnailReader, tasks: BackgroundTasks, events: EventSink) -> None:
        self.reader, self.tasks, self.events = reader, tasks, events

    def load(self, playlist: Playlist, generation: int, cancel: threading.Event) -> None:
        targets = [("__playlist__", playlist.get("thumbnail"))]
        targets.extend((entry["key"], entry["thumbnail"]) for entry in playlist["entries"])

        def work() -> None:
            for key, data in self.reader.images(targets, cancel):
                if cancel.is_set() or self.tasks.closed.is_set():
                    return
                self.events.put(AppEvent(EventKind.IMAGE, (generation, key, data)))

        self.tasks.start(work, name="thumbnails")
