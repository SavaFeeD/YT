"""Playback use cases, depending on an audio contract rather than SDL."""

from collections.abc import Iterable

from yt.application.ports import AudioOutput
from yt.domain.errors import AudioDeviceError
from yt.domain.music import PlaybackQueue, PlaybackState, Track


class Player:
    def __init__(self, backend: AudioOutput, volume: float = 0.5, shuffle: bool = False) -> None:
        self.backend = backend
        self.queue = PlaybackQueue(shuffle=shuffle)
        self.tracks: dict[str, Track] = {}
        self.current: Track | None = None
        self.state: PlaybackState = PlaybackState.IDLE
        self.volume = max(0, min(1, float(volume)))
        self.errors: list[str] = []
        self.revision = 0
        self.audio_unavailable = False

    def set_library(self, tracks: Iterable[Track], reset: bool = False) -> None:
        self.tracks = {track.key: track for track in tracks}
        self.queue.set_tracks(self.tracks)
        if reset:
            self.queue.new_pass()
        if self.current and (reset or self.current.key not in self.tracks):
            self.backend.stop()
            self.current = None
            self.state = PlaybackState.IDLE
        self.revision += 1

    def _play(self, key: str) -> bool:
        self.current = self.tracks[key]
        self.audio_unavailable = False
        try:
            self.backend.play(self.current.path, self.volume)
            self.state = PlaybackState.PLAYING
            success = True
        except Exception as error:
            self.audio_unavailable = isinstance(error, AudioDeviceError)
            self.backend.stop()
            self.state = PlaybackState.ERROR
            self.errors.append(f"Не удалось воспроизвести «{self.current.title}»: {error}")
            success = False
        self.revision += 1
        return success

    def play(self, key: str) -> bool:
        self.queue.select(key)
        return self._play(key)

    def next(self) -> None:
        failed = False
        while (key := self.queue.next()) is not None:
            if self._play(key):
                return
            failed = True
            if self.audio_unavailable:
                return
        self.backend.stop()
        self.state = (
            PlaybackState.ERROR
            if failed
            else PlaybackState.ENDED
            if self.tracks
            else PlaybackState.IDLE
        )
        self.revision += 1

    def previous(self) -> None:
        if self.state == "ended" and self.current:
            self._play(self.current.key)
        elif self.position > 3 and self.current:
            self.seek(0)
        elif (key := self.queue.previous()) is not None:
            self._play(key)
        elif self.current:
            self._play(self.current.key)

    def toggle(self) -> None:
        if self.state == "playing":
            self.backend.pause()
            self.state = PlaybackState.PAUSED
        elif self.state == "paused":
            self.backend.resume()
            self.state = PlaybackState.PLAYING
        else:
            if self.state == "ended" or not self.queue.pending:
                self.queue.new_pass()
            self.next()
        self.revision += 1

    @property
    def shuffle(self) -> bool:
        return self.queue.shuffle

    def set_shuffle(self, enabled: bool) -> None:
        self.queue.set_shuffle(enabled)
        self.revision += 1

    def restart(self) -> None:
        self.queue.new_pass()
        self.next()

    def set_volume(self, volume: float) -> None:
        self.volume = max(0, min(1, float(volume)))
        self.backend.set_volume(self.volume)

    def seek(self, seconds: float) -> None:
        if self.current and self.state in ("playing", "paused"):
            seconds = max(0, min(float(seconds), max(0, self.current.duration - 0.1)))
            try:
                self.backend.seek(seconds, self.state == "paused")
            except Exception as error:
                self.errors.append(f"Не удалось перемотать трек: {error}")

    @property
    def position(self) -> float:
        if not self.current:
            return 0
        if self.state == "ended":
            return self.current.duration
        return min(self.current.duration, self.backend.position())

    def poll(self) -> None:
        try:
            if self.state == "playing" and not self.backend.busy():
                self.next()
        except Exception as error:
            self.state = PlaybackState.ERROR
            self.errors.append(f"Ошибка звукового устройства: {error}")
            self.revision += 1

    def stop(self) -> None:
        self.backend.stop()
        self.state = PlaybackState.IDLE
        self.revision += 1

    def close(self) -> None:
        self.backend.close()
