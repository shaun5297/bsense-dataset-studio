from __future__ import annotations

from pathlib import Path
from typing import Any


def read_xdf(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import pyxdf
    except ImportError as exc:
        raise RuntimeError("读取 XDF 需要安装 dataset 可选依赖：pip install -e '.[dataset]'") from exc
    streams, header = pyxdf.load_xdf(str(path))
    return list(streams), dict(header)
