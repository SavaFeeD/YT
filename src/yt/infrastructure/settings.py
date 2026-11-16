"""Atomic JSON settings persistence with non-destructive recovery."""

import json
import logging
import tempfile
from pathlib import Path

from yt.domain.settings import AppSettings

logger = logging.getLogger(__name__)


class JsonSettingsRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppSettings:
        try:
            return AppSettings.from_mapping(json.loads(self.path.read_text(encoding="utf-8-sig")))
        except FileNotFoundError:
            return AppSettings()
        except (OSError, ValueError):
            logger.warning("Cannot read settings from %s; using defaults", self.path, exc_info=True)
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # A unique sibling avoids partially written JSON and cross-instance temp-name collisions.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix="settings-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(
                    settings.to_mapping(), stream, ensure_ascii=False, indent=2, allow_nan=False
                )
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
