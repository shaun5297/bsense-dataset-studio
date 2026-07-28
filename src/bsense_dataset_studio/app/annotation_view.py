from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ANNOTATION_TYPES = (
    "设备重新佩戴",
    "电极松动",
    "受试者明显动作",
    "打哈欠",
    "闭眼",
    "分心",
    "外部人员打断",
    "键盘故障",
    "软件异常",
    "任务理解错误",
    "主动中止",
    "数据片段排除",
    "其他",
)


class AnnotationStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, annotation_type: str, note: str = "", *, timestamp: float | None = None) -> dict[str, object]:
        if annotation_type not in ANNOTATION_TYPES:
            raise ValueError("未知人工标注类型")
        row = {
            "annotation_schema_version": "1.0",
            "annotation_type": annotation_type,
            "note": note.strip() or None,
            "timestamp": timestamp,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row
