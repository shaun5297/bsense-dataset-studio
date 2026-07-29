import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bsense_dataset_studio.dataset.eegnet import build_eegnet_dataset
from bsense_dataset_studio.labels.reference import generate_reference_label
from bsense_dataset_studio.quality.report import build_report
from bsense_dataset_studio.quality.windowed import evaluate_windows


class LabelsQualityEEGNetTests(unittest.TestCase):
    def test_reference_label_uses_independent_non_eeg_sources(self) -> None:
        impaired = generate_reference_label(
            {
                "kss_post_score": 8,
                "sleep_duration_hours": 4,
                "continuous_awake_hours": 19,
            },
            {
                "valid_trial_count": 180,
                "omission_rate": 0.12,
                "commission_rate": 0.30,
            },
            {
                "valid_trial_count": 30,
                "lapse_rate": 0.25,
                "median_reaction_time_s": 0.55,
            },
        )
        self.assertEqual(impaired.reference_state_label, "impaired")
        self.assertNotIn("eeg", impaired.reference_label_sources)
        self.assertTrue(impaired.provisional)

    def test_reference_label_ignores_sart_when_practice_failed(self) -> None:
        label = generate_reference_label(
            {"practice_criterion_met": False},
            {
                "valid_trial_count": 180,
                "omission_rate": 0.20,
                "commission_rate": 0.40,
            },
            {},
        )
        self.assertNotIn("sart", label.reference_label_sources)
        self.assertIn("SART 练习未达标，未作为标签来源", label.rationale)

    def test_windowed_quality_reports_motion_affected_windows(self) -> None:
        timestamps = [index / 10 for index in range(101)]
        eeg = [
            [math.sin(2 * math.pi * 2 * value), math.cos(2 * math.pi * 2 * value)]
            for value in timestamps
        ]
        fnirs = [
            [1 + 0.1 * math.sin(value), 1 + 0.1 * math.cos(value)]
            for value in timestamps
        ]
        motion = [[0.0] * 6 for _ in timestamps]
        for index, value in enumerate(timestamps):
            if 4 <= value < 5:
                motion[index][3] = 10.0
        windows = evaluate_windows(
            timestamps,
            eeg,
            timestamps,
            fnirs,
            timestamps,
            motion,
        )
        self.assertTrue(windows)
        self.assertTrue(any(window.motion_artifact for window in windows))
        report = build_report(
            {"valid_channel_ratio": 1.0},
            {"valid_channel_ratio": 1.0},
            {"valid_channel_ratio": 1.0},
            {"stream_complete": True},
            windows=windows,
        )
        self.assertEqual(report.quality_schema_version, "1.1")
        self.assertGreater(
            float(report.motion.extra["artifact_window_ratio"]),
            0,
        )

    def test_eegnet_builder_outputs_n_c_t_and_traceable_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stem = "sub-P001_ses-01_task-m6_readiness_reference_run-001"
            raw = root / "raw" / "sub-P001" / "ses-01"
            raw.mkdir(parents=True)
            xdf = raw / f"{stem}.xdf"
            xdf.write_bytes(b"XDF:mock")
            context = {
                "protocol_version": "2.0",
                "software_version": "0.2.0",
                "experiment_schema_version": "1.0",
                "values": {
                    "study_condition": "post_night_shift",
                    "condition_source": "operator_assigned",
                    "sleep_duration_hours": 4,
                    "continuous_awake_hours": 19,
                    "shift_type": "夜班",
                    "kss_score": 7,
                    "kss_post_score": 8,
                    "measurement_phase": "first_test",
                },
            }
            (raw / f"{stem}_context.json").write_text(
                json.dumps(context),
                encoding="utf-8",
            )
            events = [
                {"event": "experiment_start", "timestamp": 0.5, "payload": {}},
                {
                    "event": "readiness_baseline_start",
                    "timestamp": 1.0,
                    "payload": {},
                },
                {
                    "event": "readiness_baseline_end",
                    "timestamp": 9.0,
                    "payload": {},
                },
                {
                    "event": "sart_start",
                    "timestamp": 10.0,
                    "payload": {"expected_trials": 180},
                },
            ]
            events.extend(
                {
                    "event": "sart_trial_result",
                    "timestamp": 10.01 + index * 0.04,
                    "payload": {
                        "trial": index + 1,
                        "trial_kind": "assessment",
                        "exclude_from_primary_analysis": False,
                        "should_respond": True,
                        "outcome": "hit",
                        "reaction_time_s": 0.4,
                        "valid": True,
                    },
                }
                for index in range(180)
            )
            events.extend(
                [
                    {"event": "sart_end", "timestamp": 19.0, "payload": {}},
                    {"event": "pvt_start", "timestamp": 20.0, "payload": {}},
                ]
            )
            events.extend(
                {
                    "event": "pvt_trial_result",
                    "timestamp": 20.1 + index * 0.1,
                    "payload": {
                        "trial": index + 1,
                        "reaction_time_s": 0.6,
                        "lapse": True,
                        "false_start": False,
                        "timeout": False,
                        "valid": True,
                    },
                }
                for index in range(10)
            )
            events.extend(
                [
                    {"event": "pvt_end", "timestamp": 22.0, "payload": {}},
                    {"event": "experiment_end", "timestamp": 23.0, "payload": {}},
                ]
            )
            (raw / f"{stem}_events.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )
            quality = root / "quality"
            quality.mkdir()
            (quality / f"{stem}_quality.json").write_text(
                json.dumps(
                    {
                        "overall_status": "pass",
                        "quality_schema_version": "1.1",
                        "usable_for_eeg_model": True,
                        "windows": [],
                    }
                ),
                encoding="utf-8",
            )
            timestamps = [index / 10 for index in range(250)]
            eeg_rows = [
                [
                    math.sin(2 * math.pi * 2 * value),
                    math.cos(2 * math.pi * 2 * value),
                ]
                for value in timestamps
            ]
            streams = [
                _stream("EEG", 10, timestamps, eeg_rows, ("C3", "C4")),
                _stream("Motion", 10, timestamps, [[0.0] * 6 for _ in timestamps]),
            ]
            output = root / "derived" / "eegnet" / "windows.npz"
            with patch(
                "bsense_dataset_studio.dataset.eegnet.read_xdf",
                return_value=(streams, {}),
            ):
                dataset_path, metadata_path = build_eegnet_dataset(
                    root,
                    output,
                    target_srate=10,
                )
            import numpy as np

            payload = np.load(dataset_path)
            self.assertEqual(payload["X"].shape, (6, 2, 40))
            self.assertTrue((payload["y"] == 1).all())
            rows = [
                json.loads(line)
                for line in metadata_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(rows[0]["target_name"], "impaired")
            self.assertEqual(
                rows[0]["reference_label_version"],
                "reference-label-v1-provisional",
            )


def _stream(
    stream_type: str,
    sample_rate: float,
    timestamps: list[float],
    rows: list[list[float]],
    labels: tuple[str, ...] = (),
) -> dict[str, object]:
    desc = {
        "channels": [
            {
                "channel": [
                    {"label": [label]}
                    for label in labels
                ]
            }
        ]
    }
    return {
        "info": {
            "type": [stream_type],
            "name": [stream_type],
            "nominal_srate": [str(sample_rate)],
            "desc": [desc],
        },
        "time_stamps": timestamps,
        "time_series": rows,
    }


if __name__ == "__main__":
    unittest.main()
