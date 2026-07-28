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


def _identity(info: Any, descriptor: StreamDescriptor) -> tuple[object, ...]:
    return (
        descriptor.kind,
        descriptor.name,
        descriptor.stream_type,
        descriptor.channel_count,
        descriptor.source_id,
        str(_value(info, "hostname", "")),
    )


def dedupe_identical(found: Iterable[tuple[Any, StreamDescriptor]]) -> list[tuple[Any, StreamDescriptor]]:
    """Collapse repeated sightings of the same stream.

    On a LAN a single stream may be resolved several times (e.g. once per
    network interface of the publishing host). Entries whose metadata are
    fully identical refer to the same data source, so only the first
    occurrence is kept.
    """
    unique: dict[tuple[object, ...], tuple[Any, StreamDescriptor]] = {}
    for info, descriptor in found:
        unique.setdefault(_identity(info, descriptor), (info, descriptor))
    return list(unique.values())


def select_unique(found: Iterable[tuple[Any, StreamDescriptor]], required: Iterable[str]) -> dict[str, tuple[Any, StreamDescriptor]]:
    grouped: dict[str, list[tuple[Any, StreamDescriptor]]] = {}
    for item in dedupe_identical(found):
        grouped.setdefault(item[1].kind, []).append(item)
    missing = sorted(set(required) - grouped.keys())
    duplicates = sorted(kind for kind, items in grouped.items() if kind in required and len(items) != 1)
    if missing or duplicates:
        details = []
        if missing:
            details.append(f"缺少流：{', '.join(missing)}")
        if duplicates:
            conflicts = ", ".join(
                f"{kind}（{' / '.join(sorted({item[1].name for item in grouped[kind]}))}）" for kind in duplicates
            )
            details.append(f"重复流：{conflicts}")
        raise RuntimeError("；".join(details))
    return {kind: grouped[kind][0] for kind in required}
