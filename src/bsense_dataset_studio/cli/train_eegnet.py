from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="训练并导出被试隔离的 EEGNet 先导模型")
    parser.add_argument(
        "--dataset", type=Path, required=True, help="eeg_windows.npz（旁需同名 JSONL）"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument(
        "--pilot-fit-only",
        action="store_true",
        help="全部合格数据固定轮次拟合，无独立验证或校准，仅可旁路部署",
    )
    args = parser.parse_args()
    from ..training.data import TrainingDataError
    from ..training.train import train

    try:
        report = train(
            args.dataset.resolve(),
            args.output.resolve(),
            epochs=args.epochs,
            patience=args.patience,
            seed=args.seed,
            pilot_fit_only=args.pilot_fit_only,
        )
    except TrainingDataError as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        status = args.output / "training_blocked.json"
        if status.exists():
            parser.exit(2, f"训练拒绝：{exc}\n已有拒绝报告未覆盖：{status}\n")
        status.write_text(
            json.dumps(
                {"trained": False, "available": False, "reason": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        parser.exit(2, f"训练拒绝：{exc}\n{status}\n")
    print(
        json.dumps(
            {
                "model": str(args.output / "braincheck_eegnet.pt"),
                "test": report["test"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
