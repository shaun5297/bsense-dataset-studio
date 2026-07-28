from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..dataset.builder import build_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="按被试构建 BSense 数据集清单")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.dataset_root.resolve()
    output = (args.output or (root / "derived" / "features" / "records.csv")).resolve()
    output_path, manifest_path = build_dataset(root, output)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    split_path = root / "manifests" / "subject_split.json"
    split_path.write_text(json.dumps(manifest["subject_splits"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    print(manifest_path)
