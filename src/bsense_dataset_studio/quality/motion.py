from __future__ import annotations

from collections.abc import Sequence


def evaluate(samples: Sequence[Sequence[float]], *, gyro_span_threshold: float = 5.0) -> dict[str, object]:
    if not samples:
        return {"valid_channel_ratio": 0.0, "artifact_window_ratio": 1.0}
    channel_count = min(len(row) for row in samples)
    spans = [max(float(row[index]) for row in samples) - min(float(row[index]) for row in samples) for index in range(channel_count)]
    gyro_spans = spans[3:6] if len(spans) >= 6 else spans
    artifact = any(span > gyro_span_threshold for span in gyro_spans)
    return {"valid_channel_ratio": 1.0, "artifact_window_ratio": 1.0 if artifact else 0.0, "channel_spans": spans}
