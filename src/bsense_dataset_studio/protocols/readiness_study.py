from __future__ import annotations

import random

from ..behavior.pvt import (
    PVT_B_DURATION_SECONDS,
    PVT_B_FALSE_START_SECONDS,
    PVT_B_ISI_MAX_SECONDS,
    PVT_B_ISI_MIN_SECONDS,
    PVT_B_LAPSE_SECONDS,
    PVT_B_TIMEOUT_SECONDS,
)
from .definitions import InputField, Step, experiment_bounds


def _sart_sequence(count: int, rng: random.Random) -> list[str]:
    """Build a reproducible sequence with roughly 11% no-go trials and no adjacent no-go."""

    no_go_count = max(1, round(count / 9))
    candidates = list(range(1, count - 1)) if count >= 4 else list(range(count))
    for _attempt in range(200):
        no_go_positions = sorted(rng.sample(candidates, no_go_count))
        if all(right - left > 1 for left, right in zip(no_go_positions, no_go_positions[1:])):
            break
    else:
        raise RuntimeError("无法生成满足间隔限制的 SART 序列")

    go_digits = [digit for digit in "12456789" for _ in range((count // 8) + 1)]
    rng.shuffle(go_digits)
    no_go_set = set(no_go_positions)
    sequence: list[str] = []
    go_index = 0
    for position in range(count):
        if position in no_go_set:
            sequence.append("3")
        else:
            sequence.append(go_digits[go_index])
            go_index += 1
    return sequence


def _sart_steps(
    sequence: list[str],
    *,
    block: str,
    trial_kind: str,
    duration: float,
) -> list[Step]:
    steps: list[Step] = []
    for trial, digit in enumerate(sequence, start=1):
        should_respond = digit != "3"
        steps.append(
            Step(
                digit,
                "除数字 3 外均按空格；看到 3 时不要按",
                duration,
                "sart_stimulus",
                721,
                block,
                trial,
                response_key="space",
                metadata={
                    "stimulus": digit,
                    "should_respond": should_respond,
                    "is_no_go": not should_respond,
                    "trial_kind": trial_kind,
                    "exclude_from_primary_analysis": trial_kind == "practice",
                    "response_event": "sart_response",
                    "response_code": 722,
                    "result_event": "sart_trial_result",
                    "result_code": 723,
                    "false_start_threshold_s": 0.1,
                },
                text_duration=duration / 2.0,
                text_after="+",
            )
        )
    return steps


def build_m6_plan(
    short: bool = False,
    seed: int = 0,
    readiness_reference: bool = True,
    protocol_task: str = "m6_readiness_reference",
    protocol_title: str = "脑安检正式参考采集",
    sequence_set_id: str = "sart-v1-A",
    **_: object,
) -> list[Step]:
    """Build a research acquisition protocol for cognitive readiness."""

    rng = random.Random(seed)
    assessment_trial_count = 18 if short else 180
    assessment_sequence = _sart_sequence(assessment_trial_count, rng)
    background_fields = (
        InputField(
            "study_condition",
            "实验条件",
            "choice",
            choices=(
                "rested_control",
                "natural_fatigue",
                "post_night_shift",
                "post_shift",
                "post_rest_retest",
                "sleep_restricted",
                "unknown_naturalistic",
            ),
        ),
        InputField(
            "condition_source",
            "实验条件来源",
            "choice",
            choices=("operator_assigned", "schedule_derived", "participant_reported"),
        ),
        InputField(
            "sleep_duration_hours",
            "过去 24 小时累计睡眠（小时，可填小数）",
            "number",
            0,
            24,
        ),
        InputField("last_sleep_onset_time", "最近一次入睡时间（HH:MM）", "text"),
        InputField("last_wake_time", "最近一次起床时间（HH:MM）", "text"),
        InputField(
            "continuous_awake_hours",
            "截至采集时连续清醒时长（小时）",
            "number",
            0,
            72,
        ),
        InputField(
            "caffeine_mg_last_8h",
            "过去 8 小时咖啡因摄入量（mg；无则填 0）",
            "number",
            0,
            2000,
        ),
        InputField("last_caffeine_time", "最近咖啡因摄入时间（HH:MM；无则留空）", "text", required=False),
        InputField(
            "shift_type",
            "本次班次",
            "choice",
            choices=("日班", "夜班", "倒班/跨时段", "不适用"),
        ),
    )
    precheck_fields = (
        InputField("kss_score", "采集前 KSS（1=非常清醒，9=极度困倦）", "rating", 1, 9),
        InputField(
            "measurement_phase",
            "测量阶段",
            "choice",
            choices=("first_test", "retest"),
        ),
        InputField(
            "parent_session_id",
            "关联首次检测 Session（首次检测留空）",
            "text",
            required=False,
        ),
        InputField(
            "parent_run_id",
            "关联首次检测 Run（首次检测留空）",
            "text",
            required=False,
        ),
        InputField(
            "rest_duration_minutes",
            "复测前实际休息分钟数（首次检测留空）",
            "number",
            0,
            180,
            required=False,
        ),
        InputField("ready_to_test", "本人无急性不适并自愿继续本次筛查", "boolean"),
    )
    body: list[Step] = [
        Step(
            "脑状态安检",
            "本流程只用于研究采集和验证，不输出正式岗位建议，不用于医疗诊断、自动上岗或处罚。",
            2.0 if short else 5.0,
            "readiness_intro",
            709,
        ),
        Step(
            "睡眠与班次",
            "请按当前真实情况填写。时间使用 24 小时制，未知信息应由实验员核实后再继续。",
            0.0,
            "readiness_background_start",
            710,
            advance_mode="form",
            completion_event="readiness_background",
            completion_code=711,
            fields=background_fields,
            metadata={"merge_form_into_context": True},
        ),
        Step(
            "采集前状态",
            "首次检测不填关联 Run；复测必须填写首次检测 Run 和实际休息时长。",
            0.0,
            "readiness_context_start",
            716,
            advance_mode="form",
            completion_event="readiness_context",
            completion_code=717,
            fields=precheck_fields,
            metadata={"merge_form_into_context": True, "normalize_readiness_context": True},
        ),
        Step(
            "+",
            "信号质量门控：保持睁眼、自然呼吸并尽量不动。",
            2.0 if short else 30.0,
            "readiness_signal_gate_start",
            712,
            completion_event="readiness_signal_gate_end",
            completion_code=713,
        ),
        Step(
            "+",
            "睁眼个体当次基线：注视中央，保持放松和清醒。",
            2.0 if short else 60.0,
            "readiness_baseline_start",
            714,
            completion_event="readiness_baseline_end",
            completion_code=715,
        ),
        Step(
            "任务说明",
            "数字会快速出现：除 3 外都按空格；看到 3 时不要按。过早按键将记为抢按。",
            2.0 if short else 5.0,
            "sart_instruction",
            719,
        ),
        *_sart_steps(
            ["1", "2", "3", "4", "5", "6", "7", "3", "8", "1", "2", "4"],
            block="sart_practice",
            trial_kind="practice",
            duration=0.5 if short else 1.0,
        ),
        Step(
            "正式任务开始",
            f"共 {assessment_trial_count} 个试次；在保证正确的前提下尽快响应。",
            1.0 if short else 2.0,
            "sart_start",
            720,
            metadata={
                "expected_trials": assessment_trial_count,
                "sequence_set_id": sequence_set_id,
                "random_seed": seed,
                "no_go_positions": [
                    index
                    for index, stimulus in enumerate(assessment_sequence, start=1)
                    if stimulus == "3"
                ],
            },
        ),
        *_sart_steps(
            assessment_sequence,
            block="sart_assessment",
            trial_kind="assessment",
            duration=0.5 if short else 1.0,
        ),
        Step(
            "任务结束",
            "正在汇总有效试次、反应稳定性和信号质量。",
            0.5 if short else 1.0,
            "sart_end",
            724,
            metadata={"expected_trials": assessment_trial_count},
        ),
    ]
    body.append(
        Step(
            "采后状态",
            "请报告此刻的真实困倦程度。",
            0.0,
            "readiness_postcheck_start",
            732,
            advance_mode="form",
            completion_event="readiness_postcheck",
            completion_code=733,
            fields=(
                InputField(
                    "kss_post_score",
                    "采集后 KSS（1=非常清醒，9=极度困倦）",
                    "rating",
                    1,
                    9,
                ),
            ),
            metadata={"merge_form_into_context": True},
        )
    )
    if readiness_reference:
        pvt_duration = 6.0 if short else PVT_B_DURATION_SECONDS
        body.extend(
            [
                Step(
                    "PVT 说明",
                    "看到黄色计时数字后尽快按空格；等待期间不要抢按。任务持续 3 分钟。",
                    1.0 if short else 5.0,
                    "pvt_instruction",
                    735,
                ),
                Step(
                    "+",
                    "等待黄色计时数字，出现后立即按空格。",
                    pvt_duration,
                    "pvt_start",
                    740,
                    "pvt_reference",
                    response_key="space",
                    completion_event="pvt_end",
                    completion_code=744,
                    metadata={
                        "task_kind": "pvt",
                        "reference_only": True,
                        "not_used_by_rules": True,
                        "duration_s": pvt_duration,
                        "isi_min_s": PVT_B_ISI_MIN_SECONDS,
                        "isi_max_s": PVT_B_ISI_MAX_SECONDS,
                        "false_start_threshold_s": PVT_B_FALSE_START_SECONDS,
                        "lapse_threshold_s": PVT_B_LAPSE_SECONDS,
                        "response_timeout_s": PVT_B_TIMEOUT_SECONDS,
                        "stimulus_event": "pvt_stimulus",
                        "stimulus_code": 741,
                        "response_event": "pvt_response",
                        "response_code": 742,
                        "result_event": "pvt_trial_result",
                        "result_code": 743,
                    },
                ),
            ]
        )
    body.append(
        Step(
            "正在完成研究记录",
            "参考状态标签将在采集结束后由不含 EEG 的独立信息生成。",
            0.5 if short else 4.0,
            "reference_label_pending",
            730,
            metadata={
                "expected_trials": assessment_trial_count,
                "readiness_reference_enabled": readiness_reference,
                "reference_label_version": "reference-label-v1-provisional",
            },
        )
    )
    return experiment_bounds(protocol_task, protocol_title, body)
