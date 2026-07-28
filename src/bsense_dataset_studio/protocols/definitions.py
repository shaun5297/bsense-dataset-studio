from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


AdvanceMode = Literal["timed", "operator", "form", "response_or_timeout"]


@dataclass(frozen=True)
class InputField:
    key: str
    label: str
    kind: Literal["rating", "choice", "boolean", "number", "text"]
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class ProtocolStep:
    """Single source of truth for protocol preview and execution."""

    text: str
    detail: str
    duration_s: float | None
    event: str
    event_code: int | None = None
    block: str | None = None
    trial: int | None = None
    advance_mode: AdvanceMode = "timed"
    completion_event: str | None = None
    completion_code: int | None = None
    response_key: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    fields: tuple[InputField, ...] = ()
    visual: str | None = None
    start_sound: str | None = None
    warning_sound: str | None = None
    warning_at: float | None = None
    end_sound: str | None = None
    text_duration: float | None = None
    text_after: str | None = None

    @property
    def name(self) -> str:
        return self.event

    @property
    def duration(self) -> float:
        return float(self.duration_s or 0.0)

    @property
    def instruction(self) -> str:
        return "\n".join(value for value in (self.text, self.detail) if value)

    @property
    def marker(self) -> str:
        return self.event


@dataclass(frozen=True)
class Protocol:
    task: str
    display_name: str
    category: str
    version: str
    steps: tuple[ProtocolStep, ...]
    description: str = ""
    reference_labels_expected: bool = False


Step = ProtocolStep


def experiment_bounds(
    task: str,
    title: str,
    body: list[ProtocolStep],
) -> list[ProtocolStep]:
    return [
        ProtocolStep(
            "实验即将开始",
            title,
            4.0,
            "experiment_start",
            10,
            metadata={"protocol": task},
            start_sound="start",
        ),
        *body,
        ProtocolStep(
            "模块完成",
            "请保持放松，正在结束本模块录制",
            1.0,
            "experiment_end",
            11,
            end_sound="complete",
        ),
    ]
