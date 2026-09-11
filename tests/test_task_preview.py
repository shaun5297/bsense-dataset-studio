import unittest
from tkinter import Tk

from bsense_dataset_studio.app.protocol_view import ProtocolView
from bsense_dataset_studio.app.task_view import build_preview_stages, format_duration
from bsense_dataset_studio.protocols import build


class TaskPreviewTests(unittest.TestCase):
    def test_desktop_defaults_to_reference_collection(self) -> None:
        root = Tk()
        root.withdraw()
        try:
            view = ProtocolView(root)
            self.assertEqual(view.task, "m6_readiness_reference")
            self.assertEqual(len(view.selector["values"]), 2)
        finally:
            root.destroy()

    def test_device_qc_is_grouped_into_readable_stages(self) -> None:
        stages = build_preview_stages(build("deviceqc"))
        self.assertEqual(
            [stage.key for stage in stages],
            [
                "experiment_start",
                "open_rest",
                "closed_rest",
                "artifact_check",
                "final_open_rest",
                "experiment_end",
            ],
        )
        artifact = next(stage for stage in stages if stage.key == "artifact_check")
        self.assertEqual(artifact.item_count, 30)
        self.assertNotIn("+", [stage.display_title for stage in stages])

    def test_readiness_preview_collapses_sart_trials(self) -> None:
        stages = build_preview_stages(build("m6_readiness_reference"))
        self.assertLess(len(stages), 15)
        practice = next(stage for stage in stages if stage.key == "sart_practice")
        assessment = next(stage for stage in stages if stage.key == "sart_assessment")
        self.assertEqual(practice.item_count, 12)
        self.assertEqual(assessment.item_count, 180)
        self.assertIn("postcheck", [stage.key for stage in stages])
        self.assertIn("pvt", [stage.key for stage in stages])

    def test_pvt_is_present_in_collection_but_not_device_qc(self) -> None:
        reference = build_preview_stages(build("m6_readiness_reference"))
        qc = build_preview_stages(build("deviceqc"))
        self.assertIn("pvt", [stage.key for stage in reference])
        self.assertNotIn("pvt", [stage.key for stage in qc])

    def test_duration_format_is_compact(self) -> None:
        self.assertEqual(format_duration(None), "填写/确认")
        self.assertEqual(format_duration(45), "45 秒")
        self.assertEqual(format_duration(180), "3 分钟")
        self.assertEqual(format_duration(185), "3 分 5 秒")


if __name__ == "__main__":
    unittest.main()
