from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from .identifiers import validate_identifier

ALLOWED_SEX = {"女", "男", "其他", "不愿透露"}
ALLOWED_HAND = {"左", "右", "双手"}


def validate_profile(values: Mapping[str, object]) -> dict[str, object]:
    profile = {
        "participant_id": validate_identifier(str(values.get("participant_id", "")), "participant"),
        "name": str(values.get("name", "")).strip() or None,
        "age": int(values["age"]),
        "sex": str(values["sex"]),
        "education_years": float(values["education_years"]),
        "dominant_hand": str(values["dominant_hand"]),
        "group": str(values.get("group", "")).strip() or None,
        "notes": str(values.get("notes", "")).strip() or None,
    }
    if not 18 <= profile["age"] <= 120:
        raise ValueError("年龄必须在 18 至 120 岁之间")
    if profile["sex"] not in ALLOWED_SEX:
        raise ValueError("性别选项无效")
    if not 0 <= profile["education_years"] <= 40:
        raise ValueError("受教育年限必须在 0 至 40 年之间")
    if profile["dominant_hand"] not in ALLOWED_HAND:
        raise ValueError("惯用手选项无效")
    return profile


def save_profile(restricted_root: Path, profile: Mapping[str, object]) -> Path:
    normalized = validate_profile(profile)
    restricted_root.mkdir(parents=True, exist_ok=True)
    path = restricted_root / f"sub-{normalized['participant_id']}_profile.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != normalized:
            raise FileExistsError(f"资料已存在且内容不同，拒绝覆盖：{path}")
        return path
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        restricted_root.chmod(0o700)
        path.chmod(0o600)
    return path
