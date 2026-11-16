import queue
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.fakes import download
from yt.domain.urls import playlist_url
from yt.infrastructure.runtime import ffmpeg_path
from yt.infrastructure.youtube.metadata import fetch_playlist


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = self.temp.name

    def test_playlist_links(self):
        for url in (
            "https://www.youtube.com/watch?v=abc&list=PL_123-abc",
            "https://music.youtube.com/playlist?list=PL_123-abc",
            "https://youtu.be/abc?list=PL_123-abc",
        ):
            self.assertEqual(playlist_url(url), "https://www.youtube.com/playlist?list=PL_123-abc")

    def test_invalid_links(self):
        for url in (
            "",
            "https://youtube.com.evil.com/playlist?list=x",
            "file:///playlist?list=x",
            "https://youtube.com/watch?v=x",
            "https://youtube.com/playlist?list=../../bad",
        ):
            with self.assertRaises(ValueError):
                playlist_url(url)

    def test_ffmpeg_can_write_mp3_to_unicode_path(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Музыка с пробелами.mp3"
            subprocess.run(
                [
                    ffmpeg_path(),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=0.1",
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "192k",
                    str(target),
                ],
                check=True,
            )
            self.assertGreater(target.stat().st_size, 100)

    def test_cancel_before_network(self):
        cancel = threading.Event()
        cancel.set()
        events = queue.Queue()
        with patch("yt_dlp.YoutubeDL") as downloader:
            download("https://youtube.com/playlist?list=test", self.folder, "192", events, cancel)
            downloader.assert_not_called()
        self.assertIn("Остановлено", events.get_nowait()[1])

    def test_archived_video_is_skipped_without_downloading(self):
        entry = {"key": "1:abc", "id": "abc", "title": "Track", "duration": 120, "available": True}
        events = queue.Queue()
        with patch("yt_dlp.YoutubeDL") as constructor:
            downloader = constructor.return_value.__enter__.return_value
            downloader.in_download_archive.return_value = True
            download(
                "https://youtube.com/playlist?list=test",
                self.folder,
                "192",
                events,
                threading.Event(),
                playlist={"entries": [entry]},
            )
            downloader.extract_info.assert_not_called()
        messages = list(events.queue)
        self.assertTrue(
            any(kind == "track" and value["state"] == "skipped" for kind, value in messages)
        )
        self.assertTrue(messages[-1][1].startswith("Готово!"))

    def test_failed_video_does_not_stop_next_track(self):
        entries = [
            {"key": str(i), "id": str(i), "title": str(i), "available": True} for i in (1, 2)
        ]
        events = queue.Queue()
        with patch("yt_dlp.YoutubeDL") as constructor:
            downloader = constructor.return_value.__enter__.return_value
            downloader.in_download_archive.return_value = False
            downloader.extract_info.side_effect = [ValueError("Unavailable"), {"duration": 123}]
            download(
                "https://youtube.com/playlist?list=test",
                self.folder,
                "192",
                events,
                threading.Event(),
                playlist={"entries": entries},
                concurrency=1,
            )
            self.assertEqual(downloader.extract_info.call_count, 2)
        states = [
            (value["key"], value["state"]) for kind, value in list(events.queue) if kind == "track"
        ]
        self.assertIn(("1", "error"), states)
        self.assertIn(("2", "done"), states)
        self.assertIn("с ошибками", list(events.queue)[-1][1])

    def test_metadata_keeps_unavailable_entries_and_duplicate_video_ids(self):
        with patch("yt_dlp.YoutubeDL") as constructor:
            constructor.return_value.__enter__.return_value.extract_info.return_value = {
                "title": "Playlist",
                "entries": [{"id": "abc", "duration": 120}, None, {"id": "abc"}],
            }
            data = fetch_playlist("https://youtube.com/playlist?list=test", threading.Event())
        self.assertEqual(len(data["entries"]), 3)
        self.assertEqual(len({entry["key"] for entry in data["entries"]}), 3)
        self.assertFalse(data["entries"][1]["available"])


if __name__ == "__main__":
    unittest.main()
