from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..behavior.pvt import summarize_trials as summarize_pvt
from ..behavior.sart import summarize_trials as summarize_sart
from ..labels.reference import generate_reference_label
from .event_parser import ordered_events
from .feature_export import export_rows
from .manifest import build_manifest, save_manifest

_STEM = re.compile(
    r"^sub-(?P<participant>[^_]+)_ses-(?P<session>[^_]+)_task-(?P<task>.+)_run-(?P<run>[^_]+)$"
)

_CONTEXT_EXPORT_FIELDS = (
    "study_condition",
    "condition_source",
    "sleep_duration_hours",
    "continuous_awake_hours",
    "shift_type",
    "caffeine_mg_last_8h",
    "last_caffeine_time",
    "kss_score",
    "kss_post_score",
    "measurement_phase",
    "parent_session_id",
    "parent_run_id",
    "rest_duration_minutes",
    "sequence_set_id",
    "random_seed",
    "no_go_positions",
    "practice_attempts",
    "practice_criterion_met",
)


def _load_optional(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _event_payload(event: dict[str, object]) -> dict[str, object]:
    payload = event.get("payload", {})
    return dict(payload) if isinstance(payload, dict) else {}


def _context_values(context: dict[str, object]) -> dict[str, object]:
    nested = context.get("values")
    values = dict(nested) if isinstance(nested, dict) else {}
    return {**context, **values}


def trial_results(
    events: list[dict[str, object]],
    event_name: str,
    *,
    assessment_only: bool = False,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for event in events:
        if event.get("event") != event_name:
            continue
        payload = _event_payload(event)
        if assessment_only and (
            payload.get("trial_kind") != "assessment"
            or payload.get("exclude_from_primary_analysis") is True
        ):
            continue
        results.append(payload)
    return results


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
        sart_trials = trial_results(
            events,
            "sart_trial_result",
            assessment_only=True,
        )
        pvt_trials = trial_results(events, "pvt_trial_result")
        context_document = _load_optional(context_path)
        context = _context_values(context_document)
        quality = _load_optional(quality_path)
        identifiers = match.groupdict()
        row: dict[str, object] = {
            **identifiers,
            "xdf_path": str(xdf_path.relative_to(dataset_root)),
            "event_count": len(events),
            "annotation_count": (
                sum(
                    bool(line.strip())
                    for line in annotation_path.read_text(encoding="utf-8").splitlines()
                )
                if annotation_path.exists()
                else 0
            ),
            "quality_status": quality.get("overall_status"),
            "quality_grade": quality.get("quality_grade"),
            "eeg_valid_ratio": _nested_quality(quality, "eeg", "valid_window_ratio"),
            "fnirs_valid_ratio": _nested_quality(quality, "fnirs", "valid_window_ratio"),
            "motion_artifact_ratio": _nested_quality(
                quality,
                "motion",
                "extra",
                "artifact_window_ratio",
            ),
            "protocol_version": context_document.get("protocol_version"),
            "software_version": context_document.get("software_version"),
            "experiment_schema_version": context_document.get(
                "experiment_schema_version"
            ),
        }
        row.update({field: context.get(field) for field in _CONTEXT_EXPORT_FIELDS})
        sart_summary = summarize_sart(sart_trials) if sart_trials else {}
        if sart_summary:
            row.update(sart_summary)
        pvt_summary = summarize_pvt(pvt_trials) if pvt_trials else {}
        wait_false_starts = sum(
            event.get("event") == "pvt_false_start" for event in events
        )
        if pvt_summary or wait_false_starts:
            result_false_starts = sum(
                bool(trial.get("false_start")) for trial in pvt_trials
            )
            false_start_count = result_false_starts + wait_false_starts
            pvt_summary["false_start_count"] = false_start_count
            denominator = len(pvt_trials) + wait_false_starts
            pvt_summary["false_start_rate"] = (
                round(false_start_count / denominator, 6)
                if denominator
                else None
            )
        row.update({f"pvt_{key}": value for key, value in pvt_summary.items()})
        if identifiers["task"] in {
            "m6_readiness_reference",
            "m6_readiness_study",
        }:
            label = generate_reference_label(context, sart_summary, pvt_summary)
            row.update(label.to_dict())
        rows.append(row)
    return rows


def build_dataset(dataset_root: Path, output: Path) -> tuple[Path, Path]:
    rows = build_records(dataset_root)
    export_rows(rows, output)
    _save_reference_labels(dataset_root, rows)
    manifest_path = save_manifest(dataset_root, build_manifest(dataset_root))
    return output, manifest_path


def _save_reference_labels(
    dataset_root: Path,
    rows: list[dict[str, object]],
) -> None:
    output_root = dataset_root / "derived" / "labels"
    for row in rows:
        if "reference_state_label" not in row:
            continue
        stem = (
            f"sub-{row['participant']}_ses-{row['session']}"
            f"_task-{row['task']}_run-{row['run']}"
        )
        output_root.mkdir(parents=True, exist_ok=True)
        payload = {
            key: row[key]
            for key in (
                "participant",
                "session",
                "run",
                "task",
                "reference_state_label",
                "reference_state_score",
                "reference_label_version",
                "reference_label_sources",
                "reference_label_confidence",
                "rationale",
                "provisional",
            )
        }
        (output_root / f"{stem}_reference_label.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _nested_quality(
    payload: dict[str, object],
    *keys: str,
) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
