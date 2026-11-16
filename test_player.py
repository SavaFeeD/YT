import os
from pathlib import Path
import random
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from mutagen.id3 import TIT2, TPE1

from downloader import ffmpeg_path
from player import AudioBackend, AudioDeviceError, PlaybackQueue, Player, Track, scan_library


class QueueTests(unittest.TestCase):
    def test_shuffle_has_no_repeats_and_stops_after_full_pass(self):
        queue = PlaybackQueue(shuffle=True, rng=random.Random(10))
        queue.set_tracks([str(index) for index in range(100)])
        played = []
        while (key := queue.next()) is not None:
            played.append(key)
        self.assertEqual(len(played), 100)
        self.assertEqual(set(played), set(queue.keys))
        self.assertNotEqual(played, queue.keys)
        queue.new_pass()
        self.assertNotEqual(queue.next(), played[-1])

    def test_toggling_shuffle_and_refreshing_library_preserves_visited_tracks(self):
        queue = PlaybackQueue(rng=random.Random(2))
        queue.set_tracks(['a', 'b', 'c', 'd'])
        self.assertEqual(queue.next(), 'a')
        self.assertEqual(queue.next(), 'b')
        queue.set_shuffle(True)
        queue.set_tracks(['a', 'b', 'c', 'd', 'new'])
        rest = [queue.next(), queue.next(), queue.next()]
        self.assertEqual(set(rest), {'c', 'd', 'new'})
        self.assertIsNone(queue.next())

    def test_previous_and_forward_follow_history_without_replaying_unvisited_queue(self):
        queue = PlaybackQueue(shuffle=True, rng=random.Random(9))
        queue.set_tracks(['a', 'b', 'c'])
        first, second = queue.next(), queue.next()
        self.assertEqual(queue.previous(), first)
        self.assertEqual(queue.next(), second)
        self.assertNotIn(queue.next(), (first, second))
        self.assertIsNone(queue.next())


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


class PlayerTests(unittest.TestCase):
    def test_pause_does_not_advance_queue_and_auto_end_does(self):
        backend = FakeBackend()
        player = Player(backend=backend, volume=.25)
        tracks = [Track(Path('a.mp3'), 'A', duration=30), Track(Path('b.mp3'), 'B', duration=40)]
        player.set_library(tracks)
        player.toggle()
        self.assertEqual(player.current, tracks[0])
        self.assertEqual(backend.volume, .25)
        player.toggle()
        player.poll()
        self.assertEqual(player.state, 'paused')
        self.assertEqual(player.current, tracks[0])
        player.seek(12)
        self.assertEqual(player.position, 12)
        self.assertFalse(backend.playing)
        player.toggle()
        backend.playing = False
        player.poll()
        self.assertEqual(player.current, tracks[1])
        backend.playing = False
        player.poll()
        self.assertEqual(player.state, 'ended')
        self.assertEqual(len(backend.plays), 2)
        player.poll()
        self.assertEqual(len(backend.plays), 2)
        player.previous()
        self.assertEqual(player.state, 'playing')
        self.assertEqual(player.current, tracks[1])

    def test_library_refresh_does_not_restart_audio_or_reset_shuffle_pass(self):
        backend = FakeBackend()
        player = Player(backend=backend, shuffle=True)
        tracks = [Track(Path(f'{i}.mp3'), str(i), duration=10) for i in range(4)]
        player.set_library(tracks)
        player.next()
        first = player.current.key
        player.set_library(tracks)
        self.assertEqual(len(backend.plays), 1)
        played = [first]
        for _ in range(3):
            player.next()
            played.append(player.current.key)
        self.assertEqual(len(set(played)), 4)
        player.next()
        self.assertEqual(player.state, 'ended')

    def test_unreadable_track_is_skipped_without_infinite_loop(self):
        backend = FakeBackend()
        backend.play = lambda *args: (_ for _ in ()).throw(ValueError('bad file'))
        player = Player(backend=backend)
        player.set_library([Track(Path('bad.mp3'), 'Bad')])
        player.next()
        self.assertEqual(player.state, 'error')
        self.assertEqual(len(player.errors), 1)

    def test_unavailable_audio_device_does_not_consume_the_whole_queue(self):
        backend = FakeBackend()
        backend.play = lambda *args: (_ for _ in ()).throw(AudioDeviceError('No device'))
        player = Player(backend=backend)
        player.set_library([Track(Path(f'{i}.mp3'), str(i)) for i in range(10)])
        player.toggle()
        self.assertEqual(player.state, 'error')
        self.assertEqual(len(player.errors), 1)
        self.assertEqual(len(player.queue.pending), 9)


class AudioIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / 'Музыка с пробелами.mp3'
        subprocess.run([ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                        '-i', 'anullsrc=r=44100:cl=stereo', '-t', '1', '-codec:a', 'libmp3lame',
                        str(cls.path)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_scan_reads_tags_duration_subfolders_and_ignores_corrupt_files(self):
        from mutagen.mp3 import MP3
        audio = MP3(self.path)
        if audio.tags is None:
            audio.add_tags()
        audio.tags.add(TIT2(encoding=3, text='Локальный трек'))
        audio.tags.add(TPE1(encoding=3, text='Исполнитель'))
        audio.save()
        corrupt = self.path.parent / 'bad.mp3'
        corrupt.write_text('not audio', encoding='utf-8')
        tracks, unreadable = scan_library(self.path.parent)
        self.assertEqual(unreadable, 1)
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].title, 'Локальный трек')
        self.assertEqual(tracks[0].artist, 'Исполнитель')
        self.assertGreater(tracks[0].duration, .9)

    def test_mp3_decoder_pause_resume_seek_and_volume_without_physical_device(self):
        with patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
            backend = AudioBackend()
            try:
                backend.play(self.path, .2)
                self.assertTrue(backend.busy())
                backend.pause()
                backend.seek(.3, paused=True)
                self.assertGreaterEqual(backend.position(), .3)
                backend.set_volume(.4)
                self.assertAlmostEqual(backend.mixer.music.get_volume(), .4, delta=.02)
                backend.resume()
                self.assertTrue(backend.busy())
                backend.seek(.9)
                timeout = time.monotonic() + 3
                while backend.busy() and time.monotonic() < timeout:
                    time.sleep(.02)
                self.assertFalse(backend.busy())
            finally:
                backend.close()
