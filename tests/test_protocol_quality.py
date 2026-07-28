import unittest

from bsense_dataset_studio.protocols import build, list_protocols
from bsense_dataset_studio.quality.report import build_report


class ProtocolQualityTests(unittest.TestCase):
    def test_only_device_qc_and_braincheck_collection_are_exposed(self) -> None:
        self.assertEqual(
            [protocol.task for protocol in list_protocols()],
            ["deviceqc", "m6_readiness_study"],
        )
        with self.assertRaises(KeyError):
            build("m2_nback")

    def test_pvt_reference_is_optional_and_disabled_by_default(self) -> None:
        protocol = build("m6_readiness_study")
        self.assertIn("研究采集", protocol.display_name)
        self.assertFalse(any(step.name.startswith("pvt") for step in protocol.steps))
        with_pvt = build("m6_readiness_study", include_pvt=True)
        self.assertTrue(any(step.name.startswith("pvt") for step in with_pvt.steps))
        self.assertFalse(any("风险等级" in step.instruction for step in protocol.steps))
        self.assertNotIn("readiness_assessment", [step.name for step in protocol.steps])

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
