from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..acquisition.recorder import REQUIRED_KINDS
from .builder import _STEM, trial_results
from .event_parser import ordered_events
from .xdf_reader import (
    read_xdf,
    stream_data,
    stream_kind,
    stream_nominal_srate,
    stream_timestamps,
)


def validate_dataset(root: Path) -> list[str]:
    issues: list[str] = []
    manifest_path = root / "manifests" / "dataset_manifest.json"
    records: list[str] = []
    if not manifest_path.exists():
        issues.append("缺少 manifests/dataset_manifest.json")
    else:
        try:
            manifest = _load_object(manifest_path)
            records = [str(value) for value in manifest.get("records", [])]
            issues.extend(_validate_splits(manifest))
            issues.extend(_validate_checksums(root, manifest))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"Manifest 无法读取：{exc}")
    raw_records = sorted((root / "raw").rglob("*.xdf"))
    if records:
        manifest_paths = {str(path.relative_to(root)) for path in raw_records}
        if set(records) != manifest_paths:
            issues.append("Manifest records 与 raw 目录中的 XDF 文件不一致")
    for xdf_path in raw_records:
        issues.extend(validate_run(root, xdf_path))
    issues.extend(_validate_retest_links(root, raw_records))
    return issues


def validate_run(root: Path, xdf_path: Path) -> list[str]:
    issues: list[str] = []
    relative = str(xdf_path.relative_to(root))
    match = _STEM.fullmatch(xdf_path.stem)
    if match is None:
        return [f"XDF 文件名不符合规范：{relative}"]
    identifiers = match.groupdict()
    if not xdf_path.exists() or xdf_path.stat().st_size <= 4:
        issues.append(f"原始记录缺失或为空：{relative}")
        return issues
    stem = xdf_path.stem
    events_path = xdf_path.with_name(f"{stem}_events.jsonl")
    context_path = xdf_path.with_name(f"{stem}_context.json")
    quality_path = root / "quality" / f"{stem}_quality.json"
    for label, path in (
        ("events", events_path),
        ("context", context_path),
        ("quality", quality_path),
    ):
        if not path.exists():
            issues.append(f"{relative}: 缺少 {label} 文件")
    events: list[dict[str, object]] = []
    if events_path.exists():
        try:
            events = ordered_events(events_path)
            issues.extend(_validate_events(relative, identifiers["task"], events))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            issues.append(f"{relative}: events 无法读取：{exc}")
    if context_path.exists():
        try:
            context = _load_object(context_path)
            issues.extend(_validate_context(relative, identifiers, context))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"{relative}: context 无法读取：{exc}")
    if quality_path.exists():
        try:
            quality = _load_object(quality_path)
            if quality.get("quality_schema_version") != "1.1":
                issues.append(f"{relative}: quality schema 不是 1.1")
            if not isinstance(quality.get("windows"), list):
                issues.append(f"{relative}: 缺少分窗质量记录")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"{relative}: quality 无法读取：{exc}")
    try:
        streams, _header = read_xdf(xdf_path)
        issues.extend(_validate_streams(relative, streams, events))
    except Exception as exc:
        issues.append(f"{relative}: XDF 无法由 pyxdf 读取：{exc}")
    if identifiers["task"] == "m6_readiness_reference":
        label_path = root / "derived" / "labels" / f"{stem}_reference_label.json"
        if not label_path.exists():
            issues.append(f"{relative}: 缺少版本化研究参考标签")
    return issues


def _validate_events(
    relative: str,
    task: str,
    events: list[dict[str, object]],
) -> list[str]:
    issues: list[str] = []
    names = [event.get("event") for event in events]
    for name in ("experiment_start", "experiment_end"):
        if names.count(name) != 1:
            issues.append(f"{relative}: {name} 必须恰好出现一次")
    if task.startswith("m6_readiness"):
        sart_starts = [
            event for event in events if event.get("event") == "sart_start"
        ]
        expected = 180
        if len(sart_starts) == 1:
            payload = _payload(sart_starts[0])
            expected = int(payload.get("expected_trials", 180))
        results = trial_results(
            events,
            "sart_trial_result",
            assessment_only=True,
        )
        trials = [int(row["trial"]) for row in results if row.get("trial") is not None]
        if len(results) != expected:
            issues.append(
                f"{relative}: SART 正式结果应为 {expected} 条，实际 {len(results)} 条"
            )
        if sorted(trials) != list(range(1, expected + 1)):
            issues.append(f"{relative}: SART trial 编号不连续或存在重复")
        if any(row.get("outcome") is None for row in results):
            issues.append(f"{relative}: SART result 缺少 outcome")
    if task == "m6_readiness_reference":
        pvt_results = trial_results(events, "pvt_trial_result")
        if not pvt_results:
            issues.append(f"{relative}: 正式参考协议缺少 PVT trial result")
        if names.count("pvt_start") != 1 or names.count("pvt_end") != 1:
            issues.append(f"{relative}: PVT start/end 不完整")
    return issues


def _validate_context(
    relative: str,
    identifiers: dict[str, str],
    context: dict[str, object],
) -> list[str]:
    issues: list[str] = []
    for field, expected in (
        ("participant_id", identifiers["participant"]),
        ("session_id", identifiers["session"]),
        ("run_id", identifiers["run"]),
        ("task", identifiers["task"]),
    ):
        if str(context.get(field)) != expected:
            issues.append(f"{relative}: context.{field} 与文件名不一致")
    if context.get("experiment_schema_version") != "1.0":
        issues.append(f"{relative}: experiment schema 版本不受支持")
    values = context.get("values")
    if not isinstance(values, dict):
        issues.append(f"{relative}: context.values 缺失")
    elif identifiers["task"].startswith("m6_readiness"):
        for field in (
            "study_condition",
            "sleep_duration_hours",
            "continuous_awake_hours",
            "kss_score",
            "kss_post_score",
            "measurement_phase",
            "practice_criterion_met",
            "sequence_set_id",
            "random_seed",
            "no_go_positions",
        ):
            if values.get(field) is None:
                issues.append(f"{relative}: context 缺少 {field}")
        recorder_summary = values.get("recorder_summary")
        if not isinstance(recorder_summary, dict):
            issues.append(f"{relative}: context 缺少 recorder_summary")
        else:
            for kind in REQUIRED_KINDS:
                summary = recorder_summary.get(kind, {})
                if not isinstance(summary, dict):
                    issues.append(f"{relative}: recorder_summary 缺少 {kind}")
                    continue
                if int(summary.get("sample_count", 0)) <= 0:
                    issues.append(f"{relative}: {kind} 未录得样本")
                if int(summary.get("clock_offset_count", 0)) <= 0:
                    issues.append(f"{relative}: {kind} 缺少 clock offset")
    return issues


def _validate_streams(
    relative: str,
    streams: list[dict[str, Any]],
    events: list[dict[str, object]],
) -> list[str]:
    issues: list[str] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for stream in streams:
        kind = stream_kind(stream)
        if kind is not None:
            grouped.setdefault(kind, []).append(stream)
    for kind in REQUIRED_KINDS:
        count = len(grouped.get(kind, []))
        if count != 1:
            issues.append(f"{relative}: LSL 流 {kind} 应为 1 路，实际 {count} 路")
    eeg = grouped.get("eeg", [])
    if eeg:
        timestamps, rows = stream_data(eeg[0])
        channel_count = min((len(row) for row in rows), default=0)
        if channel_count != 2:
            issues.append(f"{relative}: EEG 通道数应为 2，实际 {channel_count}")
        nominal = stream_nominal_srate(eeg[0])
        if nominal <= 0:
            issues.append(f"{relative}: EEG nominal_srate 无效")
        elif len(timestamps) >= 2 and timestamps[-1] > timestamps[0]:
            observed = (len(timestamps) - 1) / (timestamps[-1] - timestamps[0])
            if abs(observed - nominal) / nominal > 0.10:
                issues.append(
                    f"{relative}: EEG 实际采样率 {observed:.2f} Hz"
                    f" 与 nominal {nominal:.2f} Hz 偏差超过 10%"
                )
    bounds = []
    for stream in streams:
        timestamps = stream_timestamps(stream)
        if timestamps:
            bounds.append((timestamps[0], timestamps[-1]))
    if bounds and events:
        minimum = min(value[0] for value in bounds)
        maximum = max(value[1] for value in bounds)
        outside = [
            event
            for event in events
            if not minimum <= float(event["timestamp"]) <= maximum
        ]
        if outside:
            issues.append(
                f"{relative}: {len(outside)} 个 Marker 位于 XDF 时间范围外"
            )
    return issues


def _validate_retest_links(
    root: Path,
    xdf_paths: list[Path],
) -> list[str]:
    issues: list[str] = []
    available = {
        (
            match.group("participant"),
            match.group("session"),
            match.group("run"),
        )
        for path in xdf_paths
        if (match := _STEM.fullmatch(path.stem)) is not None
    }
    for xdf_path in xdf_paths:
        match = _STEM.fullmatch(xdf_path.stem)
        if match is None:
            continue
        context_path = xdf_path.with_name(f"{xdf_path.stem}_context.json")
        if not context_path.exists():
            continue
        try:
            context = _load_object(context_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        values = context.get("values", {})
        if not isinstance(values, dict) or values.get("measurement_phase") != "retest":
            continue
        parent_session = str(values.get("parent_session_id") or "")
        parent = str(values.get("parent_run_id") or "")
        key = (match.group("participant"), parent_session, parent)
        if not parent_session or not parent or key not in available:
            issues.append(
                f"{xdf_path.relative_to(root)}: 复测 parent_run_id 不存在或跨被试"
            )
    return issues


def _validate_splits(manifest: dict[str, object]) -> list[str]:
    splits = manifest.get("subject_splits", {})
    if not isinstance(splits, dict):
        return ["Manifest 缺少被试级划分"]
    values = [
        set(splits.get(name, []))
        for name in ("train_subjects", "validation_subjects", "test_subjects")
    ]
    if any(
        left.intersection(right)
        for index, left in enumerate(values)
        for right in values[index + 1 :]
    ):
        return ["被试级划分存在交叉"]
    return []


def _validate_checksums(
    root: Path,
    manifest: dict[str, object],
) -> list[str]:
    if manifest.get("dataset_schema_version") != "1.1":
        return ["Manifest dataset schema 不是 1.1"]
    metadata = manifest.get("metadata", {})
    checksums = metadata.get("record_sha256", {}) if isinstance(metadata, dict) else {}
    if not isinstance(checksums, dict):
        return ["Manifest 缺少 XDF SHA-256"]
    issues: list[str] = []
    for record in manifest.get("records", []):
        path = root / str(record)
        if not path.exists():
            continue
        digest = _sha256(path)
        if checksums.get(record) != digest:
            issues.append(f"XDF SHA-256 不匹配：{record}")
    return issues


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} 不是 JSON 对象")
    return payload


def _payload(event: dict[str, object]) -> dict[str, object]:
    payload = event.get("payload", {})
    return dict(payload) if isinstance(payload, dict) else {}
