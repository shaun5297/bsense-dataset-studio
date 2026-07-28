from __future__ import annotations

from collections.abc import Callable
from tkinter import StringVar, ttk

from ..acquisition.discovery import discover


class OperatorView(ttk.LabelFrame):
    def __init__(
        self,
        parent: object,
        *,
        on_start: Callable[[], None] | None = None,
        on_abort: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, text="实验员设备监视", padding=12)
        self._on_start = on_start
        self._on_abort = on_abort
        self.status = StringVar(value="尚未扫描")
        ttk.Label(self, textvariable=self.status, wraplength=250).pack(
            anchor="w",
            fill="x",
        )
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="扫描 LSL", command=self.scan).pack(side="left")
        self.start_button = ttk.Button(
            actions,
            text="开始试采",
            command=self._start,
        )
        self.start_button.pack(side="right")
        self.abort_button = ttk.Button(
            actions,
            text="中止",
            command=self._abort,
            state="disabled",
        )
        self.abort_button.pack(side="right", padx=(0, 6))

    def scan(self) -> None:
        try:
            found = discover(1.0)
            kinds = ", ".join(sorted(item[1].kind for item in found)) or "未发现支持的流"
            self.status.set(kinds)
        except Exception as exc:
            self.status.set(f"扫描失败：{exc}")

    def set_running(self, running: bool) -> None:
        self.start_button.configure(state="disabled" if running else "normal")
        self.abort_button.configure(state="normal" if running else "disabled")
        if running:
            self.status.set("采集进行中")

    def _start(self) -> None:
        if self._on_start is not None:
            self._on_start()

    def _abort(self) -> None:
        if self._on_abort is not None:
            self._on_abort()
