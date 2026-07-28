from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..acquisition.recorder import REQUIRED_KINDS
from ..dataset.xdf_reader import read_xdf, stream_data, stream_kind
from .eeg import evaluate as evaluate_eeg
from .fnirs import evaluate as evaluate_fnirs
from .motion import evaluate as evaluate_motion
from .report import build_report
from .windowed import evaluate_windows


def build_quality_from_xdf(xdf_path: Path) -> dict[str, Any]:
    streams, _header = read_xdf(xdf_path)
    by_kind: dict[str, dict[str, Any]] = {}
    for stream in streams:
        kind = stream_kind(stream)
        if kind is not None and kind not in by_kind:
            by_kind[kind] = stream
    missing = sorted(set(REQUIRED_KINDS) - by_kind.keys())
    eeg_timestamps, eeg_samples = stream_data(by_kind.get("eeg"))
    fnirs_timestamps, fnirs_samples = stream_data(by_kind.get("fnirs"))
    motion_timestamps, motion_samples = stream_data(by_kind.get("motion"))
    windows = evaluate_windows(
        eeg_timestamps,
        eeg_samples,
        fnirs_timestamps,
        fnirs_samples,
        motion_timestamps,
        motion_samples,
    )
    report = build_report(
        evaluate_eeg(eeg_samples),
        evaluate_fnirs(fnirs_samples),
        evaluate_motion(motion_samples),
        {
            "stream_complete": not missing,
            "required_stream_kinds": list(REQUIRED_KINDS),
            "found_stream_kinds": sorted(by_kind),
            "missing_stream_kinds": missing,
        },
        windows=windows,
    )
    return report.to_dict()


def save_quality_from_xdf(xdf_path: Path, output: Path) -> Path:
    payload = build_quality_from_xdf(xdf_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output
