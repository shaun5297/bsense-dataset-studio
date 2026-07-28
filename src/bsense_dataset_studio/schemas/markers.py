"""Versioned marker records shared by acquisition and offline tooling."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Marker:
    event: str
    timestamp: float
    participant_id: str
    session_id: str
    run_id: str
    task: str
    event_code: int | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    marker_schema_version: str = "1.1"

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["payload"] = dict(self.payload)
        return row
