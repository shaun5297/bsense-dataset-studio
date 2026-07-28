from __future__ import annotations

import re
from pathlib import Path

SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_identifier(value: str, field_name: str = "identifier") -> str:
    normalized = value.strip()
    if not normalized or not SAFE_IDENTIFIER.fullmatch(normalized):
        raise ValueError(f"{field_name}只能包含字母、数字、下划线和连字符")
    return normalized


def run_stem(participant_id: str, session_id: str, task: str, run_id: str) -> str:
    values = [
        validate_identifier(participant_id, "participant"),
        validate_identifier(session_id, "session"),
        validate_identifier(task, "task"),
        validate_identifier(run_id, "run"),
    ]
    return f"sub-{values[0]}_ses-{values[1]}_task-{values[2]}_run-{values[3]}"


def ensure_dataset_layout(root: Path) -> dict[str, Path]:
    directories = {
        "restricted": root / "restricted" / "participants",
        "raw": root / "raw",
        "quality": root / "quality",
        "annotations": root / "annotations",
        "derived": root / "derived",
        "manifests": root / "manifests",
    }
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return directories
