"""Light/dark theme support for the studio UI.

The ttk ``clam`` theme is reconfigured from a small palette so every window
can switch between day and night mode at runtime. Widgets created with
explicit ``foreground=`` colors should read them via :func:`color` and
refresh through :func:`on_change`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

_MODES = ("light", "dark")

_PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#F3F4F6",
        "fg": "#111827",
        "field": "#FFFFFF",
        "border": "#D1D5DB",
        "secondary": "#4B5563",
        "muted": "#6B7280",
        "accent": "#2563EB",
        "select_fg": "#FFFFFF",
    },
    "dark": {
        "bg": "#111827",
        "fg": "#E5E7EB",
        "field": "#1F2937",
        "border": "#374151",
        "secondary": "#9CA3AF",
        "muted": "#6B7280",
        "accent": "#3B82F6",
        "select_fg": "#FFFFFF",
    },
}

# Dark by default: acquisition usually runs in dim lab rooms.
_mode = "dark"
_listeners: list[Callable[[str], None]] = []


def mode() -> str:
    return _mode


def color(role: str) -> str:
    """Current theme color for a role (bg/fg/field/border/secondary/muted/accent)."""
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
        fieldbackground=p["field"],
    )
    style.configure("TFrame", background=p["bg"])
    style.configure("TLabel", background=p["bg"], foreground=p["fg"])
    style.configure("TLabelframe", background=p["bg"], foreground=p["fg"], bordercolor=p["border"])
    style.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])
    style.configure("TButton", background=p["field"], foreground=p["fg"], bordercolor=p["border"])
    style.map(
        "TButton",
        background=[("pressed", p["accent"]), ("active", p["border"])],
        foreground=[("disabled", p["muted"])],
    )
    style.configure("TCheckbutton", background=p["bg"], foreground=p["fg"])
    style.map("TCheckbutton", background=[("active", p["bg"])])
    style.configure(
        "TEntry",
        fieldbackground=p["field"],
        foreground=p["fg"],
        insertcolor=p["fg"],
        bordercolor=p["border"],
    )
    style.configure(
        "TCombobox",
        fieldbackground=p["field"],
        foreground=p["fg"],
        bordercolor=p["border"],
        arrowcolor=p["fg"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", p["field"])],
        foreground=[("readonly", p["fg"])],
        selectbackground=[("readonly", p["field"])],
        selectforeground=[("readonly", p["fg"])],
    )
    style.configure(
        "Treeview",
        background=p["field"],
        foreground=p["fg"],
        fieldbackground=p["field"],
        bordercolor=p["border"],
    )
    style.map(
        "Treeview",
        background=[("selected", p["accent"])],
        foreground=[("selected", p["select_fg"])],
    )
    style.configure("Treeview.Heading", background=p["bg"], foreground=p["fg"], bordercolor=p["border"])
    style.configure("TProgressbar", background=p["accent"], troughcolor=p["field"], bordercolor=p["border"])
    for orient in ("Vertical", "Horizontal"):
        style.configure(
            f"{orient}.TScrollbar",
            background=p["field"],
            troughcolor=p["bg"],
            bordercolor=p["border"],
            arrowcolor=p["fg"],
        )
    root.option_add("*TCombobox*Listbox.background", p["field"])
    root.option_add("*TCombobox*Listbox.foreground", p["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["select_fg"])
