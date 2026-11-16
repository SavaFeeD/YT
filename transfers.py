"""Bounded parallel track downloads with independent yt-dlp instances."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import queue
import threading
import time

from downloader import BASE, check_cancel, fetch_playlist, ffmpeg_path


def download_parallel(url, folder, quality, events, cancel, playlist_items, playlist, concurrency):
    import yt_dlp
    counts = {'completed': 0, 'skipped': 0, 'failed': 0, 'finished': 0}
    counts_lock = threading.Lock()

    class Logger:
        def debug(self, message):
            if not message.startswith('[debug]'):
                events.put(('log', message))

        def warning(self, message):
            events.put(('log', 'Предупреждение: ' + message))

        def error(self, message):
            events.put(('log', 'Ошибка: ' + message))

    try:
        check_cancel(cancel)
        concurrency = int(concurrency)
        if not 1 <= concurrency <= 6:
            raise ValueError('Выберите от 1 до 6 одновременных загрузок.')
        playlist = playlist or fetch_playlist(url, cancel, playlist_items)
        check_cancel(cancel)
        entries = playlist['entries']
        events.put(('playlist', playlist))
        pending = queue.Queue()
        video_locks = {entry['id']: threading.Lock() for entry in entries}
        for entry in entries:
            pending.put(entry)
        ffmpeg = ffmpeg_path()

        def process(entry):
            last_update = 0

            def track(state, **extra):
                events.put(('track', {'key': entry['key'], 'state': state, **extra}))

            def progress(data):
                nonlocal last_update
                check_cancel(cancel)
                if data['status'] == 'downloading':
                    now = time.monotonic()
                    if now - last_update < 0.12:
                        return
                    last_update = now
                    total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
                    percent = min(100, data.get('downloaded_bytes', 0) / total * 100) if total else 0
                    track('downloading', percent=percent, speed=data.get('speed'), eta=data.get('eta'))
                elif data['status'] == 'finished':
                    track('converting', percent=100, speed=0)

            def postprocess(data):
                check_cancel(cancel)
                if data['status'] == 'started':
                    track('converting', percent=100, speed=0)

            try:
                check_cancel(cancel)
                if not entry['available']:
                    track('unavailable')
                    return 'failed'
                # A duplicate video must wait until the first copy has written its archive entry.
                # Other IDs run independently. yt-dlp locks the archive file when appending.
                lock = video_locks[entry['id']]
                while not lock.acquire(timeout=0.1):
                    check_cancel(cancel)
                try:
                    check_cancel(cancel)
                    options = {
                        'format': 'bestaudio/best', 'paths': {'home': folder},
                        'outtmpl': {'default': '%(title).160B [%(id)s].%(ext)s'},
                        'windowsfilenames': True, 'noplaylist': True, 'ignoreerrors': False,
                        'download_archive': str(Path(folder) / '.yt-archive.txt'),
                        'ffmpeg_location': ffmpeg,
                        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': quality}],
                        'progress_hooks': [progress], 'postprocessor_hooks': [postprocess],
                        'logger': Logger(), 'quiet': True, 'noprogress': True,
                        'socket_timeout': 20, 'retries': 3, 'continuedl': True,
                    }
                    deno, node = BASE / 'bin' / 'deno.exe', BASE / 'bin' / 'node.exe'
                    options['js_runtimes'] = {'deno': {'path': str(deno)}} if deno.exists() else {
                        'node': {'path': str(node)} if node.exists() else {},
                    }
                    with yt_dlp.YoutubeDL(options) as downloader:
                        if downloader.in_download_archive({'id': entry['id'], 'extractor_key': 'Youtube'}):
                            track('skipped', percent=100)
                            return 'skipped'
                        track('downloading', percent=0, speed=0)
                        info = downloader.extract_info('https://www.youtube.com/watch?v=' + entry['id'], download=True)
                        check_cancel(cancel)
                        if not info:
                            raise ValueError('Видео недоступно')
                        track('done', percent=100, duration=info.get('duration'))
                        events.put(('log', 'Готово: ' + entry['title']))
                        return 'completed'
                finally:
                    lock.release()
            except Exception as error:
                if cancel.is_set() or isinstance(error, yt_dlp.utils.DownloadCancelled):
                    track('stopped')
                    return None
                track('error')
                events.put(('log', f'Не удалось скачать «{entry["title"]}»: {error}'))
                return 'failed'

        def worker():
            while not cancel.is_set():
                try:
                    entry = pending.get_nowait()
                except queue.Empty:
                    return
                result = process(entry)
                if result is not None:
                    with counts_lock:
                        counts[result] += 1
                        counts['finished'] += 1
                        events.put(('overall', {'finished': counts['finished'], 'total': len(entries), 'failed': counts['failed']}))

        # Submit only the bounded workers, so cancellation leaves the rest of the queue untouched.
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix='YT-download') as executor:
            futures = [executor.submit(worker) for _ in range(min(concurrency, len(entries)))]
            for future in futures:
                future.result()
        if cancel.is_set():
            result = 'Остановлено. Можно продолжить повторным запуском.'
        elif counts['failed']:
            result = f'Завершено с ошибками. Новых MP3: {counts["completed"]}, пропущено: {counts["skipped"]}, ошибок: {counts["failed"]}.'
        else:
            result = f'Готово! Новых MP3: {counts["completed"]}. Ранее скачанных: {counts["skipped"]}.'
        events.put(('done', result))
    except Exception as error:
        events.put(('done', 'Остановлено. Можно продолжить повторным запуском.' if cancel.is_set() else f'Ошибка: {error}'))
