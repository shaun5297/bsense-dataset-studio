from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


class TrainingDataError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_training_data(
    path: Path, *, pilot_fit_only: bool = False
) -> tuple[np.ndarray, np.ndarray, list[dict], dict]:
    """Reject empty, unlabelled or subject-leaking exports before optimization."""
    with np.load(path, allow_pickle=False) as data:
        x, y = np.asarray(data["X"], dtype=np.float32), np.asarray(data["y"])
    metadata_path = path.with_suffix(".jsonl")
    rows = [
        json.loads(line)
        for line in metadata_path.read_text().splitlines()
        if line.strip()
    ]
    if (
        x.ndim != 3
        or x.shape[1:] != (2, 1000)
        or y.shape != (len(x),)
        or len(rows) != len(x)
    ):
        raise TrainingDataError("需要 X[N,2,1000]、y[N] 及逐窗一一对应的 JSONL")
    if not len(x):
        raise TrainingDataError(
            "训练窗口为 0：请核查 reference label、run 级 QC 与有效区间；不会跳过门控"
        )
    summary = json.loads(path.with_suffix(".summary.json").read_text())
    origin = summary.get("data_origin")
    quality_profile = summary.get("quality_profile", "strict")
    if quality_profile != "strict" and not pilot_fit_only:
        raise TrainingDataError(
            "放宽门控的数据必须显式使用 pilot-fit-only，不能作为正式验证"
        )
    if origin not in {"bsense_reference_export", "synthetic_test_fixture"}:
        raise TrainingDataError(
            "数据来源未声明为 BSense reference 导出，不能标成自采训练结果"
        )
    if not np.isfinite(x).all() or not np.isin(y, [0, 1]).all():
        raise TrainingDataError("EEG 必须有限，标签只能为 alert=0 / impaired=1")
    subjects: dict[str, str] = {}
    windows: set[tuple] = set()
    runs: dict[tuple, int] = {}
    channels = None
    for row, target in zip(rows, y, strict=True):
        subject, split = row["participant"], row["split"]
        if not subject or split not in {"train", "validation", "test"}:
            raise TrainingDataError(
                "缺少 participant 或有效 train/validation/test 划分"
            )
        if subjects.setdefault(subject, split) != split:
            raise TrainingDataError(f"被试泄漏：{subject} 跨数据划分")
        if (
            row.get("quality_pass") is not True
            or row.get("target_name") != ("alert", "impaired")[int(target)]
        ):
            raise TrainingDataError("窗口质量或标签语义不匹配")
        if row.get("target") != int(target) or not row.get("reference_label_version"):
            raise TrainingDataError("逐窗标签或参考标签版本缺失")
        if (
            row.get("preprocessing") != "demean+fft_bandpass_1_40_hz"
            or row.get("target_srate") != 250
        ):
            raise TrainingDataError("预处理或采样率与部署输入不一致")
        names = tuple(row.get("channel_names", ()))
        if len(names) != 2 or (channels is not None and names != channels):
            raise TrainingDataError("两通道名称/顺序必须一致")
        channels = names
        key = (subject, row["session"], row["run"], row["task"])
        if runs.setdefault(key, int(target)) != int(target):
            raise TrainingDataError("同一 run 的参考标签不一致")
        identity = (*key, row["window_start"], row["window_end"])
        if identity in windows or not np.isclose(
            row["window_end"] - row["window_start"], 4
        ):
            raise TrainingDataError("重复窗口或窗口长度不为 4 秒")
        windows.add(identity)
    original_subject_splits = {
        k: sorted(s for s, v in subjects.items() if v == k)
        for k in ("train", "validation", "test")
    }
    if pilot_fit_only:
        if set(y.tolist()) != {0, 1}:
            raise TrainingDataError("先导拟合仍需真实 alert / impaired 两类标签")
        splits = {
            "train": np.arange(len(x)),
            "validation": np.array([], dtype=int),
            "test": np.array([], dtype=int),
        }
    else:
        splits = {}
    for split in ("train", "validation", "test"):
        if pilot_fit_only:
            break
        indices = np.array(
            [i for i, row in enumerate(rows) if row["split"] == split], dtype=int
        )
        if set(y[indices].tolist()) != {0, 1}:
            raise TrainingDataError(
                f"{split} 未同时覆盖 alert / impaired，不能进行二分类校准与独立评估"
            )
        splits[split] = indices
    return (
        x,
        y.astype(np.int64),
        rows,
        {
            "indices": splits,
            "channel_names": list(channels),
            "subject_splits": {
                k: sorted(s for s, v in subjects.items() if v == k) for k in splits
            }
            if not pilot_fit_only
            else {"train": sorted(subjects), "validation": [], "test": []},
            "original_subject_splits": original_subject_splits,
            "quality_profile": quality_profile,
            "dataset_sha256": sha256(path),
            "metadata_sha256": sha256(metadata_path),
            "training_source": origin,
        },
    )
