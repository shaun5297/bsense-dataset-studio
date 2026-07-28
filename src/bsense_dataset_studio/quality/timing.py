from __future__ import annotations

from collections.abc import Sequence


def evaluate(timestamps: Sequence[float], *, expected_complete: bool = True) -> dict[str, object]:
    inversions = sum(current <= previous for previous, current in zip(timestamps, timestamps[1:]))
    return {
        "stream_complete": bool(expected_complete and timestamps),
        "timestamp_inversion_count": inversions,
        "clock_offset_available": False,
    }
