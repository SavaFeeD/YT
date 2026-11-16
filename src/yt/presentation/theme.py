"""Shared desktop colors and ttk theme."""

from tkinter import ttk

BG = "#030911"
PANEL = "#050d17"
ROW = "#07121f"
LINE = "#1c2a36"
TEXT = "#f1f5f9"
MUTED = "#98a8b6"
CYAN = "#00cce7"
RED = "#ff2854"
GREEN = "#00d18c"
ORANGE = "#ffa600"
FONT = "Segoe UI"


def configure_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        "Track.Horizontal.TProgressbar",
        background=CYAN,
        troughcolor="#1b2a38",
        borderwidth=0,
        bordercolor="#1b2a38",
        lightcolor=CYAN,
        darkcolor=CYAN,
        thickness=5,
    )
    style.configure(
        "Overall.Horizontal.TProgressbar",
        background=RED,
        troughcolor="#14212d",
        borderwidth=0,
        bordercolor="#14212d",
        lightcolor=RED,
        darkcolor=RED,
        thickness=13,
    )
    style.configure(
        "Vertical.TScrollbar",
        background="#203445",
        troughcolor=BG,
        borderwidth=0,
        bordercolor=BG,
        lightcolor=BG,
        darkcolor=BG,
        arrowcolor=MUTED,
        arrowsize=11,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("disabled", LINE), ("active", "#28495c"), ("!disabled", "#203445")],
    )
    style.configure(
        "Library.Treeview",
        background=BG,
        fieldbackground=BG,
        foreground=TEXT,
        rowheight=48,
        borderwidth=0,
        font=(FONT, 11),
    )
    style.layout("Library.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.map(
        "Library.Treeview", background=[("selected", "#133346")], foreground=[("selected", TEXT)]
    )
    style.configure(
        "Library.Treeview.Heading",
        background=PANEL,
        foreground=MUTED,
        borderwidth=0,
        padding=(12, 10),
        font=(FONT, 9, "bold"),
    )
    style.map("Library.Treeview.Heading", background=[("active", PANEL)])
    style.configure(
        "Player.Horizontal.TScale",
        background=CYAN,
        troughcolor=LINE,
        borderwidth=0,
        bordercolor=LINE,
        lightcolor=CYAN,
        darkcolor=CYAN,
        sliderlength=12,
        sliderthickness=12,
        troughborderwidth=0,
    )
