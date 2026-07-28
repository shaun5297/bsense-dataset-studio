from __future__ import annotations

from tkinter import StringVar, ttk


class SetupView(ttk.LabelFrame):
    def __init__(self, parent: object) -> None:
        super().__init__(parent, text="实验标识", padding=12)
        self.participant = StringVar(value="P001")
        self.session = StringVar(value="01")
        self.run = StringVar(value="001")
        for row, (label, variable) in enumerate((("匿名被试", self.participant), ("Session", self.session), ("Run", self.run))):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(self, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=3)
        self.columnconfigure(1, weight=1)
