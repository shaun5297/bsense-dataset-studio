from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ConsentRecord:
    participant_id: str
    consented: bool
    protocol_version: str
    recorded_at: str

    @classmethod
    def create(cls, participant_id: str, consented: bool, protocol_version: str) -> "ConsentRecord":
        return cls(participant_id, consented, protocol_version, datetime.now(timezone.utc).isoformat())
