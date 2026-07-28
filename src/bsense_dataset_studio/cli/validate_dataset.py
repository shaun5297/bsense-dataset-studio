from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(root: Path) -> list[str]:
    issues: list[str] = []
    manifest_path = root / "manifests" / "dataset_manifest.json"
    if not manifest_path.exists():
        issues.append("缺少 manifests/dataset_manifest.json")
        return issues
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in manifest.get("records", []):
        path = root / record
        if not path.exists() or path.stat().st_size == 0:
            issues.append(f"原始记录缺失或为空：{record}")
    splits = manifest.get("subject_splits", {})
    values = [set(splits.get(name, [])) for name in ("train_subjects", "validation_subjects", "test_subjects")]
    if any(left.intersection(right) for index, left in enumerate(values) for right in values[index + 1 :]):
        issues.append("被试级划分存在交叉")
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 BSense 数据集")
    parser.add_argument("--dataset-root", type=Path, required=True)
    args = parser.parse_args()
    issues = validate(args.dataset_root.resolve())
    if issues:
        raise SystemExit("\n".join(issues))
    print("数据集校验通过")
