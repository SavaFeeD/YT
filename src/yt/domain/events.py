"""Messages passed from background work to the UI thread."""

from enum import StrEnum
from typing import NamedTuple, Protocol


class EventKind(StrEnum):
    LOG = "log"
    TRACK = "track"
    PLAYLIST = "playlist"
    OVERALL = "overall"
    DONE = "done"
    PREVIEW = "preview"
    IMAGE = "image"
    LIBRARY = "library"


class AppEvent(NamedTuple):
    kind: EventKind
    payload: object


class EventSink(Protocol):
    def put(self, event: AppEvent) -> None: ...
