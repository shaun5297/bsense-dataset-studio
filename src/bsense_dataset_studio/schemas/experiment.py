from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ExperimentContext:
    participant_id: str
    session_id: str
    run_id: str
    task: str
    protocol_version: str
    software_version: str
    values: dict[str, Any]
    experiment_schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
