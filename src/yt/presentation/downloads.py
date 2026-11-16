"""Download form and playlist layout, separate from application orchestration."""

import tkinter as tk
from tkinter import ttk

from yt.presentation.theme import BG, CYAN, FONT, LINE, MUTED, RED, TEXT
from yt.presentation.widgets import Button, Cover, entry, label


class DownloadsView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        body = self
        sidebar = tk.Frame(body, bg=BG, width=355)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(body, bg="#0d1b28", width=1).pack(side="left", fill="y")
        self.sidebar_canvas = tk.Canvas(sidebar, bg=BG, highlightthickness=0, bd=0)
        self.sidebar_canvas.pack(fill="both", expand=True)
        left = tk.Frame(self.sidebar_canvas, bg=BG)
        left_window = self.sidebar_canvas.create_window(
            (26, 26), window=left, width=303, anchor="nw"
        )

        def resize_sidebar(event=None):
            available = self.sidebar_canvas.winfo_height() - 52
            height = max(available, left.winfo_reqheight())
            width = self.sidebar_canvas.winfo_width()
            self.sidebar_canvas.itemconfigure(
                left_window, height=height, width=max(200, width - 52)
            )
            self.sidebar_canvas.configure(scrollregion=(0, 0, width, height + 52))

        self.sidebar_canvas.bind("<Configure>", resize_sidebar)
        left.bind("<Configure>", resize_sidebar)

        def resize_columns(event):
            width = min(420, max(300, int(event.width * 0.24)))
            if sidebar.winfo_reqwidth() != width:
                sidebar.configure(width=width)

        body.bind("<Configure>", resize_columns)
        logo = tk.Frame(left, bg=BG)
        logo.pack(fill="x")
        label(logo, "YT", color=RED, size=36, bold=True).pack(side="left")
        label(logo, " → MP3", color=CYAN, size=32, bold=True).pack(side="left")
        label(left, "Ваш плейлист. Ваша музыка.", color=MUTED, size=11).pack(
            anchor="w", pady=(0, 28)
        )
        label(left, "ССЫЛКА НА ПЛЕЙЛИСТ", color=CYAN, size=10, bold=True).pack(anchor="w")
        border, self.link_entry = entry(left, app.url, font_size=10)
        border.pack(fill="x", pady=(9, 5))
        self.preview_hint = label(
            left, "Список загрузится автоматически", color="#668095", size=9, anchor="w"
        )
        self.preview_hint.pack(fill="x", pady=(0, 20))
        label(left, "ПАПКА СОХРАНЕНИЯ", color=CYAN, size=10, bold=True).pack(anchor="w")
        folder_frame = tk.Frame(left, bg=BG, highlightthickness=1, highlightbackground=LINE)
        folder_frame.pack(fill="x", pady=(9, 23))
        self.folder_entry = tk.Entry(
            folder_frame,
            textvariable=app.folder,
            bg=BG,
            fg=TEXT,
            insertbackground=CYAN,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(FONT, 10),
            width=12,
            disabledbackground=BG,
            disabledforeground=MUTED,
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=11, pady=17)
        self.browse = Button(folder_frame, "Выбрать…", app.choose_folder, height=34, font_size=9)
        self.browse.configure(width=83)
        self.browse.pack(side="right", padx=(0, 8), pady=8)
        label(left, "MP3 · кбит/с", color=CYAN, size=10, bold=True).pack(anchor="w")
        qualities = tk.Frame(left, bg=BG)
        qualities.pack(fill="x", pady=(10, 16))
        self.quality_buttons = {}
        for column, quality in enumerate(("128", "192", "256", "320")):
            qualities.columnconfigure(column, weight=1, uniform="quality")
            button = Button(
                qualities,
                quality,
                lambda value=quality: app.select_quality(value),
                height=48,
                font_size=14,
            )
            button.grid(row=0, column=column, sticky="ew", padx=(0, 3))
            self.quality_buttons[quality] = button
        label(left, "ПАРАЛЛЕЛЬНО ТРЕКОВ", color=CYAN, size=10, bold=True).pack(anchor="w")
        workers = tk.Frame(left, bg=BG)
        workers.pack(fill="x", pady=(9, 20))
        self.concurrency_buttons = {}
        for column, value in enumerate(("1", "2", "3", "4", "5", "6")):
            workers.columnconfigure(column, weight=1, uniform="workers")
            button = Button(
                workers,
                value,
                lambda number=value: app.select_concurrency(number),
                height=35,
                font_size=11,
            )
            button.grid(row=0, column=column, sticky="ew", padx=(0, 3))
            self.concurrency_buttons[value] = button
        self.start_button = Button(
            left, "Скачать плейлист", app.start, fill=RED, border=RED, height=62, font_size=15
        )
        self.start_button.pack(fill="x", pady=(0, 10))
        self.stop_button = Button(left, "Остановить", app.stop, height=44)
        self.stop_button.pack(fill="x", pady=(0, 10))
        self.stop_button.configure(state="disabled")
        Button(left, "Открыть папку", app.open_folder, color=MUTED, height=42).pack(fill="x")
        progress = tk.Frame(
            left, bg=BG, padx=15, pady=15, highlightthickness=1, highlightbackground=LINE
        )
        progress.pack(side="bottom", fill="x", pady=(20, 0))
        label(progress, variable=app.summary, size=10, bold=True, anchor="w").pack(fill="x")
        bar_frame = tk.Frame(progress, bg=BG)
        bar_frame.pack(fill="x", pady=12)
        self.progress_bar = ttk.Progressbar(
            bar_frame, style="Overall.Horizontal.TProgressbar", maximum=100
        )
        self.progress_bar.pack(side="left", fill="x", expand=True)
        label(bar_frame, variable=app.overall_percent, size=10, width=5, anchor="e").pack(
            side="right"
        )
        label(progress, variable=app.detail, color=MUTED, size=9, anchor="w", wraplength=265).pack(
            fill="x"
        )
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        header = tk.Frame(right, bg=BG)
        header.pack(fill="x", padx=26, pady=(28, 20))
        self.playlist_cover = Cover(header, 88)
        self.playlist_cover.pack(side="left", padx=(0, 20))
        heading = tk.Frame(header, bg=BG)
        heading.pack(side="left", fill="both", expand=True)
        label(heading, variable=app.playlist_title, size=21, bold=True, anchor="w", width=1).pack(
            fill="x", pady=(9, 6)
        )
        label(heading, variable=app.playlist_info, color=MUTED, size=11, anchor="w", width=1).pack(
            fill="x"
        )
        search_border, self.search_entry = entry(right, app.search)
        search_border.pack(fill="x", padx=26, pady=(0, 16))
        self.search_placeholder = label(
            search_border, "Поиск по названию…", color=MUTED, size=10, cursor="xterm"
        )
        self.search_placeholder.place(x=13, rely=0.5, anchor="w")
        self.search_placeholder.bind("<Button-1>", lambda event: self.search_entry.focus_set())
        self.search_entry.bind("<FocusIn>", lambda event: app.update_search_placeholder())
        self.search_entry.bind("<FocusOut>", lambda event: app.update_search_placeholder())
        journal = tk.Frame(right, bg=BG)
        journal.pack(side="bottom", fill="x", padx=26, pady=(12, 18))
        label(journal, "ЖУРНАЛ", color="#597184", size=8, bold=True).pack(anchor="w", pady=(0, 6))
        self.log = tk.Text(
            journal,
            height=4,
            bg=BG,
            fg=MUTED,
            insertbackground=CYAN,
            relief="flat",
            font=("Consolas", 9),
            state="disabled",
            wrap="word",
            bd=0,
            highlightthickness=0,
        )
        self.log.pack(fill="x")
        tracks = tk.Frame(right, bg=BG)
        tracks.pack(fill="both", expand=True, padx=(8, 12))
        self.track_canvas = tk.Canvas(tracks, bg=BG, highlightthickness=0, bd=0)
        self.track_canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(tracks, orient="vertical", command=self.track_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.track_canvas.configure(yscrollcommand=scrollbar.set)
        self.track_frame = tk.Frame(self.track_canvas, bg=BG)
        self.track_window = self.track_canvas.create_window(
            (0, 0), window=self.track_frame, anchor="nw"
        )
        self.track_frame.bind(
            "<Configure>",
            lambda event: self.track_canvas.configure(scrollregion=self.track_canvas.bbox("all")),
        )
        self.track_canvas.bind(
            "<Configure>",
            lambda event: self.track_canvas.itemconfigure(self.track_window, width=event.width),
        )
        self.empty = label(
            self.track_frame,
            "Музыка начинается со ссылки\n\nДобавьте плейлист YouTube или YouTube Music.\nЗдесь появятся обложки, длительность и статус каждого трека.",
            color=MUTED,
            size=12,
            justify="center",
            pady=70,
        )
        self.empty.pack(fill="both", expand=True)
