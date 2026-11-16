"""Explicit rotating file logging; importing modules does not configure global logging."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        directory / "yt.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger("yt").setLevel(logging.INFO)
    logging.getLogger("yt").addHandler(handler)
