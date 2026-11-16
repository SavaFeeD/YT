"""Background task ownership. All UI communication goes through events."""

import logging
from collections.abc import Callable
from threading import Event, Lock, Thread

from yt.domain.events import AppEvent, EventKind, EventSink

logger = logging.getLogger(__name__)


class BackgroundTasks:
    def __init__(self, events: EventSink) -> None:
        self.events = events
        self.closed = Event()
        self._lock = Lock()
        self._threads: set[Thread] = set()

    def start(self, target: Callable[[], None], *, name: str) -> Thread:
        if self.closed.is_set():
            raise RuntimeError("Application is shutting down")

        def run() -> None:
            try:
                target()
            except Exception as error:
                logger.exception("Background task failed: %s", name)
                if not self.closed.is_set():
                    self.events.put(AppEvent(EventKind.LOG, f"Ошибка фоновой операции: {error}"))
            finally:
                with self._lock:
                    self._threads.discard(thread)

        thread = Thread(target=run, name=f"YT-{name}", daemon=True)
        with self._lock:
            self._threads.add(thread)
        thread.start()
        return thread

    def close(self) -> None:
        self.closed.set()
