"""Local library view and persistent bottom player bar."""
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from player import scan_library
from ui import BG, PANEL, LINE, TEXT, MUTED, CYAN, RED, FONT, Button, Cover, duration_text


class LibraryView(tk.Frame):
    def __init__(self, parent, app, folder):
        super().__init__(parent, bg=BG)
        self.app = app
        self.folder = tk.StringVar(value=folder)
        self.search = tk.StringVar()
        self.token = 0
        self.applied_folder = None
        self.tracks = []
        self.refresh_after = None
        self.revision = -1
        header = tk.Frame(self, bg=BG)
        header.pack(fill='x', padx=32, pady=(20, 12))
        header.columnconfigure(0, weight=1)
        app.label(header, 'Моя музыка', size=25, bold=True, anchor='w', width=1).grid(row=0, column=0, sticky='ew')
        self.info = app.label(header, 'Скачанные MP3 · работают без интернета', color=MUTED, size=10, anchor='w', width=1)
        self.info.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        controls = tk.Frame(header, bg=BG)
        controls.grid(row=0, column=1, rowspan=2, sticky='e', padx=(20, 0))
        self.play_button = Button(controls, '▶  Слушать', self.play_first, fill=CYAN, color=BG, border=CYAN, height=42)
        self.play_button.configure(width=140)
        self.play_button.pack(side='left', padx=(0, 12))
        for text, command, width in [('Выбрать папку', self.choose_folder, 155),
                                      ('Папка загрузки', self.use_download_folder, 155),
                                      ('Обновить', self.refresh, 115)]:
            button = Button(controls, text, command, height=42)
            button.configure(width=width)
            button.pack(side='left', padx=(0, 10))
        self.path_label = app.label(self, variable=self.folder, color='#658095', size=10, anchor='w', width=1)
        self.path_label.pack(fill='x', padx=34, pady=(0, 12))
        border, self.search_entry = app.entry(self, self.search)
        border.pack(fill='x', padx=32, pady=(0, 12))
        self.search_entry.pack_configure(pady=10)
        self.placeholder = app.label(border, 'Поиск в моей музыке…', color=MUTED, size=10)
        self.placeholder.place(x=13, rely=.5, anchor='w')
        self.placeholder.bind('<Button-1>', lambda event: self.search_entry.focus_set())
        self.search_entry.bind('<FocusIn>', lambda event: self.update_placeholder(), add='+')
        self.search_entry.bind('<FocusOut>', lambda event: self.update_placeholder(), add='+')
        table = tk.Frame(self, bg=BG)
        table.pack(fill='both', expand=True, padx=32, pady=(0, 12))
        self.tree = ttk.Treeview(table, columns=('number', 'title', 'artist', 'duration'),
                                 show='headings', selectmode='browse', style='Library.Treeview')
        for name, title, width, stretch in [('number', '#', 55, False), ('title', 'НАЗВАНИЕ', 420, True),
                                           ('artist', 'ИСПОЛНИТЕЛЬ', 240, True), ('duration', 'ВРЕМЯ', 95, False)]:
            self.tree.heading(name, text=title, anchor='w')
            self.tree.column(name, width=width, minwidth=width if not stretch else 120, stretch=stretch, anchor='w')
        self.tree.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        scroll.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.tag_configure('current', foreground=CYAN)
        self.tree.bind('<Double-1>', self.play_selected)
        self.tree.bind('<Return>', self.play_selected)
        self.empty = app.label(table, 'Здесь будет ваша музыка\n\nВыберите папку со скачанными MP3\nили скачайте плейлист в разделе «Загрузки».',
                               color=MUTED, size=13, justify='center')
        self.empty.place(relx=.5, rely=.45, anchor='center')
        self.hint = app.label(self, 'Двойной щелчок — слушать  ·  Поиск не меняет очередь воспроизведения', color='#658095', size=10, anchor='w')
        self.hint.pack(fill='x', padx=34, pady=(0, 20))
        self.search.trace_add('write', lambda *args: self.render())

    def update_placeholder(self):
        if self.search.get() or self.focus_get() == self.search_entry:
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=13, rely=.5, anchor='w')

    def choose_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.folder.get() if Path(self.folder.get()).is_dir() else Path.home())
        if chosen:
            self.app.library_follow = False
            self.folder.set(chosen)
            self.refresh()
            self.app.request_save()

    def use_download_folder(self):
        self.app.library_follow = True
        self.folder.set(self.app.folder.get())
        self.refresh()
        self.app.request_save()

    def schedule_refresh(self):
        if self.refresh_after:
            self.app.after_cancel(self.refresh_after)
        self.refresh_after = self.app.after(650, self.refresh)

    def refresh(self):
        self.refresh_after = None
        self.token += 1
        token, folder = self.token, self.folder.get()
        same_folder = Path(folder).resolve() == Path(self.app.folder.get()).resolve()
        excluded = [row.entry['id'] for row in self.app.rows.values()
                    if same_folder and row.state in ('downloading', 'converting')]
        self.info.configure(text='Обновляю библиотеку…')

        def work():
            try:
                tracks, unreadable = scan_library(folder, excluded)
                self.app.events.put(('library', (token, folder, tracks, unreadable, None)))
            except Exception as error:
                self.app.events.put(('library', (token, folder, [], 0, str(error))))
        threading.Thread(target=work, daemon=True).start()

    def apply(self, payload):
        token, folder, tracks, unreadable, error = payload
        if token != self.token:
            return
        if error:
            self.info.configure(text='Не удалось прочитать папку', fg=RED)
            self.app.add_log(error)
            return
        self.app.player.set_library(tracks, reset=self.applied_folder != folder)
        self.applied_folder = folder
        self.tracks = tracks
        duration = sum(track.duration for track in tracks)
        text = f'{len(tracks)} треков  ·  {int(duration // 3600)} ч {int(duration % 3600 // 60):02} мин  ·  На этом компьютере'
        if unreadable:
            text += f'  ·  Не прочитано: {unreadable}'
        self.info.configure(text=text, fg=MUTED)
        self.render()

    def render(self):
        self.update_placeholder()
        selected = self.tree.selection()
        view = self.tree.yview()
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().strip().casefold()
        current = self.app.player.current.key if self.app.player.current else None
        count = 0
        for index, track in enumerate(self.tracks, 1):
            if query not in f'{track.title} {track.artist} {track.path.name}'.casefold():
                continue
            active = track.key == current
            self.tree.insert('', 'end', iid=track.key, values=(
                '▶' if active else index, track.title, track.artist or '—', duration_text(track.duration)),
                tags=('current',) if active else ())
            count += 1
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        if count:
            self.empty.place_forget()
        else:
            text = 'Ничего не найдено\n\nПопробуйте другое название.' if self.tracks else 'Здесь будет ваша музыка\n\nВыберите папку со скачанными MP3\nили скачайте плейлист в разделе «Загрузки».'
            self.empty.configure(text=text)
            self.empty.place(relx=.5, rely=.45, anchor='center')
        self.play_button.configure(state='normal' if self.tracks else 'disabled')
        if view:
            self.tree.yview_moveto(view[0])

    def play_selected(self, event=None):
        if event is not None and getattr(event, 'num', None) == 1:
            row = self.tree.identify_row(event.y)
            if not row:
                return 'break'
            self.tree.selection_set(row)
        selected = self.tree.selection()
        if selected:
            self.app.player.play(selected[0])
        return 'break'

    def play_first(self):
        if not self.tracks:
            return
        self.app.player.queue.new_pass()
        self.app.player.next()

    def tick(self):
        if self.revision != self.app.player.revision:
            self.revision = self.app.player.revision
            self.render()


class PlayerBar(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        self.app = app
        self.dragging = False
        self.revision = -1
        self.last_volume = max(app.player.volume, .35)
        self.columnconfigure(0, weight=2, minsize=230)
        self.columnconfigure(1, weight=3, minsize=400)
        self.columnconfigure(2, weight=1, minsize=240)
        info = tk.Frame(self, bg=PANEL)
        info.grid(row=0, column=0, sticky='nsew', padx=24, pady=16)
        Cover(info, 52).pack(side='left', padx=(0, 14))
        names = tk.Frame(info, bg=PANEL)
        names.pack(side='left', fill='both', expand=True)
        self.title = app.label(names, 'Выберите трек', size=11, bold=True, anchor='w', width=1)
        self.title.pack(fill='x', pady=(4, 4))
        self.subtitle = app.label(names, 'Локальная музыка · без интернета', color=MUTED, size=9, anchor='w', width=1)
        self.subtitle.pack(fill='x')
        transport = tk.Frame(self, bg=PANEL)
        transport.grid(row=0, column=1, sticky='ew', padx=12, pady=10)
        controls = tk.Frame(transport, bg=PANEL)
        controls.pack(anchor='center')
        self.previous = Button(controls, '⏮', app.player.previous, height=36, font_size=15)
        self.previous.configure(width=45)
        self.previous.pack(side='left', padx=6)
        self.play = Button(controls, '▶', app.player.toggle, fill=CYAN, color=BG, border=CYAN, height=38, font_size=16)
        self.play.configure(width=62)
        self.play.pack(side='left', padx=6)
        self.next = Button(controls, '⏭', app.player.next, height=36, font_size=15)
        self.next.configure(width=45)
        self.next.pack(side='left', padx=6)
        self.shuffle = Button(controls, 'Перемешать', self.toggle_shuffle, height=34, font_size=9)
        self.shuffle.configure(width=114)
        self.shuffle.pack(side='left', padx=(12, 0))
        timeline = tk.Frame(transport, bg=PANEL)
        timeline.pack(fill='x', pady=(6, 0))
        self.elapsed = app.label(timeline, '0:00', color=MUTED, size=9, width=6)
        self.elapsed.pack(side='left')
        self.position = tk.DoubleVar(value=0)
        self.seek = ttk.Scale(timeline, from_=0, to=1, variable=self.position, style='Player.Horizontal.TScale')
        self.seek.pack(side='left', fill='x', expand=True)
        self.seek.bind('<ButtonPress-1>', lambda event: setattr(self, 'dragging', True))
        self.seek.bind('<ButtonRelease-1>', self.finish_seek)
        self.seek.bind('<KeyRelease>', lambda event: app.player.seek(self.position.get()))
        self.duration = app.label(timeline, '0:00', color=MUTED, size=9, width=6)
        self.duration.pack(side='right')
        volume = tk.Frame(self, bg=PANEL)
        volume.grid(row=0, column=2, sticky='ew', padx=24, pady=16)
        self.mute = Button(volume, 'Звук', self.toggle_mute, height=32, font_size=9)
        self.mute.configure(width=48)
        self.mute.pack(side='left', padx=(0, 10))
        self.volume = tk.DoubleVar(value=app.player.volume * 100)
        ttk.Scale(volume, from_=0, to=100, variable=self.volume, command=self.change_volume,
                  style='Player.Horizontal.TScale').pack(side='left', fill='x', expand=True)
        self.volume_label = app.label(volume, f'{int(self.volume.get())}%', color=MUTED, size=9, width=5)
        self.volume_label.pack(side='right')
        self.tick()

    def finish_seek(self, event=None):
        self.app.player.seek(self.position.get())
        self.dragging = False

    def change_volume(self, value):
        volume = float(value) / 100
        self.app.player.set_volume(volume)
        if volume > 0:
            self.last_volume = volume
        self.volume_label.configure(text=f'{int(round(float(value)))}%')
        self.mute.label = 'Звук' if volume else 'Тихо'
        self.mute.draw()
        self.app.request_save()

    def toggle_mute(self):
        value = 0 if self.app.player.volume else self.last_volume
        self.volume.set(value * 100)
        self.change_volume(value * 100)

    def toggle_shuffle(self):
        self.app.player.queue.set_shuffle(not self.app.player.queue.shuffle)
        self.app.player.revision += 1
        self.app.request_save()
        self.tick()

    def tick(self):
        player = self.app.player
        if self.revision != player.revision:
            self.revision = player.revision
            self.title.configure(text=player.current.title if player.current else 'Выберите трек')
            statuses = {'playing': 'Сейчас играет', 'paused': 'На паузе', 'idle': 'Локальная музыка · без интернета',
                        'ended': 'Очередь завершена · ▶ начинает новый проход',
                        'error': 'Ошибка звука · проверьте файл и аудиоустройство'}
            self.subtitle.configure(text=statuses[player.state], fg=RED if player.state == 'error' else MUTED)
            self.play.label = 'Ⅱ' if player.state == 'playing' else '▶'
            self.play.configure(state='normal' if player.tracks else 'disabled')
            self.previous.configure(state='normal' if player.current else 'disabled')
            self.next.configure(state='normal' if player.tracks else 'disabled')
            self.play.draw()
            enabled = player.queue.shuffle
            self.shuffle.fill, self.shuffle.color = (CYAN, BG) if enabled else (BG, TEXT)
            self.shuffle.border = CYAN if enabled else LINE
            self.shuffle.draw()
            self.seek.configure(to=max(1, player.current.duration if player.current else 0),
                                state='normal' if player.state in ('playing', 'paused') else 'disabled')
        if not self.dragging:
            self.position.set(player.position)
        self.elapsed.configure(text=duration_text(self.position.get()))
        self.duration.configure(text=duration_text(player.current.duration if player.current else 0))
        while player.errors:
            self.app.add_log(player.errors.pop(0))
