"""Detailed acquisition-step definitions retained from bsense-lsl v0.8.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


AdvanceMode = Literal["timed", "operator", "form"]


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
class Step:
    text: str
    detail: str
    duration: float
    event: str | None = None
    code: int | None = None
    block: str | None = None
    trial: int | None = None
    advance: AdvanceMode = "timed"
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


@dataclass(frozen=True)
class ProtocolInfo:
    task: str
    title: str
    description: str
    priority: str


PROTOCOLS = (
    ProtocolInfo("deviceqc", "设备 QC", "验证信号、同步与常见伪迹（正式采集前推荐）", "联调"),
    ProtocolInfo(
        "m6_readiness",
        "M6 班前认知准备度研究协议",
        "脑安检训练与验证数据采集",
        "赛道7",
    ),
)

PROTOCOL_BY_TASK = {protocol.task: protocol for protocol in PROTOCOLS}


def _experiment_bounds(task: str, body: list[Step]) -> list[Step]:
    return [
        Step(
            "实验即将开始",
            PROTOCOL_BY_TASK[task].title,
            4.0,
            "experiment_start",
            10,
            metadata={"protocol": task},
            start_sound="start",
        ),
        *body,
        Step(
            "模块完成",
            "请保持放松，正在结束本模块录制",
            1.0,
            "experiment_end",
            11,
            end_sound="complete",
        ),
    ]
