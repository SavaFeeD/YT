"""Reusable widgets; no main-window imports."""

import io
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk

from yt.presentation.theme import BG, CYAN, FONT, GREEN, LINE, MUTED, ORANGE, RED, ROW, TEXT


def duration_text(seconds):
    if seconds is None:
        return "—"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


class Button(tk.Canvas):
    def __init__(
        self, parent, text, command, *, fill=BG, color=TEXT, height=44, font_size=11, border=LINE
    ):
        super().__init__(
            parent,
            height=height,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=True,
        )
        self.label, self.command = text, command
        self.fill, self.color, self.border = fill, color, border
        self.font_size = font_size
        self.hover = False
        self.bind("<Configure>", lambda event: self.draw())
        self.bind("<Enter>", lambda event: self.set_hover(True))
        self.bind("<Leave>", lambda event: self.set_hover(False))
        self.bind("<FocusIn>", lambda event: self.draw())
        self.bind("<FocusOut>", lambda event: self.draw())
        self.bind("<Button-1>", self.invoke)
        self.bind("<Return>", self.invoke)
        self.bind("<space>", self.invoke)

    def configure(self, cnf=None, **kwargs):
        result = super().configure(cnf, **kwargs)
        if hasattr(self, "label"):
            self.draw()
        return result

    def set_hover(self, value):
        self.hover = value
        self.draw()

    def draw(self):
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        disabled = self.cget("state") == "disabled"
        fill = "#101c29" if disabled else self.fill
        if self.hover and not disabled and self.fill == BG:
            fill = "#112332"
        radius = 10
        points = [
            radius,
            1,
            width - radius,
            1,
            width - 1,
            1,
            width - 1,
            radius,
            width - 1,
            height - radius,
            width - 1,
            height - 1,
            width - radius,
            height - 1,
            radius,
            height - 1,
            1,
            height - 1,
            1,
            height - radius,
            1,
            radius,
            1,
            1,
        ]
        border = CYAN if self.focus_get() == self and not disabled else self.border
        self.create_polygon(points, smooth=True, fill=fill, outline=border)
        self.create_text(
            width / 2,
            height / 2,
            text=self.label,
            fill=MUTED if disabled else self.color,
            font=(FONT, self.font_size, "bold" if self.fill != BG else "normal"),
        )

    def invoke(self, event=None):
        if self.cget("state") != "disabled":
            self.focus_set()
            self.command()


class Cover(tk.Canvas):
    def __init__(self, parent, size=52):
        super().__init__(parent, width=size, height=size, bg="#0c1a2b", highlightthickness=0)
        self.size = size
        self.photo = None
        self.reset()

    def reset(self):
        self.delete("all")
        self.photo = None
        size = self.size
        self.create_polygon(
            size * 0.5,
            size * 0.15,
            size * 0.85,
            size * 0.83,
            size * 0.15,
            size * 0.83,
            outline="#156d99",
            fill="#101d38",
            width=2,
        )
        self.create_line(
            size * 0.25,
            size * 0.72,
            size * 0.51,
            size * 0.23,
            size * 0.67,
            size * 0.54,
            fill=CYAN,
            width=2,
        )
        self.create_line(
            size * 0.42,
            size * 0.65,
            size * 0.61,
            size * 0.28,
            size * 0.84,
            size * 0.8,
            fill=RED,
            width=2,
        )

    def set_image(self, data):
        try:
            with Image.open(io.BytesIO(data)) as image:
                image = ImageOps.fit(
                    image.convert("RGB"), (self.size, self.size), method=Image.Resampling.LANCZOS
                )
                self.photo = ImageTk.PhotoImage(image, master=self)
            self.delete("all")
            self.create_image(0, 0, image=self.photo, anchor="nw")
        except (OSError, ValueError):
            pass


class TrackRow(tk.Frame):
    def __init__(self, parent, entry):
        super().__init__(
            parent, bg=ROW, padx=18, pady=13, highlightthickness=1, highlightbackground="#0a1724"
        )
        self.entry = entry
        self.state = "queued" if entry["available"] else "unavailable"
        self.columnconfigure(1, weight=1)
        self.cover = Cover(self)
        self.cover.grid(row=0, column=0, rowspan=2, padx=(0, 16))
        self.title = tk.Label(
            self, text=entry["title"], bg=ROW, fg=TEXT, anchor="w", font=(FONT, 11, "bold"), width=1
        )
        self.title.grid(row=0, column=1, sticky="ew")
        self.duration = tk.Label(
            self, text=duration_text(entry["duration"]), bg=ROW, fg=MUTED, font=(FONT, 11), width=7
        )
        self.duration.grid(row=0, column=2, padx=12)
        self.badge = tk.Label(self, bg=ROW, font=(FONT, 10), width=13, anchor="e")
        self.badge.grid(row=0, column=3)
        self.progress_frame = tk.Frame(self, bg=ROW)
        self.bar = ttk.Progressbar(
            self.progress_frame, style="Track.Horizontal.TProgressbar", maximum=100
        )
        self.bar.pack(side="left", fill="x", expand=True)
        self.percent = tk.Label(
            self.progress_frame, bg=ROW, fg=CYAN, font=(FONT, 9), width=5, anchor="e"
        )
        self.percent.pack(side="right")
        self.update_state(self.state)

    def update_state(self, state, percent=0, duration=None, **unused):
        self.state = state
        labels = {
            "queued": ("В очереди", MUTED),
            "downloading": ("Скачивание", CYAN),
            "converting": ("В MP3…", ORANGE),
            "done": ("✓  Готово", GREEN),
            "skipped": ("✓  Уже скачан", GREEN),
            "error": ("Ошибка", RED),
            "unavailable": ("Недоступно", MUTED),
            "stopped": ("Остановлено", ORANGE),
        }
        text, color = labels[state]
        self.badge.configure(text=text, fg=color)
        if duration is not None:
            self.duration.configure(text=duration_text(duration))
        if state in ("downloading", "converting"):
            self.progress_frame.grid(row=1, column=1, sticky="ew", pady=(8, 0))
            self.bar["value"] = percent
            self.percent.configure(text=f"{int(percent)}%")
        else:
            self.progress_frame.grid_remove()


def label(parent, text=None, *, variable=None, color=TEXT, size=11, bold=False, **kwargs):
    return tk.Label(
        parent,
        text=text,
        textvariable=variable,
        bg=parent.cget("bg"),
        fg=color,
        font=(FONT, size, "bold" if bold else "normal"),
        **kwargs,
    )


def entry(parent, variable, *, font_size=11):
    border = tk.Frame(parent, bg=BG, highlightthickness=1, highlightbackground=LINE)
    field = tk.Entry(
        border,
        textvariable=variable,
        bg=BG,
        fg=TEXT,
        insertbackground=CYAN,
        relief="flat",
        bd=0,
        highlightthickness=0,
        font=(FONT, font_size),
        disabledbackground=BG,
        disabledforeground=MUTED,
        selectbackground="#164459",
    )
    field.pack(fill="x", expand=True, padx=13, pady=14)
    field.bind("<FocusIn>", lambda event: border.configure(highlightbackground=CYAN))
    field.bind("<FocusOut>", lambda event: border.configure(highlightbackground=LINE))
    return border, field
