from __future__ import annotations

from dataclasses import dataclass

from .definitions import Protocol
from .device_qc import build_deviceqc_plan
from .readiness_study import build_m6_plan
from .sequences import SART_SEQUENCE_SEEDS, sequence_seed


@dataclass(frozen=True)
class _ProtocolSpec:
    task: str
    display_name: str
    category: str
    description: str
    reference_labels_expected: bool


_SPECS = (
    _ProtocolSpec(
        "m6_readiness_reference",
        "脑安检正式参考采集",
        "认知准备度",
        "用于训练集和验证集采集，包含完整背景、KSS、SART 与 PVT-B。",
        True,
    ),
    _ProtocolSpec(
        "deviceqc",
        "设备质量检查",
        "设备与基线",
        "验证信号、同步和常见伪迹，不作为认知状态训练样本。",
        False,
    ),
)

_SPEC_BY_TASK = {spec.task: spec for spec in _SPECS}


def build(
    task: str,
    *,
    short: bool = False,
    sequence_set_id: str = "sart-v1-A",
    include_pvt: bool | None = None,
) -> Protocol:
    if task == "m6_readiness_study":
        task = "m6_readiness_reference"
    if task == "m6_readiness_field":
        raise KeyError("现场短流程已停用，请使用 m6_readiness_reference 正式参考采集。")
    if task == "m6_readiness_reference" and include_pvt is False:
        raise ValueError("正式参考采集必须包含 PVT-B，不能关闭。")
    try:
        spec = _SPEC_BY_TASK[task]
    except KeyError as exc:
        raise KeyError(f"未知协议：{task}") from exc

    if task == "deviceqc":
        steps = build_deviceqc_plan(short=short)
    else:
        if sequence_set_id not in SART_SEQUENCE_SEEDS:
            raise ValueError(f"未知 SART 序列集：{sequence_set_id}")
        steps = build_m6_plan(
            short=short,
            seed=sequence_seed(sequence_set_id),
            protocol_task=task,
            protocol_title=spec.display_name,
            readiness_reference=True,
            sequence_set_id=sequence_set_id,
        )
    return Protocol(
        task=task,
        display_name=spec.display_name,
        category=spec.category,
        version="2.0",
        steps=tuple(steps),
        description=spec.description,
        reference_labels_expected=spec.reference_labels_expected,
    )


def list_protocols() -> tuple[Protocol, ...]:
    return tuple(
        Protocol(
            task=spec.task,
            display_name=spec.display_name,
            category=spec.category,
            version="2.0",
            steps=(),
            description=spec.description,
            reference_labels_expected=spec.reference_labels_expected,
        )
        for spec in _SPECS
    )
