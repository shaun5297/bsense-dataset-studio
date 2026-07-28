from __future__ import annotations

from collections.abc import Sequence
from typing import Mapping

from ..schemas.quality import ModalityQuality, QualityReport, WindowQuality


def build_report(
    eeg: Mapping[str, object],
    fnirs: Mapping[str, object],
    motion: Mapping[str, object],
    lsl: Mapping[str, object],
    *,
    windows: Sequence[WindowQuality] = (),
) -> QualityReport:
    eeg_window_ratio = (
        _window_ratio(windows, "eeg")
        if windows
        else float(eeg.get("valid_window_ratio", 0))
    )
    fnirs_window_ratio = (
        _window_ratio(windows, "fnirs")
        if windows
        else float(fnirs.get("valid_window_ratio", 0))
    )
    motion_artifact_ratio = (
        _motion_ratio(windows)
        if windows
        else float(motion.get("artifact_window_ratio", 1))
    )
    eeg_valid_channel_ratio = float(eeg.get("valid_channel_ratio", 0))
    fnirs_valid_channel_ratio = float(fnirs.get("valid_channel_ratio", 0))
    fnirs_saturation_ratio = float(fnirs.get("saturation_ratio", 0))
    stream_complete = bool(lsl.get("stream_complete"))
    usable_eeg = (
        stream_complete
        and eeg_valid_channel_ratio >= 0.5
        and eeg_window_ratio >= 0.8
        and motion_artifact_ratio <= 0.2
    )
    usable_fnirs = (
        stream_complete
        and fnirs_valid_channel_ratio >= 0.5
        and fnirs_window_ratio >= 0.8
        and fnirs_saturation_ratio <= 0.05
        and motion_artifact_ratio <= 0.2
    )
    reasons: list[str] = []
    if not stream_complete:
        reasons.append("required_stream_incomplete")
    if eeg_valid_channel_ratio < 0.5:
        reasons.append("insufficient_eeg_channels")
    if fnirs_valid_channel_ratio < 0.5:
        reasons.append("insufficient_fnirs_channels")
    if eeg_window_ratio < 0.8:
        reasons.append("low_eeg_valid_window_ratio")
    if fnirs_window_ratio < 0.8:
        reasons.append("low_fnirs_valid_window_ratio")
    if fnirs_saturation_ratio > 0.05:
        reasons.append("high_fnirs_saturation_ratio")
    if motion_artifact_ratio > 0.2:
        reasons.append("high_motion_artifact_ratio")
    if usable_eeg and usable_fnirs:
        status, grade = "pass", "A"
    elif (usable_eeg or usable_fnirs) and stream_complete:
        status, grade = "warning", "B"
    else:
        status, grade = "fail", "reject"
    return QualityReport(
        overall_status=status,
        eeg=ModalityQuality(
            valid_channel_ratio=eeg_valid_channel_ratio,
            flat_channel_count=int(eeg.get("flat_channel_count", 0)),
            clipped_channel_count=int(eeg.get("clipped_channel_count", 0)),
            valid_window_ratio=eeg_window_ratio,
        ),
        fnirs=ModalityQuality(
            valid_channel_ratio=fnirs_valid_channel_ratio,
            flat_channel_count=int(fnirs.get("flat_channel_count", 0)),
            valid_window_ratio=fnirs_window_ratio,
            extra={
                "saturation_ratio": fnirs_saturation_ratio,
                "saturation_detection": fnirs.get("saturation_detection"),
            },
        ),
        motion=ModalityQuality(
            valid_channel_ratio=float(motion.get("valid_channel_ratio", 0)),
            valid_window_ratio=1.0 - motion_artifact_ratio,
            extra={"artifact_window_ratio": motion_artifact_ratio},
        ),
        lsl=dict(lsl),
        quality_grade=grade,
        usable_for_eeg_model=usable_eeg,
        usable_for_fnirs_model=usable_fnirs,
        exclusion_reasons=tuple(reasons),
        windows=tuple(windows),
    )


def _window_ratio(windows: Sequence[WindowQuality], modality: str) -> float:
    if not windows:
        return 0.0
    attribute = f"{modality}_valid"
    return round(sum(bool(getattr(window, attribute)) for window in windows) / len(windows), 6)


def _motion_ratio(windows: Sequence[WindowQuality]) -> float:
    if not windows:
        return 1.0
    return round(sum(window.motion_artifact for window in windows) / len(windows), 6)
