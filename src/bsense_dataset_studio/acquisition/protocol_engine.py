from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ..behavior.pvt import classify_response
from ..behavior.sart import classify_trial
from ..protocols import Protocol, Step
from ..protocols.definitions import InputField
from .session import AcquisitionSession


@dataclass(frozen=True)
class EngineSnapshot:
    index: int
    total: int
    step: Step | None
    finished: bool
    pvt_stimulus_active: bool = False


class ProtocolEngine:
    """Deterministic protocol state machine independent from Tkinter."""

    def __init__(
        self,
        session: AcquisitionSession,
        protocol: Protocol,
        *,
        clock: Callable[[], float],
        on_change: Callable[[EngineSnapshot], None] | None = None,
    ) -> None:
        self.session = session
        self.protocol = protocol
        self.clock = clock
        self.on_change = on_change
        self.index = -1
        self.step_started_at: float | None = None
        self.response_timestamps: list[float] = []
        self.finished = False
        self._pvt_rng = random.Random(_protocol_seed(protocol) ^ 0x505654)
        self._pvt_end_at: float | None = None
        self._pvt_next_stimulus_at: float | None = None
        self._pvt_stimulus_at: float | None = None
        self._pvt_trial = 0
        self._practice_attempt = 1
        self._practice_results: list[dict[str, object]] = []

    @property
    def current_step(self) -> Step | None:
        if 0 <= self.index < len(self.protocol.steps):
            return self.protocol.steps[self.index]
        return None

    def start(self, *, recorder_timeout: float = 5.0) -> EngineSnapshot:
        if self.index >= 0:
            raise RuntimeError("协议已经启动")
        self.session.start(timeout=recorder_timeout)
        return self._enter_next()

    def handle_response(self, key: str, *, timestamp: float | None = None) -> bool:
        step = self.current_step
        if step is None or self.finished or key != step.response_key:
            return False
        now = self.clock() if timestamp is None else float(timestamp)
        if step.event == "pvt_start":
            return self._handle_pvt_response(now)
        self.response_timestamps.append(now)
        if len(self.response_timestamps) == 1:
            self.session.publish(
                str(step.metadata.get("response_event", "response")),
                event_code=_optional_int(step.metadata.get("response_code")),
                timestamp=now,
                payload=self._trial_payload(step)
                | {
                    "stimulus_onset_timestamp": self.step_started_at,
                    "response_timestamp": now,
                    "reaction_time_s": _elapsed(self.step_started_at, now),
                },
            )
        return True

    def advance(
        self,
        form_values: Mapping[str, Any] | None = None,
        *,
        timestamp: float | None = None,
    ) -> EngineSnapshot:
        step = self.current_step
        if step is None or self.finished:
            raise RuntimeError("没有可完成的协议步骤")
        now = self.clock() if timestamp is None else float(timestamp)
        if step.advance_mode == "form":
            normalized = validate_form(step.fields, form_values or {})
            if step.metadata.get("normalize_readiness_context"):
                normalized = validate_readiness_context(normalized)
            self.session.merge_context(normalized)
        else:
            normalized = {}
        if step.event == "sart_stimulus":
            self._publish_sart_result(step, now)
        if step.event == "pvt_start":
            self._finish_active_pvt_trial(now, timeout=True)
        if step.completion_event:
            self.session.publish(
                step.completion_event,
                event_code=step.completion_code,
                timestamp=now,
                payload=self._trial_payload(step) | normalized,
            )
        return self._enter_next()

    def tick(self, *, timestamp: float | None = None) -> EngineSnapshot:
        step = self.current_step
        if step is None or self.finished:
            return self.snapshot()
        now = self.clock() if timestamp is None else float(timestamp)
        if step.event == "pvt_start":
            self._tick_pvt(now)
            if self._pvt_end_at is not None and now >= self._pvt_end_at:
                return self.advance(timestamp=now)
            return self.snapshot()
        if (
            step.advance_mode == "timed"
            and step.duration_s is not None
            and self.step_started_at is not None
            and now - self.step_started_at >= step.duration_s
        ):
            return self.advance(timestamp=now)
        return self.snapshot()

    def abort(self, reason: str) -> None:
        if not self.finished:
            self.session.abort(reason)
            self.finished = True
            self._notify()

    def snapshot(self) -> EngineSnapshot:
        return EngineSnapshot(
            index=self.index,
            total=len(self.protocol.steps),
            step=self.current_step,
            finished=self.finished,
            pvt_stimulus_active=self._pvt_stimulus_at is not None,
        )

    def _enter_next(self) -> EngineSnapshot:
        self.index += 1
        self.response_timestamps.clear()
        self.step_started_at = self.clock()
        if self.index >= len(self.protocol.steps):
            self.finished = True
            self.session.finalize()
            return self._notify()
        step = self.current_step
        assert step is not None
        if step.event == "sart_start" and self._practice_results:
            practice_passed = _practice_criterion_met(self._practice_results)
            self.session.publish(
                "sart_practice_check",
                payload={
                    "attempt": self._practice_attempt,
                    "passed": practice_passed,
                    "correct_count": sum(
                        bool(row.get("correct")) for row in self._practice_results
                    ),
                    "trial_count": len(self._practice_results),
                },
                timestamp=self.step_started_at,
            )
            if not practice_passed and self._practice_attempt == 1:
                self._practice_attempt = 2
                self._practice_results.clear()
                self.session.publish(
                    "sart_practice_repeat",
                    payload={"attempt": 2},
                    timestamp=self.step_started_at,
                )
                first_practice = next(
                    index
                    for index, candidate in enumerate(self.protocol.steps)
                    if candidate.block == "sart_practice"
                )
                self.index = first_practice - 1
                return self._enter_next()
            if not practice_passed:
                # 练习两次仍未达标：不再中止采集。疲劳筛查的目标人群本来就容易
                # 在 SART 上犯错，直接中止会丢掉最需要的数据；记录标记后继续正式采集。
                self.session.merge_context(
                    {
                        "practice_attempts": self._practice_attempt,
                        "practice_criterion_met": False,
                    }
                )
                self.session.publish(
                    "sart_practice_criterion_not_met",
                    payload={"attempt": self._practice_attempt, "continued": True},
                    timestamp=self.step_started_at,
                )
            else:
                self.session.merge_context(
                    {
                        "practice_attempts": self._practice_attempt,
                        "practice_criterion_met": True,
                    }
                )
        self.session.publish(
            step.event,
            event_code=step.event_code,
            timestamp=self.step_started_at,
            payload=self._trial_payload(step) | dict(step.metadata),
        )
        if step.event == "pvt_start":
            duration = float(step.metadata.get("duration_s", step.duration_s or 0))
            self._pvt_end_at = self.step_started_at + duration
            self._pvt_next_stimulus_at = (
                self.step_started_at + self._pvt_rng.uniform(*self._pvt_isi(step))
            )
        return self._notify()

    def _publish_sart_result(self, step: Step, now: float) -> None:
        first_response = self.response_timestamps[0] if self.response_timestamps else None
        reaction_time = (
            _elapsed(self.step_started_at, first_response)
            if first_response is not None
            else None
        )
        result = classify_trial(
            bool(step.metadata["should_respond"]),
            reaction_time,
            trial=step.trial,
            stimulus=str(step.metadata["stimulus"]),
            response_count=len(self.response_timestamps),
        )
        if step.metadata.get("trial_kind") == "practice":
            self._practice_results.append(result)
        payload = (
            self._trial_payload(step)
            | dict(step.metadata)
            | result
            | {
                "stimulus_onset_timestamp": self.step_started_at,
                "response_timestamp": first_response,
                "result_timestamp": now,
            }
        )
        self.session.publish(
            str(step.metadata["result_event"]),
            event_code=_optional_int(step.metadata.get("result_code")),
            timestamp=now,
            payload=payload,
        )

    def _tick_pvt(self, now: float) -> None:
        step = self.current_step
        assert step is not None
        timeout = float(step.metadata["response_timeout_s"])
        if self._pvt_stimulus_at is not None and now - self._pvt_stimulus_at >= timeout:
            self._finish_active_pvt_trial(now, timeout=True)
        if (
            self._pvt_stimulus_at is None
            and self._pvt_next_stimulus_at is not None
            and now >= self._pvt_next_stimulus_at
            and (self._pvt_end_at is None or now < self._pvt_end_at)
        ):
            self._pvt_trial += 1
            self._pvt_stimulus_at = now
            self._pvt_next_stimulus_at = None
            self.session.publish(
                str(step.metadata["stimulus_event"]),
                event_code=_optional_int(step.metadata.get("stimulus_code")),
                timestamp=now,
                payload={"trial": self._pvt_trial, "trial_kind": "reference"},
            )
            self._notify()

    def _handle_pvt_response(self, now: float) -> bool:
        step = self.current_step
        assert step is not None
        if self._pvt_stimulus_at is None:
            self.session.publish(
                "pvt_false_start",
                timestamp=now,
                payload={"trial": self._pvt_trial + 1, "false_start": True},
            )
            self._pvt_next_stimulus_at = now + self._pvt_rng.uniform(
                *self._pvt_isi(step)
            )
            return True
        reaction_time = now - self._pvt_stimulus_at
        self.session.publish(
            str(step.metadata["response_event"]),
            event_code=_optional_int(step.metadata.get("response_code")),
            timestamp=now,
            payload={
                "trial": self._pvt_trial,
                "stimulus_timestamp": self._pvt_stimulus_at,
                "response_timestamp": now,
                "reaction_time_s": reaction_time,
            },
        )
        self._finish_active_pvt_trial(now, timeout=False)
        return True

    def _finish_active_pvt_trial(self, now: float, *, timeout: bool) -> None:
        step = self.current_step
        if step is None or self._pvt_stimulus_at is None:
            return
        reaction_time = None if timeout else now - self._pvt_stimulus_at
        result = classify_response(reaction_time, timeout=timeout)
        self.session.publish(
            str(step.metadata["result_event"]),
            event_code=_optional_int(step.metadata.get("result_code")),
            timestamp=now,
            payload={
                "trial": self._pvt_trial,
                "stimulus_timestamp": self._pvt_stimulus_at,
                "response_timestamp": None if timeout else now,
                "result_timestamp": now,
                **result,
            },
        )
        self._pvt_stimulus_at = None
        if self._pvt_end_at is None or now < self._pvt_end_at:
            self._pvt_next_stimulus_at = now + self._pvt_rng.uniform(*self._pvt_isi(step))
        self._notify()

    def _pvt_isi(self, step: Step) -> tuple[float, float]:
        return (
            float(step.metadata["isi_min_s"]),
            float(step.metadata["isi_max_s"]),
        )

    def _trial_payload(self, step: Step) -> dict[str, Any]:
        return {"block": step.block, "trial": step.trial}

    def _notify(self) -> EngineSnapshot:
        snapshot = self.snapshot()
        if self.on_change is not None:
            self.on_change(snapshot)
        return snapshot


def validate_form(
    fields: tuple[InputField, ...],
    values: Mapping[str, Any],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field in fields:
        raw = values.get(field.key)
        if raw in (None, ""):
            if field.required:
                raise ValueError(f"“{field.label}”不能为空")
            normalized[field.key] = None
            continue
        if field.kind in {"rating", "number"}:
            value = float(raw)
            if field.minimum is not None and value < field.minimum:
                raise ValueError(f"“{field.label}”不能小于 {field.minimum:g}")
            if field.maximum is not None and value > field.maximum:
                raise ValueError(f"“{field.label}”不能大于 {field.maximum:g}")
            normalized[field.key] = value
        elif field.kind == "boolean":
            boolean_value = (
                raw
                if isinstance(raw, bool)
                else str(raw).lower() in {"1", "true", "yes", "是"}
            )
            if field.required and not boolean_value:
                raise ValueError(f"“{field.label}”必须确认")
            normalized[field.key] = boolean_value
        elif field.kind == "choice":
            value = str(raw)
            if value not in field.choices:
                raise ValueError(f"“{field.label}”选项无效")
            normalized[field.key] = value
        else:
            normalized[field.key] = str(raw).strip()
    return normalized


def validate_readiness_context(values: dict[str, Any]) -> dict[str, Any]:
    phase = values.get("measurement_phase")
    parent_session = values.get("parent_session_id")
    parent = values.get("parent_run_id")
    rest = values.get("rest_duration_minutes")
    if phase == "retest" and (not parent_session or not parent or rest is None):
        raise ValueError(
            "复测必须填写关联首次检测 Session、Run 和实际休息时长"
        )
    if phase == "first_test" and (parent_session or parent or rest is not None):
        raise ValueError("首次检测不能填写父 Session/Run 或复测休息时长")
    return values


def _protocol_seed(protocol: Protocol) -> int:
    for step in protocol.steps:
        if step.event == "sart_start":
            return int(step.metadata.get("random_seed", 0))
    return 0


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None else None


def _elapsed(start: float | None, end: float) -> float | None:
    return round(end - start, 6) if start is not None else None


def _practice_criterion_met(results: list[dict[str, object]]) -> bool:
    if len(results) < 12:
        return False
    accuracy = sum(bool(row.get("correct")) for row in results) / len(results)
    correct_no_go = sum(
        row.get("outcome") == "correct_rejection" for row in results
    )
    return accuracy >= 0.8 and correct_no_go >= 2
