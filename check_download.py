"""Optional real network check: python check_download.py PLAYLIST_URL."""
import queue
import sys
import threading
from pathlib import Path

from app import download, playlist_url

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
folder = Path(__file__).parent / 'test-download'
folder.mkdir(exist_ok=True)
events = queue.Queue()
download(playlist_url(sys.argv[1]), str(folder.resolve()), '192', events, threading.Event(), '1')
success = False
while not events.empty():
    kind, value = events.get_nowait()
    if kind in ('log', 'done'):
        print(kind, value, flush=True)
    if kind == 'done':
        success = value.startswith('Готово!')
if not success or not list(folder.glob('*.mp3')):
    raise SystemExit('Download check failed; see log above')
