from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .participants.identifiers import ensure_dataset_layout, run_stem


@dataclass(frozen=True)
class RunStorage:
    dataset_root: Path
    raw_directory: Path
    xdf: Path
    context: Path
    events: Path
    quality: Path
    annotations: Path


def default_dataset_root() -> Path:
    return Path.home() / "BSenseDatasets" / "braincheck"


def settings_path() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "BSense Dataset Studio" / "settings.json"


def normalize_dataset_root(value: str | Path) -> Path:
    text = str(value).strip()
    if not text:
        raise ValueError("数据根目录不能为空")
    root = Path(text).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise ValueError("数据根目录指向了文件，请选择文件夹")
    return root


def plan_run_storage(
    dataset_root: str | Path,
    participant_id: str,
    session_id: str,
    task: str,
    run_id: str,
) -> RunStorage:
    root = normalize_dataset_root(dataset_root)
    stem = run_stem(participant_id, session_id, task, run_id)
    participant = participant_id.strip()
    session = session_id.strip()
    raw_directory = root / "raw" / f"sub-{participant}" / f"ses-{session}"
    return RunStorage(
        dataset_root=root,
        raw_directory=raw_directory,
        xdf=raw_directory / f"{stem}.xdf",
        context=raw_directory / f"{stem}_context.json",
        events=raw_directory / f"{stem}_events.jsonl",
        quality=root / "quality" / f"{stem}_quality.json",
        annotations=root / "annotations" / f"{stem}_annotations.jsonl",
    )


def prepare_run_storage(storage: RunStorage) -> RunStorage:
    ensure_dataset_layout(storage.dataset_root)
    storage.raw_directory.mkdir(parents=True, exist_ok=True)
    if not os.access(storage.dataset_root, os.W_OK):
        raise PermissionError(f"数据根目录不可写：{storage.dataset_root}")
    return storage


def load_dataset_root(path: Path | None = None) -> Path:
    target = path or settings_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return normalize_dataset_root(payload["dataset_root"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return default_dataset_root()


def save_dataset_root(dataset_root: str | Path, path: Path | None = None) -> Path:
    root = normalize_dataset_root(dataset_root)
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_text(
        json.dumps({"dataset_root": str(root)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return root
