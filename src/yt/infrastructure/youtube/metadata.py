"""Read playlist metadata without downloading media."""

from yt.application.cancellation import check_cancel
from yt.domain.urls import playlist_url


class QuietLogger:
    def debug(self, message):
        pass

    warning = debug
    error = debug


def fetch_playlist(url, cancel, playlist_items=None):
    import yt_dlp

    check_cancel(cancel)
    options = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "skip_download": True,
        "ignoreerrors": True,
        "socket_timeout": 15,
        "retries": 1,
        "extractor_retries": 1,
        "logger": QuietLogger(),
    }
    if playlist_items:
        options["playlist_items"] = playlist_items
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(playlist_url(url), download=False)
    check_cancel(cancel)
    if not info:
        raise ValueError("Не удалось открыть плейлист. Проверьте ссылку и доступ к YouTube.")
    entries = []
    for index, entry in enumerate(info.get("entries") or [], 1):
        check_cancel(cancel)
        entry = entry or {}
        video_id = entry.get("id")
        duration = entry.get("duration")
        entries.append(
            {
                "key": f"{index}:{video_id or 'unavailable'}",
                "id": video_id,
                "title": entry.get("title") or "Недоступное видео",
                "duration": duration
                if isinstance(duration, (int, float)) and duration >= 0
                else None,
                "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                if video_id
                else None,
                "available": bool(video_id)
                and entry.get("availability") not in ("private", "premium_only", "subscriber_only"),
            }
        )
    if not entries:
        raise ValueError(
            "Плейлист пуст или недоступен. Для приватных плейлистов нужен публичный доступ."
        )
    return {
        "url": playlist_url(url),
        "title": info.get("title") or "Плейлист YouTube",
        "thumbnail": entries[0]["thumbnail"],
        "entries": entries,
    }


class YoutubePlaylistReader:
    def fetch(self, url, cancel, playlist_items=None):
        return fetch_playlist(url, cancel, playlist_items)
