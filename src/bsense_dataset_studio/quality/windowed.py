from __future__ import annotations

from collections.abc import Sequence

from ..dataset.windowing import slice_window
from ..schemas.quality import WindowQuality
from .eeg import evaluate as evaluate_eeg
from .fnirs import evaluate as evaluate_fnirs
from .motion import evaluate as evaluate_motion


def evaluate_windows(
    eeg_timestamps: Sequence[float],
    eeg_samples: Sequence[Sequence[float]],
    fnirs_timestamps: Sequence[float],
    fnirs_samples: Sequence[Sequence[float]],
    motion_timestamps: Sequence[float],
    motion_samples: Sequence[Sequence[float]],
    *,
    window_seconds: float = 4.0,
    step_seconds: float = 2.0,
) -> tuple[WindowQuality, ...]:
    if window_seconds <= 0 or step_seconds <= 0:
        raise ValueError("质量窗口和步长必须为正数")
    starts = [
        values[0]
        for values in (eeg_timestamps, fnirs_timestamps, motion_timestamps)
        if values
    ]
    ends = [
        values[-1]
        for values in (eeg_timestamps, fnirs_timestamps, motion_timestamps)
        if values
    ]
    if len(starts) != 3 or len(ends) != 3:
        return ()
    start = max(starts)
    end = min(ends)
    windows: list[WindowQuality] = []
    cursor = start
    while cursor + window_seconds <= end:
        window_end = cursor + window_seconds
        _, eeg_rows = slice_window(
            eeg_timestamps,
            eeg_samples,
            start=cursor,
            end=window_end,
        )
        _, fnirs_rows = slice_window(
            fnirs_timestamps,
            fnirs_samples,
            start=cursor,
            end=window_end,
        )
        _, motion_rows = slice_window(
            motion_timestamps,
            motion_samples,
            start=cursor,
            end=window_end,
        )
        eeg = evaluate_eeg(eeg_rows)
        fnirs = evaluate_fnirs(fnirs_rows)
        motion = evaluate_motion(motion_rows)
        eeg_valid = (
            float(eeg.get("valid_channel_ratio", 0)) >= 0.5 and bool(eeg_rows)
        )
        fnirs_valid = (
            float(fnirs.get("valid_channel_ratio", 0)) >= 0.5
            and float(fnirs.get("saturation_ratio", 0)) <= 0.05
            and bool(fnirs_rows)
        )
        motion_artifact = float(motion.get("artifact_window_ratio", 1)) > 0
        reasons: list[str] = []
        if not eeg_valid:
            reasons.append("eeg_invalid")
        if not fnirs_valid:
            reasons.append("fnirs_invalid")
        if motion_artifact:
            reasons.append("motion_artifact")
        spans = list(motion.get("channel_spans", []))
        gyro_indexes = range(3, min(6, len(spans))) if len(spans) >= 6 else range(len(spans))
        affected = tuple(
            index
            for index in gyro_indexes
            if float(spans[index]) > 5.0
        )
        windows.append(
            WindowQuality(
                window_start=round(cursor, 6),
                window_end=round(window_end, 6),
                eeg_valid=eeg_valid,
                fnirs_valid=fnirs_valid,
                motion_artifact=motion_artifact,
                affected_channels=affected,
                exclusion_reasons=tuple(reasons),
            )
        )
        cursor += step_seconds
    return tuple(windows)
