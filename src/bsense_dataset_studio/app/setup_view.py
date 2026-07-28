from __future__ import annotations

from pathlib import Path
from tkinter import StringVar, filedialog, messagebox, ttk

from ..storage import (
    RunStorage,
    load_dataset_root,
    plan_run_storage,
    prepare_run_storage,
    save_dataset_root,
)


class SetupView(ttk.LabelFrame):
    def __init__(self, parent: object, *, initial_root: Path | None = None) -> None:
        super().__init__(parent, text="实验与存储", padding=12)
        self.participant = StringVar(value="P001")
        self.session = StringVar(value="01")
        self.run = StringVar(value="001")
        self.dataset_root = StringVar(value=str(initial_root or load_dataset_root()))
        self.output_preview = StringVar()
        self.storage_status = StringVar(value="选择目录后，点击“准备目录”进行创建与检查。")
        self._task = "m6_readiness_study"

        identifiers = (
            ("匿名被试", self.participant),
            ("Session", self.session),
            ("Run", self.run),
        )
        for row, (label, variable) in enumerate(identifiers):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(self, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=3)

        ttk.Separator(self).grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(self, text="数据根目录").grid(row=4, column=0, columnspan=2, sticky="w")
        storage_row = ttk.Frame(self)
        storage_row.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        storage_row.columnconfigure(0, weight=1)
        ttk.Entry(storage_row, textvariable=self.dataset_root).grid(row=0, column=0, sticky="ew")
        ttk.Button(storage_row, text="选择…", command=self._choose_root).grid(row=0, column=1, padx=(6, 0))

        ttk.Label(
            self,
            textvariable=self.output_preview,
            foreground="#4B5563",
            justify="left",
            wraplength=300,
        ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        actions = ttk.Frame(self)
        actions.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        ttk.Label(
            actions,
            textvariable=self.storage_status,
            foreground="#6B7280",
            justify="left",
            wraplength=210,
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(actions, text="准备目录", command=self._prepare_root).pack(side="right", padx=(6, 0))

        self.columnconfigure(1, weight=1)
        for variable in (self.participant, self.session, self.run, self.dataset_root):
            variable.trace_add("write", self._inputs_changed)
        self._refresh_output_preview()

    def set_task(self, task: str) -> None:
        self._task = task
        self._refresh_output_preview()

    def planned_storage(self) -> RunStorage:
        return plan_run_storage(
            self.dataset_root.get(),
            self.participant.get(),
            self.session.get(),
            self._task,
            self.run.get(),
        )

    def _inputs_changed(self, *_args: object) -> None:
        self.storage_status.set("设置有变更，请点击“准备目录”进行检查。")
        self._refresh_output_preview()

    def _refresh_output_preview(self) -> None:
        try:
            storage = self.planned_storage()
            relative = storage.xdf.relative_to(storage.dataset_root)
            self.output_preview.set(f"本次原始数据：{relative}")
        except ValueError as exc:
            self.output_preview.set(f"保存路径待完善：{exc}")

    def _choose_root(self) -> None:
        current = Path(self.dataset_root.get()).expanduser()
        initial = current if current.is_dir() else Path.home()
        selected = filedialog.askdirectory(
            parent=self.winfo_toplevel(),
            title="选择 BSense 数据根目录",
            initialdir=str(initial),
            mustexist=False,
        )
        if not selected:
            return
        self.dataset_root.set(selected)
        try:
            save_dataset_root(selected)
            self.storage_status.set("已记住数据根目录，请点击“准备目录”完成检查。")
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法保存目录设置", str(exc), parent=self.winfo_toplevel())

    def _prepare_root(self) -> None:
        try:
            storage = prepare_run_storage(self.planned_storage())
            save_dataset_root(storage.dataset_root)
        except (OSError, ValueError) as exc:
            self.storage_status.set(f"目录不可用：{exc}")
            messagebox.showerror("无法准备数据目录", str(exc), parent=self.winfo_toplevel())
            return
        self.dataset_root.set(str(storage.dataset_root))
        self.storage_status.set("目录已创建并通过可写检查。")
