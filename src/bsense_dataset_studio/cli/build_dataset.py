from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..dataset.builder import build_dataset
from ..dataset.eegnet import build_eegnet_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="按被试构建 BSense 数据集清单")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--eegnet-output", type=Path)
    parser.add_argument("--skip-eegnet", action="store_true")
    parser.add_argument("--target-srate", type=float, default=250.0)
    args = parser.parse_args()
    root = args.dataset_root.resolve()
    output = (args.output or (root / "derived" / "features" / "records.csv")).resolve()
    output_path, manifest_path = build_dataset(root, output)
    eegnet_path = (
        args.eegnet_output
        or (root / "derived" / "eegnet" / "eeg_windows.npz")
    ).resolve()
    eeg_metadata_path = None
    if not args.skip_eegnet:
        eegnet_path, eeg_metadata_path = build_eegnet_dataset(
            root,
            eegnet_path,
            target_srate=args.target_srate,
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    split_path = root / "manifests" / "subject_split.json"
    split_path.write_text(json.dumps(manifest["subject_splits"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    print(manifest_path)
    if eeg_metadata_path is not None:
        print(eegnet_path)
        print(eeg_metadata_path)
