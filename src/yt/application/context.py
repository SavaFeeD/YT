"""Dependencies provided to presentation by the composition root."""

from dataclasses import dataclass
from pathlib import Path
from queue import Queue

from yt.application.controllers import (
    DownloadController,
    LibraryController,
    PlaylistController,
    ThumbnailController,
)
from yt.application.playback import Player
from yt.application.ports import SettingsStore
from yt.application.tasks import BackgroundTasks
from yt.domain.events import AppEvent


@dataclass
class ApplicationServices:
    events: Queue[AppEvent]
    settings: SettingsStore
    player: Player
    tasks: BackgroundTasks
    downloads: DownloadController
    previews: PlaylistController
    library: LibraryController
    thumbnails: ThumbnailController
    icon: Path
    version: str

    def close(self) -> None:
        self.downloads.cancel()
        self.previews.cancel_event.set()
        self.library.cancel_event.set()
        self.tasks.close()
        self.player.close()
