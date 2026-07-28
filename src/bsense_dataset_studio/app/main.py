from __future__ import annotations

from pathlib import Path
from tkinter import Tk, messagebox, ttk

from ..acquisition.session import AcquisitionSession
from ..protocols import build
from ..protocols.sequences import assign_sequence_set
from .execution_window import ExecutionWindow
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
        self.operator = OperatorView(
            left,
            on_start=self.start_collection,
            on_abort=self.abort_collection,
        )
        self.operator.pack(fill="x", pady=(0, 10))
        ttk.Button(left, text="刷新协议预览", command=self.preview).pack(anchor="e", pady=(2, 0))

        self.task = TaskView(container)
        self.task.grid(row=1, column=1, sticky="nsew")
        self.execution_window: ExecutionWindow | None = None
        self.preview()

    def preview(self) -> None:
        self.setup.set_task(self.protocol.task)
        sequence_set_id = assign_sequence_set(
            self.setup.participant.get(),
            self.setup.session.get(),
            self.setup.run.get(),
        )
        protocol = build(
            self.protocol.task,
            sequence_set_id=sequence_set_id,
        )
        self.task.show_protocol(protocol)

    def start_collection(self) -> None:
        if self.execution_window is not None:
            self.execution_window.lift()
            return
        try:
            storage = self.setup.planned_storage()
            sequence_set_id = assign_sequence_set(
                self.setup.participant.get(),
                self.setup.session.get(),
                self.setup.run.get(),
            )
            protocol = build(
                self.protocol.task,
                sequence_set_id=sequence_set_id,
            )
            session = AcquisitionSession(
                storage,
                protocol,
                participant_id=self.setup.participant.get().strip(),
                session_id=self.setup.session.get().strip(),
                run_id=self.setup.run.get().strip(),
            )
            sequence_metadata = next(
                (
                    step.metadata
                    for step in protocol.steps
                    if step.event == "sart_start"
                ),
                {},
            )
            session.merge_context(
                {
                    "sequence_set_id": sequence_set_id,
                    "random_seed": sequence_metadata.get("random_seed"),
                    "no_go_positions": sequence_metadata.get("no_go_positions"),
                }
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法准备采集", str(exc))
            return
        self.operator.set_running(True)
        self.execution_window = ExecutionWindow(
            self.setup.winfo_toplevel(),
            session,
            protocol,
            on_close=self._collection_closed,
        )
        self.execution_window.start()

    def abort_collection(self) -> None:
        if self.execution_window is not None:
            self.execution_window.abort()

    def _collection_closed(self) -> None:
        self.execution_window = None
        self.operator.set_running(False)


def run(*, dataset_root: Path | None = None) -> None:
    root = Tk()
    StudioApp(root, dataset_root=dataset_root)
    root.mainloop()
