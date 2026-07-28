from __future__ import annotations

from typing import Mapping

from ..schemas.quality import ModalityQuality, QualityReport


def build_report(
    eeg: Mapping[str, object],
    fnirs: Mapping[str, object],
    motion: Mapping[str, object],
    lsl: Mapping[str, object],
) -> QualityReport:
    passed = (
        float(eeg.get("valid_channel_ratio", 0)) >= 0.5
        and float(fnirs.get("valid_channel_ratio", 0)) >= 0.5
        and float(motion.get("artifact_window_ratio", 1)) <= 0.2
        and bool(lsl.get("stream_complete"))
    )
    return QualityReport(
        overall_status="pass" if passed else "fail",
        eeg=ModalityQuality(
            valid_channel_ratio=float(eeg.get("valid_channel_ratio", 0)),
            flat_channel_count=int(eeg.get("flat_channel_count", 0)),
            clipped_channel_count=int(eeg.get("clipped_channel_count", 0)),
            valid_window_ratio=float(eeg.get("valid_window_ratio", 0)),
        ),
        fnirs=ModalityQuality(
            valid_channel_ratio=float(fnirs.get("valid_channel_ratio", 0)),
            flat_channel_count=int(fnirs.get("flat_channel_count", 0)),
            valid_window_ratio=float(fnirs.get("valid_window_ratio", 0)),
            extra={"saturation_ratio": float(fnirs.get("saturation_ratio", 0))},
        ),
        motion=ModalityQuality(
            valid_channel_ratio=float(motion.get("valid_channel_ratio", 0)),
            valid_window_ratio=1.0 - float(motion.get("artifact_window_ratio", 1)),
            extra={"artifact_window_ratio": float(motion.get("artifact_window_ratio", 1))},
        ),
        lsl=dict(lsl),
    )
