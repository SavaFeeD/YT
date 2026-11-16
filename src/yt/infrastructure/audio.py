"""SDL/pygame audio output. Initialized lazily, never on import."""

import os
from pathlib import Path

from yt.domain.errors import AudioDeviceError


class AudioBackend:
    """Initialize only the mixer, on the first Play; startup does not need an audio device."""

    def __init__(self):
        self.mixer = None
        self.offset = 0

    def _init(self):
        if self.mixer is None:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame.mixer

            try:
                pygame.mixer.init()
            except Exception as error:
                raise AudioDeviceError(f"Не удалось открыть аудиоустройство: {error}") from error
            self.mixer = pygame.mixer

    def play(self, path, volume):
        self._init()
        self.mixer.music.stop()
        self.mixer.music.load(str(path))
        self.mixer.music.set_volume(volume)
        self.mixer.music.play()
        self.offset = 0

    def pause(self):
        self.mixer.music.pause()

    def resume(self):
        self.mixer.music.unpause()

    def seek(self, seconds, paused=False):
        self.mixer.music.play(start=seconds)
        self.offset = seconds
        if paused:
            self.mixer.music.pause()

    def position(self):
        return self.offset + max(0, self.mixer.music.get_pos()) / 1000 if self.mixer else 0

    def busy(self):
        return bool(self.mixer and self.mixer.music.get_busy())

    def set_volume(self, volume):
        if self.mixer:
            self.mixer.music.set_volume(volume)

    def stop(self):
        self.offset = 0
        if self.mixer:
            self.mixer.music.stop()
            self.mixer.music.unload()

    def close(self):
        if self.mixer:
            self.stop()
            self.mixer.quit()
            self.mixer = None


def audio_smoke_test(path):
    """Exercise the installed audio decoder without emitting sound."""
    backend = AudioBackend()
    try:
        backend.play(Path(path), 0)
        if not backend.busy():
            raise RuntimeError("MP3 playback did not start")
        backend.pause()
        backend.resume()
        backend.set_volume(0)
    finally:
        backend.close()
