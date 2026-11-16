"""Playlist metadata and MP3 downloads. No GUI calls from worker threads."""
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
CONFIG = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'YT' / 'settings.json'


def playlist_url(value):
    parsed = urlparse(value.strip())
    if parsed.scheme not in ('http', 'https') or (parsed.hostname or '').lower() not in (
        'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be',
    ):
        raise ValueError('Вставьте ссылку на плейлист YouTube.')
    playlist = parse_qs(parsed.query).get('list', [''])[0]
    if not playlist or not all(c.isalnum() or c in '_-' for c in playlist):
        raise ValueError('В ссылке нет плейлиста (параметра list).')
    return 'https://www.youtube.com/playlist?list=' + playlist


def ffmpeg_path():
    bundled = BASE / 'bin' / 'ffmpeg.exe'
    if bundled.exists():
        return str(bundled)
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def check_cancel(cancel):
    if cancel.is_set():
        import yt_dlp
        raise yt_dlp.utils.DownloadCancelled('Остановлено пользователем')


class QuietLogger:
    def debug(self, message):
        pass

    warning = debug
    error = debug


def fetch_playlist(url, cancel, playlist_items=None):
    import yt_dlp
    check_cancel(cancel)
    options = {
        'extract_flat': 'in_playlist', 'quiet': True, 'skip_download': True,
        'ignoreerrors': True, 'socket_timeout': 15, 'retries': 1,
        'extractor_retries': 1, 'logger': QuietLogger(),
    }
    if playlist_items:
        options['playlist_items'] = playlist_items
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(playlist_url(url), download=False)
    check_cancel(cancel)
    if not info:
        raise ValueError('Не удалось открыть плейлист. Проверьте ссылку и доступ к YouTube.')
    entries = []
    for index, entry in enumerate(info.get('entries') or [], 1):
        check_cancel(cancel)
        entry = entry or {}
        video_id = entry.get('id')
        duration = entry.get('duration')
        entries.append({
            'key': f'{index}:{video_id or "unavailable"}', 'id': video_id,
            'title': entry.get('title') or 'Недоступное видео',
            'duration': duration if isinstance(duration, (int, float)) and duration >= 0 else None,
            'thumbnail': f'https://i.ytimg.com/vi/{video_id}/mqdefault.jpg' if video_id else None,
            'available': bool(video_id) and entry.get('availability') not in ('private', 'premium_only', 'subscriber_only'),
        })
    if not entries:
        raise ValueError('Плейлист пуст или недоступен. Для приватных плейлистов нужен публичный доступ.')
    return {
        'url': playlist_url(url), 'title': info.get('title') or 'Плейлист YouTube',
        'thumbnail': entries[0]['thumbnail'], 'entries': entries,
    }


def download(url, folder, quality, events, cancel, playlist_items=None, playlist=None, concurrency=3):
    from transfers import download_parallel
    return download_parallel(url, folder, quality, events, cancel, playlist_items, playlist, concurrency)
