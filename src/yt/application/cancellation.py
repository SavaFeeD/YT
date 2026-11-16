"""Cooperative cancellation shared by background services."""

import threading

from yt.domain.errors import OperationCancelled


def check_cancel(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise OperationCancelled("Остановлено пользователем")
