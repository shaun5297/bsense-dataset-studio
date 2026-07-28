from __future__ import annotations

from collections.abc import Sequence


def slice_window(
    timestamps: Sequence[float],
    samples: Sequence[Sequence[float]],
    *,
    start: float,
    end: float,
) -> tuple[list[float], list[Sequence[float]]]:
    if end <= start:
        raise ValueError("window end must be after start")
    indexes = [index for index, timestamp in enumerate(timestamps) if start <= timestamp < end]
    return [float(timestamps[index]) for index in indexes], [samples[index] for index in indexes]
