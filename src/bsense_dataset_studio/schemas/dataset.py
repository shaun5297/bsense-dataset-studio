from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    created_at: str
    software_version: str
    records: tuple[str, ...]
    subject_splits: dict[str, tuple[str, ...]]
    dataset_schema_version: str = "1.1"
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
