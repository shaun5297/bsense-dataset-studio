from __future__ import annotations

from collections.abc import Callable
from tkinter import BooleanVar, StringVar, Toplevel, messagebox, ttk

from ..acquisition.protocol_engine import EngineSnapshot, ProtocolEngine
from ..acquisition.session import AcquisitionSession, lsl_clock
from ..annotations import ANNOTATION_TYPES
from ..protocols import Protocol
from ..protocols.definitions import InputField, ProtocolStep
from . import theme
from .audio import play_cue

# English choice values stay untouched in stored data; only the display
# labels are translated for the operator form.
_CHOICE_LABELS = {
    "rested_control": "充分休息对照",
    "natural_fatigue": "自然疲劳",
    "post_night_shift": "夜班后",
    "post_shift": "班后",
    "post_rest_retest": "休息后复测",
    "sleep_restricted": "睡眠限制",
    "unknown_naturalistic": "未知（自然状态）",
    "operator_assigned": "实验员指定",
    "schedule_derived": "按排班推断",
    "participant_reported": "受试者填报",
    "first_test": "首次检测",
    "retest": "复测",
}


def _stimulus_font(text: str) -> tuple[str, int, str]:
    """Scale the stimulus font to the content so short stimuli dominate the screen."""
    length = len(text)
    if length <= 2:
        return ("", 120, "bold")
    if length <= 6:
        return ("", 72, "bold")
    if length <= 12:
        return ("", 48, "bold")
    return ("", 30, "bold")


class _BooleanToggle(ttk.Frame):
    """Large, theme-proof checkbox.

    ttk.Checkbutton indicator glyphs differ across themes (a check in one
    theme can render as a cross in another), so the state is shown with
    explicit text glyphs plus a colored status word instead.
    """

    def __init__(self, parent: object, variable: BooleanVar) -> None:
        super().__init__(parent)
        self._variable = variable
        self._box = ttk.Label(self, font=("", 20), cursor="hand2")
        self._box.pack(side="left")
        self._state = ttk.Label(self, font=("", 14))
        self._state.pack(side="left", padx=(10, 0))
        for widget in (self, self._box, self._state):
            widget.bind("<Button-1>", self._toggle)
        variable.trace_add("write", lambda *_args: self._sync())
        self._sync()

    def _toggle(self, _event: object | None = None) -> None:
        self._variable.set(not self._variable.get())

    def _sync(self) -> None:
        checked = bool(self._variable.get())
        self._box.configure(text="☑" if checked else "☐")
        self._state.configure(
            text="已确认" if checked else "点击确认",
            foreground=theme.color("ok") if checked else theme.color("muted"),
        )


class ExecutionWindow(Toplevel):
    def __init__(
        self,
        parent: object,
        session: AcquisitionSession,
        protocol: Protocol,
        *,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.protocol_spec = protocol
        self._on_close_callback = on_close
        self.engine = ProtocolEngine(
            session,
            protocol,
            clock=lsl_clock,
            on_change=self._render_snapshot,
        )
        self.title(f"BSense 采集执行 — {protocol.display_name}")
        self.geometry("1100x800")
        self.minsize(900, 680)
        self.protocol("WM_DELETE_WINDOW", self._request_close)
        self.bind("<space>", self._handle_space)
        self.bind("<Return>", self._handle_return)
        self.bind("<F11>", self._toggle_fullscreen)
        self._form_variables: dict[str, StringVar | BooleanVar] = {}
        self._choice_values: dict[str, dict[str, str]] = {}
        self._after_id: str | None = None
        self._current_step: ProtocolStep | None = None
        self._warning_played = False
        self._quality_prev_counts: dict[str, int] = {}
        self._quality_ticks = 0

        container = ttk.Frame(self, padding=28)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)
        self.progress = StringVar(value="准备启动")
        self.countdown = StringVar(value="")
        self.title_text = StringVar(value="正在检查 8 路 LSL 流…")
        self.detail_text = StringVar(value="Marker 流会先创建，再启动 XDF Recorder。")
        header = ttk.Frame(container)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        self.quality_badge = ttk.Label(
            header,
            text="◌ 未连接",
            font=("", 13, "bold"),
            foreground=theme.color("muted"),
        )
        self.quality_badge.grid(row=0, column=0, sticky="w", padx=(0, 14))
        self.progress_label = ttk.Label(
            header,
            textvariable=self.progress,
            font=("", 13),
            foreground=theme.color("secondary"),
        )
        self.progress_label.grid(row=0, column=1, sticky="w")
        self.progressbar = ttk.Progressbar(container, mode="determinate")
        self.progressbar.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        # Stimulus, instructions and countdown share the screen center so the
        # subject never has to look away from the fixation area.
        center = ttk.Frame(container)
        center.grid(row=2, column=0, sticky="nsew")
        self.stimulus_label = ttk.Label(
            center,
            textvariable=self.title_text,
            font=("", 40, "bold"),
            anchor="center",
        )
        self.stimulus_label.pack(fill="both", expand=True)
        ttk.Label(
            center,
            textvariable=self.detail_text,
            font=("", 18),
            anchor="center",
            justify="center",
            wraplength=900,
        ).pack(fill="x", pady=(0, 10))
        self.countdown_label = ttk.Label(
            center,
            textvariable=self.countdown,
            font=("", 22, "bold"),
            anchor="center",
        )
        self.countdown_label.pack(fill="x")

        self.form_frame = ttk.Frame(container)
        self.form_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.form_frame.columnconfigure(1, weight=1)

        footer = ttk.Frame(container)
        footer.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        self.theme_button = ttk.Button(
            footer,
            text=self._theme_button_text(),
            command=self._toggle_theme,
        )
        self.theme_button.pack(side="left")
        self.annotation_button = ttk.Button(
            footer,
            text="添加人工标注",
            command=self._open_annotation_dialog,
        )
        self.annotation_button.pack(side="right")
        self.continue_button = ttk.Button(
            footer,
            text="确认并继续",
            command=self._submit,
            state="disabled",
        )
        self.continue_button.pack(side="right", padx=(0, 8))
        self.abort_button = ttk.Button(
            footer,
            text="中止采集",
            command=self._request_abort,
        )
        self.abort_button.pack(side="right", padx=(0, 8))
        self._unsubscribe_theme = theme.on_change(self._sync_theme_widgets)

    def _sync_theme_widgets(self, _mode: str) -> None:
        try:
            self.progress_label.configure(foreground=theme.color("secondary"))
            self.theme_button.configure(text=self._theme_button_text())
        except Exception:
            pass  # window already destroyed

    def start(self) -> None:
        try:
            self.engine.start()
        except Exception as exc:
            messagebox.showerror("无法启动采集", str(exc), parent=self)
            self.destroy()
            if self._on_close_callback is not None:
                self._on_close_callback()
            return
        self.focus_force()
        self._schedule_tick()

    def abort(self) -> None:
        self._request_abort()

    def _render_snapshot(self, snapshot: EngineSnapshot) -> None:
        if snapshot.finished:
            self._play_step_sound(self._current_step, kind="end")
            self._current_step = None
            aborted = self.session.context_values.get("completion_status") == "aborted"
            self.progress.set("采集已中止" if aborted else "采集已结束")
            self.progressbar.configure(value=self.progressbar["maximum"])
            if aborted:
                reason = str(self.session.context_values.get("abort_reason") or "operator_requested")
                self.title_text.set("采集已中止")
                self.stimulus_label.configure(
                    font=_stimulus_font("采集已中止"),
                    foreground=theme.color("error"),
                )
                self.detail_text.set(f"中止原因：{reason}\n已采集数据仍已保存：{self.session.storage.xdf}")
            else:
                self.title_text.set("数据已安全保存")
                self.stimulus_label.configure(font=_stimulus_font("数据已安全保存"), foreground=theme.color("ok"))
                note = ""
                if self.session.context_values.get("practice_criterion_met") is False:
                    note = "（SART 练习未达标，已记录并继续）\n"
                self.detail_text.set(note + str(self.session.storage.xdf))
            self.quality_badge.configure(text="◌ 已结束", foreground=theme.color("muted"))
            self.countdown.set("")
            self.countdown_label.configure(foreground="")
            self.continue_button.configure(state="disabled")
            self.annotation_button.configure(state="disabled")
            self.abort_button.configure(text="关闭", command=self._finish_close)
            return
        step = snapshot.step
        if step is None:
            return
        if step is not self._current_step:
            self._play_step_sound(self._current_step, kind="end")
            self._current_step = step
            self._warning_played = False
            self._play_step_sound(step, kind="start")
        self.progress.set(
            f"{self.protocol_spec.display_name}  ·  步骤 {snapshot.index + 1}/{snapshot.total}"
        )
        self.progressbar.configure(maximum=snapshot.total, value=snapshot.index + 1)
        if step.event == "pvt_start":
            stimulus_active = snapshot.pvt_stimulus_active
            self.title_text.set("●" if stimulus_active else "+")
            self.stimulus_label.configure(
                font=("", 120, "bold"),
                foreground="#F59E0B" if stimulus_active else "#9CA3AF",
            )
            self.detail_text.set(
                "黄色圆点出现后立即按空格；等待期间不要抢按。"
            )
        else:
            self.title_text.set(step.text)
            self.stimulus_label.configure(font=_stimulus_font(step.text), foreground="")
            self.detail_text.set(step.detail)
        self._build_form(step.fields)
        enabled = step.advance_mode in {"form", "operator"}
        self.continue_button.configure(state="normal" if enabled else "disabled")

    def _build_form(self, fields: tuple[InputField, ...]) -> None:
        for child in self.form_frame.winfo_children():
            child.destroy()
        self._form_variables.clear()
        self._choice_values.clear()
        for row, field in enumerate(fields):
            ttk.Label(self.form_frame, text=field.label, font=("", 15)).grid(
                row=row,
                column=0,
                sticky="w",
                padx=(0, 14),
                pady=7,
            )
            if field.kind == "boolean":
                variable = BooleanVar(value=False)
                widget = _BooleanToggle(self.form_frame, variable)
            else:
                variable = StringVar()
                if field.kind == "choice":
                    labels = [_CHOICE_LABELS.get(choice, choice) for choice in field.choices]
                    self._choice_values[field.key] = dict(zip(labels, field.choices))
                    widget = ttk.Combobox(
                        self.form_frame,
                        textvariable=variable,
                        values=labels,
                        state="readonly",
                        font=("", 15),
                    )
                else:
                    widget = ttk.Entry(self.form_frame, textvariable=variable, font=("", 15))
            widget.grid(row=row, column=1, sticky="ew", pady=7)
            self._form_variables[field.key] = variable

    def _submit(self) -> None:
        values = {}
        for key, variable in self._form_variables.items():
            raw = variable.get()
            values[key] = self._choice_values.get(key, {}).get(raw, raw)
        try:
            self.engine.advance(values)
        except ValueError as exc:
            messagebox.showwarning("表单未完成", str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror("步骤执行失败", str(exc), parent=self)

    def _handle_space(self, _event: object) -> str:
        try:
            self.engine.handle_response("space")
        except Exception as exc:
            messagebox.showerror("响应记录失败", str(exc), parent=self)
        return "break"

    def _handle_return(self, _event: object) -> str | None:
        if str(self.continue_button["state"]) == "normal":
            self._submit()
            return "break"
        return None

    def _toggle_fullscreen(self, _event: object) -> None:
        self.attributes("-fullscreen", not bool(self.attributes("-fullscreen")))

    def _theme_button_text(self) -> str:
        return "切换到日间模式" if theme.mode() == "dark" else "切换到夜间模式"

    def _toggle_theme(self) -> None:
        theme.toggle(self.winfo_toplevel())
        self.theme_button.configure(text=self._theme_button_text())

    def _play_step_sound(self, step: ProtocolStep | None, *, kind: str) -> None:
        if step is None:
            return
        name = step.end_sound if kind == "end" else step.start_sound
        play_cue(name, bell=self.bell)

    def _schedule_tick(self) -> None:
        self._after_id = self.after(40, self._tick)

    def _tick(self) -> None:
        self._after_id = None
        if self.engine.finished:
            return
        try:
            snapshot = self.engine.tick()
            step = snapshot.step
            if step is not None and self.engine.step_started_at is not None:
                elapsed = lsl_clock() - self.engine.step_started_at
                if step.text_after and step.text_duration is not None and elapsed >= step.text_duration:
                    self.title_text.set(step.text_after)
                    self.stimulus_label.configure(font=_stimulus_font(step.text_after))
                if step.duration_s is not None:
                    remaining = max(0.0, step.duration_s - elapsed)
                    self.countdown.set(f"剩余 {remaining:.1f} 秒")
                    ending_soon = step.duration_s > 10.0 and remaining <= 5.0
                    self.countdown_label.configure(foreground=theme.color("error") if ending_soon else "")
                    if (
                        step.warning_sound
                        and step.warning_at is not None
                        and not self._warning_played
                        and remaining <= step.warning_at
                    ):
                        self._warning_played = True
                        play_cue(step.warning_sound, bell=self.bell)
                else:
                    self.countdown.set("等待填写/确认")
                    self.countdown_label.configure(foreground="")
        except Exception as exc:
            messagebox.showerror("采集执行失败", str(exc), parent=self)
            return
        self._quality_ticks += 1
        if self._quality_ticks >= 25:  # ~1s at a 40 ms tick
            self._quality_ticks = 0
            self._update_quality_badge()
        self._schedule_tick()

    _CORE_KIND_LABELS = (("eeg", "EEG"), ("fnirs", "fNIRS"), ("motion", "Motion"))

    def _update_quality_badge(self) -> None:
        summary = self.session.recorder_summary()
        if not summary:
            self.quality_badge.configure(text="◌ 未连接", foreground=theme.color("muted"))
            return
        stalled: list[str] = []
        for kind, label in self._CORE_KIND_LABELS:
            info = summary.get(kind) or {}
            count = int(info.get("sample_count") or 0)  # type: ignore[union-attr]
            if count <= self._quality_prev_counts.get(kind, 0):
                stalled.append(label)
            self._quality_prev_counts[kind] = count
        if not stalled:
            text, role = "● 信号正常", "ok"
        elif len(stalled) == len(self._CORE_KIND_LABELS):
            text, role = "● 信号中断", "error"
        else:
            text, role = f"● 信号异常：{' / '.join(stalled)}", "warn"
        self.quality_badge.configure(text=text, foreground=theme.color(role))

    def _open_annotation_dialog(self) -> None:
        AnnotationDialog(self, self.session)

    def _request_abort(self) -> None:
        if self.engine.finished:
            self._finish_close()
            return
        if not messagebox.askyesno(
            "确认中止",
            "将停止录制并保存已采集数据，同时标记本次 Run 为 aborted。是否继续？",
            parent=self,
        ):
            return
        try:
            self.engine.abort("operator_requested")
        except Exception as exc:
            messagebox.showerror("中止失败", str(exc), parent=self)

    def _request_close(self) -> None:
        if self.engine.finished:
            self._finish_close()
        else:
            self._request_abort()

    def _finish_close(self) -> None:
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.destroy()
        if self._on_close_callback is not None:
            self._on_close_callback()

    def destroy(self) -> None:
        unsubscribe, self._unsubscribe_theme = (
            getattr(self, "_unsubscribe_theme", None),
            None,
        )
        if unsubscribe is not None:
            unsubscribe()
        super().destroy()


class AnnotationDialog(Toplevel):
    def __init__(self, parent: ExecutionWindow, session: AcquisitionSession) -> None:
        super().__init__(parent)
        self.session = session
        self.title("人工标注")
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        self.annotation_type = StringVar(value=ANNOTATION_TYPES[0])
        self.note = StringVar()
        self.severity = StringVar(value="minor")
        self.duration_seconds = StringVar(value="0")
        self.exclude = BooleanVar(value=False)
        for row, label in enumerate(
            ("标注类型", "说明", "严重程度", "向前覆盖秒数")
        ):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frame,
            textvariable=self.annotation_type,
            values=ANNOTATION_TYPES,
            state="readonly",
            width=28,
        ).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Entry(frame, textvariable=self.note).grid(
            row=1,
            column=1,
            sticky="ew",
            pady=4,
        )
        ttk.Combobox(
            frame,
            textvariable=self.severity,
            values=("minor", "major"),
            state="readonly",
        ).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Entry(
            frame,
            textvariable=self.duration_seconds,
        ).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Checkbutton(
            frame,
            text="从训练数据中排除此时点",
            variable=self.exclude,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 4))
        ttk.Button(frame, text="保存标注", command=self._save).grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="e",
            pady=(10, 0),
        )
        frame.columnconfigure(1, weight=1)
        self.transient(parent)
        self.grab_set()

    def _save(self) -> None:
        try:
            duration = float(self.duration_seconds.get())
            if duration < 0:
                raise ValueError("向前覆盖秒数不能为负数")
            end = lsl_clock()
            self.session.annotate(
                self.annotation_type.get(),
                self.note.get(),
                start_timestamp=end - duration,
                end_timestamp=end,
                exclude_from_training=self.exclude.get(),
                severity=self.severity.get(),
            )
        except Exception as exc:
            messagebox.showerror("标注保存失败", str(exc), parent=self)
            return
        self.destroy()
