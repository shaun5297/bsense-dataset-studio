from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from .stream_schema import StreamDescriptor, canonical_kind


def _value(info: Any, method: str, default: object) -> object:
    try:
        return getattr(info, method)()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return default


def describe(info: Any) -> StreamDescriptor | None:
    name = str(_value(info, "name", ""))
    stream_type = str(_value(info, "type", ""))
    kind = canonical_kind(stream_type, name)
    channel_count = int(_value(info, "channel_count", 0))
    if kind is None or channel_count <= 0:
        return None
    return StreamDescriptor(
        kind=kind,
        name=name,
        stream_type=stream_type,
        channel_count=channel_count,
        nominal_srate=float(_value(info, "nominal_srate", 0.0)),
        source_id=str(_value(info, "source_id", "")),
    )


def discover(
    timeout: float = 2.0,
    *,
    resolver: Callable[[float], Iterable[Any]] | None = None,
) -> list[tuple[Any, StreamDescriptor]]:
    if resolver is None:
        from pylsl import resolve_streams

        resolver = resolve_streams
    found: list[tuple[Any, StreamDescriptor]] = []
    for info in resolver(timeout):
        descriptor = describe(info)
        if descriptor is not None:
            found.append((info, descriptor))
    return found


def select_unique(found: Iterable[tuple[Any, StreamDescriptor]], required: Iterable[str]) -> dict[str, tuple[Any, StreamDescriptor]]:
    grouped: dict[str, list[tuple[Any, StreamDescriptor]]] = {}
    for item in found:
        grouped.setdefault(item[1].kind, []).append(item)
    missing = sorted(set(required) - grouped.keys())
    duplicates = sorted(kind for kind, items in grouped.items() if kind in required and len(items) != 1)
    if missing or duplicates:
        details = []
        if missing:
            details.append(f"缺少流：{', '.join(missing)}")
        if duplicates:
            details.append(f"重复流：{', '.join(duplicates)}")
        raise RuntimeError("；".join(details))
    return {kind: grouped[kind][0] for kind in required}
