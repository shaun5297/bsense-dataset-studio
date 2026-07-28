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
class WindowQuality:
    window_start: float
    window_end: float
    eeg_valid: bool
    fnirs_valid: bool
    motion_artifact: bool
    affected_channels: tuple[int, ...] = ()
    exclusion_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualityReport:
    overall_status: str
    eeg: ModalityQuality
    fnirs: ModalityQuality
    motion: ModalityQuality
    lsl: dict[str, Any]
    quality_grade: str = "reject"
    usable_for_eeg_model: bool = False
    usable_for_fnirs_model: bool = False
    exclusion_reasons: tuple[str, ...] = ()
    windows: tuple[WindowQuality, ...] = ()
    quality_schema_version: str = "1.1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
