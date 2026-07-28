from __future__ import annotations

from .definitions import Step

def build_deviceqc_plan(short: bool = False, **_: object) -> list[Step]:
    rest_seconds = 10.0 if short else 60.0
    repetitions = 1 if short else 5
    prepare_seconds = 1.0 if short else 2.0
    cue_seconds = 2.0
    recovery_seconds = 2.0 if short else 3.0

    plan = [
        Step(
            "实验即将开始",
            "保持坐姿，双脚平放，尽量放松",
            2.0,
            "experiment_start",
            10,
            start_sound="start",
        ),
        Step("+", "睁眼静息：注视屏幕中央，保持头部不动", rest_seconds, "rest_open_start", 100),
        Step("睁眼静息结束", "继续保持不动", 0.5, "rest_open_end", 101),
        Step(
            "准备闭眼",
            "听到提示后轻轻闭眼，保持清醒和头部不动",
            3.0 if not short else 1.0,
            "rest_closed_prepare",
            112,
            start_sound="close_eyes",
        ),
        Step(
            "闭眼静息",
            "轻轻闭眼，保持清醒和头部不动",
            rest_seconds,
            "rest_closed_start",
            110,
            warning_sound="ending_soon",
            warning_at=5.0,
            end_sound="open_eyes",
        ),
        Step("闭眼静息结束", "请缓慢睁眼，等待下一阶段", 3.0 if not short else 1.0, "rest_closed_end", 111),
    ]

    actions = [
        ("blink", 120, "自然眨眼 1 次", "不要用力挤眼"),
        ("jaw_clench", 130, "轻咬后放松", "咬紧约 1 秒，然后完全放松"),
        ("head_left", 201, "缓慢左转头并回中", "只转到舒适位置，不要转动身体"),
        ("head_right", 202, "缓慢右转头并回中", "只转到舒适位置，不要转动身体"),
        ("head_nod", 203, "缓慢点头并回中", "完成一次点头后回到正中"),
        ("head_cancel", 204, "快速左右摇头并回中", "幅度适中，完成后回到正中"),
    ]
    for block_name, code, cue_text, cue_detail in actions:
        plan.append(
            Step(
                f"准备：{cue_text}",
                f"本组共 {repetitions} 次",
                1.0,
                f"block_start_{block_name}",
                20,
                block_name,
            )
        )
        for trial in range(1, repetitions + 1):
            plan.extend(
                [
                    Step(
                        "准备",
                        f"{cue_text}，第 {trial}/{repetitions} 次",
                        prepare_seconds,
                        block=block_name,
                        trial=trial,
                    ),
                    Step(cue_text, cue_detail, cue_seconds, block_name, code, block_name, trial),
                    Step(
                        "恢复正中并静止",
                        "放松，等待下一次提示",
                        recovery_seconds,
                        block=block_name,
                        trial=trial,
                    ),
                ]
            )
        plan.append(
            Step(
                f"{cue_text}组结束",
                "保持正中姿势",
                0.5,
                f"block_end_{block_name}",
                21,
                block_name,
            )
        )

    plan.extend(
        [
            Step("+", "结束睁眼静息：注视屏幕中央，保持头部不动", rest_seconds, "rest_open_final_start", 100),
            Step("结束静息完成", "继续保持不动", 0.5, "rest_open_final_end", 101),
            Step("实验完成", "请等待数据文件保存完成", 1.0, "experiment_end", 11, end_sound="complete"),
        ]
    )
    return plan
