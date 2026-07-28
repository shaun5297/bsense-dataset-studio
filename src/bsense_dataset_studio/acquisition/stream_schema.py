from __future__ import annotations

import re
from dataclasses import dataclass

SUPPORTED_STREAM_KINDS = ("eeg", "fnirs", "motion", "metric", "heart_rate", "biomultilite_marker", "general_metric", "experiment_marker")


def canonical_kind(stream_type: str, stream_name: str = "") -> str | None:
    values = {re.sub(r"[^a-z0-9]", "", value.lower()) for value in (stream_type, stream_name)}
    aliases = (
        ("experiment_marker", {"bsenseexperimentmarkers", "experimentmarkers"}),
        ("biomultilite_marker", {"biomultilitemarker", "biomultilitemarkers"}),
        ("general_metric", {"generalmetric", "generalmetrics"}),
        ("heart_rate", {"heartrate", "hr"}),
        ("fnirs", {"fnirs", "nirs", "nir", "ir"}),
        ("motion", {"motion", "imu"}),
        ("metric", {"metric", "metrics"}),
        ("eeg", {"eeg"}),
    )
    for kind, candidates in aliases:
        if values.intersection(candidates):
            return kind
    if "markers" in values or "marker" in values:
        return "biomultilite_marker"
    return None


@dataclass(frozen=True)
class StreamDescriptor:
    kind: str
    name: str
    stream_type: str
    channel_count: int
    nominal_srate: float
    source_id: str
