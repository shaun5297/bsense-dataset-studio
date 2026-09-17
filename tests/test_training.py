import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

if any(importlib.util.find_spec(name) is None for name in ("numpy", "torch")):
    raise unittest.SkipTest("EEGNet training tests require the [training] extra")

import numpy as np

from bsense_dataset_studio.training.data import TrainingDataError, load_training_data
from bsense_dataset_studio.training.train import train


def fixture(root: Path) -> Path:
    rng = np.random.default_rng(7)
    x, y, rows = [], [], []
    times = np.arange(1000) / 250
    for subject, split in [
        ("S1", "train"),
        ("S2", "train"),
        ("S3", "validation"),
        ("S4", "test"),
    ]:
        for target in (0, 1):
            for i in range(3):
                signal = np.stack(
                    [
                        np.sin(2 * np.pi * (8 + 10 * target) * times + p)
                        for p in (0.0, 0.3)
                    ]
                )
                signal += rng.normal(0, 0.03, signal.shape)
                spectrum = np.fft.rfft(signal, axis=-1)
                f = np.fft.rfftfreq(1000, 1 / 250)
                spectrum[:, (f < 1) | (f > 40)] = 0
                x.append(np.fft.irfft(spectrum, n=1000, axis=-1))
                y.append(target)
                rows.append(
                    {
                        "participant": subject,
                        "split": split,
                        "session": "01",
                        "run": str(target),
                        "task": "m6_readiness_reference",
                        "segment": "sart",
                        "window_start": i * 2.0,
                        "window_end": i * 2.0 + 4,
                        "target": target,
                        "target_name": ("alert", "impaired")[target],
                        "quality_pass": True,
                        "channel_names": ["EEG-1", "EEG-2"],
                        "target_srate": 250,
                        "preprocessing": "demean+fft_bandpass_1_40_hz",
                        "reference_label_version": "synthetic-test-only",
                    }
                )
    path = root / "eeg_windows.npz"
    np.savez_compressed(
        path, X=np.asarray(x, dtype=np.float32), y=np.array(y, dtype=np.int8)
    )
    path.with_suffix(".jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    path.with_suffix(".summary.json").write_text(
        json.dumps({"data_origin": "synthetic_test_fixture"})
    )
    return path


class TrainingTests(unittest.TestCase):
    def test_pilot_fit_has_no_test_or_calibration_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = fixture(root)
            report = train(path, root / "pilot", epochs=1, pilot_fit_only=True)
            self.assertIsNone(report["test"])
            self.assertIsNone(report["validation"])
            self.assertIsNone(report["manifest"]["decision_threshold"])
            self.assertEqual(report["manifest"]["allowed_modes"], ["shadow"])
            self.assertEqual(report["manifest"]["subject_splits"]["test"], [])

    def test_subject_leakage_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = fixture(Path(directory))
            rows = [
                json.loads(v)
                for v in path.with_suffix(".jsonl").read_text().splitlines()
            ]
            rows[-1]["participant"] = "S1"
            path.with_suffix(".jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows)
            )
            with self.assertRaisesRegex(TrainingDataError, "被试泄漏"):
                load_training_data(path)

    def test_missing_validation_class_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = fixture(Path(directory))
            rows = [
                json.loads(v)
                for v in path.with_suffix(".jsonl").read_text().splitlines()
            ]
            data = np.load(path)
            x, y = data["X"], data["y"].copy()
            for i, row in enumerate(rows):
                if row["split"] == "validation":
                    y[i] = 1
                    row.update(target=1, target_name="impaired")
            np.savez_compressed(path, X=x, y=y)
            path.with_suffix(".jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows)
            )
            with self.assertRaisesRegex(TrainingDataError, "validation 未同时覆盖"):
                load_training_data(path)

    def test_empty_data_rejected_without_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "empty.npz"
            np.savez_compressed(
                path, X=np.empty((0, 2, 1000)), y=np.empty(0, dtype=int)
            )
            path.with_suffix(".jsonl").write_text("")
            with self.assertRaisesRegex(TrainingDataError, "训练窗口为 0"):
                train(path, root / "model", epochs=1)
            self.assertFalse((root / "model/braincheck_eegnet.pt").exists())

    def test_export_is_portable_and_test_data_does_not_select_model(self):
        import torch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = fixture(root)
            report = train(path, root / "export", epochs=2, patience=1, seed=7)
            self.assertEqual(report["purpose"], "synthetic_engineering_test_only")
            exported = torch.jit.load(str(root / "export/braincheck_eegnet.pt"))
            x, y, rows, _ = load_training_data(path)
            with torch.inference_mode():
                before = exported(torch.from_numpy(x[:2]))
            self.assertTrue(torch.allclose(before.sum(1), torch.ones(2), atol=1e-6))
            # Change only held-out samples. Training weights/calibration must remain identical.
            changed = x.copy()
            for i, row in enumerate(rows):
                if row["split"] == "test":
                    changed[i] *= 8
            np.savez_compressed(path, X=changed, y=y)
            second = train(path, root / "second", epochs=2, patience=1, seed=7)
            another = torch.jit.load(str(root / "second/braincheck_eegnet.pt"))
            with torch.inference_mode():
                after = another(torch.from_numpy(x[:2]))
            self.assertTrue(torch.equal(before, after))
            self.assertEqual(
                report["manifest"]["temperature"], second["manifest"]["temperature"]
            )
            self.assertEqual(
                report["manifest"]["decision_threshold"],
                second["manifest"]["decision_threshold"],
            )


if __name__ == "__main__":
    unittest.main()
