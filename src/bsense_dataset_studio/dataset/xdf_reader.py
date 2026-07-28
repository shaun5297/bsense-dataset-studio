from __future__ import annotations

from pathlib import Path
from typing import Any

from ..acquisition.stream_schema import canonical_kind


def read_xdf(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import pyxdf
    except ImportError as exc:
        raise RuntimeError("读取 XDF 需要安装 dataset 可选依赖：pip install -e '.[dataset]'") from exc
    streams, header = pyxdf.load_xdf(str(path))
    return list(streams), dict(header)


def stream_kind(stream: dict[str, Any]) -> str | None:
    info = stream.get("info", {})
    return canonical_kind(
        str(_first(info.get("type", ""))),
        str(_first(info.get("name", ""))),
    )


def stream_data(
    stream: dict[str, Any] | None,
) -> tuple[list[float], list[list[float]]]:
    if stream is None:
        return [], []
    timestamps = stream_timestamps(stream)
    series = stream.get("time_series", [])
    rows = series.tolist() if hasattr(series, "tolist") else list(series)
    return timestamps, [[float(value) for value in row] for row in rows]


def stream_timestamps(stream: dict[str, Any] | None) -> list[float]:
    if stream is None:
        return []
    return [float(value) for value in stream.get("time_stamps", [])]


def stream_nominal_srate(stream: dict[str, Any]) -> float:
    info = stream.get("info", {})
    return float(_first(info.get("nominal_srate", 0)) or 0)


def _first(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else ""
    return value
