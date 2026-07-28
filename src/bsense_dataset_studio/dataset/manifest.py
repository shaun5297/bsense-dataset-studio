from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .. import __version__
from ..schemas.dataset import DatasetManifest


def subject_split(
    participant_ids: Iterable[str],
    *,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    seed: str = "bsense-v1",
) -> dict[str, tuple[str, ...]]:
    if validation_fraction < 0 or test_fraction < 0 or validation_fraction + test_fraction >= 1:
        raise ValueError("被试划分比例无效")
    subjects = sorted(set(participant_ids), key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).digest())
    test_count = round(len(subjects) * test_fraction)
    validation_count = round(len(subjects) * validation_fraction)
    return {
        "test_subjects": tuple(sorted(subjects[:test_count])),
        "validation_subjects": tuple(sorted(subjects[test_count : test_count + validation_count])),
        "train_subjects": tuple(sorted(subjects[test_count + validation_count :])),
    }


def build_manifest(dataset_root: Path) -> DatasetManifest:
    raw_root = dataset_root / "raw"
    records = (
        tuple(
            sorted(
                str(path.relative_to(dataset_root))
                for path in raw_root.rglob("*.xdf")
            )
        )
        if raw_root.exists()
        else ()
    )
    subjects = [part.name.removeprefix("sub-") for part in raw_root.glob("sub-*") if part.is_dir()]
    created_at = datetime.now(timezone.utc).isoformat()
    checksums = {
        record: _sha256(dataset_root / record)
        for record in records
    }
    identity = json.dumps(checksums, ensure_ascii=False, sort_keys=True)
    dataset_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return DatasetManifest(
        dataset_id,
        created_at,
        __version__,
        records,
        subject_split(subjects),
        metadata={"record_sha256": checksums},
    )


def save_manifest(dataset_root: Path, manifest: DatasetManifest) -> Path:
    path = dataset_root / "manifests" / "dataset_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
