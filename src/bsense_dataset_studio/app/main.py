from __future__ import annotations

from pathlib import Path
from tkinter import Tk, ttk

from ..protocols import build
from .operator_view import OperatorView
from .protocol_view import ProtocolView
from .setup_view import SetupView
from .task_view import TaskView


class StudioApp:
    def __init__(self, root: Tk, *, dataset_root: Path | None = None) -> None:
        root.title("BSense Dataset Studio")
        root.geometry("1180x760")
        root.minsize(980, 680)
        container = ttk.Frame(root, padding=20)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, minsize=340)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(1, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        ttk.Label(header, text="BSense Dataset Studio", font=("", 24, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="脑安检研究数据采集、实验标注与数据集构建；不输出正式岗位建议。",
            foreground="#374151",
        ).pack(anchor="w", pady=(4, 0))

        left = ttk.Frame(container)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        self.setup = SetupView(left, initial_root=dataset_root)
        self.setup.pack(fill="x", pady=(0, 10))
        self.protocol = ProtocolView(left, on_change=self.preview)
        self.protocol.pack(fill="x", pady=(0, 10))
        self.operator = OperatorView(left)
        self.operator.pack(fill="x", pady=(0, 10))
        ttk.Button(left, text="刷新协议预览", command=self.preview).pack(anchor="e", pady=(2, 0))

        self.task = TaskView(container)
        self.task.grid(row=1, column=1, sticky="nsew")
        self.preview()

    def preview(self) -> None:
        self.setup.set_task(self.protocol.task)
        protocol = build(
            self.protocol.task,
            include_pvt=self.protocol.include_pvt.get(),
        )
        self.task.show_protocol(protocol)


def run(*, dataset_root: Path | None = None) -> None:
    root = Tk()
    StudioApp(root, dataset_root=dataset_root)
    root.mainloop()
