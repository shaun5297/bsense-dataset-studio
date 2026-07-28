"""Data-quality schema; quality is never a participant-state label."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModalityQuality:
    valid_channel_ratio: float
    flat_channel_count: int = 0
    clipped_channel_count: int = 0
    valid_window_ratio: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityReport:
    overall_status: str
    eeg: ModalityQuality
    fnirs: ModalityQuality
    motion: ModalityQuality
    lsl: dict[str, Any]
    quality_schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
