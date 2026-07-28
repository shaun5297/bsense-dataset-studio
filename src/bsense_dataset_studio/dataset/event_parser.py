from __future__ import annotations

import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} 不是 JSON 对象")
        rows.append(row)
    return rows


def ordered_events(path: Path) -> list[dict[str, object]]:
    rows = read_jsonl(path)
    timestamps = [float(row["timestamp"]) for row in rows]
    if any(current < previous for previous, current in zip(timestamps, timestamps[1:])):
        raise ValueError(f"事件时间戳非单调：{path}")
    return rows
