from __future__ import annotations

from ..acquisition.discovery import discover


def main() -> None:
    found = discover(3.0)
    if not found:
        print("未发现支持的 LSL 数据流")
        return
    for _, descriptor in sorted(found, key=lambda item: item[1].kind):
        print(f"{descriptor.kind}: {descriptor.name}, {descriptor.channel_count} ch, {descriptor.nominal_srate:g} Hz")
