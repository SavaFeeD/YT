"""Optional real network check: python check_download.py PLAYLIST_URL."""

import queue
import sys
import threading
from pathlib import Path

from yt.domain.urls import playlist_url
from yt.infrastructure.youtube.transfers import download_parallel


def download(url, folder, quality, events, cancel, playlist_items):
    download_parallel(url, folder, quality, events, cancel, playlist_items, None, 1)


sys.stdout.reconfigure(encoding="utf-8", errors="replace")
folder = Path(__file__).resolve().parents[1] / "test-download"
folder.mkdir(exist_ok=True)
events = queue.Queue()
download(playlist_url(sys.argv[1]), str(folder.resolve()), "192", events, threading.Event(), "1")
success = False
while not events.empty():
    kind, value = events.get_nowait()
    if kind in ("log", "done"):
        print(kind, value, flush=True)
    if kind == "done":
        success = value.startswith("Готово!")
if not success or not list(folder.glob("*.mp3")):
    raise SystemExit("Download check failed; see log above")
