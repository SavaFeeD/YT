"""YT — desktop playlist to MP3 downloader."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs, urlparse

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
CONFIG = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'YT' / 'settings.json'


def playlist_url(value):
    value = value.strip()
    parsed = urlparse(value)
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


def download(url, folder, quality, events, cancel, playlist_items=None):
    import yt_dlp
    completed = set()
    errors = []

    class Logger:
        def debug(self, message):
            if not message.startswith('[debug]'):
                events.put(('log', message))

        def warning(self, message):
            events.put(('log', 'Предупреждение: ' + message))

        def error(self, message):
            errors.append(message)
            events.put(('log', 'Ошибка: ' + message))

    def check_cancel():
        if cancel.is_set():
            raise yt_dlp.utils.DownloadCancelled('Остановлено пользователем')

    def progress(data):
        check_cancel()
        info = data.get('info_dict', {})
        title = info.get('title', '')
        index, count = info.get('playlist_index'), info.get('playlist_count')
        prefix = f'{index} / {count} · ' if index and count else ''
        if data['status'] == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
            percent = min(100, data.get('downloaded_bytes', 0) / total * 100) if total else 0
            speed = data.get('speed') or 0
            events.put(('progress', (percent, prefix + title, f'{speed / 1048576:.1f} МБ/с')))
        elif data['status'] == 'finished':
            events.put(('progress', (100, prefix + title, 'Преобразование в MP3…')))

    def postprocess(data):
        check_cancel()
        if data['status'] == 'finished' and data.get('postprocessor') == 'MoveFiles':
            info = data.get('info_dict', {})
            completed.add(info.get('id'))
            events.put(('log', 'Готово: ' + info.get('title', '')))

    def match_filter(info, *, incomplete=False):
        check_cancel()
        return None

    try:
        check_cancel()
        options = {
            'format': 'bestaudio/best', 'paths': {'home': folder},
            'outtmpl': {'default': '%(title).160B [%(id)s].%(ext)s'},
            'windowsfilenames': True, 'noplaylist': False, 'ignoreerrors': True,
            'download_archive': str(Path(folder) / '.yt-archive.txt'),
            'ffmpeg_location': ffmpeg_path(),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3',
                                'preferredquality': quality}],
            'progress_hooks': [progress], 'postprocessor_hooks': [postprocess],
            'logger': Logger(), 'quiet': True, 'noprogress': True,
            'socket_timeout': 20, 'retries': 3, 'continuedl': True,
            'match_filter': match_filter,
        }
        if playlist_items:
            options['playlist_items'] = playlist_items
        deno = BASE / 'bin' / 'deno.exe'
        if deno.exists():
            options['js_runtimes'] = {'deno': {'path': str(deno)}}
        else:
            node = BASE / 'bin' / 'node.exe'
            options['js_runtimes'] = {'node': {'path': str(node)} if node.exists() else {}}
        with yt_dlp.YoutubeDL(options) as downloader:
            result = downloader.download([url])
        if cancel.is_set():
            events.put(('done', 'Остановлено. Можно продолжить повторным запуском.'))
        elif errors or result:
            events.put(('done', f'Завершено с ошибками. Новых MP3: {len(completed)}. Подробности в журнале.'))
        else:
            events.put(('done', f'Готово! Новых MP3: {len(completed)}. Ранее скачанные записи пропущены.'))
    except Exception as error:
        events.put(('done', 'Остановлено.' if cancel.is_set() else f'Ошибка: {error}'))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('YT · Плейлист → MP3')
        self.geometry('860x680')
        self.minsize(720, 600)
        self.configure(bg='#11151e')
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.closing = False
        settings = {}
        try:
            settings = json.loads(CONFIG.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        self.url = tk.StringVar()
        self.folder = tk.StringVar(value=settings.get('folder', str(Path.home() / 'Music' / 'YT')))
        self.quality = tk.StringVar(value=settings.get('quality', '192'))
        self.status = tk.StringVar(value='Вставьте ссылку и выберите папку')
        self.detail = tk.StringVar(value='Готов к работе')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', background='#11151e', foreground='#e8ecf5', font=('Segoe UI', 11))
        style.configure('TEntry', fieldbackground='#202837', foreground='#ffffff', padding=10)
        style.configure('TButton', background='#2a3549', padding=(15, 9))
        style.map('TButton', background=[('active', '#3b4c68')])
        style.configure('Accent.TButton', background='#c23b49', foreground='white')
        style.configure('TCombobox', fieldbackground='#202837', foreground='#ffffff', padding=7)
        style.map('TCombobox', fieldbackground=[('readonly', '#202837')], foreground=[('readonly', '#ffffff')])
        style.configure('TProgressbar', background='#ee5968', troughcolor='#202837')
        frame = ttk.Frame(self, padding=30)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text='YT', font=('Segoe UI', 32, 'bold'), foreground='#ff6575').grid(row=0, column=0, sticky='w')
        ttk.Label(frame, text='Ваш плейлист. Ваша музыка.', font=('Segoe UI', 17)).grid(row=1, column=0, sticky='w', pady=(0, 22))
        ttk.Label(frame, text='ССЫЛКА НА ПЛЕЙЛИСТ', foreground='#98a7c0').grid(row=2, column=0, sticky='w')
        self.link_entry = ttk.Entry(frame, textvariable=self.url)
        self.link_entry.grid(row=3, column=0, sticky='ew', pady=(7, 17))
        ttk.Label(frame, text='ПАПКА СОХРАНЕНИЯ', foreground='#98a7c0').grid(row=4, column=0, sticky='w')
        destination = ttk.Frame(frame)
        destination.grid(row=5, column=0, sticky='ew', pady=(7, 17))
        destination.columnconfigure(0, weight=1)
        self.folder_entry = ttk.Entry(destination, textvariable=self.folder)
        self.folder_entry.grid(row=0, column=0, sticky='ew')
        self.browse = ttk.Button(destination, text='Выбрать…', command=self.choose_folder)
        self.browse.grid(row=0, column=1, padx=(10, 0))
        controls = ttk.Frame(frame)
        controls.grid(row=6, column=0, sticky='ew')
        ttk.Label(controls, text='MP3 · кбит/с').pack(side='left', padx=(0, 10))
        self.quality_box = ttk.Combobox(controls, values=['128', '192', '256', '320'], textvariable=self.quality, width=6, state='readonly')
        self.quality_box.pack(side='left')
        self.start_button = ttk.Button(controls, text='Скачать плейлист', style='Accent.TButton', command=self.start)
        self.start_button.pack(side='right')
        self.stop_button = ttk.Button(controls, text='Остановить', command=self.stop, state='disabled')
        self.stop_button.pack(side='right', padx=10)
        ttk.Label(frame, textvariable=self.status, wraplength=770).grid(row=7, column=0, sticky='w', pady=(22, 8))
        self.progress_bar = ttk.Progressbar(frame, maximum=100)
        self.progress_bar.grid(row=8, column=0, sticky='ew')
        ttk.Label(frame, textvariable=self.detail, foreground='#98a7c0').grid(row=9, column=0, sticky='w', pady=(5, 12))
        self.log = tk.Text(frame, height=7, bg='#181f2c', fg='#bdc9dd', relief='flat', font=('Consolas', 9), state='disabled', wrap='word')
        self.log.grid(row=10, column=0, sticky='nsew')
        frame.rowconfigure(10, weight=1)
        ttk.Button(frame, text='Открыть папку', command=self.open_folder).grid(row=11, column=0, sticky='e', pady=(12, 0))
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)
        self.link_entry.focus_set()

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder.get() if Path(self.folder.get()).is_dir() else Path.home())
        if folder:
            self.folder.set(folder)

    def open_folder(self):
        folder = Path(self.folder.get()).expanduser()
        if folder.is_dir():
            os.startfile(str(folder))
        else:
            messagebox.showinfo('YT', 'Папка появится после начала загрузки.')

    def set_busy(self, busy):
        for widget in (self.start_button, self.link_entry, self.folder_entry, self.browse):
            widget.configure(state='disabled' if busy else 'normal')
        self.quality_box.configure(state='disabled' if busy else 'readonly')
        self.stop_button.configure(state='normal' if busy else 'disabled')

    def start(self):
        try:
            url = playlist_url(self.url.get())
            if not self.folder.get().strip():
                raise ValueError('Выберите папку сохранения.')
            folder = Path(self.folder.get()).expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps({'folder': str(folder), 'quality': self.quality.get()}), encoding='utf-8')
        except (ValueError, OSError) as error:
            messagebox.showerror('YT', str(error))
            return
        self.cancel.clear()
        self.set_busy(True)
        self.progress_bar['value'] = 0
        self.status.set('Читаю плейлист…')
        self.detail.set('Подключение к YouTube')
        self.worker = threading.Thread(target=download, args=(url, str(folder), self.quality.get(), self.events, self.cancel), daemon=True)
        self.worker.start()

    def stop(self):
        self.cancel.set()
        self.stop_button.configure(state='disabled')
        self.detail.set('Останавливаю… Ожидаю завершения текущей операции.')

    def poll(self):
        for _ in range(200):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                self.log.configure(state='normal')
                self.log.insert('end', value + '\n')
                if int(self.log.index('end-1c').split('.')[0]) > 1000:
                    self.log.delete('1.0', '200.0')
                self.log.see('end')
                self.log.configure(state='disabled')
            elif kind == 'progress':
                percent, title, detail = value
                self.progress_bar['value'] = percent
                self.status.set(title)
                self.detail.set(detail)
            elif kind == 'done':
                self.status.set(value)
                self.detail.set('Готов к работе')
                self.set_busy(False)
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.destroy()
            return
        self.after(100, self.poll)

    def close(self):
        if self.worker and self.worker.is_alive():
            if messagebox.askyesno('YT', 'Остановить загрузку и закрыть приложение?'):
                self.closing = True
                self.stop()
        else:
            self.destroy()


if __name__ == '__main__':
    if '--smoke-test' in sys.argv:
        app = App()
        app.withdraw()
        app.update()
        subprocess.run([ffmpeg_path(), '-version'], check=True, capture_output=True)
        app.destroy()
    else:
        App().mainloop()
