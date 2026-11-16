"""Composition root: the only place assembling concrete adapters and use cases."""

from pathlib import Path
from queue import Queue

from yt.application.context import ApplicationServices
from yt.application.controllers import (
    DownloadController,
    LibraryController,
    PlaylistController,
    ThumbnailController,
)
from yt.application.playback import Player
from yt.application.ports import AudioOutput
from yt.application.tasks import BackgroundTasks
from yt.infrastructure.audio import AudioBackend
from yt.infrastructure.library import FileLibraryReader
from yt.infrastructure.runtime import app_version, icon_path, settings_path
from yt.infrastructure.settings import JsonSettingsRepository
from yt.infrastructure.thumbnails import HttpThumbnailReader
from yt.infrastructure.youtube.metadata import YoutubePlaylistReader
from yt.infrastructure.youtube.transfers import YoutubeDownloadService


def create_services(
    *, settings_file: Path | None = None, audio: AudioOutput | None = None
) -> ApplicationServices:
    events = Queue()
    settings = JsonSettingsRepository(settings_file or settings_path())
    preferences = settings.load()
    tasks = BackgroundTasks(events)
    return ApplicationServices(
        events=events,
        settings=settings,
        player=Player(
            audio or AudioBackend(), volume=preferences.volume, shuffle=preferences.shuffle
        ),
        tasks=tasks,
        downloads=DownloadController(YoutubeDownloadService(), tasks, events),
        previews=PlaylistController(YoutubePlaylistReader(), tasks, events),
        library=LibraryController(FileLibraryReader(), tasks, events),
        thumbnails=ThumbnailController(HttpThumbnailReader(), tasks, events),
        icon=icon_path(),
        version=app_version(),
    )
