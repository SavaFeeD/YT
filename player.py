"""Local MP3 library, non-repeating playback queue, and a lazy SDL audio backend."""
from dataclasses import dataclass
import os
from pathlib import Path
import random
import re

from mutagen.mp3 import MP3


@dataclass(frozen=True)
class Track:
    path: Path
    title: str
    artist: str = ''
    duration: float = 0

    @property
    def key(self):
        return os.path.normcase(str(self.path.resolve()))


def scan_library(folder, excluded_ids=()):
    """Read headers/tags only; do not decode audio or access the network."""
    folder = Path(folder).expanduser()
    if not folder.exists():
        return [], 0
    if not folder.is_dir():
        raise ValueError('Выберите папку с музыкой.')
    tracks, unreadable = [], 0
    seen = set()
    excluded = set(excluded_ids)
    for path in folder.rglob('*'):
        if not path.is_file() or path.suffix.lower() != '.mp3':
            continue
        identity = os.path.normcase(str(path.resolve()))
        if identity in seen:
            continue
        seen.add(identity)
        match = re.search(r'\[([^\]]+)\]$', path.stem)
        if match and match[1] in excluded:
            continue
        try:
            audio = MP3(path)
            title = str(audio.tags.get('TIT2', '')) if audio.tags else ''
            artist = str(audio.tags.get('TPE1', '')) if audio.tags else ''
            fallback = re.sub(r'\s*\[[A-Za-z0-9_-]{11}\]$', '', path.stem)
            tracks.append(Track(path.resolve(), title or fallback, artist, float(audio.info.length)))
        except Exception:
            # Mutagen has several format-specific exception classes. A bad file must not hide the library.
            unreadable += 1
    tracks.sort(key=lambda track: (track.title.casefold(), track.artist.casefold(), track.key))
    return tracks, unreadable


class PlaybackQueue:
    """Shuffle only tracks not visited in this pass, including when toggled midway."""
    def __init__(self, shuffle=False, rng=None):
        self.shuffle = shuffle
        self.rng = rng or random.Random()
        self.keys = []
        self.pending = []
        self.seen = set()
        self.history = []
        self.cursor = -1
        self.current = None

    def set_tracks(self, keys):
        self.keys = list(dict.fromkeys(keys))
        self._reorder()

    def _reorder(self):
        ordered = list(self.keys)
        if not self.shuffle and self.current in ordered:
            index = ordered.index(self.current) + 1
            ordered = ordered[index:] + ordered[:index]
        self.pending = [key for key in ordered if key not in self.seen]
        if self.shuffle:
            self.rng.shuffle(self.pending)

    def set_shuffle(self, enabled):
        self.shuffle = bool(enabled)
        self._reorder()

    def new_pass(self):
        previous = self.current
        self.seen.clear()
        self.history.clear()
        self.cursor = -1
        self.current = None
        self._reorder()
        if self.shuffle and len(self.pending) > 1 and self.pending[0] == previous:
            self.pending[0], self.pending[1] = self.pending[1], self.pending[0]

    def select(self, key):
        if key not in self.keys:
            raise KeyError(key)
        self.current = key
        self.seen.add(key)
        self.history = self.history[:self.cursor + 1] + [key]
        self.cursor = len(self.history) - 1
        self._reorder()
        return key

    def next(self):
        while self.cursor + 1 < len(self.history):
            self.cursor += 1
            key = self.history[self.cursor]
            if key in self.keys:
                self.current = key
                return key
        return self.select(self.pending[0]) if self.pending else None

    def previous(self):
        while self.cursor > 0:
            self.cursor -= 1
            key = self.history[self.cursor]
            if key in self.keys:
                self.current = key
                return key
        return None


class AudioDeviceError(RuntimeError):
    pass


class AudioBackend:
    """Initialize only the mixer, on the first Play; startup does not need an audio device."""
    def __init__(self):
        self.mixer = None
        self.offset = 0

    def _init(self):
        if self.mixer is None:
            os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
            import pygame.mixer
            try:
                pygame.mixer.init()
            except Exception as error:
                raise AudioDeviceError(f'Не удалось открыть аудиоустройство: {error}') from error
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


class Player:
    def __init__(self, backend=None, volume=0.5, shuffle=False):
        self.backend = backend or AudioBackend()
        self.queue = PlaybackQueue(shuffle=shuffle)
        self.tracks = {}
        self.current = None
        self.state = 'idle'
        self.volume = max(0, min(1, float(volume)))
        self.errors = []
        self.revision = 0
        self.audio_unavailable = False

    def set_library(self, tracks, reset=False):
        self.tracks = {track.key: track for track in tracks}
        self.queue.set_tracks(self.tracks)
        if reset:
            self.queue.new_pass()
        if self.current and (reset or self.current.key not in self.tracks):
            self.backend.stop()
            self.current = None
            self.state = 'idle'
        self.revision += 1

    def _play(self, key):
        self.current = self.tracks[key]
        self.audio_unavailable = False
        try:
            self.backend.play(self.current.path, self.volume)
            self.state = 'playing'
            success = True
        except Exception as error:
            self.audio_unavailable = isinstance(error, AudioDeviceError)
            self.backend.stop()
            self.state = 'error'
            self.errors.append(f'Не удалось воспроизвести «{self.current.title}»: {error}')
            success = False
        self.revision += 1
        return success

    def play(self, key):
        self.queue.select(key)
        return self._play(key)

    def next(self):
        failed = False
        while (key := self.queue.next()) is not None:
            if self._play(key):
                return
            failed = True
            if self.audio_unavailable:
                return
        self.backend.stop()
        self.state = 'error' if failed else 'ended' if self.tracks else 'idle'
        self.revision += 1

    def previous(self):
        if self.state == 'ended' and self.current:
            self._play(self.current.key)
        elif self.position > 3 and self.current:
            self.seek(0)
        elif (key := self.queue.previous()) is not None:
            self._play(key)
        elif self.current:
            self._play(self.current.key)

    def toggle(self):
        if self.state == 'playing':
            self.backend.pause()
            self.state = 'paused'
        elif self.state == 'paused':
            self.backend.resume()
            self.state = 'playing'
        else:
            if self.state == 'ended' or not self.queue.pending:
                self.queue.new_pass()
            self.next()
        self.revision += 1

    def set_volume(self, volume):
        self.volume = max(0, min(1, float(volume)))
        self.backend.set_volume(self.volume)

    def seek(self, seconds):
        if self.current and self.state in ('playing', 'paused'):
            seconds = max(0, min(float(seconds), max(0, self.current.duration - 0.1)))
            try:
                self.backend.seek(seconds, self.state == 'paused')
            except Exception as error:
                self.errors.append(f'Не удалось перемотать трек: {error}')

    @property
    def position(self):
        if not self.current:
            return 0
        if self.state == 'ended':
            return self.current.duration
        return min(self.current.duration, self.backend.position())

    def poll(self):
        try:
            if self.state == 'playing' and not self.backend.busy():
                self.next()
        except Exception as error:
            self.state = 'error'
            self.errors.append(f'Ошибка звукового устройства: {error}')
            self.revision += 1

    def close(self):
        self.backend.close()


def audio_smoke_test(path):
    """Exercise the installed audio decoder without emitting sound."""
    backend = AudioBackend()
    try:
        backend.play(Path(path), 0)
        if not backend.busy():
            raise RuntimeError('MP3 playback did not start')
        backend.pause()
        backend.resume()
        backend.set_volume(0)
    finally:
        backend.close()
