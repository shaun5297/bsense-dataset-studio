import tempfile
import unittest
from pathlib import Path

from bsense_dataset_studio.annotations import AnnotationStore
from bsense_dataset_studio.dataset.validation import _validate_events


class AnnotationsValidationTests(unittest.TestCase):
    def test_interval_annotation_preserves_training_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "annotations.jsonl"
            row = AnnotationStore(path).append(
                "受试者明显动作",
                "调整坐姿",
                start_timestamp=10.0,
                end_timestamp=12.5,
                affected_modalities=("eeg", "fnirs", "motion"),
                exclude_from_training=True,
                severity="major",
            )
            self.assertEqual(row["annotation_schema_version"], "1.1")
            self.assertEqual(row["end_timestamp"], 12.5)
            self.assertTrue(row["exclude_from_training"])

    def test_validator_requires_exact_sart_results_and_pvt(self) -> None:
        events = [
            {"event": "experiment_start", "timestamp": 0.0, "payload": {}},
            {
                "event": "sart_start",
                "timestamp": 1.0,
                "payload": {"expected_trials": 3},
            },
        ]
        events.extend(
            {
                "event": "sart_trial_result",
                "timestamp": 2.0 + trial,
                "payload": {
                    "trial": trial,
                    "trial_kind": "assessment",
                    "outcome": "hit",
                },
            }
            for trial in (1, 2)
        )
        events.append(
            {"event": "experiment_end", "timestamp": 10.0, "payload": {}}
        )
        issues = _validate_events(
            "sample.xdf",
            "m6_readiness_reference",
            events,
        )
        self.assertTrue(any("实际 2 条" in issue for issue in issues))
        self.assertTrue(any("PVT" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
