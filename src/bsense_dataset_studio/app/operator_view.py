from __future__ import annotations

from tkinter import StringVar, ttk

from ..acquisition.discovery import discover


class OperatorView(ttk.LabelFrame):
    def __init__(self, parent: object) -> None:
        super().__init__(parent, text="实验员设备监视", padding=12)
        self.status = StringVar(value="尚未扫描")
        ttk.Label(self, textvariable=self.status).pack(side="left")
        ttk.Button(self, text="扫描 LSL", command=self.scan).pack(side="right")

    def scan(self) -> None:
        try:
            found = discover(1.0)
            kinds = ", ".join(sorted(item[1].kind for item in found)) or "未发现支持的流"
            self.status.set(kinds)
        except Exception as exc:
            self.status.set(f"扫描失败：{exc}")
