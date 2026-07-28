from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence


def evaluate(
    samples: Sequence[Sequence[float]],
    *,
    flat_span: float = 1e-9,
    saturation_abs: float | None = None,
) -> dict[str, object]:
    if not samples:
        return {
            "valid_channel_ratio": 0.0,
            "flat_channel_count": 0,
            "saturation_ratio": 0.0,
            "saturation_detection": "not_available",
        }
    channel_count = min(len(row) for row in samples)
    channels = [
        [
            float(row[index])
            for row in samples
            if math.isfinite(float(row[index]))
        ]
        for index in range(channel_count)
    ]
    flat = sum(
        bool(values) and max(values) - min(values) <= flat_span
        for values in channels
    )
    if saturation_abs is not None:
        saturated_points = sum(
            abs(value) >= saturation_abs
            for values in channels
            for value in values
        )
        saturation_detection = "configured_absolute_threshold"
    else:
        saturated_points = sum(_repeated_extreme_count(values) for values in channels)
        saturation_detection = "repeated_extrema_heuristic"
    points = sum(len(values) for values in channels)
    valid = sum(
        bool(values) and max(values) - min(values) > flat_span
        for values in channels
    )
    return {
        "valid_channel_ratio": (
            round(valid / channel_count, 6) if channel_count else 0.0
        ),
        "flat_channel_count": flat,
        "saturation_ratio": (
            round(saturated_points / points, 6) if points else 0.0
        ),
        "saturation_detection": saturation_detection,
    }


def _repeated_extreme_count(values: list[float]) -> int:
    if len(values) < 10 or max(values) == min(values):
        return 0
    counts = Counter(values)
    minimum_repeats = max(3, round(len(values) * 0.02))
    return sum(
        counts[value]
        for value in {min(values), max(values)}
        if counts[value] >= minimum_repeats
    )
