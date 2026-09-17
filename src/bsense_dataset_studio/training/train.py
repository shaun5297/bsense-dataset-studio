from __future__ import annotations

import copy
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

from .data import load_training_data, sha256
from .eegnet import EEGNet, InferenceModel


def aggregate(
    probabilities: np.ndarray, indices: np.ndarray, rows: list[dict]
) -> list[dict]:
    groups = defaultdict(list)
    for probability, index in zip(probabilities, indices, strict=True):
        row = rows[int(index)]
        key = (
            row["participant"],
            row["session"],
            row["run"],
            row["task"],
            row["target"],
        )
        groups[key].append(float(probability))
    return [
        dict(
            participant=k[0],
            session=k[1],
            run=k[2],
            task=k[3],
            target=k[4],
            probability=float(np.mean(v)),
            windows=len(v),
        )
        for k, v in sorted(groups.items())
    ]


def metrics(runs: list[dict], threshold: float) -> dict:
    # Participant-equal reporting: overlapping windows do not multiply subjects.
    groups = defaultdict(list)
    for row in runs:
        groups[row["participant"]].append(row)
    per_subject = {}
    recalls = {0: [], 1: []}
    losses = []
    for subject, values in groups.items():
        y = np.array([v["target"] for v in values])
        p = np.array([v["probability"] for v in values])
        pred = p >= threshold
        cm = [[int(np.sum((y == a) & (pred == b))) for b in (0, 1)] for a in (0, 1)]
        subject_recalls = []
        for cls in (0, 1):
            mask = y == cls
            if mask.any():
                recall = float(np.mean(pred[mask] == cls))
                recalls[cls].append(recall)
                subject_recalls.append(recall)
        loss = float(
            np.mean(
                -(
                    y * np.log(np.clip(p, 1e-7, 1 - 1e-7))
                    + (1 - y) * np.log(np.clip(1 - p, 1e-7, 1 - 1e-7))
                )
            )
        )
        losses.append(loss)
        per_subject[subject] = {
            "confusion_matrix_runs": cm,
            "runs": len(values),
            "nll": loss,
            "balanced_accuracy": float(np.mean(subject_recalls))
            if len(subject_recalls) == 2
            else None,
        }
    return {
        "subject_equal_balanced_accuracy": float(
            np.mean([np.mean(recalls[c]) for c in (0, 1)])
        ),
        "subject_equal_nll": float(np.mean(losses)),
        "per_subject": per_subject,
        "aggregation": "window probability mean per run, participant-equal class recall",
    }


def predict_logits(model: EEGNet, x: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.inference_mode():
        return np.concatenate(
            [
                model(torch.from_numpy(x[i : i + 128])).numpy()
                for i in range(0, len(x), 128)
            ]
        )


def probabilities(logits: np.ndarray, temperature: float) -> np.ndarray:
    z = logits / temperature
    z -= z.max(axis=1, keepdims=True)
    exp = np.exp(z)
    return (exp / exp.sum(axis=1, keepdims=True))[:, 1]


def train(
    dataset: Path,
    output: Path,
    *,
    epochs: int = 40,
    patience: int = 8,
    seed: int = 20260917,
    pilot_fit_only: bool = False,
) -> dict:
    x, y, rows, info = load_training_data(dataset, pilot_fit_only=pilot_fit_only)
    if epochs < 1 or patience < 1:
        raise ValueError("epochs / patience 必须为正")
    if output.exists() and any(output.iterdir()):
        raise ValueError("训练输出目录必须为空，避免覆盖已有权重或结果")
    output.mkdir(parents=True, exist_ok=True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    indices = info.pop("indices")
    tx = x[indices["train"]]
    ty = y[indices["train"]]
    scale = torch.from_numpy(np.maximum(tx.std(axis=(0, 2)), 1e-6).astype(np.float32))
    model = EEGNet(scale)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    keys = [(rows[int(i)]["participant"], int(y[i])) for i in indices["train"]]
    counts = Counter(keys)
    per_class = Counter(cls for _, cls in counts)
    weights = [1 / (counts[key] * per_class[key[1]]) for key in keys]
    sampler = WeightedRandomSampler(
        weights,
        len(weights),
        replacement=True,
        generator=torch.Generator().manual_seed(seed),
    )
    loader = DataLoader(
        TensorDataset(torch.from_numpy(tx), torch.from_numpy(ty)),
        batch_size=32,
        sampler=sampler,
    )
    history = []
    best = math.inf
    best_state = None
    stale = 0
    best_epoch = 0
    for epoch in range(1, epochs + 1):
        model.train()
        loss_sum = 0.0
        seen = 0
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = nn.functional.cross_entropy(model(xb), yb)
            if not torch.isfinite(loss):
                raise ValueError("训练 loss 非有限值")
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            loss_sum += float(loss.detach()) * len(xb)
            seen += len(xb)
        if pilot_fit_only:
            history.append({"epoch": epoch, "train_loss": loss_sum / seen})
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            continue
        vi = indices["validation"]
        val = aggregate(probabilities(predict_logits(model, x[vi]), 1.0), vi, rows)
        vm = metrics(val, 0.5)
        value = vm["subject_equal_nll"]
        history.append(
            {
                "epoch": epoch,
                "train_loss": loss_sum / seen,
                "validation_run_nll": value,
                "validation_balanced_accuracy": vm["subject_equal_balanced_accuracy"],
            }
        )
        if value < best - 1e-6:
            best = value
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            stale = 0
        else:
            stale += 1
        if stale >= patience:
            break
    assert best_state is not None
    model.load_state_dict(best_state)
    model.eval()
    if pilot_fit_only:
        temperature, threshold, validation, vm = 1.0, None, [], None
        vi = indices["train"]
    else:
        vi = indices["validation"]
        logits = predict_logits(model, x[vi])
        # Fixed grid, calibration strictly on validation, matching mean-window runtime aggregation.
        candidates = []
        for t in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0):
            runs = aggregate(probabilities(logits, t), vi, rows)
            candidates.append(
                (metrics(runs, 0.5)["subject_equal_nll"], abs(t - 1), t, runs)
            )
        _, _, temperature, validation = min(candidates, key=lambda a: a[:2])
        thresholds = np.unique(
            [
                0.5,
                *[r["probability"] for r in validation],
                *[min(1.0, r["probability"] + 1e-7) for r in validation],
            ]
        )
        thresholds = thresholds[(thresholds > 0) & (thresholds < 1)]
        threshold = min(
            thresholds,
            key=lambda t: (
                -metrics(validation, float(t))["subject_equal_balanced_accuracy"],
                abs(float(t) - 0.5),
            ),
        )
        vm = metrics(validation, float(threshold))
    bundle = InferenceModel(model, float(temperature)).eval()
    model_path = output / "braincheck_eegnet.pt"
    torch.jit.script(bundle).save(str(model_path))
    reloaded = torch.jit.load(str(model_path), map_location="cpu").eval()
    with torch.inference_mode():
        expected = bundle(torch.from_numpy(x[vi[:3]]))
        actual = reloaded(torch.from_numpy(x[vi[:3]]))
    if not torch.allclose(actual, expected, atol=1e-6):
        raise RuntimeError("导出模型与训练模型不一致")
    # Freeze model and calibration before evaluating the test set once.
    manifest = {
        "schema_version": "braincheck-eegnet-v1",
        "available": True,
        "model_type": "eegnet_torchscript",
        "model_version": f"eegnet-pilot-{sha256(model_path)[:12]}",
        "model_file": model_path.name,
        "model_sha256": sha256(model_path),
        "task": "readiness_reference",
        "classes": ["alert", "impaired"],
        "input_shape": [2, 1000],
        "sample_rate_hz": 250,
        "window_seconds": 4.0,
        "step_seconds": 2.0,
        "channel_names": info["channel_names"],
        "preprocessing": "embedded_demean_fft_1_40_train_channel_scale",
        "aggregation": "mean_window_probability",
        "reference_label_versions": sorted(
            {r["reference_label_version"] for r in rows}
        ),
        "decision_threshold": float(threshold) if threshold is not None else None,
        "temperature": float(temperature),
        "calibration_split": "none" if pilot_fit_only else "validation",
        "training_mode": "pilot_fit_only" if pilot_fit_only else "subject_independent",
        "allowed_modes": ["shadow"] if pilot_fit_only else ["shadow", "assisted"],
        "independent_evaluation_available": not pilot_fit_only,
        "calibration_balanced_accuracy": vm["subject_equal_balanced_accuracy"]
        if vm
        else None,
        "experimental": True,
        "field_validated": False,
        "default_mode": "shadow",
        "best_epoch": best_epoch,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "torch_version": torch.__version__,
        **info,
    }
    (output / "model_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    ti = indices["test"]
    test = (
        aggregate(probabilities(predict_logits(model, x[ti]), temperature), ti, rows)
        if len(ti)
        else []
    )
    report = {
        "purpose": (
            "synthetic_engineering_test_only"
            if info["training_source"] == "synthetic_test_fixture"
            else (
                "pilot_fit_only_no_independent_evaluation"
                if pilot_fit_only
                else "preliminary_reference_label_model_not_field_validation"
            )
        ),
        "manifest": manifest,
        "history": history,
        "validation": vm,
        "test": metrics(test, float(threshold)) if test else None,
        "validation_runs": validation,
        "test_runs": test,
    }
    (output / "training_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    return report
