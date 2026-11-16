"""Local tracks and playback order. No UI or audio dependency."""

import os
import random
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True)
class Track:
    path: Path
    title: str
    artist: str = ""
    duration: float = 0

    @property
    def key(self) -> str:
        # Adapters normalize paths before constructing tracks; identity does not perform I/O.
        return os.path.normcase(str(self.path))


class PlaybackState(StrEnum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    ENDED = "ended"
    ERROR = "error"


class PlaybackQueue:
    """Shuffle only tracks not visited in this pass, including when toggled midway."""

    def __init__(self, shuffle: bool = False, rng: random.Random | None = None) -> None:
        self.shuffle = shuffle
        self.rng = rng or random.Random()
        self.keys: list[str] = []
        self.pending: list[str] = []
        self.seen: set[str] = set()
        self.history: list[str] = []
        self.cursor = -1
        self.current: str | None = None

    def set_tracks(self, keys: Iterable[str]) -> None:
        self.keys = list(dict.fromkeys(keys))
        self._reorder()

    def _reorder(self) -> None:
        ordered = list(self.keys)
        if not self.shuffle and self.current in ordered:
            index = ordered.index(self.current) + 1
            ordered = ordered[index:] + ordered[:index]
        self.pending = [key for key in ordered if key not in self.seen]
        if self.shuffle:
            self.rng.shuffle(self.pending)

    def set_shuffle(self, enabled: bool) -> None:
        self.shuffle = bool(enabled)
        self._reorder()

    def new_pass(self) -> None:
        previous = self.current
        self.seen.clear()
        self.history.clear()
        self.cursor = -1
        self.current = None
        self._reorder()
        if self.shuffle and len(self.pending) > 1 and self.pending[0] == previous:
            self.pending[0], self.pending[1] = self.pending[1], self.pending[0]

    def select(self, key: str) -> str:
        if key not in self.keys:
            raise KeyError(key)
        self.current = key
        self.seen.add(key)
        self.history = self.history[: self.cursor + 1] + [key]
        self.cursor = len(self.history) - 1
        self._reorder()
        return key

    def next(self) -> str | None:
        while self.cursor + 1 < len(self.history):
            self.cursor += 1
            key = self.history[self.cursor]
            if key in self.keys:
                self.current = key
                return key
        return self.select(self.pending[0]) if self.pending else None

    def previous(self) -> str | None:
        while self.cursor > 0:
            self.cursor -= 1
            key = self.history[self.cursor]
            if key in self.keys:
                self.current = key
                return key
        return None
