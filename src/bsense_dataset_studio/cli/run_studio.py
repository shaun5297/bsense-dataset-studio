from __future__ import annotations

import argparse
from pathlib import Path

from ..app.main import run
from ..protocols import build, list_protocols


def main() -> None:
    parser = argparse.ArgumentParser(description="BSense Dataset Studio")
    parser.add_argument("--list-protocols", action="store_true")
    parser.add_argument("--preview")
    parser.add_argument("--short", action="store_true")
    parser.add_argument("--include-pvt", action="store_true")
    parser.add_argument("--dataset-root", type=Path, help="桌面界面的初始数据根目录")
    args = parser.parse_args()
    if args.list_protocols:
        for protocol in list_protocols():
            print(f"{protocol.task}\t{protocol.display_name}")
        return
    if args.preview:
        protocol = build(
            args.preview,
            short=args.short,
            include_pvt=args.include_pvt,
        )
        for step in protocol.steps:
            print(f"{step.name}\t{step.duration_s}\t{step.instruction}")
        return
    run(dataset_root=args.dataset_root)
