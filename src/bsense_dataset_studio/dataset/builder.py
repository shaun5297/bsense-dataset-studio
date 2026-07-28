from __future__ import annotations

import json
import re
from pathlib import Path

from ..behavior.sart import summarize_trials
from .event_parser import ordered_events
from .feature_export import export_rows
from .manifest import build_manifest, save_manifest

_STEM = re.compile(
    r"^sub-(?P<participant>[^_]+)_ses-(?P<session>[^_]+)_task-(?P<task>.+)_run-(?P<run>[^_]+)$"
)


def _load_optional(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _event_payload(event: dict[str, object]) -> dict[str, object]:
    payload = event.get("payload", {})
    return dict(payload) if isinstance(payload, dict) else {}


def build_records(dataset_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for xdf_path in sorted((dataset_root / "raw").rglob("*.xdf")):
        match = _STEM.fullmatch(xdf_path.stem)
        if not match:
            continue
        stem = xdf_path.stem
        events_path = xdf_path.with_name(stem + "_events.jsonl")
        context_path = xdf_path.with_name(stem + "_context.json")
        quality_path = dataset_root / "quality" / f"{stem}_quality.json"
        annotation_path = dataset_root / "annotations" / f"{stem}_annotations.jsonl"
        events = ordered_events(events_path) if events_path.exists() else []
        sart_trials = [
            _event_payload(event)
            for event in events
            if event.get("event") in {"sart_trial", "sart_response"} and _event_payload(event).get("outcome")
        ]
        context = _load_optional(context_path)
        quality = _load_optional(quality_path)
        row: dict[str, object] = {
            **match.groupdict(),
            "xdf_path": str(xdf_path.relative_to(dataset_root)),
            "event_count": len(events),
            "annotation_count": (
                sum(bool(line.strip()) for line in annotation_path.read_text(encoding="utf-8").splitlines())
                if annotation_path.exists()
                else 0
            ),
            "quality_status": quality.get("overall_status"),
            "protocol_version": context.get("protocol_version"),
            "software_version": context.get("software_version"),
            "experiment_schema_version": context.get("experiment_schema_version"),
        }
        if sart_trials:
            row.update(summarize_trials(sart_trials))
        rows.append(row)
    return rows


def build_dataset(dataset_root: Path, output: Path) -> tuple[Path, Path]:
    rows = build_records(dataset_root)
    export_rows(rows, output)
    manifest_path = save_manifest(dataset_root, build_manifest(dataset_root))
    return output, manifest_path
