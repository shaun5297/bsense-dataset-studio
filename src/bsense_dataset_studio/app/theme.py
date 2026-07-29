"""Light/dark theme support for the studio UI.

The ttk ``clam`` theme is reconfigured from a small palette so every window
can switch between day and night mode at runtime. The palettes follow
GitHub's Primer colors: flat surfaces, subtle single-tone borders and one
accent color, which keeps the interface calm in a dim lab. Widgets created
with explicit ``foreground=`` colors should read them via :func:`color`
and refresh through :func:`on_change`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

_MODES = ("light", "dark")

_PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#F6F8FA",
        "fg": "#1F2328",
        "field": "#FFFFFF",
        "border": "#D0D7DE",
        "secondary": "#57606A",
        "muted": "#6E7781",
        "accent": "#0969DA",
        "select_fg": "#FFFFFF",
        "ok": "#1A7F37",
        "warn": "#9A6700",
        "error": "#CF222E",
    },
    "dark": {
        "bg": "#0D1117",
        "fg": "#E6EDF3",
        "field": "#161B22",
        "border": "#30363D",
        "secondary": "#8B949E",
        "muted": "#6E7681",
        "accent": "#2F81F7",
        "select_fg": "#FFFFFF",
        "ok": "#3FB950",
        "warn": "#D29922",
        "error": "#F85149",
    },
}

# Dark by default: acquisition usually runs in dim lab rooms.
_mode = "dark"
_listeners: list[Callable[[str], None]] = []


def mode() -> str:
    return _mode


def color(role: str) -> str:
    """Current theme color for a role (bg/fg/field/border/secondary/muted/accent/ok/warn/error)."""
    return _PALETTES[_mode][role]


def on_change(listener: Callable[[str], None]) -> Callable[[], None]:
    """Register a callback and return an idempotent unsubscribe function."""
    _listeners.append(listener)

    def unsubscribe() -> None:
        try:
            _listeners.remove(listener)
        except ValueError:
            pass

    return unsubscribe


def set_mode(new_mode: str, root: tk.Misc | None = None) -> str:
    global _mode
    if new_mode not in _MODES:
        raise ValueError(f"未知主题模式：{new_mode}")
    _mode = new_mode
    if root is not None:
        apply(root)
    for listener in list(_listeners):
        listener(new_mode)
    return _mode


def toggle(root: tk.Misc) -> str:
    return set_mode("light" if _mode == "dark" else "dark", root)


def apply(root: tk.Misc) -> None:
    """(Re)configure ttk styles and base colors for the current mode."""
    import tkinter as tk
    from tkinter import ttk

    p = _PALETTES[_mode]
    style = ttk.Style(root)
    style.theme_use("clam")
    try:
        root.configure(bg=p["bg"])
    except tk.TclError:
        pass
    style.configure(
        ".",
        background=p["bg"],
        foreground=p["fg"],
        bordercolor=p["border"],
        darkcolor=p["border"],
        lightcolor=p["border"],
        fieldbackground=p["field"],
        troughcolor=p["bg"],
        borderwidth=1,
        focusthickness=1,
        focuscolor=p["accent"],
    )
    style.configure("TFrame", background=p["bg"])
    style.configure("TLabel", background=p["bg"], foreground=p["fg"])
    style.configure("TSeparator", background=p["border"])
    style.configure(
        "TLabelframe",
        background=p["bg"],
        foreground=p["fg"],
        bordercolor=p["border"],
        borderwidth=1,
    )
    style.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])
    style.configure(
        "TButton",
        background=p["field"],
        foreground=p["fg"],
        bordercolor=p["border"],
        padding=(12, 6),
    )
    style.map(
        "TButton",
        background=[("pressed", p["accent"]), ("active", p["border"])],
        foreground=[("pressed", p["select_fg"]), ("disabled", p["muted"])],
        bordercolor=[("focus", p["accent"])],
    )
    style.configure("TCheckbutton", background=p["bg"], foreground=p["fg"])
    style.map("TCheckbutton", background=[("active", p["bg"])])
    style.configure(
        "BooleanToggle.TCheckbutton",
        background=p["bg"],
        foreground=p["muted"],
        font=("", 14),
        padding=(4, 2),
    )
    style.map(
        "BooleanToggle.TCheckbutton",
        background=[("active", p["bg"])],
        foreground=[("selected", p["ok"]), ("!selected", p["muted"])],
    )
    style.configure(
        "TEntry",
        fieldbackground=p["field"],
        foreground=p["fg"],
        insertcolor=p["fg"],
        bordercolor=p["border"],
        padding=4,
    )
    style.map("TEntry", bordercolor=[("focus", p["accent"])])
    style.configure(
        "TCombobox",
        fieldbackground=p["field"],
        foreground=p["fg"],
        bordercolor=p["border"],
        arrowcolor=p["fg"],
        padding=4,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", p["field"])],
        foreground=[("readonly", p["fg"])],
        selectbackground=[("readonly", p["field"])],
        selectforeground=[("readonly", p["fg"])],
        bordercolor=[("focus", p["accent"])],
        arrowcolor=[("disabled", p["muted"])],
    )
    style.configure(
        "Treeview",
        background=p["field"],
        foreground=p["fg"],
        fieldbackground=p["field"],
        bordercolor=p["border"],
        rowheight=28,
    )
    style.map(
        "Treeview",
        background=[("selected", p["accent"])],
        foreground=[("selected", p["select_fg"])],
    )
    style.configure(
        "Treeview.Heading",
        background=p["bg"],
        foreground=p["fg"],
        bordercolor=p["border"],
        padding=(6, 4),
    )
    style.configure(
        "TProgressbar",
        background=p["accent"],
        troughcolor=p["field"],
        bordercolor=p["border"],
        thickness=8,
    )
    for orient in ("Vertical", "Horizontal"):
        style.configure(
            f"{orient}.TScrollbar",
            background=p["field"],
            troughcolor=p["bg"],
            bordercolor=p["border"],
            arrowcolor=p["fg"],
        )
        style.map(
            f"{orient}.TScrollbar",
            background=[("active", p["border"])],
        )
    root.option_add("*TCombobox*Listbox.background", p["field"])
    root.option_add("*TCombobox*Listbox.foreground", p["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["select_fg"])
