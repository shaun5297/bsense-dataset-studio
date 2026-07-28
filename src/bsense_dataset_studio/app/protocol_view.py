from __future__ import annotations

from collections.abc import Callable
from tkinter import BooleanVar, StringVar, ttk

from ..protocols import list_protocols


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
        self.selection = StringVar(value=protocols[0].display_name)
        self.include_pvt = BooleanVar(value=False)
        self.selector = ttk.Combobox(
            self,
            textvariable=self.selection,
            values=tuple(self._task_by_name),
            state="readonly",
            width=32,
        )
        self.selector.pack(fill="x")
        self.selector.bind("<<ComboboxSelected>>", self._selection_changed)
        self.pvt_toggle = ttk.Checkbutton(
            self,
            text="包含 PVT-B 研究参照（可选，默认关闭）",
            variable=self.include_pvt,
            command=self._notify_change,
        )
        self.pvt_toggle.pack(anchor="w", pady=(8, 0))
        ttk.Label(
            self,
            text="产品日常流程不执行 PVT-B。",
            foreground="#6B7280",
        ).pack(anchor="w", pady=(3, 0))
        self._sync_pvt_state()

    @property
    def task(self) -> str:
        return self._task_by_name[self.selection.get()]

    def _selection_changed(self, _event: object | None = None) -> None:
        self._sync_pvt_state()
        self._notify_change()

    def _sync_pvt_state(self) -> None:
        if self.task == "m6_readiness_study":
            self.pvt_toggle.state(["!disabled"])
        else:
            self.include_pvt.set(False)
            self.pvt_toggle.state(["disabled"])

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()
