"""Test doubles and adapters; never imported by application code."""


def download(
    url, folder, quality, events, cancel, playlist_items=None, playlist=None, concurrency=3
):
    from yt.infrastructure.youtube.transfers import download_parallel

    return download_parallel(
        url, folder, quality, events, cancel, playlist_items, playlist, concurrency
    )


class FakeBackend:
    def __init__(self):
        self.playing = False
        self.pos = 0
        self.volume = None
        self.plays = []

    def play(self, path, volume):
        self.plays.append(path)
        self.playing = True
        self.pos = 0
        self.volume = volume

    def pause(self):
        self.playing = False

    def resume(self):
        self.playing = True

    def busy(self):
        return self.playing

    def position(self):
        return self.pos

    def seek(self, position, paused=False):
        self.pos = position
        self.playing = not paused

    def set_volume(self, value):
        self.volume = value

    def stop(self):
        self.playing = False

    def close(self):
        self.stop()
