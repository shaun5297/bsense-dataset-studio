from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping, Sequence


def export_rows(rows: Sequence[Mapping[str, object]], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = output.suffix.lower()
    if suffix in {".json", ".jsonl"}:
        if suffix == ".json":
            output.write_text(json.dumps(list(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            output.write_text("".join(json.dumps(dict(row), ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return output
    if suffix == ".csv":
        fields = sorted({key for row in rows for key in row})
        with output.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return output
    if suffix == ".npz":
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("NPZ 导出需要安装 NumPy") from exc
        np.savez_compressed(output, rows=list(rows))
        return output
    raise ValueError("支持 .csv、.json、.jsonl 或 .npz")
