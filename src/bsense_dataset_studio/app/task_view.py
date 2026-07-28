from __future__ import annotations

from dataclasses import dataclass, replace
from tkinter import StringVar, ttk

from ..protocols.base import Protocol, Step


@dataclass(frozen=True)
class PreviewStage:
    key: str
    title: str
    description: str
    duration_s: float | None
    step_count: int = 1
    item_count: int = 0

    @property
    def display_title(self) -> str:
        if self.key == "sart_practice" and self.item_count:
            return f"{self.title}（{self.item_count} 试次）"
        if self.key == "sart_assessment" and self.item_count:
            return f"{self.title}（{self.item_count} 试次）"
        if self.key == "artifact_check" and self.item_count:
            return f"{self.title}（{self.item_count} 次动作）"
        return self.title


_STAGE_TEXT = {
    "experiment_start": ("实验准备", "确认实验环境、设备状态和受试者准备情况。"),
    "experiment_end": ("完成与保存", "结束采集并等待原始数据、Marker 和质量记录安全保存。"),
    "open_rest": ("睁眼静息", "注视屏幕中央，保持自然呼吸并尽量减少头部运动。"),
    "closed_rest": ("闭眼静息", "轻轻闭眼，保持清醒和头部稳定。"),
    "artifact_check": ("动作与伪迹检查", "依次完成眨眼、轻咬、左右转头、点头和摇头，用于验证伪迹响应。"),
    "final_open_rest": ("结束睁眼静息", "重新建立安静睁眼参考，确认设备仍保持稳定。"),
    "readiness_intro": ("研究说明", "说明采集目的、数据边界和非岗位决策用途。"),
    "readiness_background": ("睡眠与班次信息", "记录过去 24 小时睡眠、连续清醒、班次和相关研究背景。"),
    "readiness_context": ("采前状态", "记录采前 KSS、首测或复测关系及必要状态信息。"),
    "signal_gate": ("信号质量检查", "检查 EEG、fNIRS、Motion 和 LSL 完整性，质量不合格时先调整设备。"),
    "readiness_baseline": ("睁眼基线", "建立本次佩戴条件下的 EEG、fNIRS 和运动噪声参考。"),
    "sart_instruction": ("SART 任务说明", "除数字 3 外都按空格；看到数字 3 时不要按。"),
    "sart_practice": ("SART 练习", "通过 12 个练习试次确认受试者已理解按键规则。"),
    "sart_assessment": ("SART 正式任务", "记录命中、漏检、抑制错误、抢按和反应时间，并与生理信号同步。"),
    "postcheck": ("采后 KSS", "任务结束后再次记录即时困倦程度，用于研究前后比较。"),
    "pvt": ("PVT-B 研究参照", "可选的 3 分钟警觉任务，仅作为独立研究参照，不进入产品主流程。"),
    "reference_label_pending": (
        "完成研究记录",
        "采集结束后使用 KSS、PVT、SART 和睡眠背景生成可追溯的研究参考标签。",
    ),
}

_ARTIFACT_EVENTS = {
    "blink",
    "jaw_clench",
    "head_left",
    "head_right",
    "head_nod",
    "head_cancel",
}


def _stage_key(step: Step, *, assessment_started: bool) -> str:
    event = step.name
    if event == "experiment_start":
        return "experiment_start"
    if event == "experiment_end":
        return "experiment_end"
    if event.startswith("rest_open_final"):
        return "final_open_rest"
    if event.startswith("rest_open"):
        return "open_rest"
    if event.startswith("rest_closed"):
        return "closed_rest"
    if (
        event.startswith("block_")
        or event.startswith("step_")
        or event in _ARTIFACT_EVENTS
        or step.block in _ARTIFACT_EVENTS
    ):
        return "artifact_check"
    if event == "readiness_intro":
        return "readiness_intro"
    if event == "readiness_background_start":
        return "readiness_background"
    if event == "readiness_context_start":
        return "readiness_context"
    if event == "readiness_signal_gate_start":
        return "signal_gate"
    if event == "readiness_baseline_start":
        return "readiness_baseline"
    if event == "sart_instruction":
        return "sart_instruction"
    if event == "sart_stimulus":
        return "sart_assessment" if assessment_started else "sart_practice"
    if event in {"sart_start", "sart_end"}:
        return "sart_assessment"
    if event.startswith("readiness_postcheck"):
        return "postcheck"
    if event.startswith("pvt_"):
        return "pvt"
    return event


def _fallback_text(step: Step) -> tuple[str, str]:
    lines = [line.strip() for line in step.instruction.splitlines() if line.strip()]
    title = lines[0] if lines and lines[0] != "+" else "协议步骤"
    description = " ".join(lines[1:]) if len(lines) > 1 else title
    return title, description


def build_preview_stages(protocol: Protocol) -> tuple[PreviewStage, ...]:
    stages: list[PreviewStage] = []
    assessment_started = False
    for step in protocol.steps:
        if step.name == "sart_start":
            assessment_started = True
        key = _stage_key(step, assessment_started=assessment_started)
        title, description = _STAGE_TEXT.get(key, _fallback_text(step))
        item_count = int(step.name == "sart_stimulus" or step.name in _ARTIFACT_EVENTS)
        stage = PreviewStage(key, title, description, step.duration_s, item_count=item_count)
        if stages and stages[-1].key == key:
            previous = stages[-1]
            duration = None
            if previous.duration_s is not None or stage.duration_s is not None:
                duration = (previous.duration_s or 0.0) + (stage.duration_s or 0.0)
            stages[-1] = replace(
                previous,
                duration_s=duration,
                step_count=previous.step_count + 1,
                item_count=previous.item_count + stage.item_count,
            )
        else:
            stages.append(stage)
    return tuple(stages)


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "填写/确认"
    rounded = round(seconds, 1)
    if rounded < 60:
        return f"{rounded:g} 秒"
    minutes = int(rounded // 60)
    remaining = rounded - minutes * 60
    return f"{minutes} 分 {remaining:g} 秒" if remaining else f"{minutes} 分钟"


class TaskView(ttk.LabelFrame):
    def __init__(self, parent: object) -> None:
        super().__init__(parent, text="协议预览", padding=14)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.protocol_name = StringVar(value="请选择协议")
        self.summary = StringVar(value="")
        self.detail_title = StringVar(value="阶段详情")
        self.detail_text = StringVar(value="选择一个阶段查看完整说明。")
        self._stage_by_item: dict[str, PreviewStage] = {}

        ttk.Label(self, textvariable=self.protocol_name, font=("", 16, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Label(self, textvariable=self.summary, foreground="#4B5563").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(4, 12),
        )

        table = ttk.Frame(self)
        table.grid(row=2, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        style = ttk.Style(self)
        style.configure("Protocol.Treeview", rowheight=30)
        self.tree = ttk.Treeview(
            table,
            columns=("number", "stage", "description", "duration"),
            show="headings",
            style="Protocol.Treeview",
            selectmode="browse",
            height=12,
        )
        self.tree.heading("number", text="#")
        self.tree.heading("stage", text="阶段")
        self.tree.heading("description", text="说明")
        self.tree.heading("duration", text="时长")
        self.tree.column("number", width=46, minwidth=42, anchor="center", stretch=False)
        self.tree.column("stage", width=190, minwidth=150, anchor="w")
        self.tree.column("description", width=360, minwidth=240, anchor="w")
        self.tree.column("duration", width=100, minwidth=90, anchor="center", stretch=False)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._show_selected)

        details = ttk.LabelFrame(self, text="阶段详情", padding=10)
        details.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        details.columnconfigure(0, weight=1)
        ttk.Label(
            details,
            textvariable=self.detail_title,
            font=("", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.detail_label = ttk.Label(
            details,
            textvariable=self.detail_text,
            justify="left",
            wraplength=520,
        )
        self.detail_label.grid(row=1, column=0, sticky="ew")
        details.bind(
            "<Configure>",
            lambda event: self.detail_label.configure(wraplength=max(280, event.width - 28)),
        )

    def show_protocol(self, protocol: Protocol) -> None:
        stages = build_preview_stages(protocol)
        self.protocol_name.set(protocol.display_name)
        known_duration = sum(stage.duration_s or 0.0 for stage in stages)
        pvt_state = "开启" if any(stage.key == "pvt" for stage in stages) else "关闭"
        self.summary.set(
            f"预计计时 {format_duration(known_duration)}  ·  {len(stages)} 个阶段  ·  PVT-B {pvt_state}"
        )
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._stage_by_item.clear()
        for index, stage in enumerate(stages, 1):
            item = self.tree.insert(
                "",
                "end",
                values=(index, stage.display_title, stage.description, format_duration(stage.duration_s)),
            )
            self._stage_by_item[item] = stage
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
            self.tree.see(children[0])
            self._show_selected()

    def _show_selected(self, _event: object | None = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        stage = self._stage_by_item[selection[0]]
        self.detail_title.set(stage.display_title)
        self.detail_text.set(
            f"{stage.description}\n计时时长：{format_duration(stage.duration_s)}"
        )
