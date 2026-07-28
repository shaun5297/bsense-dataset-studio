from __future__ import annotations

import argparse
from pathlib import Path

from ..dataset.validation import validate_dataset


def validate(root: Path) -> list[str]:
    return validate_dataset(root)


def main() -> None:
    parser = argparse.ArgumentParser(description="严格校验 BSense 数据集")
    parser.add_argument("--dataset-root", type=Path, required=True)
    args = parser.parse_args()
    issues = validate_dataset(args.dataset_root.resolve())
    if issues:
        raise SystemExit("\n".join(f"- {issue}" for issue in issues))
    print("数据集严格校验通过")
