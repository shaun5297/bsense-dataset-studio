import json
import tempfile
import unittest
from pathlib import Path

from bsense_dataset_studio.dataset.builder import build_records
from bsense_dataset_studio.dataset.manifest import build_manifest, save_manifest, subject_split


class DatasetTests(unittest.TestCase):
    def test_subject_split_is_deterministic_and_disjoint(self) -> None:
        subjects = [f"P{index:03d}" for index in range(20)]
        first = subject_split(subjects)
        second = subject_split(reversed(subjects))
        self.assertEqual(first, second)
        values = [set(first[key]) for key in ("train_subjects", "validation_subjects", "test_subjects")]
        self.assertFalse(values[0] & values[1])
        self.assertFalse(values[0] & values[2])
        self.assertFalse(values[1] & values[2])
        self.assertEqual(set(subjects), set.union(*values))

    def test_manifest_records_raw_xdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw" / "sub-P001" / "ses-01"
            raw.mkdir(parents=True)
            (raw / "sample.xdf").write_bytes(b"XDF:")
            path = save_manifest(root, build_manifest(root))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["records"], ["raw/sub-P001/ses-01/sample.xdf"])
            self.assertEqual(payload["dataset_schema_version"], "1.1")
            self.assertIn(
                "raw/sub-P001/ses-01/sample.xdf",
                payload["metadata"]["record_sha256"],
            )

    def test_builder_joins_context_quality_events_and_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stem = "sub-P001_ses-01_task-m6_readiness_field_run-001"
            raw = root / "raw" / "sub-P001" / "ses-01"
            raw.mkdir(parents=True)
            (raw / f"{stem}.xdf").write_bytes(b"XDF:")
            (raw / f"{stem}_context.json").write_text(
                json.dumps(
                    {
                        "protocol_version": "2.0",
                        "software_version": "0.1.0",
                        "experiment_schema_version": "1.0",
                        "values": {
                            "kss_score": 6,
                            "kss_post_score": 7,
                            "sleep_duration_hours": 5.5,
                            "shift_type": "夜班",
                            "practice_attempts": 2,
                            "practice_criterion_met": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (raw / f"{stem}_events.jsonl").write_text(
                json.dumps(
                    {
                        "timestamp": 1.0,
                        "event": "sart_trial_result",
                        "payload": {
                            "trial": 1,
                            "trial_kind": "assessment",
                            "exclude_from_primary_analysis": False,
                            "should_respond": True,
                            "outcome": "hit",
                            "reaction_time_s": 0.4,
                            "valid": True,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            quality = root / "quality"
            quality.mkdir()
            (quality / f"{stem}_quality.json").write_text(json.dumps({"overall_status": "pass"}), encoding="utf-8")
            rows = build_records(root)
            self.assertEqual(rows[0]["participant"], "P001")
            self.assertEqual(rows[0]["quality_status"], "pass")
            self.assertEqual(rows[0]["valid_trial_count"], 1)
            self.assertEqual(rows[0]["kss_post_score"], 7)
            self.assertEqual(rows[0]["sleep_duration_hours"], 5.5)
            self.assertEqual(rows[0]["practice_attempts"], 2)
            self.assertIs(rows[0]["practice_criterion_met"], False)


if __name__ == "__main__":
    unittest.main()
