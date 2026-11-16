import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from yt_dlp import YoutubeDL

from tests.fakes import download


class ParallelTests(unittest.TestCase):
    def run_download(self, entries, method, concurrency=2, cancel=None):
        events = queue.Queue()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(YoutubeDL, "extract_info", new=method):
                download(
                    "https://youtube.com/playlist?list=test",
                    directory,
                    "192",
                    events,
                    cancel or threading.Event(),
                    playlist={"entries": entries},
                    concurrency=concurrency,
                )
            archive = Path(directory) / ".yt-archive.txt"
            lines = archive.read_text(encoding="utf-8").splitlines() if archive.exists() else []
        return list(events.queue), lines

    def entries(self, ids):
        return [
            {"key": str(index), "id": video, "title": video, "available": True}
            for index, video in enumerate(ids)
        ]

    def test_downloads_overlap_with_limit_and_ordered_completion_counts(self):
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        active = peak = 0

        def extract(downloader, url, download=True):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                barrier.wait(timeout=10)
                downloader.params["progress_hooks"][0](
                    {
                        "status": "downloading",
                        "downloaded_bytes": 50,
                        "total_bytes": 100,
                        "speed": 1024,
                    }
                )
                info = {"id": url.split("=")[-1], "extractor_key": "Youtube", "duration": 10}
                downloader.record_download_archive(info)
                return info
            finally:
                with lock:
                    active -= 1

        messages, archive = self.run_download(self.entries(["a", "b", "c", "d"]), extract)
        self.assertEqual(peak, 2)
        self.assertEqual(len(set(archive)), 4)
        counts = [value["finished"] for kind, value in messages if kind == "overall"]
        self.assertEqual(counts, [1, 2, 3, 4])
        done = [
            value["key"] for kind, value in messages if kind == "track" and value["state"] == "done"
        ]
        self.assertEqual(set(done), {"0", "1", "2", "3"})
        self.assertTrue(messages[-1][1].startswith("Готово!"))

    def test_cancel_stops_active_tracks_and_does_not_start_remaining_queue(self):
        cancel = threading.Event()
        barrier = threading.Barrier(2)
        started = []

        def extract(downloader, url, download=True):
            started.append(url)
            barrier.wait(timeout=10)
            cancel.set()
            downloader.params["progress_hooks"][0]({"status": "downloading"})

        messages, archive = self.run_download(
            self.entries(["a", "b", "c", "d"]), extract, cancel=cancel
        )
        self.assertEqual(len(started), 2)
        self.assertEqual(archive, [])
        self.assertTrue(messages[-1][1].startswith("Остановлено"))
        stopped = [
            value for kind, value in messages if kind == "track" and value["state"] == "stopped"
        ]
        self.assertEqual(len(stopped), 2)

    def test_duplicate_video_is_downloaded_once_and_archive_remains_valid(self):
        started = []

        def extract(downloader, url, download=True):
            started.append(url)
            info = {"id": url.split("=")[-1], "extractor_key": "Youtube"}
            downloader.record_download_archive(info)
            return info

        messages, archive = self.run_download(
            self.entries(["a", "b", "a", "c", "b"]), extract, concurrency=3
        )
        self.assertEqual(len(started), 3)
        self.assertEqual(set(archive), {"youtube a", "youtube b", "youtube c"})
        self.assertEqual(len(archive), 3)
        skipped = [
            value for kind, value in messages if kind == "track" and value["state"] == "skipped"
        ]
        self.assertEqual(len(skipped), 2)
