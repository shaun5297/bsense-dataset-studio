from __future__ import annotations

from .base import Protocol, Step
from .device_qc import build_deviceqc_plan
from .readiness_study import build_m6_plan

_SPECS = (
    ("deviceqc", "设备质量检查", "设备与基线"),
    ("m6_readiness_study", "脑安检研究采集", "认知准备度"),
)


_BUILDERS = {
    "deviceqc": build_deviceqc_plan,
    "m6_readiness_study": build_m6_plan,
}


def _details(
    task: str,
    display_name: str,
    category: str,
    short: bool,
    include_pvt: bool,
) -> Protocol:
    builder = _BUILDERS[task]
    legacy_steps = builder(short=short, seed=0, readiness_reference=include_pvt)
    steps: list[Step] = []
    for index, item in enumerate(legacy_steps, 1):
        event = str(item.event or item.completion_event or f"step_{index:04d}")
        if task == "m6_readiness_study" and event == "readiness_assessment":
            continue
        instruction = "\n".join(value for value in (item.text, item.detail) if value)
        if task == "m6_readiness_study":
            instruction = instruction.replace("脑状态安检", "班前认知准备度研究")
            instruction = instruction.replace(
                "本流程只输出当班风险等级，不展示原始脑信号，不用于医疗诊断、自动上岗或处罚。",
                "本流程用于研究采集与验证，不向被试或管理人员输出正式岗位建议。",
            )
        steps.append(
            Step(
                name=event,
                duration_s=float(item.duration) if item.duration > 0 else None,
                instruction=instruction,
                marker=str(item.event or item.completion_event or "step"),
            )
        )
    return Protocol(task, display_name, category, "1.0", tuple(steps))


def build(task: str, *, short: bool = False, include_pvt: bool = False) -> Protocol:
    for key, name, category in _SPECS:
        if key == task:
            return _details(key, name, category, short, include_pvt)
    raise KeyError(f"未知协议：{task}")


def list_protocols() -> tuple[Protocol, ...]:
    return tuple(Protocol(task, name, category, "1.0", ()) for task, name, category in _SPECS)
