from __future__ import annotations

import math
from collections.abc import Sequence


def evaluate(samples: Sequence[Sequence[float]], *, rail_abs: float = 375_000.0, flat_span: float = 1e-9) -> dict[str, object]:
    if not samples:
        return {"valid_channel_ratio": 0.0, "flat_channel_count": 0, "clipped_channel_count": 0, "valid_window_ratio": 0.0}
    channel_count = min(len(row) for row in samples)
    channels = [[float(row[index]) for row in samples if math.isfinite(float(row[index]))] for index in range(channel_count)]
    flat = sum(bool(values) and max(values) - min(values) <= flat_span for values in channels)
    clipped = sum(any(abs(value) >= rail_abs for value in values) for values in channels)
    valid = sum(bool(values) and max(values) - min(values) > flat_span and not any(abs(value) >= rail_abs for value in values) for values in channels)
    return {
        "valid_channel_ratio": round(valid / channel_count, 6) if channel_count else 0.0,
        "flat_channel_count": flat,
        "clipped_channel_count": clipped,
        "valid_window_ratio": 1.0 if valid else 0.0,
    }
