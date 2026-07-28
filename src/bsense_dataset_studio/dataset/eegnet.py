from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..quality.eeg import evaluate as evaluate_eeg
from ..quality.motion import evaluate as evaluate_motion
from .builder import build_records
from .event_parser import ordered_events, read_jsonl
from .manifest import subject_split
from .xdf_reader import (
    read_xdf,
    stream_data,
    stream_kind,
    stream_nominal_srate,
)


@dataclass(frozen=True)
class EEGWindowMetadata:
    participant: str
    session: str
    run: str
    task: str
    xdf_path: str
    window_start: float
    window_end: float
    segment: str
    target: int
    target_name: str
    split: str
    quality_pass: bool
    channel_names: tuple[str, ...]
    target_srate: float
    preprocessing: str
    reference_label_version: str


def build_eegnet_dataset(
    dataset_root: Path,
    output: Path,
    *,
    window_seconds: float = 4.0,
    step_seconds: float = 2.0,
    target_srate: float = 250.0,
    expected_channels: int = 2,
) -> tuple[Path, Path]:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("构建 EEGNet 数据需要安装 numpy") from exc
    if window_seconds <= 0 or step_seconds <= 0 or target_srate <= 0:
        raise ValueError("窗口、步长和目标采样率必须为正数")
    target_samples = round(window_seconds * target_srate)
    record_rows = build_records(dataset_root)
    records = {
        (
            str(row["participant"]),
            str(row["session"]),
            str(row["run"]),
            str(row["task"]),
        ): row
        for row in record_rows
    }
    splits = subject_split(str(row["participant"]) for row in record_rows)
    split_by_participant = {
        participant: split_name.removesuffix("_subjects")
        for split_name, participants in splits.items()
        for participant in participants
    }
    arrays: list[Any] = []
    metadata: list[EEGWindowMetadata] = []
    channel_reference: tuple[str, ...] | None = None
    for xdf_path in sorted((dataset_root / "raw").rglob("*.xdf")):
        identifiers = _parse_xdf_identifiers(xdf_path)
        if identifiers is None:
            continue
        record = records.get(identifiers)
        if record is None or record.get("reference_state_label") not in {
            "alert",
            "impaired",
        }:
            continue
        quality_path = (
            dataset_root / "quality" / f"{xdf_path.stem}_quality.json"
        )
        quality = _load_json(quality_path)
        if quality.get("usable_for_eeg_model") is not True:
            continue
        events_path = xdf_path.with_name(f"{xdf_path.stem}_events.jsonl")
        if not events_path.exists():
            continue
        events = ordered_events(events_path)
        segments = _training_segments(events)
        if not segments:
            continue
        annotations_path = (
            dataset_root
            / "annotations"
            / f"{xdf_path.stem}_annotations.jsonl"
        )
        exclusions = _annotation_exclusions(annotations_path)
        streams, _header = read_xdf(xdf_path)
        eeg_stream = next(
            (stream for stream in streams if stream_kind(stream) == "eeg"),
            None,
        )
        motion_stream = next(
            (stream for stream in streams if stream_kind(stream) == "motion"),
            None,
        )
        if eeg_stream is None or motion_stream is None:
            continue
        eeg_timestamps, eeg_rows = stream_data(eeg_stream)
        motion_timestamps, motion_rows = stream_data(motion_stream)
        if not eeg_rows or min(len(row) for row in eeg_rows) != expected_channels:
            raise ValueError(
                f"{xdf_path}: EEG 通道数不是预期的 {expected_channels}"
            )
        channel_names = _channel_names(eeg_stream, expected_channels)
        if channel_reference is None:
            channel_reference = channel_names
        elif channel_names != channel_reference:
            raise ValueError(
                f"{xdf_path}: EEG 通道顺序 {channel_names} 与数据集基准"
                f" {channel_reference} 不一致"
            )
        nominal_srate = stream_nominal_srate(eeg_stream)
        for segment, segment_start, segment_end in segments:
            cursor = segment_start
            while cursor + window_seconds <= segment_end:
                end = cursor + window_seconds
                if _overlaps_exclusion(cursor, end, exclusions):
                    cursor += step_seconds
                    continue
                eeg_window = _slice_rows(
                    eeg_timestamps,
                    eeg_rows,
                    cursor,
                    end,
                )
                motion_window = _slice_rows(
                    motion_timestamps,
                    motion_rows,
                    cursor,
                    end,
                )
                eeg_quality = evaluate_eeg(eeg_window[1])
                motion_quality = evaluate_motion(motion_window[1])
                quality_pass = (
                    float(eeg_quality.get("valid_channel_ratio", 0)) >= 0.5
                    and float(motion_quality.get("artifact_window_ratio", 1)) == 0
                )
                if not quality_pass:
                    cursor += step_seconds
                    continue
                window_array = _resample_and_filter(
                    eeg_window[0],
                    eeg_window[1],
                    start=cursor,
                    end=end,
                    target_srate=target_srate,
                    target_samples=target_samples,
                    nominal_srate=nominal_srate,
                )
                if window_array is None:
                    cursor += step_seconds
                    continue
                target_name = str(record["reference_state_label"])
                arrays.append(window_array)
                metadata.append(
                    EEGWindowMetadata(
                        participant=identifiers[0],
                        session=identifiers[1],
                        run=identifiers[2],
                        task=identifiers[3],
                        xdf_path=str(xdf_path.relative_to(dataset_root)),
                        window_start=round(cursor, 6),
                        window_end=round(end, 6),
                        segment=segment,
                        target=0 if target_name == "alert" else 1,
                        target_name=target_name,
                        split=split_by_participant[identifiers[0]],
                        quality_pass=True,
                        channel_names=channel_names,
                        target_srate=target_srate,
                        preprocessing="demean+fft_bandpass_1_40_hz",
                        reference_label_version=str(
                            record["reference_label_version"]
                        ),
                    )
                )
                cursor += step_seconds
    output.parent.mkdir(parents=True, exist_ok=True)
    if arrays:
        x_values = np.stack(arrays).astype(np.float32)
        y_values = np.asarray([item.target for item in metadata], dtype=np.int8)
    else:
        x_values = np.empty(
            (0, expected_channels, target_samples),
            dtype=np.float32,
        )
        y_values = np.empty((0,), dtype=np.int8)
    np.savez_compressed(output, X=x_values, y=y_values)
    metadata_path = output.with_suffix(".jsonl")
    metadata_path.write_text(
        "".join(
            json.dumps(asdict(item), ensure_ascii=False) + "\n"
            for item in metadata
        ),
        encoding="utf-8",
    )
    summary = {
        "shape": list(x_values.shape),
        "target_counts": {
            "alert": sum(item.target_name == "alert" for item in metadata),
            "impaired": sum(item.target_name == "impaired" for item in metadata),
        },
        "participants": sorted({item.participant for item in metadata}),
        "window_seconds": window_seconds,
        "step_seconds": step_seconds,
        "target_srate": target_srate,
        "channel_names": list(channel_reference or ()),
        "preprocessing": "demean+fft_bandpass_1_40_hz",
    }
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output, metadata_path


def _parse_xdf_identifiers(
    xdf_path: Path,
) -> tuple[str, str, str, str] | None:
    from .builder import _STEM

    match = _STEM.fullmatch(xdf_path.stem)
    if not match:
        return None
    values = match.groupdict()
    return (
        values["participant"],
        values["session"],
        values["run"],
        values["task"],
    )


def _training_segments(
    events: list[dict[str, object]],
) -> list[tuple[str, float, float]]:
    names = {
        str(event.get("event")): float(event["timestamp"])
        for event in events
        if event.get("event")
        in {
            "readiness_baseline_start",
            "readiness_baseline_end",
            "sart_start",
            "sart_end",
        }
    }
    segments: list[tuple[str, float, float]] = []
    for label, start_name, end_name in (
        (
            "baseline_open",
            "readiness_baseline_start",
            "readiness_baseline_end",
        ),
        ("sart_assessment", "sart_start", "sart_end"),
    ):
        if start_name in names and end_name in names and names[end_name] > names[start_name]:
            segments.append((label, names[start_name], names[end_name]))
    return segments


def _annotation_exclusions(path: Path) -> list[tuple[float, float]]:
    if not path.exists():
        return []
    exclusions: list[tuple[float, float]] = []
    for row in read_jsonl(path):
        if row.get("exclude_from_training") is not True:
            continue
        start = row.get("start_timestamp", row.get("timestamp"))
        end = row.get("end_timestamp", start)
        if start is not None and end is not None:
            exclusions.append((float(start), float(end)))
    return exclusions


def _overlaps_exclusion(
    start: float,
    end: float,
    exclusions: list[tuple[float, float]],
) -> bool:
    return any(start < excluded_end and end > excluded_start for excluded_start, excluded_end in exclusions)


def _slice_rows(
    timestamps: list[float],
    rows: list[list[float]],
    start: float,
    end: float,
) -> tuple[list[float], list[list[float]]]:
    indexes = [
        index
        for index, timestamp in enumerate(timestamps)
        if start <= timestamp < end
    ]
    return (
        [timestamps[index] for index in indexes],
        [rows[index] for index in indexes],
    )


def _resample_and_filter(
    timestamps: list[float],
    rows: list[list[float]],
    *,
    start: float,
    end: float,
    target_srate: float,
    target_samples: int,
    nominal_srate: float,
) -> Any | None:
    import numpy as np

    minimum_samples = max(2, round((nominal_srate or target_srate) * (end - start) * 0.8))
    if len(timestamps) < minimum_samples:
        return None
    source_times = np.asarray(timestamps, dtype=float)
    source = np.asarray(rows, dtype=float)
    target_times = start + np.arange(target_samples, dtype=float) / target_srate
    resampled = np.vstack(
        [
            np.interp(target_times, source_times, source[:, channel])
            for channel in range(source.shape[1])
        ]
    )
    resampled -= resampled.mean(axis=1, keepdims=True)
    frequencies = np.fft.rfftfreq(target_samples, d=1.0 / target_srate)
    spectrum = np.fft.rfft(resampled, axis=1)
    spectrum[:, (frequencies < 1.0) | (frequencies > 40.0)] = 0
    return np.fft.irfft(spectrum, n=target_samples, axis=1)


def _channel_names(
    stream: dict[str, Any],
    expected_channels: int,
) -> tuple[str, ...]:
    info = stream.get("info", {})
    try:
        channels = info["desc"][0]["channels"][0]["channel"]
        labels = tuple(str(channel["label"][0]) for channel in channels)
        if len(labels) == expected_channels:
            return labels
    except (KeyError, IndexError, TypeError):
        pass
    return tuple(f"EEG-{index + 1}" for index in range(expected_channels))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, dict) else {}
