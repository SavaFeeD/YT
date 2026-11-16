"""PlayerBar desktop view."""

import tkinter as tk
from tkinter import ttk

from yt.presentation.theme import BG, CYAN, LINE, MUTED, PANEL, RED, TEXT
from yt.presentation.widgets import Button, Cover, duration_text, label


class PlayerBar(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        self.app = app
        self.dragging = False
        self.revision = -1
        self.last_volume = max(app.player.volume, 0.35)
        self.columnconfigure(0, weight=2, minsize=230)
        self.columnconfigure(1, weight=3, minsize=400)
        self.columnconfigure(2, weight=1, minsize=240)
        info = tk.Frame(self, bg=PANEL)
        info.grid(row=0, column=0, sticky="nsew", padx=24, pady=16)
        Cover(info, 52).pack(side="left", padx=(0, 14))
        names = tk.Frame(info, bg=PANEL)
        names.pack(side="left", fill="both", expand=True)
        self.title = label(names, "Выберите трек", size=11, bold=True, anchor="w", width=1)
        self.title.pack(fill="x", pady=(4, 4))
        self.subtitle = label(
            names, "Локальная музыка · без интернета", color=MUTED, size=9, anchor="w", width=1
        )
        self.subtitle.pack(fill="x")
        transport = tk.Frame(self, bg=PANEL)
        transport.grid(row=0, column=1, sticky="ew", padx=12, pady=10)
        controls = tk.Frame(transport, bg=PANEL)
        controls.pack(anchor="center")
        self.previous = Button(controls, "⏮", app.player.previous, height=36, font_size=15)
        self.previous.configure(width=45)
        self.previous.pack(side="left", padx=6)
        self.play = Button(
            controls,
            "▶",
            app.player.toggle,
            fill=CYAN,
            color=BG,
            border=CYAN,
            height=38,
            font_size=16,
        )
        self.play.configure(width=62)
        self.play.pack(side="left", padx=6)
        self.next = Button(controls, "⏭", app.player.next, height=36, font_size=15)
        self.next.configure(width=45)
        self.next.pack(side="left", padx=6)
        self.shuffle = Button(controls, "Перемешать", self.toggle_shuffle, height=34, font_size=9)
        self.shuffle.configure(width=114)
        self.shuffle.pack(side="left", padx=(12, 0))
        timeline = tk.Frame(transport, bg=PANEL)
        timeline.pack(fill="x", pady=(6, 0))
        self.elapsed = label(timeline, "0:00", color=MUTED, size=9, width=6)
        self.elapsed.pack(side="left")
        self.position = tk.DoubleVar(value=0)
        self.seek = ttk.Scale(
            timeline, from_=0, to=1, variable=self.position, style="Player.Horizontal.TScale"
        )
        self.seek.pack(side="left", fill="x", expand=True)
        self.seek.bind("<ButtonPress-1>", lambda event: setattr(self, "dragging", True))
        self.seek.bind("<ButtonRelease-1>", self.finish_seek)
        self.seek.bind("<KeyRelease>", lambda event: app.player.seek(self.position.get()))
        self.duration = label(timeline, "0:00", color=MUTED, size=9, width=6)
        self.duration.pack(side="right")
        volume = tk.Frame(self, bg=PANEL)
        volume.grid(row=0, column=2, sticky="ew", padx=24, pady=16)
        self.mute = Button(volume, "Звук", self.toggle_mute, height=32, font_size=9)
        self.mute.configure(width=48)
        self.mute.pack(side="left", padx=(0, 10))
        self.volume = tk.DoubleVar(value=app.player.volume * 100)
        ttk.Scale(
            volume,
            from_=0,
            to=100,
            variable=self.volume,
            command=self.change_volume,
            style="Player.Horizontal.TScale",
        ).pack(side="left", fill="x", expand=True)
        self.volume_label = label(
            volume, f"{int(self.volume.get())}%", color=MUTED, size=9, width=5
        )
        self.volume_label.pack(side="right")
        self.tick()

    def finish_seek(self, event=None):
        self.app.player.seek(self.position.get())
        self.dragging = False

    def change_volume(self, value):
        volume = float(value) / 100
        self.app.player.set_volume(volume)
        if volume > 0:
            self.last_volume = volume
        self.volume_label.configure(text=f"{int(round(float(value)))}%")
        self.mute.label = "Звук" if volume else "Тихо"
        self.mute.draw()
        self.app.request_save()

    def toggle_mute(self):
        value = 0 if self.app.player.volume else self.last_volume
        self.volume.set(value * 100)
        self.change_volume(value * 100)

    def toggle_shuffle(self):
        self.app.player.set_shuffle(not self.app.player.shuffle)
        self.app.request_save()
        self.tick()

    def tick(self):
        player = self.app.player
        if self.revision != player.revision:
            self.revision = player.revision
            self.title.configure(text=player.current.title if player.current else "Выберите трек")
            statuses = {
                "playing": "Сейчас играет",
                "paused": "На паузе",
                "idle": "Локальная музыка · без интернета",
                "ended": "Очередь завершена · ▶ начинает новый проход",
                "error": "Ошибка звука · проверьте файл и аудиоустройство",
            }
            self.subtitle.configure(
                text=statuses[player.state], fg=RED if player.state == "error" else MUTED
            )
            self.play.label = "Ⅱ" if player.state == "playing" else "▶"
            self.play.configure(state="normal" if player.tracks else "disabled")
            self.previous.configure(state="normal" if player.current else "disabled")
            self.next.configure(state="normal" if player.tracks else "disabled")
            self.play.draw()
            enabled = player.shuffle
            self.shuffle.fill, self.shuffle.color = (CYAN, BG) if enabled else (BG, TEXT)
            self.shuffle.border = CYAN if enabled else LINE
            self.shuffle.draw()
            self.seek.configure(
                to=max(1, player.current.duration if player.current else 0),
                state="normal" if player.state in ("playing", "paused") else "disabled",
            )
        if not self.dragging:
            self.position.set(player.position)
        self.elapsed.configure(text=duration_text(self.position.get()))
        self.duration.configure(
            text=duration_text(player.current.duration if player.current else 0)
        )
        while player.errors:
            self.app.add_log(player.errors.pop(0))
