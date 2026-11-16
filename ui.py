"""Dark desktop interface for YT."""
import ctypes
import io
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk
import requests

from downloader import CONFIG, download, fetch_playlist, playlist_url

BG = '#030911'
PANEL = '#050d17'
ROW = '#07121f'
LINE = '#1c2a36'
TEXT = '#f1f5f9'
MUTED = '#98a8b6'
CYAN = '#00cce7'
RED = '#ff2854'
GREEN = '#00d18c'
ORANGE = '#ffa600'
FONT = 'Segoe UI'


def duration_text(seconds):
    if seconds is None:
        return '—'
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}:{minutes:02}:{seconds:02}' if hours else f'{minutes}:{seconds:02}'


class Button(tk.Canvas):
    def __init__(self, parent, text, command, *, fill=BG, color=TEXT, height=44, font_size=11, border=LINE):
        super().__init__(parent, height=height, bg=parent.cget('bg'), highlightthickness=0, bd=0,
                         cursor='hand2', takefocus=True)
        self.label, self.command = text, command
        self.fill, self.color, self.border = fill, color, border
        self.font_size = font_size
        self.hover = False
        self.bind('<Configure>', lambda event: self.draw())
        self.bind('<Enter>', lambda event: self.set_hover(True))
        self.bind('<Leave>', lambda event: self.set_hover(False))
        self.bind('<FocusIn>', lambda event: self.draw())
        self.bind('<FocusOut>', lambda event: self.draw())
        self.bind('<Button-1>', self.invoke)
        self.bind('<Return>', self.invoke)
        self.bind('<space>', self.invoke)

    def configure(self, cnf=None, **kwargs):
        result = super().configure(cnf, **kwargs)
        if hasattr(self, 'label'):
            self.draw()
        return result

    def set_hover(self, value):
        self.hover = value
        self.draw()

    def draw(self):
        self.delete('all')
        width, height = self.winfo_width(), self.winfo_height()
        disabled = self.cget('state') == 'disabled'
        fill = '#101c29' if disabled else self.fill
        if self.hover and not disabled and self.fill == BG:
            fill = '#112332'
        radius = 10
        points = [radius, 1, width-radius, 1, width-1, 1, width-1, radius,
                  width-1, height-radius, width-1, height-1, width-radius, height-1,
                  radius, height-1, 1, height-1, 1, height-radius, 1, radius, 1, 1]
        border = CYAN if self.focus_get() == self and not disabled else self.border
        self.create_polygon(points, smooth=True, fill=fill, outline=border)
        self.create_text(width / 2, height / 2, text=self.label,
                         fill=MUTED if disabled else self.color,
                         font=(FONT, self.font_size, 'bold' if self.fill != BG else 'normal'))

    def invoke(self, event=None):
        if self.cget('state') != 'disabled':
            self.focus_set()
            self.command()


class Cover(tk.Canvas):
    def __init__(self, parent, size=52):
        super().__init__(parent, width=size, height=size, bg='#0c1a2b', highlightthickness=0)
        self.size = size
        self.photo = None
        self.reset()

    def reset(self):
        self.delete('all')
        self.photo = None
        size = self.size
        self.create_polygon(size*.5, size*.15, size*.85, size*.83, size*.15, size*.83,
                            outline='#156d99', fill='#101d38', width=2)
        self.create_line(size*.25, size*.72, size*.51, size*.23, size*.67, size*.54, fill=CYAN, width=2)
        self.create_line(size*.42, size*.65, size*.61, size*.28, size*.84, size*.8, fill=RED, width=2)

    def set_image(self, data):
        try:
            with Image.open(io.BytesIO(data)) as image:
                image = ImageOps.fit(image.convert('RGB'), (self.size, self.size), method=Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(image, master=self)
            self.delete('all')
            self.create_image(0, 0, image=self.photo, anchor='nw')
        except (OSError, ValueError):
            pass


class TrackRow(tk.Frame):
    def __init__(self, parent, entry):
        super().__init__(parent, bg=ROW, padx=18, pady=13, highlightthickness=1, highlightbackground='#0a1724')
        self.entry = entry
        self.state = 'queued' if entry['available'] else 'unavailable'
        self.columnconfigure(1, weight=1)
        self.cover = Cover(self)
        self.cover.grid(row=0, column=0, rowspan=2, padx=(0, 16))
        self.title = tk.Label(self, text=entry['title'], bg=ROW, fg=TEXT, anchor='w',
                              font=(FONT, 11, 'bold'), width=1)
        self.title.grid(row=0, column=1, sticky='ew')
        self.duration = tk.Label(self, text=duration_text(entry['duration']), bg=ROW, fg=MUTED,
                                 font=(FONT, 11), width=7)
        self.duration.grid(row=0, column=2, padx=12)
        self.badge = tk.Label(self, bg=ROW, font=(FONT, 10), width=13, anchor='e')
        self.badge.grid(row=0, column=3)
        self.progress_frame = tk.Frame(self, bg=ROW)
        self.bar = ttk.Progressbar(self.progress_frame, style='Track.Horizontal.TProgressbar', maximum=100)
        self.bar.pack(side='left', fill='x', expand=True)
        self.percent = tk.Label(self.progress_frame, bg=ROW, fg=CYAN, font=(FONT, 9), width=5, anchor='e')
        self.percent.pack(side='right')
        self.update_state(self.state)

    def update_state(self, state, percent=0, duration=None, **unused):
        self.state = state
        labels = {'queued': ('В очереди', MUTED), 'downloading': ('Скачивание', CYAN),
                  'converting': ('В MP3…', ORANGE), 'done': ('✓  Готово', GREEN),
                  'skipped': ('✓  Уже скачан', GREEN), 'error': ('Ошибка', RED),
                  'unavailable': ('Недоступно', MUTED), 'stopped': ('Остановлено', ORANGE)}
        text, color = labels[state]
        self.badge.configure(text=text, fg=color)
        if duration is not None:
            self.duration.configure(text=duration_text(duration))
        if state in ('downloading', 'converting'):
            self.progress_frame.grid(row=1, column=1, sticky='ew', pady=(8, 0))
            self.bar['value'] = percent
            self.percent.configure(text=f'{int(percent)}%')
        else:
            self.progress_frame.grid_remove()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('YT · Плейлист → MP3')
        width = min(1360, self.winfo_screenwidth() - 70)
        height = min(900, self.winfo_screenheight() - 100)
        self.geometry(f'{width}x{height}')
        self.minsize(1000, 700)
        self.configure(bg=BG)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.closing = False
        self.busy = False
        self.active_transfers = {}
        self.playlist = None
        self.rows = {}
        self.preview_after = None
        self.preview_token = 0
        self.image_generation = 0
        self.image_cancel = threading.Event()
        settings = {}
        try:
            settings = json.loads(CONFIG.read_text(encoding='utf-8'))
            if not isinstance(settings, dict):
                settings = {}
        except (OSError, ValueError):
            pass
        self.url = tk.StringVar(value=settings.get('url', ''))
        self.folder = tk.StringVar(value=settings.get('folder', str(Path.home() / 'Music' / 'YT')))
        self.quality = tk.StringVar(value=str(settings.get('quality', '192')))
        if self.quality.get() not in ('128', '192', '256', '320'):
            self.quality.set('192')
        self.concurrency = tk.StringVar(value=str(settings.get('concurrency', 3)))
        if self.concurrency.get() not in ('1', '2', '3', '4', '5', '6'):
            self.concurrency.set('3')
        self.search = tk.StringVar()
        self.status = tk.StringVar(value='Готов к работе')
        self.detail = tk.StringVar(value='Скорость —  ·  Осталось —')
        self.summary = tk.StringVar(value='Ожидание загрузки')
        self.overall_percent = tk.StringVar(value='0%')
        self.playlist_title = tk.StringVar(value='Ваш следующий плейлист')
        self.playlist_info = tk.StringVar(value='Вставьте ссылку слева — треки появятся здесь')
        self.setup_style()
        self.build_interface()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.url.trace_add('write', self.schedule_preview)
        self.search.trace_add('write', lambda *args: self.filter_rows())
        self.bind_all('<MouseWheel>', self.scroll_tracks, add='+')
        self.after(100, self.poll)
        self.after(100, self.dark_titlebar)
        self.link_entry.focus_set()
        if self.url.get() and '--smoke-test' not in sys.argv:
            self.schedule_preview()

    def setup_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Track.Horizontal.TProgressbar', background=CYAN, troughcolor='#1b2a38',
                        borderwidth=0, bordercolor='#1b2a38', lightcolor=CYAN, darkcolor=CYAN, thickness=5)
        style.configure('Overall.Horizontal.TProgressbar', background=RED, troughcolor='#14212d',
                        borderwidth=0, bordercolor='#14212d', lightcolor=RED, darkcolor=RED, thickness=13)
        style.configure('Vertical.TScrollbar', background='#203445', troughcolor=BG,
                        borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG, arrowcolor=MUTED, arrowsize=11)

    def dark_titlebar(self):
        if os.name != 'nt':
            return
        try:
            window = ctypes.windll.user32.GetParent(self.winfo_id())
            enabled = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(window, 20, ctypes.byref(enabled), 4)
        except (AttributeError, OSError):
            pass

    def label(self, parent, text=None, *, variable=None, color=TEXT, size=11, bold=False, **kwargs):
        return tk.Label(parent, text=text, textvariable=variable, bg=parent.cget('bg'), fg=color,
                        font=(FONT, size, 'bold' if bold else 'normal'), **kwargs)

    def entry(self, parent, variable, *, font_size=11):
        border = tk.Frame(parent, bg=BG, highlightthickness=1, highlightbackground=LINE)
        field = tk.Entry(border, textvariable=variable, bg=BG, fg=TEXT, insertbackground=CYAN,
                         relief='flat', bd=0, highlightthickness=0, font=(FONT, font_size), disabledbackground=BG,
                         disabledforeground=MUTED, selectbackground='#164459')
        field.pack(fill='x', expand=True, padx=13, pady=14)
        field.bind('<FocusIn>', lambda event: border.configure(highlightbackground=CYAN))
        field.bind('<FocusOut>', lambda event: border.configure(highlightbackground=LINE))
        return border, field

    def build_interface(self):
        footer = tk.Frame(self, bg=BG, height=44, highlightthickness=1, highlightbackground='#0d1b28')
        footer.pack(side='bottom', fill='x')
        footer.pack_propagate(False)
        self.indicator = self.label(footer, '●', color=GREEN, size=13)
        self.indicator.pack(side='left', padx=(20, 10))
        self.label(footer, variable=self.status, color=MUTED, size=10, anchor='w').pack(side='left', fill='x', expand=True)
        self.label(footer, 'YT  /  MP3', color='#456073', size=9).pack(side='right', padx=20)
        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True)
        sidebar = tk.Frame(body, bg=BG, width=355)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        tk.Frame(body, bg='#0d1b28', width=1).pack(side='left', fill='y')
        self.sidebar_canvas = tk.Canvas(sidebar, bg=BG, highlightthickness=0, bd=0)
        self.sidebar_canvas.pack(fill='both', expand=True)
        left = tk.Frame(self.sidebar_canvas, bg=BG)
        left_window = self.sidebar_canvas.create_window((26, 26), window=left, width=303, anchor='nw')

        def resize_sidebar(event=None):
            available = self.sidebar_canvas.winfo_height() - 52
            height = max(available, left.winfo_reqheight())
            self.sidebar_canvas.itemconfigure(left_window, height=height)
            self.sidebar_canvas.configure(scrollregion=(0, 0, 355, height + 52))

        self.sidebar_canvas.bind('<Configure>', resize_sidebar)
        left.bind('<Configure>', resize_sidebar)
        logo = tk.Frame(left, bg=BG)
        logo.pack(fill='x')
        self.label(logo, 'YT', color=RED, size=36, bold=True).pack(side='left')
        self.label(logo, ' → MP3', color=CYAN, size=32, bold=True).pack(side='left')
        self.label(left, 'Ваш плейлист. Ваша музыка.', color=MUTED, size=11).pack(anchor='w', pady=(0, 28))
        self.label(left, 'ССЫЛКА НА ПЛЕЙЛИСТ', color=CYAN, size=10, bold=True).pack(anchor='w')
        border, self.link_entry = self.entry(left, self.url, font_size=10)
        border.pack(fill='x', pady=(9, 5))
        self.preview_hint = self.label(left, 'Список загрузится автоматически', color='#668095', size=9, anchor='w')
        self.preview_hint.pack(fill='x', pady=(0, 20))
        self.label(left, 'ПАПКА СОХРАНЕНИЯ', color=CYAN, size=10, bold=True).pack(anchor='w')
        folder_frame = tk.Frame(left, bg=BG, highlightthickness=1, highlightbackground=LINE)
        folder_frame.pack(fill='x', pady=(9, 23))
        self.folder_entry = tk.Entry(folder_frame, textvariable=self.folder, bg=BG, fg=TEXT,
                                     insertbackground=CYAN, relief='flat', bd=0, highlightthickness=0, font=(FONT, 10), width=12,
                                     disabledbackground=BG, disabledforeground=MUTED)
        self.folder_entry.pack(side='left', fill='x', expand=True, padx=11, pady=17)
        self.browse = Button(folder_frame, 'Выбрать…', self.choose_folder, height=34, font_size=9)
        self.browse.configure(width=83)
        self.browse.pack(side='right', padx=(0, 8), pady=8)
        self.label(left, 'MP3 · кбит/с', color=CYAN, size=10, bold=True).pack(anchor='w')
        qualities = tk.Frame(left, bg=BG)
        qualities.pack(fill='x', pady=(10, 16))
        self.quality_buttons = {}
        for column, quality in enumerate(('128', '192', '256', '320')):
            qualities.columnconfigure(column, weight=1, uniform='quality')
            button = Button(qualities, quality, lambda value=quality: self.select_quality(value), height=48, font_size=14)
            button.grid(row=0, column=column, sticky='ew', padx=(0, 3))
            self.quality_buttons[quality] = button
        self.select_quality(self.quality.get())
        self.label(left, 'ПАРАЛЛЕЛЬНО ТРЕКОВ', color=CYAN, size=10, bold=True).pack(anchor='w')
        workers = tk.Frame(left, bg=BG)
        workers.pack(fill='x', pady=(9, 20))
        self.concurrency_buttons = {}
        for column, value in enumerate(('1', '2', '3', '4', '5', '6')):
            workers.columnconfigure(column, weight=1, uniform='workers')
            button = Button(workers, value, lambda number=value: self.select_concurrency(number), height=35, font_size=11)
            button.grid(row=0, column=column, sticky='ew', padx=(0, 3))
            self.concurrency_buttons[value] = button
        self.select_concurrency(self.concurrency.get())
        self.start_button = Button(left, 'Скачать плейлист', self.start, fill=RED, border=RED, height=62, font_size=15)
        self.start_button.pack(fill='x', pady=(0, 10))
        self.stop_button = Button(left, 'Остановить', self.stop, height=44)
        self.stop_button.pack(fill='x', pady=(0, 10))
        self.stop_button.configure(state='disabled')
        Button(left, 'Открыть папку', self.open_folder, color=MUTED, height=42).pack(fill='x')
        progress = tk.Frame(left, bg=BG, padx=15, pady=15, highlightthickness=1, highlightbackground=LINE)
        progress.pack(side='bottom', fill='x', pady=(20, 0))
        self.label(progress, variable=self.summary, size=10, bold=True, anchor='w').pack(fill='x')
        bar_frame = tk.Frame(progress, bg=BG)
        bar_frame.pack(fill='x', pady=12)
        self.progress_bar = ttk.Progressbar(bar_frame, style='Overall.Horizontal.TProgressbar', maximum=100)
        self.progress_bar.pack(side='left', fill='x', expand=True)
        self.label(bar_frame, variable=self.overall_percent, size=10, width=5, anchor='e').pack(side='right')
        self.label(progress, variable=self.detail, color=MUTED, size=9, anchor='w', wraplength=265).pack(fill='x')
        right = tk.Frame(body, bg=BG)
        right.pack(side='left', fill='both', expand=True)
        header = tk.Frame(right, bg=BG)
        header.pack(fill='x', padx=26, pady=(28, 20))
        self.playlist_cover = Cover(header, 88)
        self.playlist_cover.pack(side='left', padx=(0, 20))
        heading = tk.Frame(header, bg=BG)
        heading.pack(side='left', fill='both', expand=True)
        self.label(heading, variable=self.playlist_title, size=21, bold=True, anchor='w', width=1).pack(fill='x', pady=(9, 6))
        self.label(heading, variable=self.playlist_info, color=MUTED, size=11, anchor='w', width=1).pack(fill='x')
        search_border, self.search_entry = self.entry(right, self.search)
        search_border.pack(fill='x', padx=26, pady=(0, 16))
        self.search_placeholder = self.label(search_border, 'Поиск по названию…', color=MUTED, size=10, cursor='xterm')
        self.search_placeholder.place(x=13, rely=.5, anchor='w')
        self.search_placeholder.bind('<Button-1>', lambda event: self.search_entry.focus_set())
        self.search_entry.bind('<FocusIn>', lambda event: self.update_search_placeholder())
        self.search_entry.bind('<FocusOut>', lambda event: self.update_search_placeholder())
        journal = tk.Frame(right, bg=BG)
        journal.pack(side='bottom', fill='x', padx=26, pady=(12, 18))
        self.label(journal, 'ЖУРНАЛ', color='#597184', size=8, bold=True).pack(anchor='w', pady=(0, 6))
        self.log = tk.Text(journal, height=4, bg=BG, fg=MUTED, insertbackground=CYAN,
                           relief='flat', font=('Consolas', 9), state='disabled', wrap='word', bd=0, highlightthickness=0)
        self.log.pack(fill='x')
        tracks = tk.Frame(right, bg=BG)
        tracks.pack(fill='both', expand=True, padx=(8, 12))
        self.track_canvas = tk.Canvas(tracks, bg=BG, highlightthickness=0, bd=0)
        self.track_canvas.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(tracks, orient='vertical', command=self.track_canvas.yview)
        scrollbar.pack(side='right', fill='y')
        self.track_canvas.configure(yscrollcommand=scrollbar.set)
        self.track_frame = tk.Frame(self.track_canvas, bg=BG)
        self.track_window = self.track_canvas.create_window((0, 0), window=self.track_frame, anchor='nw')
        self.track_frame.bind('<Configure>', lambda event: self.track_canvas.configure(scrollregion=self.track_canvas.bbox('all')))
        self.track_canvas.bind('<Configure>', lambda event: self.track_canvas.itemconfigure(self.track_window, width=event.width))
        self.empty = self.label(self.track_frame, 'Музыка начинается со ссылки\n\nДобавьте плейлист YouTube или YouTube Music.\nЗдесь появятся обложки, длительность и статус каждого трека.',
                                color=MUTED, size=12, justify='center', pady=70)
        self.empty.pack(fill='both', expand=True)

    def select_quality(self, quality):
        self.quality.set(quality)
        for value, button in self.quality_buttons.items():
            button.fill = ORANGE if value == quality else BG
            button.border = ORANGE if value == quality else LINE
            button.draw()

    def select_concurrency(self, value):
        self.concurrency.set(value)
        for number, button in self.concurrency_buttons.items():
            button.fill = CYAN if number == value else BG
            button.color = BG if number == value else TEXT
            button.border = CYAN if number == value else LINE
            button.draw()

    def update_search_placeholder(self):
        if self.search.get() or self.focus_get() == self.search_entry:
            self.search_placeholder.place_forget()
        else:
            self.search_placeholder.place(x=13, rely=.5, anchor='w')

    def filter_rows(self):
        self.update_search_placeholder()
        query = self.search.get().casefold().strip()
        visible = 0
        for row in self.rows.values():
            row.pack_forget()
            if query in row.entry['title'].casefold():
                row.pack(fill='x', pady=(0, 2))
                visible += 1
        self.empty.pack_forget()
        if self.rows and not visible:
            self.empty.configure(text='Ничего не найдено\n\nПопробуйте другое название.')
            self.empty.pack(fill='x')
        self.track_canvas.yview_moveto(0)

    def scroll_tracks(self, event):
        widget = event.widget
        while widget is not None:
            if widget in (self.track_canvas, self.sidebar_canvas):
                widget.yview_scroll(-int(event.delta / 120), 'units')
                return 'break'
            widget = getattr(widget, 'master', None)

    def schedule_preview(self, *args):
        self.preview_token += 1
        if self.preview_after:
            self.after_cancel(self.preview_after)
            self.preview_after = None
        if self.busy:
            return
        try:
            url = playlist_url(self.url.get())
        except ValueError:
            self.preview_hint.configure(text='Вставьте ссылку на плейлист', fg='#668095')
            self.clear_playlist()
            return
        if self.playlist and self.playlist['url'] == url:
            return
        self.clear_playlist()
        self.preview_hint.configure(text='Читаю плейлист…', fg=CYAN)
        self.preview_after = self.after(700, lambda: self.start_preview(url, self.preview_token))

    def start_preview(self, url, token):
        self.preview_after = None

        def work():
            try:
                data = fetch_playlist(url, threading.Event())
                self.events.put(('preview', (token, data, None)))
            except Exception as error:
                self.events.put(('preview', (token, None, str(error))))
        threading.Thread(target=work, daemon=True).start()

    def clear_playlist(self):
        self.image_cancel.set()
        self.image_generation += 1
        self.playlist = None
        for row in self.rows.values():
            row.destroy()
        self.rows.clear()
        self.playlist_title.set('Ваш следующий плейлист')
        self.playlist_info.set('Вставьте ссылку слева — треки появятся здесь')
        self.playlist_cover.reset()
        self.empty.configure(text='Музыка начинается со ссылки\n\nДобавьте плейлист YouTube или YouTube Music.\nЗдесь появятся обложки, длительность и статус каждого трека.')
        self.empty.pack(fill='x')

    def show_playlist(self, data):
        self.clear_playlist()
        self.playlist = data
        self.empty.pack_forget()
        self.playlist_title.set(data['title'])
        entries = data['entries']
        known = [entry['duration'] for entry in entries if entry['duration'] is not None]
        total_duration = sum(known)
        duration = f'{int(total_duration // 3600)} ч {int(total_duration % 3600 // 60):02} мин'
        if len(known) != len(entries):
            duration = 'длительность уточняется'
        self.playlist_info.set(f'{len(entries)} треков  ·  {duration}')
        self.preview_hint.configure(text=f'Найдено треков: {len(entries)}', fg=GREEN)
        for entry in entries:
            row = TrackRow(self.track_frame, entry)
            self.rows[entry['key']] = row
        self.filter_rows()
        self.image_cancel = threading.Event()
        threading.Thread(target=self.load_images, args=(data, self.image_generation, self.image_cancel), daemon=True).start()

    def load_images(self, data, generation, cancel):
        targets = [('__playlist__', data.get('thumbnail'))]
        targets.extend((entry['key'], entry['thumbnail']) for entry in data['entries'])
        cache = {}
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
                                    raise ValueError('Thumbnail is too large')
                            cache[url] = bytes(content)
                    self.events.put(('image', (generation, key, cache[url])))
                except (requests.RequestException, ValueError):
                    continue

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
        self.busy = busy
        for widget in (self.start_button, self.link_entry, self.folder_entry, self.browse,
                       *self.quality_buttons.values(), *self.concurrency_buttons.values()):
            widget.configure(state='disabled' if busy else 'normal')
        self.stop_button.configure(state='normal' if busy else 'disabled')
        self.indicator.configure(fg=CYAN if busy else GREEN)

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            url = playlist_url(self.url.get())
            if not self.folder.get().strip():
                raise ValueError('Выберите папку сохранения.')
            folder = Path(self.folder.get()).expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps({'folder': str(folder), 'quality': self.quality.get(), 'url': url,
                                          'concurrency': int(self.concurrency.get())}, ensure_ascii=False), encoding='utf-8')
        except (ValueError, OSError) as error:
            messagebox.showerror('YT', str(error))
            return
        if self.preview_after:
            self.after_cancel(self.preview_after)
            self.preview_after = None
        self.preview_token += 1
        self.cancel.clear()
        self.active_transfers.clear()
        self.set_busy(True)
        self.progress_bar['value'] = 0
        self.overall_percent.set('0%')
        self.summary.set('Подготовка плейлиста…')
        self.status.set('Подключение к YouTube')
        self.detail.set('Скорость —  ·  Осталось —')
        cached = self.playlist if self.playlist and self.playlist['url'] == url else None
        self.worker = threading.Thread(target=download,
            args=(url, str(folder), self.quality.get(), self.events, self.cancel),
            kwargs={'playlist': cached, 'concurrency': int(self.concurrency.get())}, daemon=True)
        self.worker.start()

    def stop(self):
        self.cancel.set()
        self.stop_button.configure(state='disabled')
        self.status.set('Останавливаю… Ожидаю завершения текущей операции.')

    def add_log(self, value):
        self.log.configure(state='normal')
        self.log.insert('end', value + '\n')
        if int(self.log.index('end-1c').split('.')[0]) > 1000:
            self.log.delete('1.0', '200.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def handle_event(self, kind, value):
        if kind == 'log':
            self.add_log(value)
        elif kind == 'preview':
            token, data, error = value
            if token != self.preview_token or self.busy:
                return
            if error:
                self.preview_hint.configure(text='Не удалось прочитать плейлист', fg=RED)
                self.playlist_title.set('Плейлист недоступен')
                self.playlist_info.set('Проверьте ссылку и доступ к YouTube')
                self.add_log(error)
            else:
                self.show_playlist(data)
        elif kind == 'playlist':
            self.active_transfers.clear()
            self.show_playlist(value)
            self.summary.set(f'Загрузка…  0 из {len(value["entries"])}')
        elif kind == 'image':
            generation, key, data = value
            if generation == self.image_generation:
                cover = self.playlist_cover if key == '__playlist__' else self.rows.get(key)
                if cover:
                    (cover if key == '__playlist__' else cover.cover).set_image(data)
        elif kind == 'track':
            row = self.rows.get(value['key'])
            if row:
                row.update_state(**{key: item for key, item in value.items() if key != 'key'})
                if value['state'] in ('downloading', 'converting'):
                    self.active_transfers[value['key']] = value
                else:
                    self.active_transfers.pop(value['key'], None)
                if not self.cancel.is_set():
                    downloading = sum(item['state'] == 'downloading' for item in self.active_transfers.values())
                    converting = sum(item['state'] == 'converting' for item in self.active_transfers.values())
                    speed = sum((item.get('speed') or 0) for item in self.active_transfers.values() if item['state'] == 'downloading')
                    self.status.set(f'Скачивание: {downloading}  ·  Преобразование в MP3: {converting}')
                    self.detail.set(f'Скорость {speed / 1048576:.1f} МБ/с  ·  Активно {len(self.active_transfers)}')
        elif kind == 'overall':
            percent = value['finished'] / value['total'] * 100
            self.progress_bar['value'] = percent
            self.overall_percent.set(f'{int(percent)}%')
            self.summary.set(f'Обработано  {value["finished"]} из {value["total"]}')
        elif kind == 'done':
            self.active_transfers.clear()
            self.status.set(value)
            self.add_log(value)
            self.detail.set('Скорость —  ·  Осталось —')
            self.set_busy(False)
            if value.startswith('Ошибка:') or 'с ошибками' in value:
                self.indicator.configure(fg=RED)
            for row in self.rows.values():
                if row.state in ('queued', 'downloading', 'converting'):
                    row.update_state('stopped')

    def poll(self):
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            self.handle_event(kind, value)
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.destroy()
            return
        self.after(80, self.poll)

    def destroy(self):
        self.image_cancel.set()
        for callback in self.tk.call('after', 'info'):
            self.after_cancel(callback)
        super().destroy()

    def close(self):
        if self.worker and self.worker.is_alive():
            if messagebox.askyesno('YT', 'Остановить загрузку и закрыть приложение?'):
                self.closing = True
                self.stop()
        else:
            self.destroy()
