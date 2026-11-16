"""Asynchronous use cases with deterministic fakes, without Tk or network access."""

from pathlib import Path
from queue import Queue
from threading import Event

import pytest

from yt.application.controllers import DownloadController, PlaylistController
from yt.application.tasks import BackgroundTasks
from yt.domain.downloads import DownloadRequest
from yt.domain.events import AppEvent, EventKind


def test_download_controller_prevents_overlap_and_cancels_running_work():
    started = Event()

    class Backend:
        def download(self, request, events, cancel):
            started.set()
            assert cancel.wait(2)
            events.put(AppEvent(EventKind.DONE, "cancelled"))

    events = Queue()
    tasks = BackgroundTasks(events)
    controller = DownloadController(Backend(), tasks, events)
    request = DownloadRequest("https://youtube.com/playlist?list=test", Path("music"))
    controller.start(request)
    assert started.wait(2)
    with pytest.raises(RuntimeError):
        controller.start(request)
    controller.cancel()
    controller.worker.join(timeout=2)
    assert not controller.worker.is_alive()
    assert events.get(timeout=2).kind == EventKind.DONE
    tasks.close()


def test_stale_playlist_request_cannot_publish_after_a_new_request():
    first_started, release_first = Event(), Event()

    class Reader:
        def fetch(self, url, cancel):
            if url == "old":
                first_started.set()
                assert release_first.wait(2)
            return {"url": url}

    events = Queue()
    tasks = BackgroundTasks(events)
    controller = PlaylistController(Reader(), tasks, events)
    controller.load("old", 1)
    assert first_started.wait(2)
    controller.load("new", 2)
    newest = events.get(timeout=2)
    assert newest.kind == EventKind.PREVIEW
    assert newest.payload[0] == 2
    release_first.set()
    tasks.close()


@pytest.mark.parametrize(
    "quality,concurrency", [("flac", 3), ("192", 0), ("320", 7), ("192", None), ("192", True)]
)
def test_invalid_request_is_rejected_before_background_work(quality, concurrency):
    with pytest.raises(ValueError):
        DownloadRequest("url", Path("music"), quality=quality, concurrency=concurrency)


def test_unexpected_download_error_always_publishes_completion():
    class BrokenBackend:
        def download(self, request, events, cancel):
            raise RuntimeError("unexpected adapter failure")

    events = Queue()
    tasks = BackgroundTasks(events)
    controller = DownloadController(BrokenBackend(), tasks, events)
    controller.start(DownloadRequest("url", Path("music")))
    controller.worker.join(timeout=2)
    event = events.get(timeout=2)
    assert event.kind == EventKind.DONE
    assert "unexpected adapter failure" in event.payload
    tasks.close()
