from __future__ import annotations

from collections.abc import Callable
from tkinter import StringVar, ttk

from ..protocols import list_protocols
from . import theme


class ProtocolView(ttk.LabelFrame):
    def __init__(
        self,
        parent: object,
        *,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, text="研究协议", padding=12)
        self._on_change = on_change
        protocols = list_protocols()
        self._task_by_name = {item.display_name: item.task for item in protocols}
        self._description_by_name = {item.display_name: item.description for item in protocols}
        self.selection = StringVar(value=protocols[0].display_name)
        self.description = StringVar(value=self._description_by_name[self.selection.get()])
        self.selector = ttk.Combobox(
            self,
            textvariable=self.selection,
            values=tuple(self._task_by_name),
            state="readonly",
            width=32,
        )
        self.selector.pack(fill="x")
        self.selector.bind("<<ComboboxSelected>>", self._selection_changed)
        self.description_label = ttk.Label(
            self,
            textvariable=self.description,
            foreground=theme.color("muted"),
            justify="left",
            wraplength=300,
        )
        self.description_label.pack(anchor="w", fill="x", pady=(6, 0))
        theme.on_change(self._sync_theme)

    def _sync_theme(self, _mode: str) -> None:
        try:
            self.description_label.configure(foreground=theme.color("muted"))
        except Exception:
            pass  # widget already destroyed

    @property
    def task(self) -> str:
        return self._task_by_name[self.selection.get()]

    def _selection_changed(self, _event: object | None = None) -> None:
        self.description.set(self._description_by_name[self.selection.get()])
        self._notify_change()

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()
