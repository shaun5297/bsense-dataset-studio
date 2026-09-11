import unittest

from bsense_dataset_studio.protocols import build, list_protocols
from bsense_dataset_studio.protocols.sequences import SART_SEQUENCE_SEEDS
from bsense_dataset_studio.quality.report import build_report


class ProtocolQualityTests(unittest.TestCase):
    def test_only_device_qc_and_braincheck_collection_are_exposed(self) -> None:
        self.assertEqual(
            [protocol.task for protocol in list_protocols()],
            ["m6_readiness_reference", "deviceqc"],
        )
        with self.assertRaises(KeyError):
            build("m2_nback")

    def test_only_reference_collection_can_be_started_and_pvt_is_required(self) -> None:
        reference = build("m6_readiness_reference")
        self.assertTrue(any(step.name.startswith("pvt") for step in reference.steps))
        self.assertTrue(reference.reference_labels_expected)
        with self.assertRaises(KeyError):
            build("m6_readiness_field")
        with self.assertRaises(ValueError):
            build("m6_readiness_reference", include_pvt=False)
        with self.assertRaises(ValueError):
            build("m6_readiness_study", include_pvt=False)
        legacy = build("m6_readiness_study")
        self.assertEqual(legacy.task, reference.task)
        self.assertEqual(legacy.steps, reference.steps)

    def test_protocol_step_retains_execution_metadata_and_fields(self) -> None:
        protocol = build("m6_readiness_reference")
        form = next(step for step in protocol.steps if step.event == "readiness_background_start")
        trial = next(
            step
            for step in protocol.steps
            if step.event == "sart_stimulus" and step.block == "sart_assessment"
        )
        self.assertEqual(form.event_code, 710)
        self.assertTrue(form.fields)
        self.assertEqual(form.advance_mode, "form")
        self.assertEqual(trial.metadata["result_event"], "sart_trial_result")
        self.assertEqual(trial.response_key, "space")

    def test_balanced_sequence_sets_are_distinct_and_non_adjacent(self) -> None:
        sequences = []
        for sequence_set_id in SART_SEQUENCE_SEEDS:
            protocol = build(
                "m6_readiness_reference",
                sequence_set_id=sequence_set_id,
            )
            stimuli = [
                str(step.metadata["stimulus"])
                for step in protocol.steps
                if step.event == "sart_stimulus"
                and step.block == "sart_assessment"
            ]
            no_go = [index for index, value in enumerate(stimuli) if value == "3"]
            self.assertEqual(len(stimuli), 180)
            self.assertTrue(
                all(right - left > 1 for left, right in zip(no_go, no_go[1:]))
            )
            sequences.append(tuple(stimuli))
        self.assertEqual(len(set(sequences)), len(SART_SEQUENCE_SEEDS))

    def test_quality_is_separate_pass_fail_schema(self) -> None:
        report = build_report(
            {"valid_channel_ratio": 1, "valid_window_ratio": 1},
            {"valid_channel_ratio": 1, "valid_window_ratio": 1},
            {"valid_channel_ratio": 1, "artifact_window_ratio": 0},
            {"stream_complete": True},
        )
        self.assertEqual(report.overall_status, "pass")
        self.assertNotIn("readiness", report.to_dict())


if __name__ == "__main__":
    unittest.main()
