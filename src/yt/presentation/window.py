"""Main window: binds Tk view state to injected application services."""

import ctypes
import logging
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from yt.application.context import ApplicationServices
from yt.domain.downloads import DownloadRequest
from yt.domain.settings import AppSettings
from yt.domain.urls import playlist_url
from yt.presentation.downloads import DownloadsView
from yt.presentation.library import LibraryView
from yt.presentation.player_bar import PlayerBar
from yt.presentation.theme import (
    BG,
    CYAN,
    GREEN,
    LINE,
    MUTED,
    ORANGE,
    PANEL,
    RED,
    TEXT,
    configure_theme,
)
from yt.presentation.widgets import Button, TrackRow, label

logger = logging.getLogger(__name__)


class ApplicationWindow(tk.Tk):
    def __init__(
        self,
        services: ApplicationServices,
        start_maximized=None,
        scan_on_start=True,
        persist_on_close: bool = True,
    ):
        super().__init__()
        self.services = services
        self.persist_on_close = persist_on_close
        self.is_closed = False
        self.title(f"YT {services.version} · Музыка и загрузки")
        icon = services.icon
        if os.name == "nt" and icon.is_file():
            self.iconbitmap(default=str(icon))
        width = min(1440, self.winfo_screenwidth() - 70)
        height = min(int(width * 9 / 16), self.winfo_screenheight() - 100)
        self.geometry(f"{width}x{height}")
        self.minsize(1000, 640)
        self.configure(bg=BG)
        self.events = services.events
        self.cancel = services.downloads.cancel_event
        self.closing = False
        self.busy = False
        self.active_transfers = {}
        self.playlist = None
        self.rows = {}
        self.preview_after = None
        self.preview_token = 0
        self.image_generation = 0
        self.image_cancel = threading.Event()
        self.save_after = None
        self.fullscreen = False
        settings = services.settings.load().to_mapping()
        self.settings = settings
        self.player = services.player
        self.library_follow = bool(settings.get("library_follow", True))
        self.page = "library"
        self.url = tk.StringVar(value=settings.get("url", ""))
        self.folder = tk.StringVar(value=settings.get("folder", str(Path.home() / "Music" / "YT")))
        self.quality = tk.StringVar(value=str(settings.get("quality", "192")))
        if self.quality.get() not in ("128", "192", "256", "320"):
            self.quality.set("192")
        self.concurrency = tk.StringVar(value=str(settings.get("concurrency", 3)))
        if self.concurrency.get() not in ("1", "2", "3", "4", "5", "6"):
            self.concurrency.set("3")
        self.search = tk.StringVar()
        self.status = tk.StringVar(value="Готов к работе")
        self.detail = tk.StringVar(value="Скорость —  ·  Осталось —")
        self.summary = tk.StringVar(value="Ожидание загрузки")
        self.overall_percent = tk.StringVar(value="0%")
        self.playlist_title = tk.StringVar(value="Ваш следующий плейлист")
        self.playlist_info = tk.StringVar(value="Вставьте ссылку слева — треки появятся здесь")
        configure_theme(self)
        self.build_interface()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.url.trace_add("write", self.schedule_preview)
        self.search.trace_add("write", lambda *args: self.filter_rows())
        self.bind_all("<MouseWheel>", self.scroll_tracks, add="+")
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        self.after(100, self.poll)
        self.after(100, self.dark_titlebar)
        self.library.search_entry.focus_set()
        self.folder.trace_add("write", self.download_folder_changed)
        if scan_on_start:
            self.after(120, self.library.refresh)
        maximize = settings.get("maximized", True) if start_maximized is None else start_maximized
        if maximize and os.name == "nt":
            self.state("zoomed")

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.attributes("-fullscreen", self.fullscreen)
        return "break"

    def exit_fullscreen(self, event=None):
        if self.fullscreen:
            self.fullscreen = False
            self.attributes("-fullscreen", False)
            return "break"

    def request_save(self):
        if self.save_after:
            self.after_cancel(self.save_after)
        self.save_after = self.after(350, self.save_settings)

    def save_settings(self):
        self.save_after = None
        self.settings.update(
            {
                "folder": self.folder.get(),
                "quality": self.quality.get(),
                "url": self.url.get(),
                "concurrency": int(self.concurrency.get()),
                "volume": self.player.volume,
                "shuffle": self.player.shuffle,
                "library_folder": self.library.folder.get(),
                "library_follow": self.library_follow,
            }
        )
        if not self.fullscreen and self.state() != "withdrawn":
            self.settings["maximized"] = self.state() == "zoomed"
        try:
            self.services.settings.save(AppSettings.from_mapping(self.settings))
        except OSError as error:
            self.add_log(f"Не удалось сохранить настройки: {error}")

    def download_folder_changed(self, *args):
        if self.library_follow:
            self.library.folder.set(self.folder.get())
            self.library.schedule_refresh()
        self.request_save()

    def show_page(self, page):
        self.page = page
        self.download_page.pack_forget()
        self.library.pack_forget()
        (self.library if page == "library" else self.download_page).pack(fill="both", expand=True)
        for name, button in self.page_buttons.items():
            button.fill, button.color = (CYAN, BG) if name == page else (BG, MUTED)
            button.border = CYAN if name == page else LINE
            button.draw()
        if page == "downloads" and self.url.get() and not self.busy and not self.playlist:
            self.schedule_preview()

    def dark_titlebar(self):
        if os.name != "nt":
            return
        try:
            window = ctypes.windll.user32.GetParent(self.winfo_id())
            enabled = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(window, 20, ctypes.byref(enabled), 4)
        except (AttributeError, OSError):
            pass

    def build_interface(self):
        footer = tk.Frame(
            self, bg=BG, height=28, highlightthickness=1, highlightbackground="#0d1b28"
        )
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        self.indicator = label(footer, "●", color=GREEN, size=13)
        self.indicator.pack(side="left", padx=(20, 10))
        label(footer, variable=self.status, color=MUTED, size=10, anchor="w").pack(
            side="left", fill="x", expand=True
        )
        label(footer, "F11 — полный экран  ·  Esc — выйти", color="#456073", size=9).pack(
            side="right", padx=20
        )
        self.player_bar = PlayerBar(self, self)
        self.player_bar.pack(side="bottom", fill="x")
        nav = tk.Frame(self, bg=PANEL, padx=24, pady=12)
        nav.pack(fill="x")
        label(nav, "YT", color=RED, size=20, bold=True).pack(side="left", padx=(0, 30))
        self.page_buttons = {}
        for name, text in [("library", "Моя музыка"), ("downloads", "Загрузки")]:
            button = Button(
                nav, text, lambda target=name: self.show_page(target), height=36, font_size=10
            )
            button.configure(width=150)
            button.pack(side="left", padx=(0, 10))
            self.page_buttons[name] = button
        label(nav, "ВАША МУЗЫКА. НА ВАШЕМ КОМПЬЮТЕРЕ.", color="#658095", size=9).pack(side="right")
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)
        self.download_view = DownloadsView(self.content, self)
        self.download_page = self.download_view
        self.select_quality(self.quality.get())
        self.select_concurrency(self.concurrency.get())
        library_folder = (
            self.folder.get()
            if self.library_follow
            else self.settings.get("library_folder", self.folder.get())
        )
        self.library = LibraryView(self.content, self, library_folder)
        self.show_page("library")

    def select_quality(self, quality):
        self.quality.set(quality)
        for value, button in self.download_view.quality_buttons.items():
            button.fill = ORANGE if value == quality else BG
            button.border = ORANGE if value == quality else LINE
            button.draw()

    def select_concurrency(self, value):
        self.concurrency.set(value)
        for number, button in self.download_view.concurrency_buttons.items():
            button.fill = CYAN if number == value else BG
            button.color = BG if number == value else TEXT
            button.border = CYAN if number == value else LINE
            button.draw()

    def update_search_placeholder(self):
        if self.search.get() or self.focus_get() == self.download_view.search_entry:
            self.download_view.search_placeholder.place_forget()
        else:
            self.download_view.search_placeholder.place(x=13, rely=0.5, anchor="w")

    def filter_rows(self):
        self.update_search_placeholder()
        query = self.search.get().casefold().strip()
        visible = 0
        for row in self.rows.values():
            row.pack_forget()
            if query in row.entry["title"].casefold():
                row.pack(fill="x", pady=(0, 2))
                visible += 1
        self.download_view.empty.pack_forget()
        if self.rows and not visible:
            self.download_view.empty.configure(
                text="Ничего не найдено\n\nПопробуйте другое название."
            )
            self.download_view.empty.pack(fill="x")
        self.download_view.track_canvas.yview_moveto(0)

    def scroll_tracks(self, event):
        widget = event.widget
        while widget is not None:
            if widget in (self.download_view.track_canvas, self.download_view.sidebar_canvas):
                widget.yview_scroll(-int(event.delta / 120), "units")
                return "break"
            widget = getattr(widget, "master", None)

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
            self.download_view.preview_hint.configure(
                text="Вставьте ссылку на плейлист", fg="#668095"
            )
            self.clear_playlist()
            return
        if self.playlist and self.playlist["url"] == url:
            return
        self.clear_playlist()
        self.download_view.preview_hint.configure(text="Читаю плейлист…", fg=CYAN)
        self.preview_after = self.after(700, lambda: self.start_preview(url, self.preview_token))

    def start_preview(self, url, token):
        self.preview_after = None

        self.services.previews.load(url, token)

    def clear_playlist(self):
        self.image_cancel.set()
        self.image_generation += 1
        self.playlist = None
        for row in self.rows.values():
            row.destroy()
        self.rows.clear()
        self.playlist_title.set("Ваш следующий плейлист")
        self.playlist_info.set("Вставьте ссылку слева — треки появятся здесь")
        self.download_view.playlist_cover.reset()
        self.download_view.empty.configure(
            text="Музыка начинается со ссылки\n\nДобавьте плейлист YouTube или YouTube Music.\nЗдесь появятся обложки, длительность и статус каждого трека."
        )
        self.download_view.empty.pack(fill="x")

    def show_playlist(self, data):
        self.clear_playlist()
        self.playlist = data
        self.download_view.empty.pack_forget()
        self.playlist_title.set(data["title"])
        entries = data["entries"]
        known = [entry["duration"] for entry in entries if entry["duration"] is not None]
        total_duration = sum(known)
        duration = f"{int(total_duration // 3600)} ч {int(total_duration % 3600 // 60):02} мин"
        if len(known) != len(entries):
            duration = "длительность уточняется"
        self.playlist_info.set(f"{len(entries)} треков  ·  {duration}")
        self.download_view.preview_hint.configure(text=f"Найдено треков: {len(entries)}", fg=GREEN)
        for entry in entries:
            row = TrackRow(self.download_view.track_frame, entry)
            self.rows[entry["key"]] = row
        self.filter_rows()
        self.image_cancel = threading.Event()
        self.services.thumbnails.load(data, self.image_generation, self.image_cancel)

    def choose_folder(self):
        folder = filedialog.askdirectory(
            initialdir=self.folder.get() if Path(self.folder.get()).is_dir() else Path.home()
        )
        if folder:
            self.folder.set(folder)

    def open_folder(self):
        folder = Path(self.folder.get()).expanduser()
        if folder.is_dir():
            os.startfile(str(folder))
        else:
            messagebox.showinfo("YT", "Папка появится после начала загрузки.")

    def set_busy(self, busy):
        self.busy = busy
        for widget in (
            self.download_view.start_button,
            self.download_view.link_entry,
            self.download_view.folder_entry,
            self.download_view.browse,
            *self.download_view.quality_buttons.values(),
            *self.download_view.concurrency_buttons.values(),
        ):
            widget.configure(state="disabled" if busy else "normal")
        self.download_view.stop_button.configure(state="normal" if busy else "disabled")
        self.indicator.configure(fg=CYAN if busy else GREEN)

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            url = playlist_url(self.url.get())
            if not self.folder.get().strip():
                raise ValueError("Выберите папку сохранения.")
            folder = Path(self.folder.get()).expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
            self.save_settings()
        except (ValueError, OSError) as error:
            messagebox.showerror("YT", str(error))
            return
        if self.preview_after:
            self.after_cancel(self.preview_after)
            self.preview_after = None
        self.preview_token += 1
        self.cancel.clear()
        self.active_transfers.clear()
        self.set_busy(True)
        self.download_view.progress_bar["value"] = 0
        self.overall_percent.set("0%")
        self.summary.set("Подготовка плейлиста…")
        self.status.set("Подключение к YouTube")
        self.detail.set("Скорость —  ·  Осталось —")
        cached = self.playlist if self.playlist and self.playlist["url"] == url else None
        self.services.downloads.start(
            DownloadRequest(
                url=url,
                folder=folder,
                quality=self.quality.get(),
                playlist=cached,
                concurrency=int(self.concurrency.get()),
            )
        )

    def stop(self):
        self.cancel.set()
        self.download_view.stop_button.configure(state="disabled")
        self.status.set("Останавливаю… Ожидаю завершения текущей операции.")

    def add_log(self, value):
        logger.info("%s", value)
        self.download_view.log.configure(state="normal")
        self.download_view.log.insert("end", value + "\n")
        if int(self.download_view.log.index("end-1c").split(".")[0]) > 1000:
            self.download_view.log.delete("1.0", "200.0")
        self.download_view.log.see("end")
        self.download_view.log.configure(state="disabled")

    def handle_event(self, kind, value):
        if kind == "library":
            self.library.apply(value)
        elif kind == "log":
            self.add_log(value)
        elif kind == "preview":
            token, data, error = value
            if token != self.preview_token or self.busy:
                return
            if error:
                self.download_view.preview_hint.configure(
                    text="Не удалось прочитать плейлист", fg=RED
                )
                self.playlist_title.set("Плейлист недоступен")
                self.playlist_info.set("Проверьте ссылку и доступ к YouTube")
                self.add_log(error)
            else:
                self.show_playlist(data)
        elif kind == "playlist":
            self.active_transfers.clear()
            self.show_playlist(value)
            self.summary.set(f"Загрузка…  0 из {len(value['entries'])}")
        elif kind == "image":
            generation, key, data = value
            if generation == self.image_generation:
                cover = (
                    self.download_view.playlist_cover
                    if key == "__playlist__"
                    else self.rows.get(key)
                )
                if cover:
                    (cover if key == "__playlist__" else cover.cover).set_image(data)
        elif kind == "track":
            if (
                value["state"] == "done"
                and Path(self.library.folder.get()).resolve() == Path(self.folder.get()).resolve()
            ):
                self.library.schedule_refresh()
            row = self.rows.get(value["key"])
            if row:
                row.update_state(**{key: item for key, item in value.items() if key != "key"})
                if value["state"] in ("downloading", "converting"):
                    self.active_transfers[value["key"]] = value
                else:
                    self.active_transfers.pop(value["key"], None)
                if not self.cancel.is_set():
                    downloading = sum(
                        item["state"] == "downloading" for item in self.active_transfers.values()
                    )
                    converting = sum(
                        item["state"] == "converting" for item in self.active_transfers.values()
                    )
                    speed = sum(
                        (item.get("speed") or 0)
                        for item in self.active_transfers.values()
                        if item["state"] == "downloading"
                    )
                    self.status.set(
                        f"Скачивание: {downloading}  ·  Преобразование в MP3: {converting}"
                    )
                    self.detail.set(
                        f"Скорость {speed / 1048576:.1f} МБ/с  ·  Активно {len(self.active_transfers)}"
                    )
        elif kind == "overall":
            percent = value["finished"] / value["total"] * 100
            self.download_view.progress_bar["value"] = percent
            self.overall_percent.set(f"{int(percent)}%")
            self.summary.set(f"Обработано  {value['finished']} из {value['total']}")
        elif kind == "done":
            if Path(self.library.folder.get()).resolve() == Path(self.folder.get()).resolve():
                self.library.schedule_refresh()
            self.active_transfers.clear()
            self.status.set(value)
            self.add_log(value)
            self.detail.set("Скорость —  ·  Осталось —")
            self.set_busy(False)
            if value.startswith("Ошибка:") or "с ошибками" in value:
                self.indicator.configure(fg=RED)
            for row in self.rows.values():
                if row.state in ("queued", "downloading", "converting"):
                    row.update_state("stopped")

    def poll(self):
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            self.handle_event(kind, value)
        self.player.poll()
        self.player_bar.tick()
        self.library.tick()
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.destroy()
            return
        self.after(80, self.poll)

    def destroy(self):
        if self.is_closed:
            return
        self.is_closed = True
        self.image_cancel.set()
        if self.persist_on_close:
            self.save_settings()
        self.services.close()
        for callback in self.tk.call("after", "info"):
            self.after_cancel(callback)
        super().destroy()

    def close(self):
        if self.worker and self.worker.is_alive():
            if messagebox.askyesno("YT", "Остановить загрузку и закрыть приложение?"):
                self.closing = True
                self.stop()
                self.player.stop()
        else:
            self.destroy()

    @property
    def worker(self):
        return self.services.downloads.worker

    def report_callback_exception(self, exception, value, traceback):
        logger.error("Tk callback failed", exc_info=(exception, value, traceback))
        self.status.set("Ошибка интерфейса. Подробности — в журнале.")
        self.add_log(str(value))
