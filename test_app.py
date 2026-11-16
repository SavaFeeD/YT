import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess

from app import download, ffmpeg_path, playlist_url


class Tests(unittest.TestCase):
    def test_playlist_links(self):
        for url in ('https://www.youtube.com/watch?v=abc&list=PL_123-abc',
                    'https://music.youtube.com/playlist?list=PL_123-abc',
                    'https://youtu.be/abc?list=PL_123-abc'):
            self.assertEqual(playlist_url(url), 'https://www.youtube.com/playlist?list=PL_123-abc')

    def test_invalid_links(self):
        for url in ('', 'https://youtube.com.evil.com/playlist?list=x',
                    'file:///playlist?list=x', 'https://youtube.com/watch?v=x',
                    'https://youtube.com/playlist?list=../../bad'):
            with self.assertRaises(ValueError):
                playlist_url(url)

    def test_ffmpeg_can_write_mp3_to_unicode_path(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Музыка с пробелами.mp3'
            subprocess.run([ffmpeg_path(), '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1',
                            '-codec:a', 'libmp3lame', '-b:a', '192k', str(target)], check=True)
            self.assertGreater(target.stat().st_size, 100)

    def test_cancel_before_network(self):
        cancel = threading.Event()
        cancel.set()
        events = queue.Queue()
        with patch('yt_dlp.YoutubeDL') as downloader:
            download('https://youtube.com/playlist?list=test', '.', '192', events, cancel)
            downloader.assert_not_called()
        self.assertIn('Остановлено', events.get_nowait()[1])


if __name__ == '__main__':
    unittest.main()
