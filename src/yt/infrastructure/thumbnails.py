"""Bounded image downloads. Images never create Tk objects off the UI thread."""

import logging
from collections.abc import Iterable, Iterator
from threading import Event

import requests

logger = logging.getLogger(__name__)


class HttpThumbnailReader:
    def images(
        self, targets: Iterable[tuple[str, str | None]], cancel: Event
    ) -> Iterator[tuple[str, bytes]]:
        cache: dict[str, bytes] = {}
        with requests.Session() as session:
            for key, url in targets:
                if cancel.is_set():
                    return
                if not url:
                    continue
                try:
                    if url not in cache:
                        with session.get(url, timeout=(4, 6), stream=True) as response:
                            response.raise_for_status()
                            content = bytearray()
                            for chunk in response.iter_content(16384):
                                if cancel.is_set():
                                    return
                                content.extend(chunk)
                                if len(content) > 2_000_000:
                                    raise ValueError("Thumbnail is too large")
                            cache[url] = bytes(content)
                    yield key, cache[url]
                except (requests.RequestException, ValueError):
                    logger.debug("Thumbnail unavailable: %s", url, exc_info=True)
